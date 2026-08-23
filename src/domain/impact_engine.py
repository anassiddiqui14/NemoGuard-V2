"""Deterministic business-impact and SLA risk calculation.

This module deliberately contains no LLM calls and no database access.  It
turns already persisted incident, asset, and observed impact facts into an
explainable score that can be stored alongside the incident-impact record.

The score is normalized to ``0.00..1.00``.  Missing business metadata never
creates a synthetic SLA deadline: callers receive ``sla_status="UNKNOWN"``
until a freshness SLA is configured for the affected asset.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional


_CRITICALITY_WEIGHTS = {
    "CRITICAL": 0.35,
    "HIGH": 0.25,
    "MEDIUM": 0.15,
    "LOW": 0.05,
}

_SEVERITY_WEIGHTS = {
    # Both descriptive values and the persisted Severity enum values are
    # accepted. The webhook correlator stores SEV_1..SEV_4 in incident rows.
    "CRITICAL": 0.25,
    "SEV_1": 0.25,
    "HIGH": 0.18,
    "SEV_2": 0.18,
    "MEDIUM": 0.10,
    "SEV_3": 0.10,
    "LOW": 0.05,
    "SEV_4": 0.05,
}

_ENVIRONMENT_WEIGHTS = {
    "PRODUCTION": 0.10,
    "PROD": 0.10,
    "STAGING": 0.04,
    "STAGE": 0.04,
    "DEVELOPMENT": 0.00,
    "DEV": 0.00,
}

_IMPACT_STATUS_WEIGHTS = {
    "BLOCKED": 0.20,
    "FAILED": 0.20,
    "AT_RISK": 0.12,
    "DEGRADED": 0.08,
    "IMPACTED": 0.08,
}

_IMPACT_BAND_WEIGHTS = {
    "CRITICAL": 0.10,
    "HIGH": 0.07,
    "MEDIUM": 0.04,
    "LOW": 0.01,
}


@dataclass(frozen=True)
class ImpactAssessment:
    """The persisted, explainable result for one affected asset."""

    impact_score: float
    business_risk: str
    expected_breach_at: Optional[str]
    minutes_to_breach: Optional[int]
    sla_status: str
    score_components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise(value: object) -> str:
    return str(value or "").strip().upper().replace("-", "_").replace(" ", "_")


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _consumer_weight(estimated_user_count: object) -> float:
    try:
        users = max(0, int(estimated_user_count or 0))
    except (TypeError, ValueError):
        return 0.0

    if users >= 10_000:
        return 0.15
    if users >= 1_000:
        return 0.10
    if users >= 100:
        return 0.05
    return 0.0


def _risk_label(score: float) -> str:
    if score >= 0.75:
        return "CRITICAL"
    if score >= 0.50:
        return "HIGH"
    if score >= 0.25:
        return "MEDIUM"
    return "LOW"


def _sla_assessment(
    *,
    detected_at: datetime,
    freshness_sla_minutes: object,
    now: datetime,
) -> tuple[Optional[str], Optional[int], str]:
    try:
        sla_minutes = int(freshness_sla_minutes)
    except (TypeError, ValueError):
        sla_minutes = 0

    if sla_minutes <= 0:
        return None, None, "UNKNOWN"

    expected_breach_at = detected_at + timedelta(minutes=sla_minutes)
    seconds_to_breach = (expected_breach_at - now).total_seconds()
    minutes_to_breach = max(0, int(seconds_to_breach // 60))

    if seconds_to_breach <= 0:
        sla_status = "BREACHED"
    elif seconds_to_breach <= 15 * 60:
        sla_status = "AT_RISK"
    else:
        sla_status = "HEALTHY"

    return expected_breach_at.isoformat(), minutes_to_breach, sla_status


def assess_business_impact(
    *,
    incident_severity: object,
    incident_environment: object,
    impact_status: object,
    detected_at: datetime | str,
    asset_metadata: Optional[Mapping[str, Any]] = None,
    now: Optional[datetime] = None,
) -> ImpactAssessment:
    """Calculate deterministic risk and SLA state for one impacted asset.

    ``asset_metadata`` may provide ``criticality``, ``freshness_sla_minutes``,
    ``estimated_user_count``, and ``impact_band`` from ``data_asset``. Unknown
    metadata contributes zero weight and produces ``UNKNOWN`` SLA state.
    """

    metadata = asset_metadata or {}
    observed_at = _coerce_datetime(now or datetime.now(timezone.utc))
    detected = _coerce_datetime(detected_at)

    components = {
        "incident_severity": _SEVERITY_WEIGHTS.get(_normalise(incident_severity), 0.0),
        "environment": _ENVIRONMENT_WEIGHTS.get(_normalise(incident_environment), 0.0),
        "asset_criticality": _CRITICALITY_WEIGHTS.get(
            _normalise(metadata.get("criticality")), 0.0
        ),
        "impact_status": _IMPACT_STATUS_WEIGHTS.get(_normalise(impact_status), 0.0),
        "consumer_count": _consumer_weight(metadata.get("estimated_user_count")),
        "impact_band": _IMPACT_BAND_WEIGHTS.get(_normalise(metadata.get("impact_band")), 0.0),
    }
    score = round(min(1.0, sum(components.values())), 2)

    expected_breach_at, minutes_to_breach, sla_status = _sla_assessment(
        detected_at=detected,
        freshness_sla_minutes=metadata.get("freshness_sla_minutes"),
        now=observed_at,
    )

    return ImpactAssessment(
        impact_score=score,
        business_risk=_risk_label(score),
        expected_breach_at=expected_breach_at,
        minutes_to_breach=minutes_to_breach,
        sla_status=sla_status,
        score_components=components,
    )
