import httpx
from app.llm.base import BaseLLMProvider


def _to_ollama_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _parse_tool_calls(raw: list[dict]) -> list[dict]:
    """Normalize Ollama tool_calls → internal format [{name, arguments, id}]."""
    result = []
    for i, tc in enumerate(raw):
        fn = tc.get("function", {})
        result.append({
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments", {}),
            "id": f"ollama-{i}",
        })
    return result


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        model_config: dict,
    ) -> dict:
        supports_tools = model_config.get("supports_tools", False)
        timeout = float(model_config.get("timeout_seconds", 300))

        payload: dict = {
            "model": model_config.get("model_id", "llama3.3:70b"),
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": model_config.get("max_tokens", 8192),
                "temperature": model_config.get("temperature", 0.7),
                "num_ctx": model_config.get("context_length", 32768),
            },
        }

        if tools and supports_tools:
            payload["tools"] = _to_ollama_tools(tools)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        msg = data.get("message", {})
        content = msg.get("content", "")
        raw_tool_calls = msg.get("tool_calls")

        parsed_tool_calls = _parse_tool_calls(raw_tool_calls) if raw_tool_calls else None

        return {
            "content": content,
            "tool_calls": parsed_tool_calls,
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        }

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def list_local_models(self) -> list[str]:
        """Return model names available on this Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
