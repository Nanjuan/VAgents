import asyncio
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp_client.schemas import MCPServerConfig
from app.mcp_client.server_registry import MCPServerRegistry
from app.mcp_client.tool_adapter import mcp_tool_to_tool_definition
from app.mcp_client.permissions import check_profile_allowed, check_tool_allowed
from app.mcp_client.result_normalizer import normalize_mcp_result
from app.tools.schemas import ToolDefinition
from app.config.settings import get_settings
import yaml


class MCPClientManager:
    def __init__(self) -> None:
        self._registry = MCPServerRegistry()
        self._loaded = False

    async def load_servers(self, config_path: str) -> None:
        self._registry.load(config_path)
        self._loaded = True

    def _get_profile_allowed_tools(self, profile_name: str) -> list[str]:
        settings = get_settings()
        profiles_path = settings.config_dir / "profiles.yaml"
        with open(profiles_path) as f:
            data = yaml.safe_load(f)
        profile = data.get("profiles", {}).get(profile_name, {})
        return profile.get("allowed_mcp_tools", [])

    async def _open_stdio_session(self, server_config: MCPServerConfig):
        """Context manager that yields a live ClientSession for a stdio server."""
        env = {**os.environ, **server_config.env}
        params = StdioServerParameters(
            command=server_config.command or "python",
            args=server_config.args,
            env=env,
        )
        return stdio_client(params)

    async def list_tools_for_profile(self, profile_name: str) -> list[ToolDefinition]:
        if not self._loaded:
            settings = get_settings()
            await self.load_servers(str(settings.config_dir / "mcp_servers.yaml"))

        allowed_mcp_tools = self._get_profile_allowed_tools(profile_name)
        results: list[ToolDefinition] = []

        for server_config in self._registry.all_enabled():
            if not check_profile_allowed(server_config, profile_name):
                continue
            try:
                tools = await self._list_server_tools(server_config)
                for tool in tools:
                    if check_tool_allowed(allowed_mcp_tools, server_config.name, tool.name):
                        results.append(mcp_tool_to_tool_definition(server_config.name, tool, server_config))
            except Exception as e:
                # Server unavailable — skip silently
                pass

        return results

    async def _list_server_tools(self, server_config: MCPServerConfig) -> list[Any]:
        if server_config.transport == "stdio":
            return await self._list_tools_stdio(server_config)
        elif server_config.transport in ("streamable_http", "http"):
            return await self._list_tools_http(server_config)
        return []

    async def _list_tools_stdio(self, server_config: MCPServerConfig) -> list[Any]:
        env = {**os.environ, **server_config.env}
        params = StdioServerParameters(
            command=server_config.command or "python",
            args=server_config.args,
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(
                    session.initialize(), timeout=server_config.timeout_seconds
                )
                result = await asyncio.wait_for(
                    session.list_tools(), timeout=server_config.timeout_seconds
                )
                return result.tools

    async def _list_tools_http(self, server_config: MCPServerConfig) -> list[Any]:
        from mcp.client.streamable_http import streamablehttp_client
        url = server_config.url or ""
        headers = {k: os.environ.get(v, "") for k, v in server_config.headers_env.items()}
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(
                    session.initialize(), timeout=server_config.timeout_seconds
                )
                result = await asyncio.wait_for(
                    session.list_tools(), timeout=server_config.timeout_seconds
                )
                return result.tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
        profile_name: str,
        limit_chars: int = 20000,
    ) -> dict:
        if not self._loaded:
            settings = get_settings()
            await self.load_servers(str(settings.config_dir / "mcp_servers.yaml"))

        server_config = self._registry.get(server_name)
        if not server_config:
            return {"status": "error", "error": f"Server '{server_name}' not configured"}
        if not server_config.enabled:
            return {"status": "error", "error": f"Server '{server_name}' is disabled"}
        if not check_profile_allowed(server_config, profile_name):
            return {"status": "error", "error": f"Profile '{profile_name}' not allowed for server '{server_name}'"}

        allowed_mcp_tools = self._get_profile_allowed_tools(profile_name)
        if not check_tool_allowed(allowed_mcp_tools, server_name, tool_name):
            return {"status": "error", "error": f"Tool '{server_name}.{tool_name}' not in profile allowlist"}

        try:
            if server_config.transport == "stdio":
                raw = await self._call_tool_stdio(server_config, tool_name, arguments)
            else:
                raw = await self._call_tool_http(server_config, tool_name, arguments)
            return normalize_mcp_result(raw, limit_chars)
        except asyncio.TimeoutError:
            return {"status": "error", "error": f"Tool call timed out after {server_config.timeout_seconds}s"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _call_tool_stdio(self, server_config: MCPServerConfig, tool_name: str, arguments: dict) -> Any:
        env = {**os.environ, **server_config.env}
        params = StdioServerParameters(
            command=server_config.command or "python",
            args=server_config.args,
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(
                    session.initialize(), timeout=server_config.timeout_seconds
                )
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments),
                    timeout=server_config.timeout_seconds,
                )
                return result

    async def _call_tool_http(self, server_config: MCPServerConfig, tool_name: str, arguments: dict) -> Any:
        from mcp.client.streamable_http import streamablehttp_client
        url = server_config.url or ""
        headers = {k: os.environ.get(v, "") for k, v in server_config.headers_env.items()}
        async with streamablehttp_client(url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(
                    session.initialize(), timeout=server_config.timeout_seconds
                )
                result = await asyncio.wait_for(
                    session.call_tool(tool_name, arguments),
                    timeout=server_config.timeout_seconds,
                )
                return result

    async def test_server(self, server_name: str) -> dict:
        server_config = self._registry.get(server_name)
        if not server_config:
            return {"status": "error", "error": f"Server '{server_name}' not configured"}
        try:
            tools = await self._list_server_tools(server_config)
            return {
                "status": "ok",
                "server": server_name,
                "tools": [{"name": t.name, "description": t.description} for t in tools],
            }
        except Exception as e:
            return {"status": "error", "server": server_name, "error": str(e)}

    async def list_servers(self) -> list[dict]:
        if not self._loaded:
            settings = get_settings()
            await self.load_servers(str(settings.config_dir / "mcp_servers.yaml"))
        return [
            {
                "name": s.name,
                "enabled": s.enabled,
                "description": s.description,
                "transport": s.transport,
                "allowed_profiles": s.allowed_profiles,
                "require_approval": s.require_approval,
            }
            for s in self._registry.all()
        ]
