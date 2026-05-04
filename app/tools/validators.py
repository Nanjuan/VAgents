from app.tools.schemas import ToolDefinition

_TRAVERSAL_PATTERNS = ["../", "..\\", "%2e%2e", "%252e"]


def validate_tool_arguments(tool_def: ToolDefinition, arguments: dict) -> tuple[bool, str]:
    schema = tool_def.input_schema
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in arguments:
            return False, f"Missing required argument: {field}"

    for key, value in arguments.items():
        if key not in properties:
            return False, f"Unexpected argument: {key}"
        if isinstance(value, str):
            for pattern in _TRAVERSAL_PATTERNS:
                if pattern in value.lower():
                    return False, f"Path traversal detected in argument '{key}'"

    return True, ""
