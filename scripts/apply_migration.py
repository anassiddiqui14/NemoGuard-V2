import sqlite3
import os

db_path = 'data/generated/pipeline.db'
migration_path = 'migrations/002_domain_model.sql'

if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

with open(migration_path, 'r') as f:
    sql = f.read()

with sqlite3.connect(db_path) as conn:
    conn.executescript(sql)
    conn.commit()

print("Migration 002_domain_model.sql applied successfully.")
