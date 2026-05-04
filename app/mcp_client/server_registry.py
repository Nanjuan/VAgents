import yaml
from app.mcp_client.schemas import MCPServerConfig


class MCPServerRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}

    def load(self, config_path: str) -> None:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        for name, cfg in data.get("mcp_servers", {}).items():
            self._servers[name] = MCPServerConfig(name=name, **cfg)

    def get(self, name: str) -> MCPServerConfig | None:
        return self._servers.get(name)

    def all_enabled(self) -> list[MCPServerConfig]:
        return [s for s in self._servers.values() if s.enabled]

    def all(self) -> list[MCPServerConfig]:
        return list(self._servers.values())
