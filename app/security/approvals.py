import json
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.db.models import ApprovalRequest


class ApprovalManager:
    def create_request(
        self,
        project_id: str,
        tool_type: str,
        server_name: str | None,
        tool_name: str,
        arguments: dict,
        reason: str,
        session: Session,
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            project_id=project_id,
            tool_type=tool_type,
            server_name=server_name,
            tool_name=tool_name,
            arguments_json=json.dumps(arguments),
            reason=reason,
            status="pending",
        )
        session.add(req)
        session.commit()
        session.refresh(req)
        return req

    def approve(self, approval_id: str, session: Session) -> ApprovalRequest:
        req = session.get(ApprovalRequest, approval_id)
        if not req:
            raise ValueError(f"Approval request {approval_id} not found")
        req.status = "approved"
        req.resolved_at = datetime.now(timezone.utc)
        session.add(req)
        session.commit()
        session.refresh(req)
        return req

    def deny(self, approval_id: str, session: Session) -> ApprovalRequest:
        req = session.get(ApprovalRequest, approval_id)
        if not req:
            raise ValueError(f"Approval request {approval_id} not found")
        req.status = "denied"
        req.resolved_at = datetime.now(timezone.utc)
        session.add(req)
        session.commit()
        session.refresh(req)
        return req

    def get_pending(self, project_id: str, session: Session) -> list[ApprovalRequest]:
        statement = select(ApprovalRequest).where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.status == "pending",
        )
        return list(session.exec(statement).all())
