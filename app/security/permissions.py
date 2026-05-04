class PermissionChecker:
    def check_profile_can_use_tool(self, profile: dict, tool_id: str) -> bool:
        """Check if a tool_id is within the profile's allowed tool groups or MCP tools."""
        if tool_id.startswith("native:"):
            tool_name = tool_id[len("native:"):]
            allowed_groups = profile.get("allowed_tool_groups", [])
            # Resolved at registry level; here we check groups match
            return len(allowed_groups) > 0

        if tool_id.startswith("mcp:"):
            # format: mcp:{server_name}.{tool_name}
            remainder = tool_id[len("mcp:"):]
            qualified = remainder  # "server_name.tool_name"
            allowed_mcp_tools = profile.get("allowed_mcp_tools", [])
            return qualified in allowed_mcp_tools

        return False

    def check_mcp_server_allowed(self, profile: dict, server_name: str) -> bool:
        allowed_servers = profile.get("allowed_mcp_servers", [])
        return server_name in allowed_servers
