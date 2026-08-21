"""
Unit tests locking in the Severity enum's canonical string convention and
guarding against the exact silent bug documented in
docs/CURRENT_ARCHITECTURE_DESIGN_DOC.md and
docs/NemoGuard_Enterprise_Hardening_and_Productization_Build_Plan.md
Priority 21.1: the `Severity` enum stores underscore-separated values
(SEV_1, SEV_2, ...), and multiple places in the codebase used to (and one
place -- src/api/main.py::get_overview -- was silently) query/compare
against the HYPHENATED display form ("SEV-1") instead, which never matches
any stored row.

These tests exist so that any future regression of that mismatch fails a
test immediately rather than silently zeroing out dashboard KPIs again.
"""

from src.domain.enums import Severity
from src.domain.correlator import CorrelatorEngine


class TestSeverityEnumCanonicalForm:
    def test_severity_values_use_underscore_convention(self):
        assert Severity.SEV_1.value == "SEV_1"
        assert Severity.SEV_2.value == "SEV_2"
        assert Severity.SEV_3.value == "SEV_3"
        assert Severity.SEV_4.value == "SEV_4"

    def test_no_severity_value_contains_a_hyphen(self):
        # Guards against ever silently reintroducing the SEV-1 (hyphen) form
        # as the STORED value -- hyphenation belongs only in display/UI code.
        for sev in Severity:
            assert "-" not in sev.value, (
                f"{sev.name} value {sev.value!r} contains a hyphen; "
                f"canonical stored form must use underscores."
            )


class TestCorrelatorSeverityMapping:
    """
    CorrelatorEngine.create_incident() is the code path that actually writes
    an incident's `severity` column (via severity_map inside correlator.py).
    Confirm it maps webhook/alert severity strings ("critical"/"high"/etc.)
    to the canonical underscore Severity enum members, not the hyphenated
    display form.
    """

    def _incident_severity_for(self, alert_severity: str):
        from datetime import datetime, timezone
        from src.domain.models import Alert

        alert = Alert(
            alert_id="TEST-ALERT-1",
            run_id="RUN-1",
            opened_ts=datetime.now(timezone.utc),
            severity=alert_severity,
            alert_type="TEST_TYPE",
            source_system="test",
            message="test message",
            status="open",
        )
        engine = CorrelatorEngine()
        cluster = {"primary_alert": alert, "alerts": [alert], "duplicate_count": 0, "cluster_score": 1.0}
        incident = engine.create_incident(cluster)
        return incident.severity

    def test_critical_alert_maps_to_sev_1(self):
        assert self._incident_severity_for("critical") == Severity.SEV_1
        assert self._incident_severity_for("critical").value == "SEV_1"

    def test_high_alert_maps_to_sev_2(self):
        assert self._incident_severity_for("high") == Severity.SEV_2

    def test_unknown_severity_defaults_to_sev_3(self):
        assert self._incident_severity_for("totally_unknown_severity") == Severity.SEV_3
