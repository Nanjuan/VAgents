from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    project_id: str
    profile_name: str
    model_key: str
    messages: list[dict] = Field(default_factory=list)
    pending_tool_calls: list[dict] = Field(default_factory=list)
    max_turns: int = 20
    # When set, bypasses model_key and routes directly to LM Studio with this model id
    lmstudio_model_id: str | None = None
