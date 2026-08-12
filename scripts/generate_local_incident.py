"""Generate a fresh, realistic local incident dataset in SQLite."""
from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "local.db"

SCENARIOS = [
    {
        "service": "customer_profile",
        "title": "Customer profile pipeline blocked by schema regression",
        "summary": "A producer schema update removed a consumer-required field, blocking downstream profile processing.",
        "root_cause": "A producer-side schema change removed a required compatibility field without a versioned contract migration.",
        "team": "Data Platform",
        "assets": ["Customer Profile Ingestion", "Marketing Sync", "Loyalty Executive Dashboard", "Campaign Audience Export"],
    },
    {
        "service": "payments_etl",
        "title": "Payments warehouse load delayed by compute exhaustion",
        "summary": "The nightly warehouse load exhausted executor memory and delayed finance reporting dependencies.",
        "root_cause": "A volume spike exceeded the configured Spark executor memory allocation during the aggregation stage.",
        "team": "Analytics Engineering",
        "assets": ["Payments Warehouse Load", "Finance Reporting", "Revenue Dashboard", "Settlement Export"],
    },
    {
        "service": "inventory_sync",
        "title": "Inventory synchronization stalled after upstream API timeouts",
        "summary": "Repeated upstream timeouts stalled inventory updates and left customer availability views stale.",
        "root_cause": "The supplier API connection pool saturated after retry amplification during a latency spike.",
        "team": "Commerce Platform",
        "assets": ["Inventory Sync", "Availability Service", "Storefront Inventory", "Replenishment Feed"],
    },
]


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("SQLite database is not initialized. Start the local API once, then rerun this script.")
    scenario = random.choice(SCENARIOS)
    now = datetime.now(timezone.utc)
    incident_id = f"INC-{now:%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    severity = random.choice(["SEV-1", "SEV-2"])
    detected = (now - timedelta(minutes=random.randint(8, 35))).isoformat()
    next_sla = (now + timedelta(minutes=random.randint(12, 42))).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO incident VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (incident_id, scenario["title"], "AWAITING_APPROVAL", severity, detected, next_sla, scenario["team"], scenario["service"], scenario["summary"]))
        alert_rows = [
            (f"ALT-{uuid.uuid4().hex[:7].upper()}", incident_id, "critical" if severity == "SEV-1" else "high", "Pipeline failure", "Datadog", f"{scenario['service']} failed during run {run_id}."),
            (f"ALT-{uuid.uuid4().hex[:7].upper()}", incident_id, "high", "Downstream delay", "Airflow", f"A dependent workload is waiting on {scenario['service']}"),
            (f"ALT-{uuid.uuid4().hex[:7].upper()}", incident_id, "high", "Freshness risk", "PagerDuty", f"Customer-facing data products may breach freshness targets."),
        ]
        conn.executemany("INSERT INTO alert VALUES (?, ?, ?, ?, ?, ?)", alert_rows)
        conn.execute("INSERT INTO hypothesis VALUES (?, ?, ?, ?)", (f"HYP-{uuid.uuid4().hex[:7].upper()}", incident_id, scenario["root_cause"], round(random.uniform(0.84, 0.96), 2)))
        evidence_rows = [
            (f"EVD-{uuid.uuid4().hex[:7].upper()}", incident_id, "Execution logs", "Failure signature", "Repeated failure pattern identified", f"ERROR {scenario['service']}: {scenario['root_cause']}"),
            (f"EVD-{uuid.uuid4().hex[:7].upper()}", incident_id, "Topology", "Dependency analysis", "Downstream dependency chain confirmed", f"{scenario['assets'][1]} depends on {scenario['assets'][0]}"),
            (f"EVD-{uuid.uuid4().hex[:7].upper()}", incident_id, "SLO monitor", "Freshness exposure", "Customer product freshness at risk", f"{scenario['assets'][2]} freshness target is approaching breach."),
        ]
        conn.executemany("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)", evidence_rows)
        impact_rows = [(f"AST-{uuid.uuid4().hex[:7].upper()}", incident_id, asset, "Job" if index < 2 else "Data Product", "BLOCKED" if index < 2 else "AT RISK", f"Impacted by {scenario['service']} failure") for index, asset in enumerate(scenario["assets"])]
        conn.executemany("INSERT INTO impact VALUES (?, ?, ?, ?, ?, ?)", impact_rows)
        steps = [
            {"sequence_no": 1, "title": "Stabilize source", "action_type": f"Restore healthy processing for {scenario['service']}.", "risk_level": "LOW"},
            {"sequence_no": 2, "title": "Recover backlog", "action_type": "Replay failed work from the durable checkpoint.", "risk_level": "MEDIUM"},
            {"sequence_no": 3, "title": "Verify outcomes", "action_type": "Confirm downstream freshness and SLO recovery.", "risk_level": "LOW"},
        ]
        conn.execute("INSERT INTO plan VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (f"PLAN-{uuid.uuid4().hex[:7].upper()}", incident_id, "PENDING_APPROVAL", f"The proposed recovery stabilizes {scenario['service']}, replays the backlog, and verifies impacted products.", "Affected workloads return to their expected freshness targets.", "MEDIUM", uuid.uuid4().hex, json.dumps(steps)))
        agents = [("Watcher Agent", "ALERT_CORRELATED", "Grouped related monitoring signals into one incident."), ("RCA Agent", "HYPOTHESIS_CREATED", "Ranked the root-cause hypothesis from the evidence."), ("Dependency_Agent", "IMPACT_CALCULATED", "Calculated technical and business blast radius."), ("Runbook Agent", "RUNBOOK_RETRIEVED", "Retrieved the matched recovery procedure."), ("Safety Agent", "SAFETY_VALIDATION_PASSED", "Validated recovery constraints and approval requirements.")]
        for index, (agent, event_type, message) in enumerate(agents):
            timestamp = (now - timedelta(minutes=12 - index * 2)).isoformat()
            conn.execute("INSERT INTO event VALUES (?, ?, ?, ?, ?, ?)", (f"EVT-{uuid.uuid4().hex[:7].upper()}", incident_id, timestamp, agent, event_type, message))
    print(f"Generated {incident_id} in {DB_PATH}")


if __name__ == "__main__":
    main()
