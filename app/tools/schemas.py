from enum import Enum
from pydantic import BaseModel


class ToolType(str, Enum):
    native = "native"
    mcp = "mcp"


class ToolDefinition(BaseModel):
    tool_type: ToolType
    tool_id: str           # "native:http_get_headers" or "mcp:server.tool"
    server_name: str | None = None
    tool_name: str
    display_name: str
    description: str
    input_schema: dict
    requires_approval: bool
    allowed_profiles: list[str]


class ToolCallRequest(BaseModel):
    profile_name: str
    tool_id: str
    arguments: dict
    reason: str


class ToolCallResult(BaseModel):
    tool_id: str
    status: str            # success | error
    result: dict | str | None = None
    error: str | None = None
    duration_ms: int
