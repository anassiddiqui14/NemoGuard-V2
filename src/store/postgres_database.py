import psycopg2
import psycopg2.extras
import json
import csv
import os
from contextlib import contextmanager

class ConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
    def execute(self, query, vars=None):
        cur = self.conn.cursor()
        cur.execute(query, vars)
        return cur
    def cursor(self, *args, **kwargs):
        return self.conn.cursor(*args, **kwargs)
    def commit(self):
        self.conn.commit()
    def rollback(self):
        self.conn.rollback()
    def close(self):
        self.conn.close()

class PostgresDatabase:
    def __init__(self, db_path: str):
        # db_path is treated as the connection string (DATABASE_URL)
        self.db_path = db_path
            
    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(self.db_path)
        try:
            yield ConnectionWrapper(conn)
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_schema(self):
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        migration_path = os.path.join(os.path.dirname(__file__), '../../migrations/002_domain_model.sql')
        with open(migration_path, 'r') as f:
            migration_sql = f.read()

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                cur.execute(migration_sql)

        self.apply_pending_migrations()

    def apply_pending_migrations(self):
        """
        Applies every migrations/NNN_*.sql file (in numeric order) that isn't
        002_domain_model.sql (already applied above as part of init_schema).
        Each file uses `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT
        EXISTS` style guards, so re-running this on every startup is safe and
        idempotent -- this is how 007_platform_users.sql (real credentialed
        accounts) gets applied to existing deployments without a manual step.
        """
        migrations_dir = os.path.join(os.path.dirname(__file__), '../../migrations')
        if not os.path.isdir(migrations_dir):
            return
        filenames = sorted(f for f in os.listdir(migrations_dir) if f.endswith('.sql') and f != '002_domain_model.sql')
        for filename in filenames:
            path = os.path.join(migrations_dir, filename)
            with open(path, 'r') as f:
                sql = f.read()
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql)
            except Exception as e:
                print(f"Migration {filename} failed (may already be applied): {e}")

    def load_seed_data(self, data_dir: str):
        def load_csv(filename, table):
            path = os.path.join(data_dir, filename)
            if not os.path.exists(path):
                return
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = list(reader)
                if not rows:
                    return
                placeholders = ','.join(['%s'] * len(headers))
                query = f"INSERT INTO {table} ({','.join(headers)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        psycopg2.extras.execute_batch(cur, query, rows)
                    
        load_csv('jobs.csv', 'job')
        load_csv('dependencies.csv', 'dependency')
        load_csv('business_assets.csv', 'business_asset')
        load_csv('asset_dependencies.csv', 'asset_dependency')

    def insert_executions(self, executions: list):
        if not executions:
            return
        query = """
            INSERT INTO execution (
                run_id, job_id, scheduled_ts, start_ts, end_ts, status, attempt, 
                records_in, records_out, schema_version, incident_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = []
        for e in executions:
            if hasattr(e, 'run_id'):
                rows.append((
                    e.run_id, e.job_id, e.scheduled_ts, e.start_ts,
                    e.end_ts, e.status, getattr(e, 'attempt', 1),
                    e.records_in, e.records_out, e.schema_version,
                    getattr(e, 'incident_id', None)
                ))
            else:
                rows.append((
                    e.get('run_id'), e.get('job_id'), e.get('scheduled_ts'), e.get('start_ts'),
                    e.get('end_ts'), e.get('status'), e.get('attempt', 1),
                    e.get('records_in'), e.get('records_out'), e.get('schema_version'),
                    e.get('incident_id')
                ))
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, rows)

    def insert_logs(self, logs: list):
        if not logs:
            return
        query = """
            INSERT INTO log_event (
                log_id, run_id, timestamp, level, component, error_code, message, attributes_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = []
        for l in logs:
            if hasattr(l, 'log_id'):
                attrs = getattr(l, 'attributes', None)
                attrs_json = json.dumps(attrs) if attrs is not None else None
                rows.append((
                    l.log_id, l.run_id, l.timestamp, l.level,
                    l.component, l.error_code, l.message, attrs_json
                ))
            else:
                attrs = l.get('attributes')
                attrs_json = json.dumps(attrs) if attrs is not None else None
                rows.append((
                    l.get('log_id'), l.get('run_id'), l.get('timestamp'), l.get('level'),
                    l.get('component'), l.get('error_code'), l.get('message'), attrs_json
                ))
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, rows)

    def insert_alerts(self, alerts: list):
        if not alerts:
            return
        query = """
            INSERT INTO alert (
                alert_id, run_id, opened_ts, severity, alert_type, source_system, message, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        rows = []
        for a in alerts:
            if hasattr(a, 'alert_id'):
                rows.append((
                    a.alert_id, a.run_id, a.opened_ts, a.severity,
                    a.alert_type, getattr(a, 'source_system', 'Pipeline Monitor'),
                    a.message, getattr(a, 'status', 'open')
                ))
            else:
                rows.append((
                    a.get('alert_id'), a.get('run_id'), a.get('opened_ts'), a.get('severity'),
                    a.get('alert_type'), a.get('source_system', 'Pipeline Monitor'),
                    a.get('message'), a.get('status', 'open')
                ))
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, rows)

    def insert_ground_truth(self, ground_truths: list, filepath: str):
        import dataclasses
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([dataclasses.asdict(gt) if hasattr(gt, '__dataclass_fields__') else gt for gt in ground_truths], f, indent=2)

    def get_stats(self) -> dict:
        tables = [
            'job', 'dependency', 'business_asset', 'asset_dependency',
            'execution', 'log_event', 'alert', 'incident',
            'incident_alert', 'incident_evidence', 'approval', 'audit_event'
        ]
        stats = {}
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for table in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {table}")
                        stats[table] = cur.fetchone()[0]
                    except psycopg2.Error:
                        conn.rollback()
                        stats[table] = 0
        return stats

    def reset(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                tables = [
                    'audit_event', 'approval', 'incident_evidence', 'incident_alert',
                    'incident', 'alert', 'log_event', 'execution',
                    'asset_dependency', 'business_asset', 'dependency', 'job'
                ]
                for table in tables:
                    cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        self.init_schema()

    def close(self):
        pass
