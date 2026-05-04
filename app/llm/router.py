from pathlib import Path
import yaml
from app.llm.base import BaseLLMProvider
from app.config.settings import get_settings


class ModelRouter:
    def __init__(self) -> None:
        self._models: dict = {}
        self._providers: dict[str, BaseLLMProvider] = {}
        self._load_models()

    def _load_models(self) -> None:
        settings = get_settings()
        config_path = settings.config_dir / "models.yaml"
        with open(config_path) as f:
            data = yaml.safe_load(f)
        self._models = data.get("models", {})

    def _build_provider(self, provider_name: str, model_cfg: dict) -> BaseLLMProvider:
        # Cache key includes provider name and any custom base_url
        cache_key = f"{provider_name}:{model_cfg.get('base_url', '')}"
        if cache_key in self._providers:
            return self._providers[cache_key]

        settings = get_settings()
        provider: BaseLLMProvider

        if provider_name == "anthropic":
            from app.llm.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(api_key=settings.anthropic_api_key)
        elif provider_name == "openai":
            from app.llm.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key=settings.openai_api_key)
        elif provider_name == "ollama":
            from app.llm.ollama_provider import OllamaProvider
            provider = OllamaProvider(base_url=settings.ollama_base_url)
        elif provider_name == "openai_compatible":
            from app.llm.openai_compatible_provider import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(
                base_url=model_cfg["base_url"],
                api_key=model_cfg.get("api_key", "not-needed"),
            )
        elif provider_name == "lmstudio":
            # OpenAI-compatible endpoint — uses LM_STUDIO_BASE_URL from settings
            from app.llm.openai_compatible_provider import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(
                base_url=settings.lm_studio_base_url,
                api_key="lm-studio",  # LM Studio ignores the key
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

        self._providers[cache_key] = provider
        return provider

    async def route(
        self,
        model_key: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        model_cfg = self._models.get(model_key)
        if not model_cfg:
            raise ValueError(f"Model key '{model_key}' not found in models.yaml")

        provider = self._build_provider(model_cfg["provider"], model_cfg)
        return await provider.chat(messages, tools, model_cfg)

    def get_provider_type(self, model_key: str) -> str:
        model_cfg = self._models.get(model_key, {})
        return model_cfg.get("provider", "unknown")

    async def route_dynamic(
        self,
        base_url: str,
        model_id: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> dict:
        """Route to any OpenAI-compatible endpoint with an explicit model id (e.g. LM Studio)."""
        from app.llm.openai_compatible_provider import OpenAICompatibleProvider
        cache_key = f"openai_compatible:{base_url}"
        if cache_key not in self._providers:
            self._providers[cache_key] = OpenAICompatibleProvider(base_url=base_url)
        provider = self._providers[cache_key]
        model_cfg = {"model_id": model_id, "max_tokens": max_tokens, "temperature": temperature}
        return await provider.chat(messages, tools, model_cfg)

    def model_supports_tools(self, model_key: str) -> bool:
        """False only for ollama models with supports_tools=false."""
        model_cfg = self._models.get(model_key, {})
        provider = model_cfg.get("provider", "")
        if provider == "ollama":
            return bool(model_cfg.get("supports_tools", False))
        # anthropic, openai, openai_compatible, lmstudio all use OpenAI-format tool calling
        return True
