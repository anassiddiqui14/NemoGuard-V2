import random
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from .topology import Topology
from .healthy_runs import Execution, LogEvent

@dataclass
class Alert:
    alert_id: str
    run_id: Optional[str]
    opened_ts: str
    severity: str
    alert_type: str
    source_system: str
    message: str
    status: str

@dataclass
class GroundTruth:
    incident_id: str
    scenario_type: str
    root_run_id: str
    root_error_code: str
    symptom_alert_ids: List[str]
    affected_asset_ids: List[str]
    expected_runbook_id: str
    expected_action_ids: List[str]
    forbidden_action_ids: List[str]

class ScenarioInjector:
    def __init__(self, topology: Topology, config: dict, rng: random.Random):
        self.topology = topology
        self.config = config
        self.rng = rng
        self.log_counter = 100000
        
    def _generate_log_id(self) -> str:
        self.log_counter += 1
        return f"LOG_{self.log_counter:06d}"

    def inject_demo_incidents(self, executions: List[Execution], logs: List[LogEvent]) -> Tuple[List[Execution], List[LogEvent], List[Alert], List[GroundTruth]]:
        alerts = []
        ground_truths = []
        
        base_date_str = self.config.get('base_date', datetime.utcnow().strftime('%Y-%m-%d'))
        demo_date = datetime.strptime(base_date_str, '%Y-%m-%d').strftime('%Y%m%d')
        
        demo_run_id = f"RUN_{demo_date}_0900_JOB_AWS_CANARY_CHECK_01"
        
        target_run = None
        for exe in executions:
            if exe.run_id == demo_run_id:
                target_run = exe
                break
                
        if not target_run:
            return executions, logs, alerts, ground_truths
            
        incident_id = f"INC_{uuid.uuid4().hex[:8]}"
        target_run.incident_id = incident_id
        
        target_run.status = 'failed'
        start_ts_dt = datetime.fromisoformat(target_run.start_ts)
        fail_ts_dt = start_ts_dt + timedelta(seconds=120)
        target_run.end_ts = fail_ts_dt.isoformat()
        target_run.records_out = 0
        target_run.schema_version = 'orders_v18'
        
        logs.append(LogEvent(
            self._generate_log_id(),
            demo_run_id,
            (start_ts_dt + timedelta(seconds=110)).isoformat(),
            'WARN',
            'schema-validator',
            None,
            'Starting schema validation',
            {}
        ))
        
        logs.append(LogEvent(
            self._generate_log_id(),
            demo_run_id,
            fail_ts_dt.isoformat(),
            'ERROR',
            'schema-validator',
            'SCHEMA_COLUMN_MISSING',
            'Missing expected columns in source',
            {
                'expected_columns': ['id', 'user_id', 'total'],
                'observed_columns': ['id', 'user_id'],
                'last_successful_schema_version': 'orders_v17',
                'observed_schema_version': 'orders_v18'
            }
        ))
        
        filtered_logs = []
        for log in logs:
            if log.run_id == demo_run_id:
                log_dt = datetime.fromisoformat(log.timestamp)
                if log_dt > fail_ts_dt or log.message.startswith('Job completed successfully'):
                    continue
            filtered_logs.append(log)
        logs = filtered_logs
        
        retry_run_id = f"RUN_{demo_date}_0900_JOB_AWS_CANARY_CHECK_02"
        retry_start_dt = fail_ts_dt + timedelta(seconds=300)
        retry_fail_dt = retry_start_dt + timedelta(seconds=120)
        
        retry_exe = Execution(
            run_id=retry_run_id,
            job_id="JOB_AWS_CANARY_CHECK",
            scheduled_ts=target_run.scheduled_ts,
            start_ts=retry_start_dt.isoformat(),
            end_ts=retry_fail_dt.isoformat(),
            status='failed',
            attempt=2,
            records_in=target_run.records_in,
            records_out=0,
            schema_version='orders_v18',
            incident_id=incident_id
        )
        executions.append(retry_exe)
        
        logs.append(LogEvent(
            self._generate_log_id(),
            retry_run_id,
            retry_fail_dt.isoformat(),
            'ERROR',
            'schema-validator',
            'SCHEMA_COLUMN_MISSING',
            'Missing expected columns in source',
            {}
        ))
        
        descendants = self.topology.get_descendants("JOB_AWS_CANARY_CHECK")
        symptom_alerts = []
        
        alert_id = f"ALT_{uuid.uuid4().hex[:8]}"
        symptom_alerts.append(alert_id)
        alerts.append(Alert(
            alert_id=alert_id,
            run_id=target_run.run_id,
            opened_ts=fail_ts_dt.isoformat(),
            severity='critical',
            alert_type='job_failed',
            source_system='scheduler',
            message='Job JOB_AWS_CANARY_CHECK failed after 2 attempts',
            status='open'
        ))
        
        for exe in executions:
            if exe.job_id in descendants and exe.scheduled_ts == target_run.scheduled_ts:
                exe.incident_id = incident_id
                if exe.job_id == 'JOB_AWS_EXTRACT_RESERVATION':
                    exe.status = 'failed'
                    exe.end_ts = (datetime.fromisoformat(exe.start_ts) + timedelta(seconds=10)).isoformat()
                    alert_id = f"ALT_{uuid.uuid4().hex[:8]}"
                    symptom_alerts.append(alert_id)
                    alerts.append(Alert(
                        alert_id=alert_id,
                        run_id=exe.run_id,
                        opened_ts=exe.end_ts,
                        severity='high',
                        alert_type='job_failed',
                        source_system='scheduler',
                        message=f'Job {exe.job_id} failed due to parent failure',
                        status='open'
                    ))
                else:
                    exe.status = 'blocked'
                    exe.end_ts = exe.start_ts
                    alert_id = f"ALT_{uuid.uuid4().hex[:8]}"
                    symptom_alerts.append(alert_id)
                    alerts.append(Alert(
                        alert_id=alert_id,
                        run_id=exe.run_id,
                        opened_ts=exe.start_ts,
                        severity='warning',
                        alert_type='job_blocked',
                        source_system='scheduler',
                        message=f'Job {exe.job_id} blocked by upstream dependency',
                        status='open'
                    ))
                
        affected_assets = self.topology.get_affected_assets(["JOB_AWS_CANARY_CHECK"] + descendants)
        for asset_id in affected_assets:
            alert_id = f"ALT_{uuid.uuid4().hex[:8]}"
            symptom_alerts.append(alert_id)
            alerts.append(Alert(
                alert_id=alert_id,
                run_id=None,
                opened_ts=(fail_ts_dt + timedelta(hours=2)).isoformat(),
                severity='high',
                alert_type='freshness_alert',
                source_system='quality-gate',
                message=f'Asset {asset_id} missed SLA',
                status='open'
            ))

        gt = GroundTruth(
            incident_id=incident_id,
            scenario_type='schema_drift',
            root_run_id=target_run.run_id,
            root_error_code='SCHEMA_COLUMN_MISSING',
            symptom_alert_ids=symptom_alerts,
            affected_asset_ids=affected_assets,
            expected_runbook_id='RB_SCHEMA_UPDATE',
            expected_action_ids=['ACT_ACK', 'ACT_UPDATE_SCHEMA', 'ACT_RERUN'],
            forbidden_action_ids=['ACT_IGNORE']
        )
        ground_truths.append(gt)

        return executions, logs, alerts, ground_truths

    def inject_random_incidents(self, executions: List[Execution], logs: List[LogEvent], count: int) -> Tuple[List[Execution], List[LogEvent], List[Alert], List[GroundTruth]]:
        alerts = []
        ground_truths = []
        return executions, logs, alerts, ground_truths
