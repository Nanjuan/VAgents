from typing import Any


def normalize_mcp_result(raw: Any, limit_chars: int) -> dict:
    if raw is None:
        return {"status": "success", "content": None}

    # MCP SDK returns a CallToolResult with .content list of TextContent/ImageContent etc.
    if hasattr(raw, "isError") and raw.isError:
        error_text = _extract_text(raw)
        return {"status": "error", "error": _truncate(error_text, limit_chars)}

    if hasattr(raw, "content"):
        content = _extract_text(raw)
        return {"status": "success", "content": _truncate(content, limit_chars)}

    # Plain string or dict fallback
    text = str(raw)
    return {"status": "success", "content": _truncate(text, limit_chars)}


def _extract_text(raw: Any) -> str:
    parts = []
    content_list = getattr(raw, "content", None)
    if content_list is None:
        return str(raw)
    for item in content_list:
        if hasattr(item, "text"):
            parts.append(item.text)
        else:
            parts.append(str(item))
    return "\n".join(parts)


def _truncate(text: str, limit: int) -> str:
    if len(text) > limit:
        return text[:limit] + f"\n[truncated at {limit} chars]"
    return text
