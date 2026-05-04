import json
from typing import Any

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
        tool_call_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """
        tool_calls: raw list from orchestrator [{id, name, arguments}, ...] for assistant rows.
        tool_call_id: for role=tool, OpenAI tool_call id.
        """
        tjson = json.dumps(tool_calls) if tool_calls else None
        msg = ChatMessage(
            project_id=project_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_args_json=json.dumps(tool_args) if tool_args else None,
            tool_calls_json=tjson,
            tool_call_id=tool_call_id,
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
        rows = list(rows)[-limit:]

        messages: list[dict] = []
        for row in rows:
            if row.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "content": row.content,
                        "tool_call_id": row.tool_call_id or "",
                    }
                )
            elif row.role == "assistant" and row.tool_calls_json:
                try:
                    tcs = json.loads(row.tool_calls_json)
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": row.content})
                    continue
                oa_tool_calls = []
                for tc in tcs:
                    oa_tool_calls.append(
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc.get("arguments", {}))
                                if isinstance(tc.get("arguments"), dict)
                                else str(tc.get("arguments", "")),
                            },
                        }
                    )
                entry: dict = {
                    "role": "assistant",
                    "content": row.content if row.content else None,
                    "tool_calls": oa_tool_calls,
                }
                messages.append(entry)
            else:
                messages.append({"role": row.role, "content": row.content})
        return messages
