"""
Model Evaluation Service engine (WP-ORG-004).

Provider abstraction: this deliberately does NOT introduce a second LLM
client abstraction. Every agent already accepts a `model_override`
constructor parameter (see rca_agent.py, dependency_agent.py,
runbook_agent.py, langgraph_investigator.py's GroundingCritic), and
BaseAgent's client is a single OpenAI-compatible client pointed at NVIDIA
NIM (https://integrate.api.nvidia.com/v1) -- any organization-approved
model reachable through that same OpenAI-compatible endpoint (Nemotron
Ultra, Nemotron Super, or a future model NVIDIA NIM exposes) can be passed
as `model_override` with zero code changes. That IS the provider
abstraction: one call signature, swappable model string.

Evaluation flow:

    create_run(models, historical_incident_ids)
        -> for each (model, incident) pair:
               ReplayEngine.start_replay(incident, model_name=model)
               ReplayEngine.run_replay(replay_id)
        -> get_scorecard(run_id) aggregates real
           historical_incident_replay_result rows, grouped by model.

Every scorecard value is computed live from persisted replay results --
never hardcoded. Metrics this deployment cannot yet measure (unnecessary
tool count, tool loop count, tool failure recovery, input/output token
counts, estimated cost) are explicitly reported as unavailable rather than
fabricated, since no code path currently persists per-call token/tool-loop
telemetry for replay runs.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.store.postgres_database import PostgresDatabase


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class EvaluationEngine:
    def __init__(self, db: Optional[PostgresDatabase] = None):
        self.db = db or PostgresDatabase(
            os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )

    def create_run(
        self, *, name: str, models: List[str], historical_incident_ids: List[str],
        prompt_version: str = "v1", created_by: Optional[str] = None,
    ) -> str:
        if not models:
            raise ValueError("At least one model must be specified for an evaluation run.")
        if not historical_incident_ids:
            raise ValueError("At least one historical incident must be specified for an evaluation run.")

        run_id = _generate_id("MEVAL")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO model_evaluation_run (
                    run_id, name, models_json, historical_incident_ids_json, prompt_version,
                    status, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, name, json.dumps(models), json.dumps(historical_incident_ids),
                    prompt_version, "PENDING", created_by, now,
                ),
            )
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM model_evaluation_run WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cursor.description]
            result = dict(zip(cols, row))
        result["models"] = json.loads(result.get("models_json") or "[]")
        result["historical_incident_ids"] = json.loads(result.get("historical_incident_ids_json") or "[]")
        return result

    def list_runs(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM model_evaluation_run ORDER BY created_at DESC")
            cols = [c[0] for c in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
        for r in rows:
            r["models"] = json.loads(r.get("models_json") or "[]")
            r["historical_incident_ids"] = json.loads(r.get("historical_incident_ids_json") or "[]")
        return rows

    async def run_evaluation(self, run_id: str) -> Dict[str, Any]:
        """
        Executes every (model, historical_incident) pair for this run
        sequentially through the real ReplayEngine -- the SAME investigation
        graph, tools, and scoring logic used for a normal WP-ORG-001 replay.
        This is what makes the comparison meaningful: it isn't a separate,
        simplified evaluation harness, it's the real pipeline run
        repeatedly with only the model swapped.
        """
        from src.domain.replay.replay_engine import ReplayEngine

        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Evaluation run {run_id} not found")

        replay_engine = ReplayEngine(self.db.db_path if hasattr(self.db, "db_path") else None)
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute("UPDATE model_evaluation_run SET status = 'RUNNING' WHERE run_id = %s", (run_id,))

        completed = 0
        failed = 0
        for model_name in run["models"]:
            for historical_incident_id in run["historical_incident_ids"]:
                try:
                    replay_id = replay_engine.start_replay(
                        historical_incident_id, model_name=model_name, prompt_version=run["prompt_version"],
                        created_by=run.get("created_by"),
                    )
                    with self.db.get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO model_evaluation_replay_link (run_id, replay_id, model_name, historical_incident_id)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (run_id, replay_id, model_name, historical_incident_id),
                        )
                    await replay_engine.run_replay(replay_id)
                    completed += 1
                except Exception as e:
                    print(f"Model evaluation: replay failed for run={run_id} model={model_name} incident={historical_incident_id}: {e}")
                    failed += 1

        completed_at = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE model_evaluation_run SET status = %s, completed_at = %s WHERE run_id = %s",
                ("COMPLETED" if failed == 0 else "COMPLETED_WITH_ERRORS", completed_at, run_id),
            )
        return {"run_id": run_id, "completed": completed, "failed": failed}

    def get_scorecard(self, run_id: str) -> Dict[str, Any]:
        """
        Computes the real scorecard for this run, grouped by model, straight
        from persisted historical_incident_replay(_result) rows joined
        through model_evaluation_replay_link. Never hardcodes a value --
        any metric this deployment does not yet instrument (tool-loop
        counts, token counts, cost) is explicitly reported as
        `"available": false` rather than a fabricated number, per the
        spec's "Never hardcode result values."
        """
        run = self.get_run(run_id)
        if not run:
            raise ValueError(f"Evaluation run {run_id} not found")

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT l.model_name, l.historical_incident_id, r.status,
                       res.top1_correct, res.top3_correct, res.cause_family_correct,
                       res.elapsed_seconds, res.evidence_ids_json, res.top_hypothesis_score
                FROM model_evaluation_replay_link l
                JOIN historical_incident_replay r ON r.id = l.replay_id
                LEFT JOIN historical_incident_replay_result res ON res.replay_id = l.replay_id
                WHERE l.run_id = %s
                """,
                (run_id,),
            )
            rows = cursor.fetchall()

        by_model: Dict[str, Dict[str, Any]] = {}
        for model_name in run["models"]:
            by_model[model_name] = {
                "model_name": model_name,
                "total_incidents": 0,
                "completed_replays": 0,
                "failed_replays": 0,
                "top1_correct_count": 0,
                "top3_correct_count": 0,
                "cause_family_correct_count": 0,
                "scored_count": 0,
                "evidence_present_count": 0,
                "elapsed_seconds_samples": [],
            }

        for (model_name, incident_id, status, top1_correct, top3_correct,
             cause_family_correct, elapsed_seconds, evidence_ids_json, top_score) in rows:
            bucket = by_model.setdefault(model_name, {
                "model_name": model_name, "total_incidents": 0, "completed_replays": 0,
                "failed_replays": 0, "top1_correct_count": 0, "top3_correct_count": 0,
                "cause_family_correct_count": 0, "scored_count": 0,
                "evidence_present_count": 0, "elapsed_seconds_samples": [],
            })
            bucket["total_incidents"] += 1
            if status == "COMPLETED":
                bucket["completed_replays"] += 1
            elif status == "FAILED":
                bucket["failed_replays"] += 1

            if top1_correct is not None:
                bucket["scored_count"] += 1
                bucket["top1_correct_count"] += int(top1_correct)
                bucket["top3_correct_count"] += int(top3_correct or 0)
                bucket["cause_family_correct_count"] += int(cause_family_correct or 0)
            if evidence_ids_json:
                try:
                    if json.loads(evidence_ids_json):
                        bucket["evidence_present_count"] += 1
                except Exception:
                    pass
            if elapsed_seconds is not None:
                bucket["elapsed_seconds_samples"].append(elapsed_seconds)

        scorecard_rows = []
        for model_name, bucket in by_model.items():
            scored = bucket["scored_count"]
            total = bucket["total_incidents"]
            samples = bucket["elapsed_seconds_samples"]
            avg_latency = round(sum(samples) / len(samples), 1) if samples else None
            p95_latency = None
            if samples:
                sorted_samples = sorted(samples)
                idx = min(len(sorted_samples) - 1, int(len(sorted_samples) * 0.95))
                p95_latency = round(sorted_samples[idx], 1)

            scorecard_rows.append({
                "model_name": model_name,
                "total_incidents": total,
                "completed_replays": bucket["completed_replays"],
                "failed_replays": bucket["failed_replays"],
                # RCA metrics -- real counts / real denominators, never estimated.
                "rca_top1_accuracy": round(bucket["top1_correct_count"] / scored, 3) if scored else None,
                "rca_top3_accuracy": round(bucket["top3_correct_count"] / scored, 3) if scored else None,
                "cause_family_accuracy": round(bucket["cause_family_correct_count"] / scored, 3) if scored else None,
                "scored_incident_count": scored,
                # Evidence: a weak proxy (evidence citation presence), matching the
                # same caveat already documented in scripts/run_ai_evaluation.py --
                # not a claim-level citation audit.
                "evidence_citation_presence_rate": round(bucket["evidence_present_count"] / total, 3) if total else None,
                # Performance
                "avg_latency_seconds": avg_latency,
                "p95_latency_seconds": p95_latency,
                # Explicitly unavailable metrics -- this deployment does not
                # currently persist per-call token counts, tool-loop counts,
                # unnecessary-tool-call counts, or per-token cost for replay
                # runs. Reported honestly as unavailable rather than
                # fabricated, per "Never hardcode result values."
                "unsupported_claim_rate": {"available": False, "reason": "No claim-level citation audit implemented yet."},
                "contradictory_evidence_handling": {"available": False, "reason": "Not yet instrumented."},
                "unnecessary_tool_count": {"available": False, "reason": "Per-call tool-loop telemetry not yet persisted for replay runs."},
                "tool_loop_count": {"available": False, "reason": "Per-call tool-loop telemetry not yet persisted for replay runs."},
                "tool_failure_recovery": {"available": False, "reason": "Not yet instrumented."},
                "safe_action_rate": {"available": False, "reason": "Requires WP-ORG-005 scenario catalog's allowed/prohibited-action fields; not yet cross-referenced here."},
                "input_tokens": {"available": False, "reason": "Token usage not yet persisted per replay call."},
                "output_tokens": {"available": False, "reason": "Token usage not yet persisted per replay call."},
                "estimated_cost": {"available": False, "reason": "Requires token usage, which is not yet persisted."},
            })

        return {
            "run_id": run_id,
            "run_name": run["name"],
            "models": run["models"],
            "historical_incident_count": len(run["historical_incident_ids"]),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scorecard": scorecard_rows,
        }
