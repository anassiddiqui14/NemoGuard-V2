import sqlite3
import json
import csv
import os
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('PRAGMA foreign_keys=ON;')
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.execute('PRAGMA busy_timeout=5000;')
            
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute('PRAGMA foreign_keys=OFF;')
            yield conn
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
            conn.executescript(schema_sql)
            conn.executescript(migration_sql)

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
                placeholders = ','.join(['?'] * len(headers))
                query = f"INSERT OR REPLACE INTO {table} ({','.join(headers)}) VALUES ({placeholders})"
                with self.get_connection() as conn:
                    conn.executemany(query, rows)
                    
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.executemany(query, rows)

    def insert_logs(self, logs: list):
        if not logs:
            return
        query = """
            INSERT INTO log_event (
                log_id, run_id, timestamp, level, component, error_code, message, attributes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.executemany(query, rows)

    def insert_alerts(self, alerts: list):
        if not alerts:
            return
        query = """
            INSERT INTO alert (
                alert_id, run_id, opened_ts, severity, alert_type, source_system, message, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.executemany(query, rows)

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
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table] = 0
        return stats

    def reset(self):
        with self.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            tables = [
                'audit_event', 'approval', 'incident_evidence', 'incident_alert',
                'incident', 'alert', 'log_event', 'execution',
                'asset_dependency', 'business_asset', 'dependency', 'job'
            ]
            for table in tables:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def close(self):
        pass
