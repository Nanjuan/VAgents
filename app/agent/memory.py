import json
from sqlmodel import Session, select
from app.db.models import ChatMessage


class AgentMemory:
    def save_message(
        self,
        project_id: str,
        role: str,
        content: str,
        session: Session,
        tool_name: str | None = None,
        tool_args: dict | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            project_id=project_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_args_json=json.dumps(tool_args) if tool_args else None,
        )
        session.add(msg)
        session.commit()
        session.refresh(msg)
        return msg

    def load_history(
        self,
        project_id: str,
        session: Session,
        limit: int = 50,
    ) -> list[dict]:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.project_id == project_id)
            .order_by(ChatMessage.created_at)  # type: ignore[arg-type]
        )
        rows = session.exec(statement).all()
        # Take last `limit` rows
        rows = list(rows)[-limit:]

        messages = []
        for row in rows:
            if row.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "content": row.content,
                        "tool_name": row.tool_name,
                    }
                )
            else:
                messages.append({"role": row.role, "content": row.content})
        return messages
