"""Persist tool executions for audit API and operators."""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlmodel import Session

from app.db.models import AuditLog, ToolRun
from app.tools.schemas import ToolCallResult

logger = logging.getLogger(__name__)


def split_tool_id(tool_id: str) -> tuple[str, Optional[str], str]:
    """Returns tool_type, server_name or None, short tool name."""
    if tool_id.startswith("native:"):
        return "native", None, tool_id.split(":", 1)[1]
    if tool_id.startswith("mcp:"):
        rest = tool_id[4:]
        dot = rest.find(".")
        if dot == -1:
            return "mcp", None, rest
        return "mcp", rest[:dot], rest[dot + 1 :]
    return "unknown", None, tool_id


def record_tool_run(
    session: Session,
    project_id: str,
    profile_name: str,
    tool_id: str,
    arguments: dict,
    result: ToolCallResult,
    approved_by_user: bool,
) -> None:
    tt, sn, tn = split_tool_id(tool_id)
    tr = ToolRun(
        project_id=project_id,
        profile_id=profile_name,
        tool_type=tt,
        tool_name=tn,
        server_name=sn,
        arguments_json=json.dumps(arguments),
        status=result.status,
        result_json=json.dumps({"result": result.result, "error": result.error}),
        error=result.error,
        duration_ms=result.duration_ms,
        approved_by_user=approved_by_user,
    )
    session.add(tr)
    session.add(
        AuditLog(
            project_id=project_id,
            event_type="tool_call",
            detail_json=json.dumps(
                {
                    "profile_name": profile_name,
                    "tool_id": tool_id,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "approved_by_user": approved_by_user,
                }
            ),
        )
    )
    try:
        session.commit()
    except Exception:
        logger.exception("Failed to persist tool run / audit log")
        session.rollback()
        raise


def record_approval_event(session: Session, project_id: str, approval_id: str, action: str) -> None:
    session.add(
        AuditLog(
            project_id=project_id,
            event_type="approval",
            detail_json=json.dumps({"approval_id": approval_id, "action": action}),
        )
    )
    try:
        session.commit()
    except Exception:
        logger.exception("Failed to persist approval audit")
        session.rollback()
        raise
