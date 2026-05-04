from app.mcp_client.schemas import MCPServerConfig
from app.tools.schemas import ToolDefinition, ToolType


def mcp_tool_to_tool_definition(
    server_name: str,
    mcp_tool,
    server_config: MCPServerConfig,
) -> ToolDefinition:
    tool_id = f"mcp:{server_name}.{mcp_tool.name}"

    # MCP SDK tool has .inputSchema dict
    input_schema = {}
    if hasattr(mcp_tool, "inputSchema") and mcp_tool.inputSchema:
        raw = mcp_tool.inputSchema
        if hasattr(raw, "model_dump"):
            input_schema = raw.model_dump()
        elif isinstance(raw, dict):
            input_schema = raw
        else:
            input_schema = {}

    return ToolDefinition(
        tool_type=ToolType.mcp,
        tool_id=tool_id,
        server_name=server_name,
        tool_name=mcp_tool.name,
        display_name=mcp_tool.name.replace("_", " ").title(),
        description=mcp_tool.description or "",
        input_schema=input_schema,
        requires_approval=server_config.require_approval,
        allowed_profiles=server_config.allowed_profiles,
    )
