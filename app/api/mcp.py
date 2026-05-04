import json
import re
import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.agent.memory import AgentMemory
from app.config.settings import get_settings
from app.db.database import get_session
from app.db.models import ApprovalRequest, Project
from app.mcp_client.client_manager import MCPClientManager
from app.security.approvals import ApprovalManager
from app.security.audit_service import record_approval_event, record_tool_run
from app.tools.gateway import ToolGateway
from app.tools.manager import NativeToolManager

router = APIRouter()

# ── YAML helpers ──────────────────────────────────────────────────────────────

def _config_path() -> Path:
    return get_settings().config_dir / "mcp_servers.yaml"


def _read_yaml() -> dict:
    path = _config_path()
    with open(path) as f:
        return yaml.safe_load(f) or {"mcp_servers": {}}


def _write_yaml(data: dict) -> None:
    with open(_config_path(), "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _valid_name(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9_]{0,63}$", name))


# ── Request models ────────────────────────────────────────────────────────────

class MCPServerBody(BaseModel):
    enabled: bool = True
    description: str = ""
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    url: str | None = None
    headers_env: dict[str, str] = {}
    allowed_profiles: list[str] = []
    require_approval: bool = True
    timeout_seconds: int = 60
    tool_output_limit_chars: int = 20000


class MCPToolCallBody(BaseModel):
    profile_name: str
    server_name: str
    tool_name: str
    arguments: dict
    reason: str


# ── Builder helpers ───────────────────────────────────────────────────────────

def _build_mcp_manager() -> MCPClientManager:
    return MCPClientManager()


def _build_gateway() -> ToolGateway:
    return ToolGateway(NativeToolManager(), _build_mcp_manager(), {})


# ── MCP Server CRUD ───────────────────────────────────────────────────────────

@router.get("/mcp/servers")
async def list_servers():
    data = _read_yaml()
    servers = []
    for name, cfg in data.get("mcp_servers", {}).items():
        servers.append({"name": name, **cfg})
    return {"servers": servers}


@router.get("/mcp/servers/{server_name}")
async def get_server(server_name: str):
    data = _read_yaml()
    cfg = data.get("mcp_servers", {}).get(server_name)
    if not cfg:
        raise HTTPException(404, f"Server '{server_name}' not found")
    return {"name": server_name, **cfg}


@router.post("/mcp/servers", status_code=201)
async def create_server(name: str, body: MCPServerBody):
    if not _valid_name(name):
        raise HTTPException(400, "Name must be lowercase letters/numbers/underscores, start with a letter, max 64 chars")
    data = _read_yaml()
    servers = data.setdefault("mcp_servers", {})
    if name in servers:
        raise HTTPException(409, f"Server '{name}' already exists")
    servers[name] = body.model_dump(exclude_none=False)
    _write_yaml(data)
    return {"name": name, **servers[name]}


@router.put("/mcp/servers/{server_name}")
async def update_server(server_name: str, body: MCPServerBody):
    data = _read_yaml()
    servers = data.get("mcp_servers", {})
    if server_name not in servers:
        raise HTTPException(404, f"Server '{server_name}' not found")
    servers[server_name] = body.model_dump(exclude_none=False)
    _write_yaml(data)
    return {"name": server_name, **servers[server_name]}


@router.delete("/mcp/servers/{server_name}", status_code=204)
async def delete_server(server_name: str):
    data = _read_yaml()
    servers = data.get("mcp_servers", {})
    if server_name not in servers:
        raise HTTPException(404, f"Server '{server_name}' not found")
    del servers[server_name]
    _write_yaml(data)


@router.patch("/mcp/servers/{server_name}/toggle")
async def toggle_server(server_name: str):
    data = _read_yaml()
    servers = data.get("mcp_servers", {})
    if server_name not in servers:
        raise HTTPException(404, f"Server '{server_name}' not found")
    servers[server_name]["enabled"] = not servers[server_name].get("enabled", True)
    _write_yaml(data)
    return {"name": server_name, "enabled": servers[server_name]["enabled"]}


@router.post("/mcp/servers/{server_name}/test")
async def test_server(server_name: str):
    mgr = _build_mcp_manager()
    result = await mgr.test_server(server_name)
    return result


