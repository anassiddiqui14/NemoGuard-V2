import json
import os
import psycopg2.extras
from src.store.postgres_database import PostgresDatabase

def query_logs(incident_id: str, keyword: str = "") -> str:
    """Queries the log_event table for the primary_run_id associated with an incident."""
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get primary run ID
        cursor.execute("SELECT primary_run_id FROM incident WHERE incident_id = %s", (incident_id,))
        row = cursor.fetchone()
        if not row:
            return f"Incident {incident_id} not found."
        
        run_id = row['primary_run_id']
        if not run_id:
            return f"No primary_run_id associated with incident {incident_id}."
            
        # Get logs
        # NOTE: log_event's actual column is `component`, not `source` (see migrations/002_domain_model.sql
        # and src/store/schema.sql). Using `source` here previously caused a hard Postgres error
        # ('column "source" does not exist'), which silently broke RCA investigation for every incident
        # and caused the Grounding Critic to correctly (but unhelpfully) flag every plan as NEEDS_REVIEW.
        if keyword:
            cursor.execute(
                "SELECT timestamp, level, component, message FROM log_event WHERE run_id = %s AND (message LIKE %s OR component LIKE %s) ORDER BY timestamp ASC LIMIT 50",
                (run_id, f"%{keyword}%", f"%{keyword}%")
            )
        else:
            cursor.execute(
                "SELECT timestamp, level, component, message FROM log_event WHERE run_id = %s AND level IN ('ERROR', 'WARN') ORDER BY timestamp ASC LIMIT 50",
                (run_id,)
            )
            
        logs = [dict(r) for r in cursor.fetchall()]
        if not logs:
            return f"No logs found matching criteria for run {run_id}."
            
        return json.dumps(logs, indent=2)


def get_cmdb_context(service_name: str) -> str:
    """Fetches downstream/upstream dependencies from the CMDB database."""
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # We find jobs that match the service_name, then get their asset_dependencies
        cursor.execute("SELECT job_id, job_name FROM job WHERE job_id ILIKE %s OR job_name ILIKE %s", (f"%{service_name}%", f"%{service_name}%"))
        jobs = cursor.fetchall()
        
        if not jobs:
            # Fallback: if no exact match, return recent assets to ensure LLM has context
            cursor.execute("SELECT asset_name, owner, sla_minutes FROM business_asset LIMIT 5")
            assets = cursor.fetchall()
            if not assets:
                return f"Service {service_name} not found in CMDB, and CMDB is empty."
            return json.dumps({"query": service_name, "note": "Exact match not found, showing available downstream assets in CMDB", "downstream_assets": [dict(a) for a in assets]}, indent=2)
            
        job_id = jobs[0]['job_id']
        cursor.execute('''
            SELECT b.asset_name, b.asset_type, b.owner, b.sla_minutes, b.criticality 
            FROM asset_dependency a
            JOIN business_asset b ON a.asset_id = b.asset_id
            WHERE a.job_id = %s
        ''', (job_id,))
        assets = cursor.fetchall()
        
        results = {
            jobs[0]['job_name']: {
                "downstream": [dict(a) for a in assets]
            }
        }
        
        return json.dumps({"query": service_name, "matches": results}, indent=2)

def get_runbook(service_name: str) -> str:
    """Fetches Runbook based on service name from the database."""
    db = PostgresDatabase(os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db"))
    with db.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT title, incident_type, prerequisites_json, verification_json, rollback_json FROM runbook WHERE title ILIKE %s OR runbook_id ILIKE %s", (f"%{service_name}%", f"%{service_name}%"))
        rbs = cursor.fetchall()
        if rbs:
            return json.dumps([dict(r) for r in rbs], indent=2)
            
        # Fallback: return any available runbook in the demo environment
        cursor.execute("SELECT title, incident_type, prerequisites_json, verification_json, rollback_json FROM runbook LIMIT 3")
        rbs = cursor.fetchall()
        if rbs:
            return json.dumps([dict(r) for r in rbs], indent=2)
            
    return f"No runbook found for service {service_name}. Default recommendation: Escalate to L3."

# The OpenAI JSON schema definitions for the tools
AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_logs",
            "description": "Queries logs for a given incident_id. Use this to find errors or trace the failure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "incident_id": {
                        "type": "string",
                        "description": "The ID of the incident (e.g. INC-12345)"
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Optional keyword to filter logs (e.g. 'schema' or 'timeout')"
                    }
                },
                "required": ["incident_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cmdb_context",
            "description": "Fetches upstream and downstream dependencies for a given service or job name from the CMDB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "The name of the service, job, or table (e.g. 'customer_profile')"
                    }
                },
                "required": ["service_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_runbook",
            "description": "Fetches recovery runbooks and standard operating procedures for a given service or job.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "The name of the service or job to get a runbook for."
                    }
                },
                "required": ["service_name"]
            }
        }
    }
]

async def execute_tool_call(tool_name: str, arguments: str) -> str:
    print(f"Executing tool {tool_name} with args {arguments}")
    try:
        args = json.loads(arguments)
    except:
        args = {}
        
    try:
        if tool_name == "query_logs":
            return query_logs(args.get("incident_id"), args.get("keyword", ""))
        elif tool_name == "get_cmdb_context":
            return get_cmdb_context(args.get("service_name", ""))
        elif tool_name == "get_runbook":
            return get_runbook(args.get("service_name", ""))
        else:
            return f"Error: Tool {tool_name} not found."
    except Exception as e:
        return f"Error executing {tool_name}: {str(e)}"
