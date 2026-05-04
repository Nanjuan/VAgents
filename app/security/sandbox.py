import re
import os
from pathlib import Path

_DEFAULT_SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|password|token|bearer)\s*[=:]\s*\S+",
]


class SandboxValidator:
    def validate_command(self, command: str, allowed_commands: list[str]) -> bool:
        base = command.split()[0] if command.strip() else ""
        return base in allowed_commands

    def validate_path(self, path: str, workspace_root: str) -> bool:
        try:
            resolved = str(Path(path).resolve())
            root = str(Path(workspace_root).resolve())
            return resolved.startswith(root)
        except Exception:
            return False

    def redact_secrets(self, text: str, patterns: list[str] | None = None) -> str:
        active = patterns if patterns is not None else _DEFAULT_SECRET_PATTERNS
        result = text
        for pattern in active:
            result = re.sub(pattern, "[REDACTED]", result)
        return result
