import json
from sqlmodel import Session
from app.db.models import AuditLog

VALID_EVENT_TYPES = {
    "tool_call",
    "tool_approved",
    "tool_denied",
    "mcp_connect",
    "mcp_error",
    "chat_message",
    "profile_switch",
}


class AuditLogger:
    def log(
        self,
        project_id: str,
        event_type: str,
        detail: dict,
        session: Session,
    ) -> AuditLog:
        entry = AuditLog(
            project_id=project_id,
            event_type=event_type,
            detail_json=json.dumps(detail),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
