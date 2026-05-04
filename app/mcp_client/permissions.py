from app.mcp_client.schemas import MCPServerConfig


def check_profile_allowed(server_config: MCPServerConfig, profile_name: str) -> bool:
    return profile_name in server_config.allowed_profiles


def check_tool_allowed(allowed_mcp_tools: list[str], server_name: str, tool_name: str) -> bool:
    # Format in profiles.yaml: "server_name.tool_name"
    qualified = f"{server_name}.{tool_name}"
    return qualified in allowed_mcp_tools
