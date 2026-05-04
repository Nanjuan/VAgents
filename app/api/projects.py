from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import Project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    active_profile: str = "general_assistant"


@router.get("/projects")
async def list_projects(session: Session = Depends(get_session)):
    projects = session.exec(select(Project)).all()
    return {"projects": [p.model_dump() for p in projects]}


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectCreate,
    session: Session = Depends(get_session),
):
    project = Project(
        name=body.name,
        description=body.description,
        active_profile=body.active_profile,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project.model_dump()


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    session.delete(project)
    session.commit()
