-- Deterministic business-impact engine (WP-010).
--
-- `incident_impact` previously retained only an opaque score, often supplied
-- by an LLM or a fixed fallback. These additive fields retain the
-- deterministic, explainable calculation and its SLA interpretation.

ALTER TABLE incident_impact
    ADD COLUMN IF NOT EXISTS business_risk VARCHAR;

ALTER TABLE incident_impact
    ADD COLUMN IF NOT EXISTS minutes_to_breach INTEGER;

ALTER TABLE incident_impact
    ADD COLUMN IF NOT EXISTS sla_status VARCHAR;

ALTER TABLE incident_impact
    ADD COLUMN IF NOT EXISTS score_components_json VARCHAR;

CREATE INDEX IF NOT EXISTS idx_incident_impact_sla_status
    ON incident_impact(incident_id, sla_status);
