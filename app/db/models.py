import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    description: str = ""
    active_profile: str = "general_assistant"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ChatMessage(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    role: str  # user | assistant | tool
    content: str = ""
    tool_name: Optional[str] = None
    tool_args_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class ToolRun(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    profile_id: str = ""
    tool_type: str = ""  # native | mcp
    tool_name: str = ""
    server_name: Optional[str] = None
    arguments_json: str = "{}"
    status: str = ""  # success | error
    result_json: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    approved_by_user: bool = False
    created_at: datetime = Field(default_factory=_now)


class ApprovalRequest(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    tool_type: str = ""
    server_name: Optional[str] = None
    tool_name: str = ""
    arguments_json: str = "{}"
    reason: str = ""
    status: str = "pending"  # pending | approved | denied
    created_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None


class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    event_type: str = ""
    detail_json: str = "{}"
    created_at: datetime = Field(default_factory=_now)
