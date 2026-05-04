from contextlib import asynccontextmanager
from fastapi import FastAPI
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


app.mount("/ui", StaticFiles(directory="frontend"), name="ui")
