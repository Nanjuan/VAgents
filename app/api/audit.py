from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.database import get_session
from app.db.models import AuditLog, ToolRun, Project

router = APIRouter()


@router.get("/audit/{project_id}")
async def get_audit_log(
    project_id: str,
    event_type: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = select(AuditLog).where(AuditLog.project_id == project_id)
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)  # type: ignore[arg-type]

    logs = session.exec(stmt).all()
    return {"project_id": project_id, "logs": [l.model_dump() for l in logs]}


@router.get("/audit/{project_id}/tool-runs")
async def get_tool_runs(
    project_id: str,
    limit: int = 100,
    session: Session = Depends(get_session),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stmt = (
        select(ToolRun)
        .where(ToolRun.project_id == project_id)
        .order_by(ToolRun.created_at.desc())  # type: ignore[arg-type]
        .limit(limit)
    )
    runs = session.exec(stmt).all()
    return {"project_id": project_id, "tool_runs": [r.model_dump() for r in runs]}
