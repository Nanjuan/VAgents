from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.db.database import create_db_and_tables
from app.api import chat, tools, mcp, profiles, projects, audit, lmstudio


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(title="VAgents", version="0.1.0", lifespan=lifespan)

app.include_router(chat.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(profiles.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(lmstudio.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return RedirectResponse(url="/ui/index.html")


@app.middleware("http")
async def no_cache_for_ui(request: Request, call_next):
    """Disable caching for the static UI bundle so updates always reach the browser."""
    response = await call_next(request)
    if request.url.path.startswith("/ui/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/ui", StaticFiles(directory="frontend"), name="ui")
