"""
Replay execution engine (WP-ORG-001).

Runs a historical incident through the SAME multi-agent investigation
graph used for live incidents (LangGraphInvestigator) -- not a separate,
simplified pipeline -- using only point-in-time evidence
(historical_incident_snapshot rows), with the real root cause/recovery
(historical_incident_ground_truth) never queried by this code path.

Isolation from write capabilities: LangGraphInvestigator's own tool schema
(_get_full_tools_schema) never advertises write/execution tools to RCA,
Impact, or Runbook agents in the first place (only the Grounding Critic is
restricted to read-only tools, and even RCA/Impact/Runbook only ever see
query_logs/get_cmdb_context/get_runbook/read_runbook_document plus the
optional read-only LocalStack observability tools -- see agent_tools.py's
AGENT_TOOLS_SCHEMA). Replay therefore inherits "no write tools" for free
from the live investigation path; nothing here grants any additional
capability.
"""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.store.postgres_database import PostgresDatabase
from src.domain.agents.agent_tools import REPLAY_CONTEXT
from src.domain.agents.langgraph_investigator import LangGraphInvestigator


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class HistoricalIncidentNotFoundError(Exception):
    pass


class ReplayEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db = PostgresDatabase(
            db_path or os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )

    # ------------------------------------------------------------------
    # Historical incident CRUD (ingestion)
    # ------------------------------------------------------------------

    def create_historical_incident(
        self,
        *,
        source_system: str,
        title: str,
        opened_at: str,
        resolved_at: Optional[str] = None,
        service: Optional[str] = None,
        pipeline: Optional[str] = None,
        environment: Optional[str] = None,
        severity: Optional[str] = None,
        external_incident_id: Optional[str] = None,
        created_by: Optional[str] = None,
        snapshots: Optional[List[Dict[str, Any]]] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Creates a historical_incident row plus its point-in-time
        snapshots and (optionally) its hidden ground truth in one call.

        `snapshots`: list of {"snapshot_type": "logs"|"cmdb"|"runbooks"|
        "alerts"|..., "payload": <json-serializable>, "snapshot_timestamp":
        iso str, "source_reference": optional str}.
        """
        now = datetime.now(timezone.utc).isoformat()
        incident_id = _generate_id("HIST")
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO historical_incident (
                    id, external_incident_id, source_system, opened_at, resolved_at,
                    service, pipeline, environment, severity, title, created_at, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    incident_id, external_incident_id, source_system, opened_at, resolved_at,
                    service, pipeline, environment, severity, title, now, created_by,
                ),
            )
            for snap in (snapshots or []):
                conn.execute(
                    """
                    INSERT INTO historical_incident_snapshot (
                        id, historical_incident_id, snapshot_type, snapshot_timestamp,
                        source_reference, payload_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        _generate_id("SNAP"), incident_id, snap["snapshot_type"],
                        snap.get("snapshot_timestamp") or now, snap.get("source_reference"),
                        json.dumps(snap["payload"]), now,
                    ),
                )
            if ground_truth:
                conn.execute(
                    """
                    INSERT INTO historical_incident_ground_truth (
                        historical_incident_id, root_cause, cause_type, actual_recovery,
                        actual_impacted_assets_json, actual_business_impact,
                        actual_resolution_time_seconds, postmortem_reference, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        incident_id, ground_truth["root_cause"], ground_truth.get("cause_type"),
                        ground_truth.get("actual_recovery"),
                        json.dumps(ground_truth.get("actual_impacted_assets") or []),
                        ground_truth.get("actual_business_impact"),
                        ground_truth.get("actual_resolution_time_seconds"),
                        ground_truth.get("postmortem_reference"), now,
                    ),
                )
        return incident_id

    def list_historical_incidents(self) -> List[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, external_incident_id, source_system, title, opened_at, resolved_at, "
                "service, pipeline, environment, severity, created_at "
                "FROM historical_incident ORDER BY opened_at DESC"
            )
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_historical_incident(self, historical_incident_id: str) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM historical_incident WHERE id = %s", (historical_incident_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HistoricalIncidentNotFoundError(historical_incident_id)
            cols = [c[0] for c in cursor.description]
            return dict(zip(cols, row))

    def get_replay(self, replay_id: str) -> Dict[str, Any]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM historical_incident_replay WHERE id = %s", (replay_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Replay {replay_id} not found")
            cols = [c[0] for c in cursor.description]
            return dict(zip(cols, row))

    def get_replay_result(self, replay_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM historical_incident_replay_result WHERE replay_id = %s", (replay_id,))
            row = cursor.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cursor.description]
            result = dict(zip(cols, row))
        for field in ("top_3_hypotheses_json", "recommended_plan_json", "tool_calls_json", "evidence_ids_json"):
            if result.get(field):
                try:
                    result[field.replace("_json", "")] = json.loads(result[field])
                except Exception:
                    pass
        return result

    # ------------------------------------------------------------------
    # Replay execution
    # ------------------------------------------------------------------

    def start_replay(
        self,
        historical_incident_id: str,
        *,
        model_provider: str = "nvidia_nim",
        model_name: str = "nvidia/nemotron-3-ultra-550b-a55b",
        prompt_version: str = "v1",
        created_by: Optional[str] = None,
    ) -> str:
        """Creates a PENDING replay row and returns its id. Does not run the
        investigation itself -- the caller schedules run_replay() (e.g. via
        FastAPI BackgroundTasks or asyncio.create_task) so the API request
        that starts a replay can return immediately, matching how live
        triage is dispatched to Temporal rather than run inline."""
        # Fail fast rather than creating a replay row for an incident that
        # doesn't exist.
        self.get_historical_incident(historical_incident_id)

        replay_id = _generate_id("REPLAY")
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO historical_incident_replay (
                    id, historical_incident_id, model_provider, model_name, prompt_version,
                    status, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (replay_id, historical_incident_id, model_provider, model_name, prompt_version, "PENDING", created_by),
            )
        return replay_id

    async def run_replay(self, replay_id: str) -> Dict[str, Any]:
        """
        Runs the actual investigation for a previously-created replay row.

        Sets REPLAY_CONTEXT to the historical_incident_id for the duration
        of the investigation so every read tool (query_logs, get_cmdb_context,
        get_runbook, read_runbook_document) resolves evidence exclusively
        from historical_incident_snapshot rows -- see agent_tools.py. Always
        clears the contextvar in a `finally` block so a failed/aborted
        replay can never leave a later, unrelated live investigation
        accidentally reading historical snapshot data.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT historical_incident_id FROM historical_incident_replay WHERE id = %s",
                (replay_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Replay {replay_id} not found")
            historical_incident_id = row[0]

        started_at = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE historical_incident_replay SET status = 'RUNNING', started_at = %s WHERE id = %s",
                (started_at, replay_id),
            )

        # Historical alerts are just another snapshot type; feed them into
        # the investigator exactly like a live incident's `alerts` list.
        alerts: List[Dict[str, Any]] = []
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT payload_json FROM historical_incident_snapshot "
                "WHERE historical_incident_id = %s AND snapshot_type = 'alerts' "
                "ORDER BY snapshot_timestamp ASC",
                (historical_incident_id,),
            )
            for (payload_json,) in cursor.fetchall():
                try:
                    parsed = json.loads(payload_json)
                    if isinstance(parsed, list):
                        alerts.extend(parsed)
                    else:
                        alerts.append(parsed)
                except Exception:
                    continue

        token = REPLAY_CONTEXT.set(historical_incident_id)
        start_perf = time.perf_counter()
        try:
            investigator = LangGraphInvestigator()
            final_state = await investigator.investigate(historical_incident_id, alerts)
        except Exception as e:
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE historical_incident_replay SET status = 'FAILED', completed_at = %s, error_message = %s WHERE id = %s",
                    (datetime.now(timezone.utc).isoformat(), str(e), replay_id),
                )
            return {"status": "FAILED", "error": str(e)}
        finally:
            REPLAY_CONTEXT.reset(token)

        elapsed_seconds = time.perf_counter() - start_perf

        rca_res = final_state.get("rca_result", {}) or {}
        runbook_res = final_state.get("runbook_result", {}) or {}
        final_plan = final_state.get("final_plan", {}) or {}

        hypotheses = rca_res.get("hypotheses") or []
        if not hypotheses and rca_res.get("finding"):
            hypotheses = [{
                "statement": rca_res.get("finding"),
                "cause_type": rca_res.get("cause_type", "OTHER"),
                "confidence": rca_res.get("confidence", 0.5),
            }]
        top_hypothesis = hypotheses[0] if hypotheses else {}
        top_3 = hypotheses[:3]

        evidence_ids = [e.get("title", "") for e in (rca_res.get("evidence") or [])]

        completed_at = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE historical_incident_replay SET status = 'COMPLETED', completed_at = %s WHERE id = %s",
                (completed_at, replay_id),
            )
            conn.execute(
                """
                INSERT INTO historical_incident_replay_result (
                    replay_id, top_hypothesis, top_hypothesis_cause_type, top_hypothesis_score,
                    top_3_hypotheses_json, selected_runbook, recommended_plan_json,
                    tool_calls_json, evidence_ids_json, elapsed_seconds
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (replay_id) DO UPDATE SET
                    top_hypothesis = EXCLUDED.top_hypothesis,
                    top_hypothesis_cause_type = EXCLUDED.top_hypothesis_cause_type,
                    top_hypothesis_score = EXCLUDED.top_hypothesis_score,
                    top_3_hypotheses_json = EXCLUDED.top_3_hypotheses_json,
                    selected_runbook = EXCLUDED.selected_runbook,
                    recommended_plan_json = EXCLUDED.recommended_plan_json,
                    tool_calls_json = EXCLUDED.tool_calls_json,
                    evidence_ids_json = EXCLUDED.evidence_ids_json,
                    elapsed_seconds = EXCLUDED.elapsed_seconds
                """,
                (
                    replay_id,
                    top_hypothesis.get("statement"),
                    top_hypothesis.get("cause_type"),
                    top_hypothesis.get("confidence"),
                    json.dumps(top_3),
                    runbook_res.get("finding"),
                    json.dumps(final_plan),
                    json.dumps([]),
                    json.dumps(evidence_ids),
                    elapsed_seconds,
                ),
            )

        # Score against hidden ground truth, if one was recorded for this
        # historical incident. This is the ONLY point in the whole replay
        # flow that reads historical_incident_ground_truth -- never during
        # investigation itself.
        self.score_replay(replay_id)

        return {
            "status": "COMPLETED",
            "replay_id": replay_id,
            "top_hypothesis": top_hypothesis,
            "elapsed_seconds": elapsed_seconds,
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_replay(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """
        Compares the replay's top hypothesis/top-3 against
        historical_incident_ground_truth and persists top1_correct/
        top3_correct/cause_family_correct on the result row. Returns None
        (no-op) if no ground truth was recorded for this historical
        incident -- a replay can run and be inspected qualitatively even
        without a hidden answer to score against.

        Matching is deliberately conservative: cause_type equality is the
        primary signal (both are drawn from the same constrained enum-like
        vocabulary used throughout RCAAgent: SCHEMA_REGRESSION,
        DATA_QUALITY, RESOURCE_EXHAUSTION, PARTIAL_WRITE, OTHER), with a
        case-insensitive substring check on the free-text root_cause/
        statement as a secondary signal. This avoids overclaiming semantic
        equivalence between two natural-language strings.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT historical_incident_id FROM historical_incident_replay WHERE id = %s",
                (replay_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            historical_incident_id = row[0]

            cursor = conn.execute(
                "SELECT root_cause, cause_type FROM historical_incident_ground_truth WHERE historical_incident_id = %s",
                (historical_incident_id,),
            )
            gt_row = cursor.fetchone()
            if not gt_row:
                return None
            gt_root_cause, gt_cause_type = gt_row

            cursor = conn.execute(
                "SELECT top_hypothesis, top_hypothesis_cause_type, top_3_hypotheses_json FROM historical_incident_replay_result WHERE replay_id = %s",
                (replay_id,),
            )
            result_row = cursor.fetchone()
            if not result_row:
                return None
            top_hyp, top_cause_type, top_3_json = result_row

        def _matches(cause_type: Optional[str], statement: Optional[str]) -> bool:
            if gt_cause_type and cause_type and gt_cause_type.strip().upper() == cause_type.strip().upper():
                return True
            if gt_root_cause and statement and gt_root_cause.strip().lower() in statement.strip().lower():
                return True
            return False

        top1_correct = _matches(top_cause_type, top_hyp)

        top_3 = []
        try:
            top_3 = json.loads(top_3_json) if top_3_json else []
        except Exception:
            top_3 = []
        top3_correct = top1_correct or any(
            _matches(h.get("cause_type"), h.get("statement")) for h in top_3
        )
        cause_family_correct = bool(
            gt_cause_type and top_cause_type and gt_cause_type.strip().upper() == top_cause_type.strip().upper()
        )

        scored_at = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE historical_incident_replay_result
                SET top1_correct = %s, top3_correct = %s, cause_family_correct = %s, scored_at = %s
                WHERE replay_id = %s
                """,
                (int(top1_correct), int(top3_correct), int(cause_family_correct), scored_at, replay_id),
            )

        return {
            "top1_correct": top1_correct,
            "top3_correct": top3_correct,
            "cause_family_correct": cause_family_correct,
        }
