from typing import Dict, Any, Optional
from datetime import datetime, timezone
import json

class DatadogConnector:
    """
    Parses Datadog Webhook payloads and maps them to NemoGuard Alert schemas.
    """
    
    @staticmethod
    def parse_webhook(payload: Dict[str, Any], tenant_id: str = "default_tenant") -> Optional[Dict[str, Any]]:
        """
        Parses a Datadog monitor alert payload.
        Returns a normalized NemoGuard Alert dictionary, or None if invalid.
        """
        # Datadog payloads usually have an 'id', 'title', 'body', 'alert_transition'
        if "id" not in payload and "event_type" not in payload:
            # Fallback heuristic for generic payload
            pass
            
        alert_id = payload.get("id") or str(payload.get("event_id", ""))
        if not alert_id:
            return None
            
        title = payload.get("title", payload.get("event_title", "Unknown Datadog Alert"))
        body = payload.get("body", payload.get("text", ""))
        
        # Map Datadog severity/status to NemoGuard severity
        dd_status = payload.get("alert_transition", payload.get("alert_type", "info")).lower()
        
        severity = "info"
        if dd_status in ["triggered", "error", "critical"]:
            severity = "critical"
        elif dd_status in ["warning", "warn"]:
            severity = "warning"
            
        # Extract tags
        tags = payload.get("tags", "")
        if isinstance(tags, str):
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        else:
            tag_list = tags if isinstance(tags, list) else []
            
        # Attempt to extract affected resource/service from tags
        affected_resource = "Unknown"
        for tag in tag_list:
            if tag.startswith("service:"):
                affected_resource = tag.split("service:", 1)[1]
            elif tag.startswith("host:"):
                affected_resource = tag.split("host:", 1)[1]
                
        now = datetime.now(timezone.utc).isoformat()
        
        return {
            "alert_id": f"DD-{alert_id}",
            "tenant_id": tenant_id,
            "workspace_id": "default_workspace",
            "environment_id": "production",
            "opened_ts": now,
            "severity": severity,
            "alert_type": title,
            "source_system": "Datadog",
            "message": body,
            "affected_resource": affected_resource,
            "status": "open",
            "raw_payload_json": json.dumps(payload)
        }
