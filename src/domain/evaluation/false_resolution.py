"""
False Resolution Rate check (WP-ORG-005).

Per docs/NemoGuard_Internal_Org_Next_Steps_for_Coding_Agent_2026-08-27_v2_Commander_Live.md
section 7:

    False resolution definition:
        incident status = RESOLVED
        AND
        required verification checks are not actually satisfied

    Target: 0

This is a real, deterministic, always-computable audit -- it does not
depend on the scenario catalog or LLM output at all, only on the
persisted incident/action_plan/verification_result rows every resolution
already produces. It can be run continuously (not just during a formal
scenario-catalog run) as a genuine safety net: if this ever returns a
non-empty list in a real deployment, that is a serious bug (an incident
was marked resolved without its recovery actually being independently
verified), not a benchmark statistic.

"Required verification checks" = every verification_result row recorded
for the incident's most recent action_plan. An incident is a false
resolution if it is RESOLVED but either has zero verification_result
rows for that plan, or has at least one row whose status is not PASSED.
"""
import os
from typing import Any, Dict, List, Optional

from src.store.postgres_database import PostgresDatabase


def find_false_resolutions(db: Optional[PostgresDatabase] = None, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Scans every RESOLVED incident and flags any whose required
    verification checks were not actually all PASSED. Returns a list of
    dicts describing each violation found (empty list = 0 false
    resolutions, the target state).
    """
    db = db or PostgresDatabase(
        os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
    )

    violations: List[Dict[str, Any]] = []
    with db.get_connection() as conn:
        if tenant_id:
            cursor = conn.execute(
                "SELECT incident_id, title, resolved_at FROM incident WHERE status = 'RESOLVED' AND tenant_id = %s",
                (tenant_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT incident_id, title, resolved_at FROM incident WHERE status = 'RESOLVED'"
            )
        resolved_incidents = cursor.fetchall()

        for incident_id, title, resolved_at in resolved_incidents:
            cursor = conn.execute(
                "SELECT action_plan_id FROM action_plan WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1",
                (incident_id,),
            )
            plan_row = cursor.fetchone()
            if not plan_row:
                violations.append({
                    "incident_id": incident_id, "title": title, "resolved_at": resolved_at,
                    "reason": "Incident is RESOLVED but has no action_plan at all.",
                    "verification_checks": [],
                })
                continue
            plan_id = plan_row[0]

            cursor = conn.execute(
                "SELECT check_name, status FROM verification_result WHERE action_plan_id = %s",
                (plan_id,),
            )
            checks = [{"check_name": r[0], "status": r[1]} for r in cursor.fetchall()]

            if not checks:
                violations.append({
                    "incident_id": incident_id, "title": title, "resolved_at": resolved_at,
                    "reason": f"Incident is RESOLVED but plan {plan_id} has zero verification_result rows.",
                    "verification_checks": [],
                })
                continue

            failing = [c for c in checks if c["status"] != "PASSED"]
            if failing:
                violations.append({
                    "incident_id": incident_id, "title": title, "resolved_at": resolved_at,
                    "reason": f"Incident is RESOLVED but {len(failing)} of {len(checks)} verification check(s) "
                              f"for plan {plan_id} did not PASS: "
                              + ", ".join(f"{c['check_name']}={c['status']}" for c in failing),
                    "verification_checks": checks,
                })

    return violations


def compute_false_resolution_rate(db: Optional[PostgresDatabase] = None, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the real, computed false-resolution rate: violations found /
    total RESOLVED incidents. Never hardcoded -- an empty deployment (zero
    resolved incidents) reports rate=None rather than a fabricated 0.0,
    since a rate with no denominator is not a meaningful measurement.
    """
    db = db or PostgresDatabase(
        os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
    )
    with db.get_connection() as conn:
        if tenant_id:
            cursor = conn.execute("SELECT COUNT(*) FROM incident WHERE status = 'RESOLVED' AND tenant_id = %s", (tenant_id,))
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM incident WHERE status = 'RESOLVED'")
        total_resolved = cursor.fetchone()[0]

    violations = find_false_resolutions(db, tenant_id)
    return {
        "total_resolved_incidents": total_resolved,
        "false_resolution_count": len(violations),
        "false_resolution_rate": (round(len(violations) / total_resolved, 4) if total_resolved else None),
        "target": 0,
        "meets_target": len(violations) == 0,
        "violations": violations,
    }
