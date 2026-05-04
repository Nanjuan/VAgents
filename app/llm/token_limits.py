"""Shared limits for chat completion max_tokens (client override + models.yaml)."""

MIN_CHAT_MAX_TOKENS = 256
MAX_CHAT_MAX_TOKENS = 262_144
DEFAULT_MAX_TOKENS = 8192
LMSTUDIO_YAML_KEY = "lmstudio-default"


def clamp_max_tokens(n: int) -> int:
    return max(MIN_CHAT_MAX_TOKENS, min(MAX_CHAT_MAX_TOKENS, int(n)))


def yaml_default_max_tokens(models_data: dict, model_key: str) -> int:
    entry = (models_data or {}).get("models", {}).get(model_key) or {}
    raw = entry.get("max_tokens", DEFAULT_MAX_TOKENS)
    try:
        return clamp_max_tokens(int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MAX_TOKENS


def resolve_effective_max_tokens(body_value: int | None, models_data: dict, model_key: str) -> int:
    """Prefer explicit request value; else models.yaml for profile's model_key."""
    if body_value is not None:
        try:
            return clamp_max_tokens(int(body_value))
        except (TypeError, ValueError):
            pass
    return yaml_default_max_tokens(models_data, model_key)
