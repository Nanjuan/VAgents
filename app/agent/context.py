from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    project_id: str
    profile_name: str
    model_key: str
    messages: list[dict] = Field(default_factory=list)
    pending_tool_calls: list[dict] = Field(default_factory=list)
    max_turns: int = 20
    # Resolved in chat API from models.yaml + optional client override (clamped)
    max_tokens: int = 8192
    # When set, bypasses model_key and routes directly to LM Studio with this model id
    lmstudio_model_id: str | None = None
    # True: resume after tool approvals — do not append a new user message
    continuation: bool = False
