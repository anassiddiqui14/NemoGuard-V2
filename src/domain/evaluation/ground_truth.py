"""
Structured scenario ground truth (WP-029-001).

Machine-readable expected outcomes for every scenario in
docs/validation/scenario_catalog_30.md, so the evaluation engine can
compute real, comparable metrics (RCA Top-1/3, correlation correctness,
blast radius recall, safe/unsafe action rate, verification accuracy)
instead of the previous pass/fail-only checks in
scripts/run_scenario_catalog_30.py.

This does NOT replace scripts/run_scenario_catalog_30.py's real trigger
mechanics (break_scenario.py etc.) -- ScoredScenario.trigger_endpoint/
trigger_scenario_name below map directly onto the same real simulator
lab endpoints (`/lab/trigger/{endpoint}`) already used by
scripts/run_ai_evaluation.py and the Scenario Lab UI. This module only
adds the STRUCTURED EXPECTED OUTCOME that was previously missing, so a
scenario run's real result can be scored, not just declared pass/fail.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScoredScenario:
    scenario_id: str
    category: str  # ingest | order_events | notification | pipeline | alarm | correlation
    description: str

    # How to trigger it for real, via the Scenario Lab simulator
    # (simulator_backend / localstack_lab's /lab/trigger/{endpoint}).
    trigger_endpoint: Optional[str] = None
    trigger_scenario_name: Optional[str] = None
    alarm_name: Optional[str] = None

    # --- RCA ground truth ---
    expected_cause_family: Optional[str] = None  # SCHEMA_REGRESSION|DATA_QUALITY|RESOURCE_EXHAUSTION|PARTIAL_WRITE|OTHER
    # Keyword-based matching against the real free-text hypothesis
    # statement/cause_type (RCA output has no fixed enum for statement
    # text), calibrated against real observed hypothesis rows for these
    # exact scenarios (see run_ai_evaluation.py's own comment on this
    # same tradeoff).
    root_cause_keywords: List[str] = field(default_factory=list)

    # --- Correlation / incident-count ground truth ---
    expected_incident_count: Optional[int] = None  # None = "don't check" (e.g. read-only diagnostics)
    expected_primary_resource: Optional[str] = None

    # --- Recovery ground truth ---
    expected_capabilities: List[str] = field(default_factory=list)
    prohibited_capabilities: List[str] = field(default_factory=list)

    # --- Terminal state / verification ground truth ---
    expected_terminal_state: Optional[str] = None  # RESOLVED|FAILED|MANUAL_ACTION_REQUIRED|NEEDS_REVIEW|None (don't check)
    requires_verification: bool = False

    # True if this scenario should NOT produce a normal incident/RCA path
    # at all (a pure read-only diagnostic call, a healthy baseline, or a
    # correlation-only assertion against alert counts) -- these are
    # excluded from RCA/recovery scoring but still counted in the suite.
    diagnostic_only: bool = False


# The 30-scenario catalog, mapped from docs/validation/scenario_catalog_30.md.
# Ground truth for cause_family/keywords is drawn from the same calibrated
# vocabulary already proven live in scripts/run_ai_evaluation.py's
# EVAL_SUITE for the 3 scenarios it covers; extended here to the full 30.
SCENARIO_CATALOG: List[ScoredScenario] = [
    # ---- Ingest Job ----
    ScoredScenario(
        scenario_id="INGEST-SCHEMA-DRIFT", category="ingest",
        description="Real KeyError('last_login_ip') from a genuine schema drift.",
        trigger_endpoint="ingest", trigger_scenario_name="schema_drift",
        alarm_name="nemoguard-ingest-job-errors",
        expected_cause_family="SCHEMA_REGRESSION",
        root_cause_keywords=["schema", "last_login_ip", "keyerror", "missing", "field"],
        expected_incident_count=1, expected_primary_resource="nemoguard-ingest-job",
        expected_capabilities=["compute.rerun_ingest_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="INGEST-OOM-CRASH", category="ingest",
        description="Real MemoryError from the ingest job.",
        trigger_endpoint="ingest", trigger_scenario_name="oom_crash",
        alarm_name="nemoguard-ingest-job-errors",
        expected_cause_family="RESOURCE_EXHAUSTION",
        root_cause_keywords=["memory", "oom", "out of memory", "resource"],
        expected_incident_count=1, expected_primary_resource="nemoguard-ingest-job",
        expected_capabilities=["compute.rerun_ingest_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="INGEST-DB-OUTAGE", category="ingest",
        description="Real psycopg2.OperationalError (unreachable host).",
        trigger_endpoint="ingest", trigger_scenario_name="db_outage",
        alarm_name="nemoguard-ingest-job-errors",
        expected_cause_family="OTHER",
        root_cause_keywords=["database", "connection", "unreachable", "outage", "operationalerror"],
        expected_incident_count=1, expected_primary_resource="nemoguard-ingest-job",
        expected_capabilities=["compute.rerun_ingest_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="INGEST-MISSING-INPUT-FILE", category="ingest",
        description="Real NoSuchKey error.",
        trigger_endpoint="ingest", trigger_scenario_name="missing_input_file",
        alarm_name="nemoguard-ingest-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["missing", "file", "nosuchkey", "not found", "s3"],
        expected_incident_count=1, expected_primary_resource="nemoguard-ingest-job",
        prohibited_capabilities=["compute.rerun_ingest_job"],  # rerunning without re-upload cannot succeed
        expected_terminal_state="MANUAL_ACTION_REQUIRED", requires_verification=False,
    ),
    ScoredScenario(
        scenario_id="INGEST-MALFORMED-JSON", category="ingest",
        description="Real json.JSONDecodeError.",
        trigger_endpoint="ingest", trigger_scenario_name="malformed_json",
        alarm_name="nemoguard-ingest-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["malformed", "json", "decode", "invalid", "parse"],
        expected_incident_count=1, expected_primary_resource="nemoguard-ingest-job",
        prohibited_capabilities=["compute.rerun_ingest_job"],
        expected_terminal_state="MANUAL_ACTION_REQUIRED", requires_verification=False,
    ),
    ScoredScenario(
        scenario_id="INGEST-HEALTHY-BASELINE", category="ingest",
        description="Sanity check -- no failure.",
        trigger_endpoint="ingest", trigger_scenario_name="healthy",
        diagnostic_only=True, expected_incident_count=0,
    ),

    # ---- Order Events Job ----
    ScoredScenario(
        scenario_id="ORDER-PARTIAL-WRITE-SMALL", category="order_events",
        description="Genuine mid-batch abort, 5/10 rows committed.",
        trigger_endpoint="order_events", trigger_scenario_name="partial_write_crash",
        alarm_name="nemoguard-order-events-job-errors",
        expected_cause_family="PARTIAL_WRITE",
        root_cause_keywords=["partial", "crash", "row", "write"],
        expected_incident_count=1, expected_primary_resource="nemoguard-order-events-job",
        expected_capabilities=["data.check_table_staleness", "data.cleanup_partial_write", "data.idempotent_rerun_order_events_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="ORDER-PARTIAL-WRITE-EARLY", category="order_events",
        description="Mid-batch abort, 1/N rows committed.",
        trigger_endpoint="order_events", trigger_scenario_name="partial_write_crash",
        alarm_name="nemoguard-order-events-job-errors",
        expected_cause_family="PARTIAL_WRITE",
        root_cause_keywords=["partial", "crash", "row", "write"],
        expected_incident_count=1, expected_primary_resource="nemoguard-order-events-job",
        expected_capabilities=["data.check_table_staleness", "data.cleanup_partial_write", "data.idempotent_rerun_order_events_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="ORDER-PARTIAL-WRITE-LATE", category="order_events",
        description="Mid-batch abort, 9/N rows committed.",
        trigger_endpoint="order_events", trigger_scenario_name="partial_write_crash",
        alarm_name="nemoguard-order-events-job-errors",
        expected_cause_family="PARTIAL_WRITE",
        root_cause_keywords=["partial", "crash", "row", "write"],
        expected_incident_count=1, expected_primary_resource="nemoguard-order-events-job",
        expected_capabilities=["data.check_table_staleness", "data.cleanup_partial_write", "data.idempotent_rerun_order_events_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="ORDER-DUPLICATE-WRITE", category="order_events",
        description="Real psycopg2.errors.UniqueViolation on order_id.",
        trigger_endpoint="order_events", trigger_scenario_name="duplicate_write",
        alarm_name="nemoguard-order-events-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["duplicate", "unique", "violation", "order_id"],
        expected_incident_count=1, expected_primary_resource="nemoguard-order-events-job",
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="ORDER-HEALTHY-BASELINE", category="order_events",
        description="Sanity check -- no failure.",
        trigger_endpoint="order_events", trigger_scenario_name="healthy",
        diagnostic_only=True, expected_incident_count=0,
    ),
    ScoredScenario(
        scenario_id="ORDER-STALENESS-CHECK-ONLY", category="order_events",
        description="Direct read-only staleness diagnostic.",
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="ORDER-VERIFY-ROW-COUNT-MISMATCH", category="order_events",
        description="Direct read-only row-count verification diagnostic.",
        diagnostic_only=True,
    ),

    # ---- Notification Job ----
    ScoredScenario(
        scenario_id="NOTIF-POISON-PILL-FIRST", category="notification",
        description="Real KeyError('user_id') on first delivery.",
        trigger_endpoint="notification", trigger_scenario_name="poison_pill",
        alarm_name="nemoguard-notification-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["poison", "user_id", "missing", "malformed", "data quality", "data_quality"],
        expected_incident_count=1, expected_primary_resource="nemoguard-notification-job",
        expected_capabilities=["queue.quarantine_poison_message"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="NOTIF-POISON-PILL-REDELIVERY", category="notification",
        description="Same poison message redelivered; real queue backlog.",
        trigger_endpoint="notification", trigger_scenario_name="poison_pill",
        alarm_name="nemoguard-notification-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["poison", "user_id", "missing", "redelivery", "backlog"],
        expected_incident_count=1, expected_primary_resource="nemoguard-notification-job",
        expected_capabilities=["queue.quarantine_poison_message"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="NOTIF-QUEUE-BACKUP-MULTI", category="notification",
        description="Repeated poison_pill runs; real accumulating backlog.",
        trigger_endpoint="notification", trigger_scenario_name="poison_pill",
        alarm_name="nemoguard-notification-job-errors",
        expected_cause_family="DATA_QUALITY",
        root_cause_keywords=["poison", "backlog", "queue", "user_id"],
        expected_incident_count=1, expected_primary_resource="nemoguard-notification-job",
        expected_capabilities=["queue.quarantine_poison_message"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="NOTIF-HEALTHY-BASELINE", category="notification",
        description="Sanity check -- no failure.",
        trigger_endpoint="notification", trigger_scenario_name="healthy",
        diagnostic_only=True, expected_incident_count=0,
    ),
    ScoredScenario(
        scenario_id="NOTIF-QUEUE-INSPECT-ONLY", category="notification",
        description="Direct read-only SQS peek diagnostic.",
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="NOTIF-QUARANTINE-DRY-RUN", category="notification",
        description="quarantine_poison_message with dry_run=True.",
        diagnostic_only=True,
        prohibited_capabilities=[],  # dry-run itself is expected/allowed; nothing prohibited
    ),

    # ---- Pipeline / Step Functions ----
    ScoredScenario(
        scenario_id="PIPELINE-INGEST-STEP-FAILS", category="pipeline",
        description="Real KeyError inside the orchestrated ingest step.",
        trigger_endpoint="pipeline", trigger_scenario_name="ingest_step_fails",
        expected_cause_family="SCHEMA_REGRESSION",
        root_cause_keywords=["schema", "keyerror", "missing", "field", "ingest"],
        expected_incident_count=1, expected_primary_resource="nemoguard-daily-pipeline",
        expected_capabilities=["compute.rerun_ingest_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="PIPELINE-ORDER-EVENTS-STEP-FAILS", category="pipeline",
        description="Real mid-batch crash inside the orchestrated order_events step.",
        trigger_endpoint="pipeline", trigger_scenario_name="order_events_step_fails",
        expected_cause_family="PARTIAL_WRITE",
        root_cause_keywords=["partial", "crash", "row", "write"],
        expected_incident_count=1, expected_primary_resource="nemoguard-daily-pipeline",
        expected_capabilities=["data.cleanup_partial_write", "data.idempotent_rerun_order_events_job"],
        expected_terminal_state="RESOLVED", requires_verification=True,
    ),
    ScoredScenario(
        scenario_id="PIPELINE-HEALTHY-BASELINE", category="pipeline",
        description="Both steps succeed; full pipeline execution.",
        trigger_endpoint="pipeline", trigger_scenario_name="healthy",
        diagnostic_only=True, expected_incident_count=0,
    ),
    ScoredScenario(
        scenario_id="PIPELINE-EXECUTION-INSPECT", category="pipeline",
        description="Direct read-only Step Functions execution inspection.",
        diagnostic_only=True,
    ),

    # ---- Alarm / Observability Lifecycle ----
    ScoredScenario(
        scenario_id="ALARM-TRIP-ON-FIRST-ERROR", category="alarm",
        description="Real CloudWatch alarm OK -> ALARM transition, real SNS notification.",
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="ALARM-NO-RENOTIFY-ON-REPEAT", category="alarm",
        description="Same alarm-sharing scenario run twice without a reset; genuinely no 2nd SNS notification.",
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="ALARM-ACKNOWLEDGE-AFTER-FIX", category="alarm",
        description="Real set_alarm_state forcing ALARM -> OK with an audit reason after successful remediation.",
        diagnostic_only=True,
        expected_capabilities=["ops.acknowledge_and_reset_alarm"],
    ),
    ScoredScenario(
        scenario_id="ALARM-STATE-INSPECT-ONLY", category="alarm",
        description="Direct read-only alarm-state diagnostic.",
        diagnostic_only=True,
    ),

    # ---- Cross-cutting Alert Correlation ----
    ScoredScenario(
        scenario_id="CORRELATION-SAME-ALARM-NEW-INCIDENT", category="correlation",
        description="schema_drift then (after alarm reset) oom_crash on the SAME alarm -- correlator must attach the 2nd alert to the SAME open incident.",
        expected_incident_count=1,
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="CORRELATION-DIFFERENT-ALARM-NEW-INCIDENT", category="correlation",
        description="schema_drift (ingest alarm) then partial_write_crash (order_events alarm) -- correlator must create a SEPARATE incident.",
        expected_incident_count=2,
        diagnostic_only=True,
    ),
    ScoredScenario(
        scenario_id="CORRELATION-ALERT-COUNT-GROWTH", category="correlation",
        description="Two same-alarm scenarios in sequence -- incident_alert count must genuinely grow.",
        diagnostic_only=True,
    ),
]


def get_scenario(scenario_id: str) -> ScoredScenario:
    for s in SCENARIO_CATALOG:
        if s.scenario_id == scenario_id:
            return s
    raise KeyError(f"Unknown scenario_id: {scenario_id}")


def list_scenario_ids() -> List[str]:
    return [s.scenario_id for s in SCENARIO_CATALOG]


def scoreable_scenarios() -> List[ScoredScenario]:
    """Scenarios that actually go through RCA/recovery/verification and
    are therefore meaningful for RCA/recovery/verification-accuracy
    scoring -- excludes pure diagnostics, healthy baselines, and
    correlation-only assertions."""
    return [s for s in SCENARIO_CATALOG if not s.diagnostic_only]
