from datetime import datetime, timezone

from src.domain.impact_engine import assess_business_impact


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def test_critical_production_blocked_asset_has_differentiated_high_risk_and_healthy_sla():
    assessment = assess_business_impact(
        incident_severity="CRITICAL",
        incident_environment="production",
        impact_status="BLOCKED",
        detected_at="2026-08-21T11:00:00+00:00",
        asset_metadata={
            "criticality": "CRITICAL",
            "freshness_sla_minutes": 120,
            "estimated_user_count": 12_000,
            "impact_band": "CRITICAL",
        },
        now=NOW,
    )

    assert assessment.impact_score == 1.0
    assert assessment.business_risk == "CRITICAL"
    assert assessment.sla_status == "HEALTHY"
    assert assessment.minutes_to_breach == 60
    assert assessment.expected_breach_at == "2026-08-21T13:00:00+00:00"
    assert assessment.score_components == {
        "incident_severity": 0.25,
        "environment": 0.10,
        "asset_criticality": 0.35,
        "impact_status": 0.20,
        "consumer_count": 0.15,
        "impact_band": 0.10,
    }


def test_near_breach_low_metadata_incident_is_at_risk_with_explainable_score():
    assessment = assess_business_impact(
        incident_severity="MEDIUM",
        incident_environment="staging",
        impact_status="AT_RISK",
        detected_at="2026-08-21T11:45:00+00:00",
        asset_metadata={
            "criticality": "LOW",
            "freshness_sla_minutes": 30,
            "estimated_user_count": 50,
            "impact_band": "LOW",
        },
        now=NOW,
    )

    assert assessment.impact_score == 0.32
    assert assessment.business_risk == "MEDIUM"
    assert assessment.sla_status == "AT_RISK"
    assert assessment.minutes_to_breach == 15
    assert assessment.expected_breach_at == "2026-08-21T12:15:00+00:00"


def test_missing_sla_metadata_never_fabricates_a_breach_deadline():
    assessment = assess_business_impact(
        incident_severity="LOW",
        incident_environment="development",
        impact_status="DEGRADED",
        detected_at="2026-08-21T11:00:00+00:00",
        asset_metadata={"criticality": "LOW"},
        now=NOW,
    )

    assert assessment.impact_score == 0.18
    assert assessment.business_risk == "LOW"
    assert assessment.sla_status == "UNKNOWN"
    assert assessment.minutes_to_breach is None
    assert assessment.expected_breach_at is None


def test_elapsed_sla_is_marked_breached():
    assessment = assess_business_impact(
        incident_severity="HIGH",
        incident_environment="prod",
        impact_status="FAILED",
        detected_at="2026-08-21T11:00:00+00:00",
        asset_metadata={"freshness_sla_minutes": 30},
        now=NOW,
    )

    assert assessment.sla_status == "BREACHED"
    assert assessment.minutes_to_breach == 0
    assert assessment.expected_breach_at == "2026-08-21T11:30:00+00:00"
