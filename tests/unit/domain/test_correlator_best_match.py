"""
Unit tests for CorrelatorEngine.best_match_for_alert -- the deterministic
first-pass correlation check that WP-003 makes primary over the Watcher
Agent LLM's own correlation guess.
"""

from datetime import datetime, timezone, timedelta

import pytest

from src.domain.correlator import CorrelatorEngine
from src.domain.models import Alert


def make_alert(alert_id, run_id=None, opened_ts=None, severity="high", alert_type="JOB_FAILURE", source_system="Airflow", message="failure"):
    return Alert(
        alert_id=alert_id,
        run_id=run_id,
        opened_ts=opened_ts or datetime.now(timezone.utc),
        severity=severity,
        alert_type=alert_type,
        source_system=source_system,
        message=message,
        status="open",
    )


class TestBestMatchForAlert:
    def test_no_candidates_returns_none(self):
        engine = CorrelatorEngine()
        new_alert = make_alert("A1")
        incident_id, score, reasons = engine.best_match_for_alert(new_alert, {})
        assert incident_id is None
        assert score == 0.0
        assert reasons == []

    def test_same_run_id_is_strong_match(self):
        engine = CorrelatorEngine()
        now = datetime.now(timezone.utc)
        existing = make_alert("A0", run_id="RUN-123", opened_ts=now)
        new_alert = make_alert("A1", run_id="RUN-123", opened_ts=now)

        incident_id, score, reasons = engine.best_match_for_alert(
            new_alert, {"INC-1": [existing]}
        )
        assert incident_id == "INC-1"
        assert score >= engine.min_cluster_score
        assert any("run_id" in r for r in reasons)

    def test_different_run_id_and_far_apart_time_no_match(self):
        engine = CorrelatorEngine()
        now = datetime.now(timezone.utc)
        existing = make_alert("A0", run_id="RUN-A", opened_ts=now - timedelta(hours=5), alert_type="SCHEMA_DRIFT")
        new_alert = make_alert("A1", run_id="RUN-B", opened_ts=now, alert_type="JOB_FAILURE")

        incident_id, score, reasons = engine.best_match_for_alert(
            new_alert, {"INC-1": [existing]}
        )
        assert incident_id is None or score < engine.min_cluster_score

    def test_picks_the_best_scoring_incident_among_multiple(self):
        engine = CorrelatorEngine()
        now = datetime.now(timezone.utc)
        weak_match = make_alert("A0", run_id="RUN-OTHER", opened_ts=now - timedelta(hours=2), alert_type="OTHER_TYPE")
        strong_match = make_alert("A2", run_id="RUN-STRONG", opened_ts=now, alert_type="JOB_FAILURE")
        new_alert = make_alert("A1", run_id="RUN-STRONG", opened_ts=now, alert_type="JOB_FAILURE")

        incident_id, score, reasons = engine.best_match_for_alert(
            new_alert, {"INC-WEAK": [weak_match], "INC-STRONG": [strong_match]}
        )
        assert incident_id == "INC-STRONG"
        assert score >= engine.min_cluster_score

    def test_matching_alert_type_and_time_proximity_without_run_id(self):
        engine = CorrelatorEngine()
        now = datetime.now(timezone.utc)
        existing = make_alert("A0", run_id=None, opened_ts=now, alert_type="SCHEMA_DRIFT")
        new_alert = make_alert("A1", run_id=None, opened_ts=now + timedelta(seconds=30), alert_type="SCHEMA_DRIFT")

        incident_id, score, reasons = engine.best_match_for_alert(
            new_alert, {"INC-1": [existing]}
        )
        # Same alert_type (0.2) + within 60s (0.3) = 0.5, below default
        # min_cluster_score (0.6) -- correctly NOT a confident deterministic
        # match on its own, demonstrating the engine doesn't over-claim.
        assert score == pytest.approx(0.5, abs=0.01)
        assert incident_id == "INC-1"  # still the best (only) candidate, just below the confidence bar
