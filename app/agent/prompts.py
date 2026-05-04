def build_system_prompt(profile: dict) -> str:
    name = profile.get("name", "Agent")
    role = profile.get("role", "AI assistant")
    description = profile.get("description", "")
    tone = profile.get("tone", "helpful")
    verbosity = profile.get("verbosity", "balanced")
    style = profile.get("style", "conversational")

    allowed_tool_groups = profile.get("allowed_tool_groups", [])
    allowed_mcp_servers = profile.get("allowed_mcp_servers", [])
    allowed_mcp_tools = profile.get("allowed_mcp_tools", [])
    system_rules = profile.get("system_rules", [])

    rules_block = "\n".join(f"- {r}" for r in system_rules) if system_rules else "None"
    tool_groups_block = ", ".join(allowed_tool_groups) if allowed_tool_groups else "None"
    mcp_servers_block = ", ".join(allowed_mcp_servers) if allowed_mcp_servers else "None"
    mcp_tools_block = "\n".join(f"- {t}" for t in allowed_mcp_tools) if allowed_mcp_tools else "None"

    prompt = f"""You are {name}, a {role}.

{description}

## Behavior
- Tone: {tone}
- Verbosity: {verbosity}
- Style: {style}

## Allowed Tool Groups
{tool_groups_block}

## Allowed MCP Servers
{mcp_servers_block}

## Allowed MCP Tools
{mcp_tools_block}

## Rules
{rules_block}

Always stay within your defined scope. When using tools, prefer the least-privileged option that satisfies the request."""

    return prompt.strip()
