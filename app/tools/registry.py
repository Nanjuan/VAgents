from pathlib import Path
import yaml
from app.tools.schemas import ToolDefinition, ToolType
from app.config.settings import get_settings

# Static metadata for native tools
_NATIVE_TOOL_META: dict[str, dict] = {
    "http_get_headers": {
        "description": "Send an HTTP HEAD request and return response headers.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Target URL"}},
            "required": ["url"],
        },
        "requires_approval": False,
    },
    "dns_lookup": {
        "description": "Resolve a hostname to IP addresses.",
        "input_schema": {
            "type": "object",
            "properties": {"hostname": {"type": "string", "description": "Hostname to resolve"}},
            "required": ["hostname"],
        },
        "requires_approval": False,
    },
    "check_ssl_cert": {
        "description": "Retrieve and summarize an SSL/TLS certificate for a host.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hostname": {"type": "string"},
                "port": {"type": "integer", "default": 443},
            },
            "required": ["hostname"],
        },
        "requires_approval": False,
    },
    "parse_nmap_xml": {
        "description": "Parse nmap XML output and return a structured summary.",
        "input_schema": {
            "type": "object",
            "properties": {"xml_content": {"type": "string", "description": "Raw nmap XML"}},
            "required": ["xml_content"],
        },
        "requires_approval": True,
    },
    "list_workspace_files": {
        "description": "List files in the workspace directory.",
        "input_schema": {"type": "object", "properties": {}},
        "requires_approval": False,
    },
    "read_workspace_file": {
        "description": "Read a file from the workspace directory.",
        "input_schema": {
            "type": "object",
            "properties": {"relative_path": {"type": "string", "description": "Path relative to workspace/"}},
            "required": ["relative_path"],
        },
        "requires_approval": False,
    },
}


class ToolRegistry:
    def __init__(self) -> None:
        self._tool_groups: dict[str, list[str]] = {}
        self._definitions: dict[str, ToolDefinition] = {}
        self._load()

    def _load(self) -> None:
        settings = get_settings()
        config_path = settings.config_dir / "tools.yaml"
        with open(config_path) as f:
            data = yaml.safe_load(f)
        self._tool_groups = data.get("tool_groups", {})
        self._build_definitions()

    def _build_definitions(self) -> None:
        # Build reverse map: tool_name -> list of groups it belongs to
        tool_to_groups: dict[str, list[str]] = {}
        for group, names in self._tool_groups.items():
            for name in names:
                tool_to_groups.setdefault(name, []).append(group)

        for name, meta in _NATIVE_TOOL_META.items():
            tool_id = f"native:{name}"
            self._definitions[tool_id] = ToolDefinition(
                tool_type=ToolType.native,
                tool_id=tool_id,
                server_name=None,
                tool_name=name,
                display_name=name.replace("_", " ").title(),
                description=meta["description"],
                input_schema=meta["input_schema"],
                requires_approval=meta["requires_approval"],
                allowed_profiles=[],  # resolved by profile groups at runtime
            )

    def get_tools_for_profile(self, profile_name: str) -> list[ToolDefinition]:
        """Return tools accessible to a profile based on allowed_tool_groups in profiles.yaml."""
        settings = get_settings()
        profiles_path = settings.config_dir / "profiles.yaml"
        with open(profiles_path) as f:
            profiles_data = yaml.safe_load(f)

        profile = profiles_data.get("profiles", {}).get(profile_name, {})
        allowed_groups = profile.get("allowed_tool_groups", [])

        allowed_tool_names: set[str] = set()
        for group in allowed_groups:
            allowed_tool_names.update(self._tool_groups.get(group, []))

        result = []
        for tool_id, defn in self._definitions.items():
            if defn.tool_name in allowed_tool_names:
                result.append(defn)
        return result

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        return self._definitions.get(tool_id)
