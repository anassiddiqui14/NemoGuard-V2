import random
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from .topology import Topology, Job

@dataclass
class Execution:
    run_id: str
    job_id: str
    scheduled_ts: str
    start_ts: str
    end_ts: Optional[str]
    status: str
    attempt: int
    records_in: Optional[int]
    records_out: Optional[int]
    schema_version: Optional[str]
    incident_id: Optional[str]

@dataclass
class LogEvent:
    log_id: str
    run_id: str
    timestamp: str
    level: str
    component: str
    error_code: Optional[str]
    message: str
    attributes: dict

class HealthyRunGenerator:
    def __init__(self, topology: Topology, config: dict, rng: random.Random):
        self.topology = topology
        self.config = config
        self.rng = rng
        self.log_counter = 0

    def _generate_log_id(self) -> str:
        self.log_counter += 1
        return f"LOG_{self.log_counter:06d}"

    def generate(self) -> Tuple[List[Execution], List[LogEvent]]:
        executions = []
        logs = []
        
        base_date_str = self.config.get('base_date', datetime.utcnow().strftime('%Y-%m-%d'))
        base_date = datetime.strptime(base_date_str, '%Y-%m-%d')
        history_days = self.config.get('history_days', 7)
        
        sorted_jobs = self.topology.topological_sort()
        
        parent_completions: Dict[Tuple[str, str], datetime] = {}
        
        for day_offset in range(history_days, -1, -1):
            current_date = base_date - timedelta(days=day_offset)
            date_str = current_date.strftime('%Y%m%d')
            
            for job_id in sorted_jobs:
                job = self.topology.get_job(job_id)
                if not job or not job.active:
                    continue
                    
                schedule_times = self._get_schedule_times(job.schedule, current_date)
                
                for scheduled_dt in schedule_times:
                    hour = scheduled_dt.hour
                    minute = scheduled_dt.minute
                    attempt = 1
                    run_id = f"RUN_{date_str}_{hour:02d}{minute:02d}_{job_id}_{attempt:02d}"
                    scheduled_ts = scheduled_dt.isoformat()
                    
                    max_parent_completion = scheduled_dt
                    for edge in self.topology.get_parents(job_id):
                        if edge.required:
                            parent_key = (edge.parent_job_id, scheduled_ts)
                            if parent_key in parent_completions:
                                p_end = parent_completions[parent_key]
                                if p_end > max_parent_completion:
                                    max_parent_completion = p_end
                    
                    delay_sec = self.rng.randint(0, 60) if job.schedule == 'hourly' else self.rng.randint(0, 300)
                    start_dt = max_parent_completion + timedelta(seconds=delay_sec)
                    
                    duration_sec = int(job.default_duration_sec * (0.8 + self.rng.random() * 0.4))
                    end_dt = start_dt + timedelta(seconds=duration_sec)
                    
                    parent_completions[(job_id, scheduled_ts)] = end_dt
                    
                    base_records = 10000
                    records_in = int(base_records * (0.9 + self.rng.random() * 0.2))
                    
                    ratio_map = {'ingest': 0.99, 'bronze': 0.98, 'silver': 0.85, 'gold': 0.7, 'publish': 1.0}
                    ratio = ratio_map.get(job.stage.lower(), 1.0)
                    records_out = int(records_in * ratio)
                    
                    schema_version = f"{job.domain}_v17"
                    
                    exe = Execution(
                        run_id=run_id,
                        job_id=job_id,
                        scheduled_ts=scheduled_ts,
                        start_ts=start_dt.isoformat(),
                        end_ts=end_dt.isoformat(),
                        status='succeeded',
                        attempt=attempt,
                        records_in=records_in,
                        records_out=records_out,
                        schema_version=schema_version,
                        incident_id=None
                    )
                    executions.append(exe)
                    
                    log_times = [
                        start_dt,
                        start_dt + timedelta(seconds=duration_sec * 0.1),
                        start_dt + timedelta(seconds=duration_sec * 0.5),
                        end_dt
                    ]
                    
                    logs.append(LogEvent(self._generate_log_id(), run_id, log_times[0].isoformat(), 'INFO', 'scheduler', None, 'Job started', {}))
                    logs.append(LogEvent(self._generate_log_id(), run_id, log_times[1].isoformat(), 'INFO', 'reader', None, 'Config loaded', {}))
                    logs.append(LogEvent(self._generate_log_id(), run_id, log_times[2].isoformat(), 'INFO', 'transform', None, f'Processing row {records_in//2}', {}))
                    logs.append(LogEvent(self._generate_log_id(), run_id, log_times[3].isoformat(), 'INFO', 'writer', None, f'Job completed successfully. Out: {records_out}', {}))
                    
        return executions, logs

    def _get_schedule_times(self, schedule: str, date: datetime) -> List[datetime]:
        times = []
        if schedule == 'hourly':
            for h in range(24):
                times.append(date.replace(hour=h, minute=0, second=0, microsecond=0))
        elif schedule == 'daily':
            times.append(date.replace(hour=0, minute=0, second=0, microsecond=0))
        elif schedule == 'every_15_min':
            for h in range(24):
                for m in [0, 15, 30, 45]:
                    times.append(date.replace(hour=h, minute=m, second=0, microsecond=0))
        else:
            times.append(date.replace(hour=0, minute=0, second=0, microsecond=0))
        return times
