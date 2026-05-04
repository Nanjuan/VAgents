"""
Minimal example MCP server using FastMCP.

To add a new MCP server to VAgents:
1. Create your server here (or in app/mcp_servers/examples/)
2. Add an entry to app/config/mcp_servers.yaml
3. Add the server and tools to relevant profiles in app/config/profiles.yaml
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("example-server")


@mcp.tool()
def hello(name: str) -> dict:
    """Return a greeting."""
    return {"message": f"Hello, {name}! This is an example MCP tool."}


@mcp.tool()
def add_numbers(a: float, b: float) -> dict:
    """Add two numbers."""
    return {"result": a + b, "expression": f"{a} + {b} = {a + b}"}


if __name__ == "__main__":
    mcp.run()
