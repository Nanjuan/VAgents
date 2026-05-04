import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config.settings import get_settings

router = APIRouter(prefix="/lmstudio", tags=["lmstudio"])


def _v1_url() -> str:
    """e.g. http://localhost:1234/v1"""
    return get_settings().lm_studio_base_url.rstrip("/")


def _root_url() -> str:
    """e.g. http://localhost:1234 — used for management API endpoints."""
    url = _v1_url()
    # Strip trailing /v1 so management endpoints resolve correctly
    if url.endswith("/v1"):
        return url[:-3]
    return url


async def _get(path: str, base: str | None = None, timeout: float = 8.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{base or _v1_url()}{path}")
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict, base: str | None = None, timeout: float = 30.0) -> dict:
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{base or _v1_url()}{path}", json=body)
        r.raise_for_status()
        return r.json()


@router.get("/status")
async def lmstudio_status():
    """Check whether LM Studio is reachable and return basic info."""
    try:
        data = await _get("/models")
        loaded = [m["id"] for m in data.get("data", [])]
        return {
            "available": True,
            "base_url": _v1_url(),
            "loaded_models": loaded,
        }
    except httpx.ConnectError:
        return {"available": False, "base_url": _v1_url(), "error": "Connection refused — is LM Studio running?"}
    except Exception as e:
        return {"available": False, "base_url": _v1_url(), "error": str(e)}


@router.get("/models")
async def list_models():
    """List models currently loaded in LM Studio (via GET /v1/models)."""
    try:
        data = await _get("/models")
    except httpx.ConnectError:
        raise HTTPException(503, "LM Studio not reachable. Start LM Studio and enable the local server.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, str(e))

    models = [
        {
            "id": m["id"],
            "object": m.get("object", "model"),
            "owned_by": m.get("owned_by", "lmstudio"),
        }
        for m in data.get("data", [])
    ]
    return {"models": models, "count": len(models), "endpoint": _v1_url()}


class LoadRequest(BaseModel):
    model_id: str
    context_length: int = 32768
    gpu_offload: int = -1   # -1 = auto (offload as much as fits in VRAM)


@router.post("/load")
async def load_model(body: LoadRequest):
    """
    Load a model in LM Studio (requires LM Studio 0.3+ with REST API enabled).
    Falls back gracefully if the endpoint is not available (older LM Studio).
    """
    # LM Studio 0.3+ exposes a management API on a separate port or path.
    # The standard /v1 endpoint does not support loading; we try the known paths.
    # Management API lives at root (e.g. http://localhost:1234), not under /v1
    root = _root_url()
    load_paths = [
        # LM Studio 0.3.x management API
        ("/api/v0/models/load", {"identifier": body.model_id, "contextLength": body.context_length, "gpuOffload": body.gpu_offload}),
        # Fallback: some builds use this path
        ("/v0/models/load", {"model": body.model_id}),
    ]

    last_error = ""
    for path, payload in load_paths:
        try:
            result = await _post(path, payload, base=root, timeout=60.0)
            return {"status": "loaded", "model_id": body.model_id, "detail": result}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                last_error = f"{path} not found"
                continue
            raise HTTPException(e.response.status_code, e.response.text)
        except httpx.ConnectError:
            raise HTTPException(503, "LM Studio not reachable.")
        except Exception as e:
            last_error = str(e)
            continue

    # If load endpoint doesn't exist, the model can still be used if already loaded.
    # Return a soft success so the frontend can still attempt to chat.
    return {
        "status": "load_api_unavailable",
        "model_id": body.model_id,
        "message": "Load API not found (LM Studio < 0.3 or REST API not enabled). "
                   "Select the model manually in LM Studio, then use it here.",
        "last_error": last_error,
    }
