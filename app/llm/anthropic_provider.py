import anthropic
from app.llm.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        converted = []
        for t in tools:
            converted.append(
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema") or t.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    def _extract_system(self, messages: list[dict]) -> tuple[list[dict], str]:
        system_text = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"] if isinstance(m["content"], str) else ""
            else:
                filtered.append(m)
        return filtered, system_text

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: dict,
    ) -> dict:
        filtered_messages, system_text = self._extract_system(messages)

        # Build system with prompt caching
        system_block: list[dict] | str
        if system_text:
            system_block = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = []

        kwargs: dict = {
            "model": model_config.get("model_id", "claude-sonnet-4-6"),
            "max_tokens": model_config.get("max_tokens", 8192),
            "messages": filtered_messages,
        }
        if system_block:
            kwargs["system"] = system_block
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        response = await self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    }
                )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        return {
            "content": content_text,
            "tool_calls": tool_calls if tool_calls else None,
            "usage": usage,
        }

    async def is_available(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