@router.get("/mcp/servers/{server_name}/tools")
async def discover_server_tools(server_name: str):
    mgr = _build_mcp_manager()
    result = await mgr.test_server(server_name)
    return result


# ── MCP Tool calling ──────────────────────────────────────────────────────────

@router.get("/mcp/tools")
async def list_mcp_tools(profile: str | None = None):
    mgr = _build_mcp_manager()
    if profile:
        tools = await mgr.list_tools_for_profile(profile)
        return {"tools": [t.model_dump() for t in tools]}
    return {"tools": [], "note": "Provide ?profile=<name> to list tools for a profile"}


@router.post("/mcp/tools/call")
async def call_mcp_tool(
    body: MCPToolCallBody,
    session: Session = Depends(get_session),
):
    tool_id = f"mcp:{body.server_name}.{body.tool_name}"
    gateway = _build_gateway()
    gate_result = await gateway.request_tool_call(
        body.profile_name, tool_id, body.arguments, body.reason
    )
    if gate_result.get("status") == "pending_approval":
        return {"status": "pending_approval", "approval_id": gate_result["approval_id"]}
    if gate_result.get("status") == "error":
        raise HTTPException(status_code=400, detail=gate_result.get("error"))
    result = await gateway.execute_tool_call(None, body.profile_name, tool_id, body.arguments)
    return result.model_dump()


# ── Approval endpoints ────────────────────────────────────────────────────────

@router.post("/mcp/approvals/{approval_id}/approve")
async def approve_tool(approval_id: str, session: Session = Depends(get_session)):
    req = session.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(400, detail=f"Approval already {req.status}")

    mgr = ApprovalManager()
    mgr.approve(approval_id, session)

    args = json.loads(req.arguments_json) if req.arguments_json else {}
    tid = req.tool_id or ""
    if not tid:
        tid = (
            f"mcp:{req.server_name}.{req.tool_name}"
            if req.server_name
            else f"native:{req.tool_name}"
        )

    profile_name = (req.profile_name or "").strip()
    if not profile_name:
        proj = session.get(Project, req.project_id)
        profile_name = proj.active_profile if proj else "general_assistant"

    gateway = _build_gateway()
    result = await gateway.execute_tool_call(None, profile_name, tid, args)
    record_tool_run(
        session,
        req.project_id,
        profile_name,
        tid,
        args,
        result,
        approved_by_user=True,
    )

    mem = AgentMemory()
    mem.save_message(
        req.project_id,
        "tool",
        json.dumps({"result": result.result, "error": result.error}),
        session,
        tool_call_id=req.tool_call_id,
        tool_name=tid,
        tool_args=args,
    )
    record_approval_event(session, req.project_id, approval_id, "approved")

    return {
        "status": "approved",
        "approval_id": req.id,
        "tool_result": result.model_dump(),
    }


@router.post("/mcp/approvals/{approval_id}/deny")
async def deny_tool(approval_id: str, session: Session = Depends(get_session)):
    req = session.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(400, detail=f"Approval already {req.status}")

    mgr = ApprovalManager()
    mgr.deny(approval_id, session)

    args = json.loads(req.arguments_json) if req.arguments_json else {}
    tid = req.tool_id or ""
    if not tid:
        tid = (
            f"mcp:{req.server_name}.{req.tool_name}"
            if req.server_name
            else f"native:{req.tool_name}"
        )

    mem = AgentMemory()
    mem.save_message(
        req.project_id,
        "tool",
        json.dumps({"error": "User denied this tool call.", "denied": True}),
        session,
        tool_call_id=req.tool_call_id,
        tool_name=tid,
        tool_args=args,
    )
    record_approval_event(session, req.project_id, approval_id, "denied")
    return {"status": "denied", "approval_id": approval_id}


@router.get("/mcp/approvals/{project_id}/pending")
async def get_pending_approvals(project_id: str, session: Session = Depends(get_session)):
    mgr = ApprovalManager()
    pending = mgr.get_pending(project_id, session)
    return {"approvals": [p.model_dump() for p in pending]}
