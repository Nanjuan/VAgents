from fastapi import APIRouter, HTTPException
from app.agent.profile_manager import ProfileManager
from app.tools.manager import NativeToolManager
from app.mcp_client.client_manager import MCPClientManager
from app.llm.router import ModelRouter

router = APIRouter()


@router.get("/profiles")
async def list_profiles():
    mgr = ProfileManager()
    return {"profiles": mgr.list_profiles()}


@router.get("/profiles/{name}")
async def get_profile(name: str):
    mgr = ProfileManager()
    profile = mgr.get_profile(name)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile '{name}' not found")

    native_mgr = NativeToolManager()
    native_tools = native_mgr.list_tools(name)

    mcp_mgr = MCPClientManager()
    mcp_tools = await mcp_mgr.list_tools_for_profile(name)

    return {
        "name": name,
        "profile": profile,
        "native_tools": [t.model_dump() for t in native_tools],
        "mcp_tools": [t.model_dump() for t in mcp_tools],
    }


@router.get("/models")
async def list_models():
    """Configured model keys and their Ollama availability."""
    router_inst = ModelRouter()
    models_info = []
    for key, cfg in router_inst._models.items():
        entry = {"key": key, "provider": cfg.get("provider"), "model_id": cfg.get("model_id"), "supports_tools": router_inst.model_supports_tools(key)}
        if cfg.get("provider") == "ollama":
            provider = router_inst._build_provider("ollama", cfg)
            entry["available"] = await provider.is_available()
        models_info.append(entry)
    return {"models": models_info}


@router.get("/models/ollama")
async def list_ollama_models():
    """Models actually pulled and available on the local Ollama instance."""
    from app.config.settings import get_settings
    from app.llm.ollama_provider import OllamaProvider
    settings = get_settings()
    provider = OllamaProvider(base_url=settings.ollama_base_url)
    available = await provider.is_available()
    if not available:
        return {"available": False, "models": [], "message": f"Ollama not reachable at {settings.ollama_base_url}"}
    models = await provider.list_local_models()
    return {"available": True, "ollama_url": settings.ollama_base_url, "models": models}
