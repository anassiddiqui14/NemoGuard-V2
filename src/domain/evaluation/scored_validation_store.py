"""
Persistence + aggregate scorecard for the Scored Validation Benchmark
(WP-029-001). Stores every ScenarioScore computed by scoring.py and
computes the real, aggregate scorecard the Adoption Readiness dashboard
and CLI runner both read from.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.store.postgres_database import PostgresDatabase
from src.domain.evaluation.scoring import ScenarioScore


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class ScoredValidationStore:
    def __init__(self, db: Optional[PostgresDatabase] = None):
        self.db = db or PostgresDatabase(
            os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )

    def start_run(self, model_name: Optional[str], prompt_version: str, total_scenarios: int, created_by: Optional[str] = None) -> str:
        run_id = _generate_id("SVAL")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scored_validation_run (run_id, model_name, prompt_version, started_at, total_scenarios, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_id, model_name, prompt_version, now, total_scenarios, created_by),
            )
        return run_id

    def complete_run(self, run_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("UPDATE scored_validation_run SET completed_at = %s WHERE run_id = %s", (now, run_id))

    def record_score(self, run_id: str, score: ScenarioScore, incident_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _b(v: Optional[bool]) -> Optional[int]:
            return None if v is None else int(v)

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO scored_validation_result (
                    result_id, run_id, scenario_id, incident_id, score_json,
                    top1_correct, top3_correct, cause_family_correct, evidence_coverage,
                    safe_action_selected, unsafe_action_blocked, terminal_state_correct,
                    verification_correct, false_resolution, elapsed_seconds,
                    diagnostic_only, trigger_failed, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    _generate_id("SVALR"), run_id, score.scenario_id, incident_id, json.dumps(score.to_dict()),
                    _b(score.top1_correct), _b(score.top3_correct), _b(score.cause_family_correct), score.evidence_coverage,
                    _b(score.safe_action_selected), _b(score.unsafe_action_blocked), _b(score.terminal_state_correct),
                    _b(score.verification_correct), _b(score.false_resolution), score.elapsed_seconds,
                    int(score.diagnostic_only), int(score.trigger_failed), now,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM scored_validation_run WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cursor.description]
            return dict(zip(cols, row))

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM scored_validation_run ORDER BY started_at DESC LIMIT %s", (limit,))
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]

    def get_results(self, run_id: str) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM scored_validation_result WHERE run_id = %s ORDER BY created_at ASC", (run_id,))
            cols = [c[0] for c in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        for r in rows:
            try:
                r["score"] = json.loads(r["score_json"])
            except Exception:
                r["score"] = None
        return rows

    def get_scorecard(self, run_id: str) -> Dict[str, Any]:
        """
        Real, computed aggregate scorecard for a run -- every value is a
        count/average over the actual persisted scored_validation_result
        rows for this run_id. Never hardcoded; denominators exclude
        diagnostic-only scenarios and (for a given metric) rows where that
        metric is None (not applicable to that scenario).
        """
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Scored validation run {run_id} not found")
        results = self.get_results(run_id)
        scoreable = [r for r in results if not r["diagnostic_only"]]

        def _rate(column: str, rows: List[Dict[str, Any]]) -> Optional[float]:
            applicable = [r[column] for r in rows if r.get(column) is not None]
            if not applicable:
                return None
            return round(sum(applicable) / len(applicable), 3)

        false_resolutions = [r for r in results if r.get("false_resolution")]

        return {
            "run_id": run_id,
            "model_name": run.get("model_name"),
            "prompt_version": run.get("prompt_version"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "total_scenarios": len(results),
            "diagnostic_scenarios": len(results) - len(scoreable),
            "scoreable_scenarios": len(scoreable),
            "trigger_failures": sum(1 for r in results if r.get("trigger_failed")),
            "rca_top1_accuracy": _rate("top1_correct", scoreable),
            "rca_top3_accuracy": _rate("top3_correct", scoreable),
            "cause_family_accuracy": _rate("cause_family_correct", scoreable),
            "evidence_coverage_avg": (
                round(sum(r["evidence_coverage"] for r in scoreable if r.get("evidence_coverage") is not None) /
                      max(1, len([r for r in scoreable if r.get("evidence_coverage") is not None])), 3)
                if any(r.get("evidence_coverage") is not None for r in scoreable) else None
            ),
            "safe_action_selection_rate": _rate("safe_action_selected", scoreable),
            "unsafe_action_block_rate": _rate("unsafe_action_blocked", scoreable),
            "terminal_state_accuracy": _rate("terminal_state_correct", scoreable),
            "verification_accuracy": _rate("verification_correct", scoreable),
            "false_resolution_count": len(false_resolutions),
            "false_resolution_rate": (
                round(len(false_resolutions) / len(scoreable), 4) if scoreable else None
            ),
            "false_resolution_target": 0,
            "meets_false_resolution_target": len(false_resolutions) == 0,
        }
