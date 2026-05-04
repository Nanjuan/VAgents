from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db.database import get_session
from app.db.models import Project
from app.agent.orchestrator import AgentOrchestrator
from app.agent.context import AgentContext
from app.agent.memory import AgentMemory
from app.agent.profile_manager import ProfileManager
from app.llm.router import ModelRouter
from app.tools.manager import NativeToolManager
from app.tools.gateway import ToolGateway
from app.mcp_client.client_manager import MCPClientManager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    profile_name: str | None = None
    lmstudio_model: str | None = None  # model id from LM Studio, overrides profile default


def _build_orchestrator() -> AgentOrchestrator:
    model_router = ModelRouter()
    native_manager = NativeToolManager()
    mcp_manager = MCPClientManager()
    gateway = ToolGateway(native_manager, mcp_manager, {})
    profile_manager = ProfileManager()
    memory = AgentMemory()
    return AgentOrchestrator(model_router, gateway, profile_manager, memory)


@router.post("/chat/{project_id}")
async def chat(
    project_id: str,
    body: ChatRequest,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    profile_name = body.profile_name or project.active_profile
    profile_mgr = ProfileManager()
    if not profile_mgr.validate_profile(profile_name):
        raise HTTPException(status_code=400, detail=f"Profile '{profile_name}' not found")

    import yaml
    from app.config.settings import get_settings
    settings = get_settings()
    with open(settings.config_dir / "models.yaml") as f:
        models_data = yaml.safe_load(f)
    with open(settings.config_dir / "profiles.yaml") as f:
        profiles_data = yaml.safe_load(f)

    profile_cfg = profiles_data["profiles"][profile_name]
    model_key = profile_cfg.get("default_model", "local-default")

    context = AgentContext(
        project_id=project_id,
        profile_name=profile_name,
        model_key=model_key,
        lmstudio_model_id=body.lmstudio_model or None,
    )

    orchestrator = _build_orchestrator()
    result = await orchestrator.run_turn(context, body.message, session)
    return result


@router.get("/chat/{project_id}/history")
async def get_history(
    project_id: str,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    memory = AgentMemory()
    history = memory.load_history(project_id, session)
    return {"project_id": project_id, "messages": history}
