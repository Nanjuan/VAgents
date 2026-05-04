import time
from app.tools.registry import ToolRegistry
from app.tools.runner import NativeToolRunner
from app.tools.validators import validate_tool_arguments
from app.tools.schemas import ToolDefinition, ToolCallResult


class NativeToolManager:
    def __init__(self) -> None:
        self._registry = ToolRegistry()
        self._runner = NativeToolRunner()

    def list_tools(self, profile_name: str) -> list[ToolDefinition]:
        return self._registry.get_tools_for_profile(profile_name)

    async def execute(
        self,
        tool_id: str,
        arguments: dict,
        profile_name: str,
    ) -> ToolCallResult:
        tool_def = self._registry.get_tool(tool_id)
        if not tool_def:
            return ToolCallResult(
                tool_id=tool_id,
                status="error",
                result=None,
                error=f"Tool '{tool_id}' not found",
                duration_ms=0,
            )

        valid, msg = validate_tool_arguments(tool_def, arguments)
        if not valid:
            return ToolCallResult(
                tool_id=tool_id,
                status="error",
                result=None,
                error=f"Validation error: {msg}",
                duration_ms=0,
            )

        start = time.monotonic()
        raw = await self._runner.run(tool_def.tool_name, arguments)
        duration_ms = int((time.monotonic() - start) * 1000)

        return ToolCallResult(
            tool_id=tool_id,
            status=raw.get("status", "error"),
            result=raw.get("result"),
            error=raw.get("error"),
            duration_ms=duration_ms,
        )
