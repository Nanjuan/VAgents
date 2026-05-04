import openai
from app.llm.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**kwargs)

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        converted = []
        for t in tools:
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema") or t.get("parameters", {"type": "object", "properties": {}}),
                    },
                }
            )
        return converted

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: dict,
    ) -> dict:
        kwargs: dict = {
            "model": model_config.get("model_id", "gpt-4o"),
            "max_tokens": model_config.get("max_tokens", 8192),
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = self._convert_tools(tools)
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        content_text = message.content or ""
        tool_calls = None

        if message.tool_calls:
            import json
            tool_calls = []
            for tc in message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                )

        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }

        return {"content": content_text, "tool_calls": tool_calls, "usage": usage}

    async def is_available(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False
