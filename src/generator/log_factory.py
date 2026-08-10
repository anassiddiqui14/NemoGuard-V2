import random
from typing import List, Optional, Any
from datetime import datetime
from .topology import Job
from .healthy_runs import LogEvent

class LogFactory:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.log_counter = 200000
        
    def _generate_log_id(self) -> str:
        self.log_counter += 1
        return f"LOG_{self.log_counter:06d}"

    def success_logs(self, run_id: str, job: Job, start_ts: str, end_ts: str, records_in: Optional[int], records_out: Optional[int], log_id_counter: int) -> List[LogEvent]:
        return []

    def failure_logs(self, run_id: str, job: Job, scenario_type: str, error_code: str, start_ts: str, fail_ts: str, attributes: dict, log_id_counter: int) -> List[LogEvent]:
        logs = []
        
        err_messages = {
            'SCHEMA_COLUMN_MISSING': [
                "Missing required column in source data",
                "Schema validation failed: columns not found",
                "Source data structure changed, missing expected fields"
            ],
            'SCHEMA_TYPE_MISMATCH': [
                "Invalid data type for column",
                "Type cast error in processing",
                "Schema mismatch: unexpected type encountered"
            ],
            'SOURCE_FILE_MISSING': [
                "Source file not found at expected path",
                "Input partition missing",
                "Cannot locate data files in S3"
            ],
            'SOURCE_FILE_LATE': [
                "Source file arrival delayed",
                "Data SLA missed for input file"
            ],
            'AUTH_EXPIRED': [
                "Authentication token expired",
                "Access denied: invalid credentials",
                "Failed to authenticate with external service"
            ],
            'NETWORK_TIMEOUT': [
                "Connection timed out",
                "Read timeout on network socket",
                "Failed to connect to downstream service"
            ],
            'DQ_THRESHOLD_FAILED': [
                "Data quality threshold breached",
                "Too many nulls detected in primary key",
                "Anomaly score above acceptable limit"
            ],
            'RESOURCE_EXHAUSTED': [
                "OOM Killer terminated process",
                "Exceeded memory limits during shuffle",
                "Not enough compute resources available"
            ],
            'DUPLICATE_BATCH_KEY': [
                "Duplicate keys found in batch",
                "Unique constraint violation detected",
                "Merge failed due to multiple matches"
            ],
            'TABLE_LOCKED': [
                "Target table is locked by another transaction",
                "Deadlock detected during write"
            ],
            'API_RATE_LIMITED': [
                "Rate limit exceeded on external API",
                "Received HTTP 429 Too Many Requests"
            ],
            'CODE_EXCEPTION': [
                "NullPointerException during row processing",
                "IndexOutOfBoundsException in transform step",
                "Unhandled exception in UDF"
            ],
            'PARENT_FAILED': [
                "Aborting execution due to parent job failure",
                "Upstream dependency ended in error state"
            ],
            'DEPENDENCY_BLOCKED': [
                "Execution blocked, dependencies not met",
                "Cannot start: upstream jobs pending or failed"
            ],
            'API_5XX_ERROR': [
                "Triggered: [P3] {job_name} 5xx error rate - Prod",
                "Re-Triggered: {job_name} 5xx error rate high"
            ],
            'INFA_SESSION_FAILED': [
                "Informatica Bad File-{job_name}",
                "FAILURE: Session {job_name} failed"
            ],
            'CANARY_NOT_RECEIVED': [
                "Canary Files Not Received - {job_name}",
                "Timeout waiting for canary file on {job_name}"
            ],
            'SQS_LOW_VOLUME': [
                "Warn: LOW SQS MESSAGE VOLUME DETECTED",
                "Warn: LOW SQS MESSAGE VOLUME RECEIVED"
            ]
        }
        
        msg_variants = err_messages.get(error_code, ["Unknown error occurred"])
        msg = self.rng.choice(msg_variants).replace('{job_name}', job.job_name)
        
        logs.append(LogEvent(
            self._generate_log_id(),
            run_id,
            fail_ts,
            'ERROR',
            'job-runner',
            error_code,
            msg,
            attributes
        ))
        return logs

    def blocked_logs(self, run_id: str, job: Job, scheduled_ts: str, blocking_parent_run_id: str, log_id_counter: int) -> List[LogEvent]:
        logs = []
        msg_variants = [
            f"Execution blocked, dependency {blocking_parent_run_id} not met",
            f"Cannot start: upstream job {blocking_parent_run_id} pending or failed"
        ]
        msg = self.rng.choice(msg_variants)
        
        logs.append(LogEvent(
            self._generate_log_id(),
            run_id,
            scheduled_ts,
            'WARN',
            'scheduler',
            'DEPENDENCY_BLOCKED',
            msg,
            {'blocking_parent': blocking_parent_run_id}
        ))
        return logs

    def freshness_alert_log(self, job: Job, asset: Any, last_refresh_ts: str, log_id_counter: int) -> LogEvent:
        return LogEvent(
            self._generate_log_id(),
            "NONE",
            datetime.utcnow().isoformat(),
            'ERROR',
            'quality-gate',
            'FRESHNESS_SLA_MISSED',
            f"Asset {asset.asset_id} missed freshness SLA.",
            {'last_refresh': last_refresh_ts}
        )
