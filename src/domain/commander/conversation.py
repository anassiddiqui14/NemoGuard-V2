"""
Commander Live conversation (WP-ORG-002 §4.6-4.10).

Three explicit operator intents:
  ASK       -- read-only. Answers using current incident state/evidence,
               never mutates anything.
  GUIDE     -- persists as commander_guidance, increments the incident's
               guidance_revision. May trigger reinvestigation (deterministic
               rule, not purely LLM-decided).
  ADD_FACT  -- like GUIDE, but marked with stronger evidence authority
               (HUMAN_CONFIRMED_FACT vs HUMAN_OBSERVATION).

Conversation text is NEVER a valid approval or execution path -- see
guard in main.py: approval is still only ever performed through
POST /plans/{plan_id}/approve with an exact plan_hash match.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.store.postgres_database import PostgresDatabase
from src.domain.commander.status_projector import StatusProjector


def _generate_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


VALID_GUIDANCE_TYPES = {
    "INVESTIGATION_DIRECTION", "HYPOTHESIS_FEEDBACK", "RECOVERY_CONSTRAINT",
    "EVIDENCE_REQUEST", "BUSINESS_CONTEXT", "MANUAL_EVIDENCE_REFERENCE",
}

# Deterministic classifier for whether guidance/a fact is materially
# state-changing enough to warrant flagging for reinvestigation (spec
# §4.13). Intentionally simple and keyword-based rather than another LLM
# call -- per the roadmap, "deterministic safety checks must make the
# final decision for plan invalidation", not the model itself.
_MATERIAL_KEYWORDS = (
    "not correct", "incorrect", "wrong", "actually", "instead",
    "already", "partial", "stale", "duplicate", "do not", "don't",
    "confirmed", "rule out", "ruled out", "contradicts", "unsafe",
)


def _is_materially_state_changing(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _MATERIAL_KEYWORDS)


class IncidentNotFoundError(Exception):
    pass


class CommanderConversation:
    def __init__(self, db: Optional[PostgresDatabase] = None):
        self.db = db or PostgresDatabase(
            os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@postgres:5432/nemoguard_db")
        )
        self.projector = StatusProjector(self.db)

    def _log_audit(self, incident_id: str, actor: str, event_type: str, summary: str) -> None:
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_event (audit_event_id, incident_id, actor_type, actor_id, event_type, event_summary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (_generate_id("AUD"), incident_id, "HUMAN", actor, event_type, summary, datetime.now(timezone.utc).isoformat()),
            )

    def _require_incident(self, incident_id: str, tenant_id: str) -> None:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM incident WHERE incident_id = %s AND tenant_id = %s", (incident_id, tenant_id),
            )
            if not cursor.fetchone():
                raise IncidentNotFoundError(incident_id)

    def _get_current_revision(self, incident_id: str) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT current_revision FROM incident_guidance_revision WHERE incident_id = %s", (incident_id,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def _increment_revision(self, incident_id: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO incident_guidance_revision (incident_id, current_revision, updated_at)
                VALUES (%s, 1, %s)
                ON CONFLICT (incident_id) DO UPDATE SET
                    current_revision = incident_guidance_revision.current_revision + 1,
                    updated_at = EXCLUDED.updated_at
                RETURNING current_revision
                """,
                (incident_id, now),
            )
            cursor = conn.execute(
                "SELECT current_revision FROM incident_guidance_revision WHERE incident_id = %s", (incident_id,),
            )
            return cursor.fetchone()[0]

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def get_messages(self, incident_id: str, tenant_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        self._require_incident(incident_id, tenant_id)
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT message_id, role, intent, content, created_by, created_at, evidence_refs_json, guidance_revision
                FROM incident_message WHERE incident_id = %s ORDER BY created_at ASC LIMIT %s
                """,
                (incident_id, limit),
            )
            cols = [c[0] for c in cursor.description]
            rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        for r in rows:
            if r.get("evidence_refs_json"):
                try:
                    r["evidence_refs"] = json.loads(r["evidence_refs_json"])
                except Exception:
                    r["evidence_refs"] = []
        return rows

    def _add_message(
        self, incident_id: str, role: str, content: str, *, intent: Optional[str] = None,
        created_by: Optional[str] = None, evidence_refs: Optional[List[str]] = None,
        guidance_id: Optional[str] = None, guidance_revision: Optional[int] = None,
    ) -> str:
        message_id = _generate_id("MSG")
        now = datetime.now(timezone.utc).isoformat()
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO incident_message (
                    message_id, incident_id, role, intent, content, created_by, created_at,
                    evidence_refs_json, guidance_id, guidance_revision
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    message_id, incident_id, role, intent, content, created_by, now,
                    json.dumps(evidence_refs or []), guidance_id, guidance_revision,
                ),
            )
        return message_id

    # ------------------------------------------------------------------
    # ASK -- read-only
    # ------------------------------------------------------------------

    def ask(self, incident_id: str, tenant_id: str, question: str, asked_by: str) -> Dict[str, Any]:
        """Read-only: answers using current incident state, never mutates
        anything. Uses a deterministic evidence-grounded summary rather
        than invoking a full LLM call for every question, keeping ASK fast
        and guaranteed side-effect-free -- see class docstring."""
        self._require_incident(incident_id, tenant_id)
        self._add_message(incident_id, "OPERATOR", question, intent="ASK", created_by=asked_by)

        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT status, actual_root_cause, rca_confidence FROM incident WHERE incident_id = %s",
                (incident_id,),
            )
            status, root_cause, confidence = cursor.fetchone() or (None, None, None)

            cursor = conn.execute(
                "SELECT statement, cause_type, confidence FROM hypothesis WHERE incident_id = %s ORDER BY confidence DESC LIMIT 3",
                (incident_id,),
            )
            hypotheses = [{"statement": r[0], "cause_type": r[1], "confidence": r[2]} for r in cursor.fetchall()]

            cursor = conn.execute(
                "SELECT action_plan_id, status, overall_risk FROM action_plan WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1",
                (incident_id,),
            )
            plan_row = cursor.fetchone()

        if hypotheses:
            top = hypotheses[0]
            answer = (
                f"Incident is currently {status}. Top hypothesis ({round((top['confidence'] or 0) * 100)}% "
                f"confidence, {top['cause_type']}): {top['statement']}."
            )
            if len(hypotheses) > 1:
                answer += f" {len(hypotheses) - 1} alternative hypothesis(es) were also considered."
        else:
            answer = f"Incident is currently {status}. No root-cause hypothesis has been formulated yet."

        if plan_row:
            plan_id, plan_status, plan_risk = plan_row
            answer += f" A {plan_risk}-risk recovery plan ({plan_id}) is currently {plan_status}."

        self._add_message(incident_id, "COMMANDER", answer, evidence_refs=[h["statement"] for h in hypotheses])

        return {
            "answer": answer,
            "incident_state": status,
            "hypotheses": hypotheses,
            "guidance_revision": self._get_current_revision(incident_id),
        }

    # ------------------------------------------------------------------
    # GUIDE / ADD_FACT -- state-changing, persisted, revision-tracked
    # ------------------------------------------------------------------

    def guide(
        self, incident_id: str, tenant_id: str, text: str, submitted_by: str, *,
        guidance_type: str = "INVESTIGATION_DIRECTION", is_fact: bool = False,
    ) -> Dict[str, Any]:
        """Persists operator guidance/fact as a first-class, auditable
        record and increments guidance_revision. Determines (via a
        deterministic keyword classifier, not an LLM) whether this looks
        materially state-changing enough to flag for reinvestigation --
        the actual decision to re-run the investigation graph is left to
        the caller (API layer), matching how live re-investigation is
        already triggered elsewhere in the codebase
        (IncidentOrchestrator._maybe_reinvestigate_on_new_evidence)."""
        self._require_incident(incident_id, tenant_id)
        if guidance_type not in VALID_GUIDANCE_TYPES:
            guidance_type = "INVESTIGATION_DIRECTION"

        new_revision = self._increment_revision(incident_id)
        guidance_id = _generate_id("GUID")
        now = datetime.now(timezone.utc).isoformat()
        authority = "HUMAN_CONFIRMED_FACT" if is_fact else "HUMAN_OBSERVATION"
        is_material = _is_materially_state_changing(text)

        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO commander_guidance (
                    guidance_id, incident_id, created_at, created_by, source_channel,
                    guidance_type, authority, text, guidance_revision, triggered_reinvestigation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    guidance_id, incident_id, now, submitted_by, "UI",
                    guidance_type, authority, text, new_revision, int(is_material),
                ),
            )

        self._add_message(
            incident_id, "OPERATOR", text,
            intent="ADD_FACT" if is_fact else "GUIDE",
            created_by=submitted_by, guidance_id=guidance_id, guidance_revision=new_revision,
        )

        event_type = "CONFIRMED_FACT_ADDED" if is_fact else "HUMAN_GUIDANCE_RECEIVED"
        self._log_audit(
            incident_id, submitted_by, event_type,
            f"Operator {'confirmed a fact' if is_fact else 'provided guidance'} (revision {new_revision}): {text}",
        )

        commander_ack = (
            "Noted -- I've recorded this as a confirmed fact and will weigh it accordingly."
            if is_fact else "Understood -- I've recorded this guidance."
        )
        if is_material:
            commander_ack += " This looks like it may materially affect the current investigation; flagging for review."
        self._add_message(incident_id, "COMMANDER", commander_ack)

        return {
            "guidance_id": guidance_id,
            "guidance_revision": new_revision,
            "is_material": is_material,
            "authority": authority,
            "commander_response": commander_ack,
        }
