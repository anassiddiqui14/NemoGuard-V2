import os
import psycopg2

DATABASE_URL = os.environ.get("POSTGRES_URL", "postgresql://nemoguard:nemoguard_password@localhost:5432/nemoguard_db")

with psycopg2.connect(DATABASE_URL) as conn:
    with conn.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE incident CASCADE;")
        cursor.execute("TRUNCATE TABLE alert CASCADE;")
    conn.commit()
print("Cleared incidents and alerts")
