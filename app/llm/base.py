from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: dict,
    ) -> dict:
        """Returns {"content": str, "tool_calls": list | None, "usage": dict}"""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if provider is reachable."""
