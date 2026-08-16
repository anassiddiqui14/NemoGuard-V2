-- LocalStack lab: target table for the "Glue job writing to a database
-- table" test scenario. A genuine, unmocked partial-write failure mode is
-- possible here: order_events is written to in row-by-row batches (not a
-- single atomic transaction, matching how many real Glue/Spark JDBC sinks
-- behave), so a mid-batch crash leaves some rows committed for a run_id and
-- others missing -- exactly the "stale/partial data" scenario the agent
-- needs to detect and clean up before it's safe to rerun.

CREATE TABLE IF NOT EXISTS order_events (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    amount NUMERIC,
    written_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_order_events_run_id ON order_events(run_id);

-- Tracks the *expected* row count per run so a "staleness/completeness"
-- check has a real, independently-recorded number to compare against
-- (mirrors how a real Glue job would log its expected batch size to
-- CloudWatch before writing, separate from the write itself).
CREATE TABLE IF NOT EXISTS order_events_run_manifest (
    run_id VARCHAR PRIMARY KEY,
    expected_row_count INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
