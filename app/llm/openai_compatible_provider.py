from app.llm.openai_provider import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):
    """Works with LM Studio, LocalAI, and any OpenAI-compatible server."""

    def __init__(self, base_url: str, api_key: str = "not-needed") -> None:
        super().__init__(api_key=api_key, base_url=base_url)
