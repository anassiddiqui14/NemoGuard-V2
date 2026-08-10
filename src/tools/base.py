from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

class ToolErrorCode:
    NOT_FOUND = "NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    STALE_STATE = "STALE_STATE"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

@dataclass
class ToolResponse:
    ok: bool
    tool: str
    request_id: str = field(default_factory=lambda: f"REQ_{uuid.uuid4().hex[:8]}")
    data: Optional[Dict[str, Any]] = None
    evidence_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    truncated: bool = False
    next_page_token: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False

    def to_dict(self) -> dict:
        result = {
            "ok": self.ok,
            "tool": self.tool,
            "request_id": self.request_id,
            "evidence_ids": self.evidence_ids,
            "warnings": self.warnings,
            "truncated": self.truncated,
            "retryable": self.retryable,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.next_page_token is not None:
            result["next_page_token"] = self.next_page_token
        if self.error_code is not None:
            result["error_code"] = self.error_code
        if self.error_message is not None:
            result["error_message"] = self.error_message
        return result
