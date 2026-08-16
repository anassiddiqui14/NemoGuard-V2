"""
Backfill script to fix incident titles that were truncated at creation time.

Prior to the fix in src/domain/correlator.py, incident titles were always
generated as f"Incident: {primary.message[:50]}..." — appending "..." even
when the underlying alert message was shorter than 50 characters. This
script re-derives the correct title for each existing incident using the
same primary-alert-selection logic as CorrelatorEngine.create_incident()
(earliest alert by opened_ts) and the same (now-fixed) truncation rules.
"""
import os
import psycopg2
import psycopg2.extras

TITLE_MSG_LIMIT = 120

POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db",
)


def build_title(message: str) -> str:
    msg = message or ""
    title_msg = msg[:TITLE_MSG_LIMIT] + "..." if len(msg) > TITLE_MSG_LIMIT else msg
    return f"Incident: {title_msg}"


def main():
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT incident_id, title FROM incident")
            incidents = cur.fetchall()

            updated = 0
            for inc in incidents:
                incident_id = inc["incident_id"]
                cur.execute(
                    """
                    SELECT a.message
                    FROM incident_alert ia
                    JOIN alert a ON a.alert_id = ia.alert_id
                    WHERE ia.incident_id = %s
                    ORDER BY a.opened_ts ASC
                    LIMIT 1
                    """,
                    (incident_id,),
                )
                row = cur.fetchone()
                if not row:
                    print(f"[skip] {incident_id}: no linked alerts found")
                    continue

                new_title = build_title(row["message"])
                if new_title != inc["title"]:
                    cur.execute(
                        "UPDATE incident SET title = %s, updated_at = updated_at WHERE incident_id = %s",
                        (new_title, incident_id),
                    )
                    updated += 1
                    print(f"[update] {incident_id}: {inc['title']!r} -> {new_title!r}")
                else:
                    print(f"[ok] {incident_id}: title already correct")

        conn.commit()
        print(f"\nDone. Updated {updated} incident title(s).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
