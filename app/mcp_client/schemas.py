from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    name: str
    enabled: bool
    description: str
    transport: str  # stdio | streamable_http
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers_env: dict[str, str] = {}
    allowed_profiles: list[str]
    require_approval: bool
    timeout_seconds: int
    tool_output_limit_chars: int


class MCPToolInfo(BaseModel):
    server_name: str
    tool_name: str
    display_name: str
    description: str
    input_schema: dict
    requires_approval: bool
    allowed_profiles: list[str]
