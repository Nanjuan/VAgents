from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db.database import get_session
from app.tools.manager import NativeToolManager
from app.tools.gateway import ToolGateway
from app.mcp_client.client_manager import MCPClientManager

router = APIRouter()


class ToolCallBody(BaseModel):
    profile_name: str
    tool_id: str
    arguments: dict
    reason: str


def _build_gateway() -> ToolGateway:
    native = NativeToolManager()
    mcp = MCPClientManager()
    return ToolGateway(native, mcp, {})


_NATIVE_CATALOG = [
    {"name": "http_get_headers", "group": "general", "description": "Fetch HTTP response headers from a URL.", "args": {"url": "string"}},
    {"name": "dns_lookup", "group": "security", "description": "Resolve a hostname to IP addresses.", "args": {"hostname": "string"}},
    {"name": "check_ssl_cert", "group": "security", "description": "Inspect TLS certificate details for a host.", "args": {"hostname": "string", "port": "int (default 443)"}},
    {"name": "parse_nmap_xml", "group": "security", "description": "Parse nmap XML output and summarize open ports and services.", "args": {"xml_content": "string"}},
    {"name": "list_workspace_files", "group": "files", "description": "List all files inside the local ./workspace/ directory.", "args": {}},
    {"name": "read_workspace_file", "group": "files", "description": "Read a file from ./workspace/ (max 1MB, path traversal blocked).", "args": {"relative_path": "string"}},
]


@router.get("/tools/native")
async def list_native_tools():
    return {"tools": _NATIVE_CATALOG, "count": len(_NATIVE_CATALOG)}


@router.get("/tools")
async def list_tools(profile: str | None = None):
    mgr = NativeToolManager()
    if profile:
        tools = mgr.list_tools(profile)
    else:
        # Return all unique native tools across all definitions
        from app.tools.registry import ToolRegistry
        reg = ToolRegistry()
        tools = list(reg._definitions.values())
    return {"tools": [t.model_dump() for t in tools]}


@router.post("/tools/call")
async def call_tool(
    body: ToolCallBody,
    session: Session = Depends(get_session),
):
    gateway = _build_gateway()
    gate_result = await gateway.request_tool_call(
        body.profile_name, body.tool_id, body.arguments, body.reason
    )

    if gate_result.get("status") == "pending_approval":
        return {"status": "pending_approval", "approval_id": gate_result["approval_id"]}

    if gate_result.get("status") == "error":
        raise HTTPException(status_code=400, detail=gate_result.get("error"))

    result = await gateway.execute_tool_call(
        None, body.profile_name, body.tool_id, body.arguments
    )
    return result.model_dump()
