import hashlib
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid

from .models import Alert, Incident
from .enums import IncidentState, Severity

class CorrelatorEngine:
    def __init__(self, time_window_seconds: int = 300, min_cluster_score: float = 0.6):
        self.time_window = timedelta(seconds=time_window_seconds)
        self.min_cluster_score = min_cluster_score
        
        # Load topology cache for advanced correlation
        try:
            import json, os
            cmdb_path = os.path.join(os.path.dirname(__file__), '../../data/mock_dimensions/cmdb.json')
            with open(cmdb_path, "r") as f:
                self.cmdb_graph = json.load(f).get("edges", [])
        except Exception:
            self.cmdb_graph = []

    def _normalize_dt(self, dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    def generate_fingerprint(self, alert: Alert) -> str:
        """
        Generate a fingerprint for deduplication.
        Uses stable fields: source_system + run_id + alert_type + hour bucket
        """
        hour_bucket = self._normalize_dt(alert.opened_ts).replace(minute=0, second=0, microsecond=0).isoformat()
        run_id = alert.run_id or "NO_RUN"
        base_string = f"{alert.source_system}:{run_id}:{alert.alert_type}:{hour_bucket}"
        return hashlib.sha256(base_string.encode('utf-8')).hexdigest()

    def deduplicate(self, alerts: List[Alert]) -> Tuple[List[Alert], Dict[str, int]]:
        """
        Deduplicate alerts based on their fingerprint.
        Returns unique alerts and a map of fingerprint -> duplicate count.
        """
        unique_alerts = []
        seen = set()
        duplicate_counts = {}

        for alert in sorted(alerts, key=lambda a: self._normalize_dt(a.opened_ts)):
            fp = self.generate_fingerprint(alert)
            if fp not in seen:
                seen.add(fp)
                unique_alerts.append(alert)
                duplicate_counts[fp] = 0
            else:
                duplicate_counts[fp] += 1
                
        return unique_alerts, duplicate_counts
        
    def _is_topologically_related(self, run_id_1: str, run_id_2: str) -> bool:
        """
        Checks if two run_ids are related in the CMDB graph (e.g. parent/child).
        For this mock, we assume run_id == job_id.
        """
        if not run_id_1 or not run_id_2:
            return False
            
        job_1 = run_id_1.replace("DEMO-RUN-", "") # simplistic extraction
        job_2 = run_id_2.replace("DEMO-RUN-", "")
        
        for edge in self.cmdb_graph:
            source = edge.get("source_id")
            target = edge.get("target_id")
            if (source == job_1 and target == job_2) or (source == job_2 and target == job_1):
                return True
        return False

    def best_match_for_alert(
        self, alert: Alert, candidate_alerts_by_incident: Dict[str, List[Alert]]
    ) -> Tuple[Any, float, List[str]]:
        """
        Deterministic first-pass correlation check (spec §8 / build plan
        Priority 4): given a newly-normalized alert and a map of
        {incident_id: [alerts already correlated to that incident]}, returns
        the (incident_id, score, signal_reasons) of the best-matching active
        incident using ONLY the deterministic pairwise scoring rules in
        calculate_pairwise_score -- same-run-id, time proximity, matching
        error signature, and CMDB topology adjacency.

        This is intentionally independent of any LLM judgment. It exists so
        that when the deterministic signal is strong (score >=
        min_cluster_score), the caller can attach/create the correlation
        immediately WITHOUT spending an LLM call on a decision that already
        has clear, explainable, deterministic ground truth -- and so the UI
        can show a real answer to "why was this alert consolidated into this
        incident" rather than an opaque LLM "reasoning" string.

        For each candidate incident, the score used is the MAX pairwise score
        across all of that incident's already-correlated alerts (an alert
        need only strongly match ONE existing member of an incident's alert
        set to justify joining it, not all of them).

        Returns (None, 0.0, []) if there are no candidates or no alert in
        any candidate incident has run_id/alert_type/opened_ts information
        (e.g. malformed historical data).
        """
        best_incident_id = None
        best_score = 0.0
        best_reasons: List[str] = []

        for incident_id, existing_alerts in candidate_alerts_by_incident.items():
            for existing in existing_alerts:
                score = self.calculate_pairwise_score(alert, existing)
                if score > best_score:
                    best_score = score
                    best_incident_id = incident_id
                    reasons = []
                    if alert.run_id and existing.run_id and alert.run_id == existing.run_id:
                        reasons.append("same run_id")
                    time_diff = abs((self._normalize_dt(alert.opened_ts) - self._normalize_dt(existing.opened_ts)).total_seconds())
                    if time_diff <= 60:
                        reasons.append(f"occurred within {int(time_diff)}s of an existing alert")
                    elif time_diff <= self.time_window.total_seconds():
                        reasons.append(f"occurred within {int(time_diff)}s (within correlation window) of an existing alert")
                    if alert.alert_type == existing.alert_type:
                        reasons.append(f"matching alert_type '{alert.alert_type}'")
                    if self._is_topologically_related(alert.run_id, existing.run_id):
                        reasons.append("topologically adjacent resource in CMDB")
                    best_reasons = reasons

        return best_incident_id, best_score, best_reasons

    def calculate_pairwise_score(self, alert1: Alert, alert2: Alert) -> float:
        """
        Calculate correlation score between two alerts using time, identity, and topology.
        """
        score = 0.0
        
        # 1. Same Run (very strong)
        if alert1.run_id and alert2.run_id and alert1.run_id == alert2.run_id:
            score += 0.8
            
        # 2. Time Proximity (medium)
        time_diff = abs((self._normalize_dt(alert1.opened_ts) - self._normalize_dt(alert2.opened_ts)).total_seconds())
        if time_diff <= 60:
            score += 0.3
        elif time_diff <= self.time_window.total_seconds():
            score += 0.15
            
        # 3. Same Error Signature (medium)
        if alert1.alert_type == alert2.alert_type:
            score += 0.2
            
        # 4. Topology Graph checking (parent-child relationship)
        if score < 0.8 and self._is_topologically_related(alert1.run_id, alert2.run_id):
            score += 0.6

        return min(1.0, score)

    def correlate(self, alerts: List[Alert]) -> List[Dict[str, Any]]:
        """
        Cluster unassigned alerts into incident candidates.
        """
        if not alerts:
            return []
            
        # First, deduplicate
        unique_alerts, duplicate_counts = self.deduplicate(alerts)
        
        # Simple clustering: group by high pairwise score
        clusters = []
        unassigned = list(unique_alerts)
        
        while unassigned:
            # Sort by severity to pick the primary alert (critical > high > warning > info)
            severity_order = {"critical": 0, "high": 1, "warning": 2, "info": 3}
            unassigned.sort(key=lambda a: (severity_order.get(a.severity.lower(), 4), self._normalize_dt(a.opened_ts)))
            
            primary = unassigned.pop(0)
            cluster = [primary]
            member_scores = []  # pairwise scores of each additional alert against the primary
            
            i = 0
            while i < len(unassigned):
                candidate = unassigned[i]
                score = self.calculate_pairwise_score(primary, candidate)
                if score >= self.min_cluster_score:
                    cluster.append(candidate)
                    member_scores.append(score)
                    unassigned.pop(i)
                else:
                    i += 1
            
            # A single-alert cluster (no correlated members) is a confirmed, unambiguous
            # incident — confidence 1.0 is honest here. Once we start merging in other alerts,
            # the overall cluster confidence should reflect how strongly *all* members actually
            # correlate, not just default to 1.0 regardless of evidence. We use the mean pairwise
            # score of members against the primary, which degrades appropriately as weaker
            # (borderline min_cluster_score) matches get folded in.
            cluster_score = 1.0 if not member_scores else sum(member_scores) / len(member_scores)
            
            clusters.append({
                "primary_alert": primary,
                "alerts": cluster,
                "duplicate_count": sum(duplicate_counts[self.generate_fingerprint(a)] for a in cluster),
                "cluster_score": cluster_score
            })
            
        return clusters

    def create_incident(self, cluster: Dict[str, Any]) -> Incident:
        """
        Create an Incident record from a correlated cluster.
        """
        primary = cluster["primary_alert"]
        severity_map = {
            "critical": Severity.SEV_1,
            "high": Severity.SEV_2,
            "warning": Severity.SEV_3,
            "info": Severity.SEV_4
        }
        
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        
        # Serialize correlation metadata
        correlation_reasons = []
        if len(cluster['alerts']) > 1:
            correlation_reasons.append("Topological or temporal proximity detected")
        if cluster['duplicate_count'] > 0:
            correlation_reasons.append(f"Deduplicated {cluster['duplicate_count']} exact match events")
            
        # Previously this always appended "..." even when the message was
        # shorter than the truncation length, so incident titles looked
        # permanently cut off ("Incident: short message...") with no way to
        # see the rest — the ellipsis was baked into the stored title itself,
        # not a CSS overflow effect. Only truncate (and only then add "...")
        # when the message actually exceeds the limit, and use a longer,
        # more informative limit.
        _TITLE_MSG_LIMIT = 120
        _msg = primary.message or ""
        _title_msg = _msg[:_TITLE_MSG_LIMIT] + "..." if len(_msg) > _TITLE_MSG_LIMIT else _msg

        return Incident(
            incident_id=incident_id,
            title=f"Incident: {_title_msg}",
            summary=f"Created from {len(cluster['alerts'])} correlated alerts (and {cluster['duplicate_count']} duplicates). \nReasons: {', '.join(correlation_reasons)}",
            status=IncidentState.DETECTED,
            severity=severity_map.get(primary.severity.lower(), Severity.SEV_3),
            primary_run_id=primary.run_id,
            detected_at=primary.opened_ts,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            correlation_confidence=cluster["cluster_score"]
        )
