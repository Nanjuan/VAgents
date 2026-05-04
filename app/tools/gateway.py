import logging
import uuid

from app.security.approvals import ApprovalManager
from app.tools.manager import NativeToolManager
from app.tools.schemas import ToolCallResult, ToolDefinition

logger = logging.getLogger(__name__)


def _split_tool_id(tool_id: str) -> tuple[str, str | None, str]:
    """Returns tool_type, server_name or None, short tool name for ApprovalRequest."""
    if tool_id.startswith("native:"):
        return "native", None, tool_id[len("native:") :]
    if tool_id.startswith("mcp:"):
        rest = tool_id[4:]
        dot = rest.find(".")
        if dot == -1:
            return "mcp", None, rest
        return "mcp", rest[:dot], rest[dot + 1 :]
    return "unknown", None, tool_id


class ToolGateway:
    def __init__(
        self,
        native_manager: NativeToolManager,
        mcp_manager,  # MCPClientManager — avoid circular import
        safety_config: dict,
    ) -> None:
        self._native = native_manager
        self._mcp = mcp_manager
        self._safety = safety_config
        # In-memory store for pending approvals; keyed by approval_id
        self._pending: dict[str, dict] = {}

    async def list_tools(self, profile_name: str) -> list[ToolDefinition]:
        native_tools = self._native.list_tools(profile_name)
        mcp_tools: list[ToolDefinition] = []
        if self._mcp is not None:
            try:
                mcp_tools = await self._mcp.list_tools_for_profile(profile_name)
            except Exception as e:
                logger.warning("MCP list_tools failed for profile %s: %s", profile_name, e)
        return native_tools + mcp_tools

    async def request_tool_call(
        self,
        profile_name: str,
        tool_id: str,
        arguments: dict,
        reason: str,
        session=None,
        project_id: str | None = None,
        tool_call_id: str | None = None,
    ) -> dict:
        all_tools = await self.list_tools(profile_name)
        tool_map = {t.tool_id: t for t in all_tools}
        tool_def = tool_map.get(tool_id)

        if not tool_def:
            return {"status": "error", "error": f"Tool '{tool_id}' not available for profile '{profile_name}'"}

        if tool_def.requires_approval:
            if session is not None and project_id is not None:
                tt, sn, tn = _split_tool_id(tool_id)
                am = ApprovalManager()
                req = am.create_request(
                    project_id,
                    tt,
                    sn,
                    tn,
                    arguments,
                    reason,
                    session,
                    profile_name=profile_name,
                    tool_id=tool_id,
                    tool_call_id=tool_call_id,
                )
                return {"status": "pending_approval", "approval_id": req.id}

            approval_id = str(uuid.uuid4())
            self._pending[approval_id] = {
                "profile_name": profile_name,
                "tool_id": tool_id,
                "arguments": arguments,
                "reason": reason,
            }
            return {"status": "pending_approval", "approval_id": approval_id}

        return {"status": "ready", "approval_id": None}

    async def execute_tool_call(
        self,
        approval_id: str | None,
        profile_name: str,
        tool_id: str,
        arguments: dict,
    ) -> ToolCallResult:
        if tool_id.startswith("native:"):
            return await self._native.execute(tool_id, arguments, profile_name)

        if tool_id.startswith("mcp:"):
            # format: mcp:{server_name}.{tool_name}
            remainder = tool_id[len("mcp:"):]
            dot_idx = remainder.find(".")
            if dot_idx == -1:
                return ToolCallResult(
                    tool_id=tool_id, status="error", error="Invalid MCP tool_id format", duration_ms=0
                )
            server_name = remainder[:dot_idx]
            tool_name = remainder[dot_idx + 1:]

            all_tools = await self.list_tools(profile_name)
            tool_def = next((t for t in all_tools if t.tool_id == tool_id), None)
            limit = 20000
            if tool_def is None:
                return ToolCallResult(
                    tool_id=tool_id, status="error", error=f"Tool '{tool_id}' not found", duration_ms=0
                )

            import time
            start = time.monotonic()
            raw = await self._mcp.call_tool(server_name, tool_name, arguments, profile_name, limit)
            duration_ms = int((time.monotonic() - start) * 1000)

            return ToolCallResult(
                tool_id=tool_id,
                status=raw.get("status", "error"),
                result=raw.get("content"),
                error=raw.get("error"),
                duration_ms=duration_ms,
            )

        return ToolCallResult(
            tool_id=tool_id, status="error", error=f"Unknown tool_id prefix: {tool_id}", duration_ms=0
        )

    async def approve_tool_call(self, approval_id: str) -> ToolCallResult:
        pending = self._pending.pop(approval_id, None)
        if not pending:
            return ToolCallResult(
                tool_id="",
                status="error",
                error=f"Approval ID '{approval_id}' not found or already resolved",
                duration_ms=0,
            )
        return await self.execute_tool_call(
            approval_id=None,
            profile_name=pending["profile_name"],
            tool_id=pending["tool_id"],
            arguments=pending["arguments"],
        )
