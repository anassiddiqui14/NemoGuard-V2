-- WP-ORG-006: historical recurrence tracking.
--
-- When a new alert does NOT match any active incident (so a brand new
-- incident is created), we additionally search TERMINAL incidents for a
-- similar historical root cause. If found, we record a recurrence LINK --
-- we NEVER reopen/reuse the old incident itself (it stays terminal and
-- immutable), we just make the connection visible to operators so they
-- can see "this looks like it happened before, in INC-X, and here's what
-- worked/didn't work last time."

CREATE TABLE IF NOT EXISTS incident_recurrence (
    recurrence_id VARCHAR PRIMARY KEY,
    new_incident_id VARCHAR NOT NULL,
    prior_incident_id VARCHAR NOT NULL,
    similarity_score REAL NOT NULL,
    match_reasons_json VARCHAR NOT NULL DEFAULT '[]',
    detected_at VARCHAR NOT NULL,
    CONSTRAINT incident_recurrence_new_fk FOREIGN KEY (new_incident_id) REFERENCES incident(incident_id),
    CONSTRAINT incident_recurrence_prior_fk FOREIGN KEY (prior_incident_id) REFERENCES incident(incident_id)
);

CREATE INDEX IF NOT EXISTS idx_incident_recurrence_new ON incident_recurrence(new_incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_recurrence_prior ON incident_recurrence(prior_incident_id);
