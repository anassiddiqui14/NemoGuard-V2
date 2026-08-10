import os
import sys
from typing import Optional, List, Dict, Any
from fastmcp import FastMCP
from pydantic import BaseModel

# Add the parent directory to sys.path so we can import src
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))

from src.tools.read_tools import ReadTools

# Initialize FastMCP server
mcp = FastMCP("Pipeline Copilot Tools")

# Initialize our tools with a dummy database path for now (or a real one if generated)
db_path = os.path.join(os.path.dirname(__file__), "../../data/demo.db")
if not os.path.exists(os.path.dirname(db_path)):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
# Create a dummy sqlite DB if it doesn't exist so tools don't crash
import sqlite3
if not os.path.exists(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS incident (id TEXT, state TEXT, severity TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS alert (id TEXT, incident_id TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS execution (id TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS log_event (id TEXT, run_id TEXT, message TEXT, timestamp TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS dependency (upstream_id TEXT, downstream_id TEXT)")

read_tools = ReadTools(db_path=db_path)

@mcp.tool()
def list_open_incidents(severity: str = None, limit: int = 50) -> dict:
    """Lists open incidents"""
    return read_tools.list_open_incidents(severity, limit).to_dict()

@mcp.tool()
def get_alert_bundle(alert_ids: list[str] = None, incident_id: str = None) -> dict:
    """Gets details for specific alerts or all alerts linked to an incident"""
    return read_tools.get_alert_bundle(alert_ids, incident_id).to_dict()

@mcp.tool()
def get_run(run_id: str) -> dict:
    """Gets execution details for a specific run"""
    return read_tools.get_run(run_id).to_dict()

@mcp.tool()
def get_run_timeline(run_id: str) -> dict:
    """Gets chronological logs for a specific run"""
    return read_tools.get_run_timeline(run_id).to_dict()

@mcp.tool()
def search_logs(query: str, limit: int = 50) -> dict:
    """Searches across all logs for a specific query string"""
    return read_tools.search_logs(query, limit).to_dict()

@mcp.tool()
def get_job_graph(job_id: str, direction: str = 'downstream', depth: int = 3) -> dict:
    """Gets upstream or downstream dependencies for a job"""
    return read_tools.get_job_graph(job_id, direction, depth).to_dict()

@mcp.tool()
def calculate_business_impact(root_run_id: str) -> dict:
    """Calculates downstream business impact for a root cause failure"""
    return read_tools.calculate_business_impact(root_run_id).to_dict()

@mcp.tool()
def get_runbook(failure_type: str, job_id: str) -> dict:
    """Gets runbook steps for a specific failure type and job"""
    return read_tools.get_runbook(failure_type, job_id).to_dict()

if __name__ == "__main__":
    # Start the server using stdio transport (default)
    mcp.run()
