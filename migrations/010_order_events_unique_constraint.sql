-- Adds a real UNIQUE constraint on order_events(order_id) so a genuine
-- duplicate-key failure mode is possible for the order_events lab job --
-- distinct from the existing partial_write_crash (mid-batch crash leaving
-- SOME rows missing) scenario. This models a real "job was rerun without
-- deduplication" failure: attempting to write an order_id that was already
-- successfully committed by an earlier run raises a genuine
-- psycopg2.errors.UniqueViolation, exactly what a real production
-- Glue/Spark JDBC sink hits when a retry mechanism doesn't first check
-- what already landed.
--
-- Uses a partial/best-effort backfill-safe approach: if any pre-existing
-- demo/seed data already has duplicate order_ids, this ADD CONSTRAINT would
-- fail outright on a live database, so we deduplicate defensively first
-- (keeping the earliest-written row per order_id) before adding the
-- constraint. This is a one-time, idempotent cleanup — safe to re-run.

DELETE FROM order_events a
USING order_events b
WHERE a.order_id = b.order_id
  AND a.id > b.id;

ALTER TABLE order_events
    ADD CONSTRAINT order_events_order_id_unique UNIQUE (order_id);
