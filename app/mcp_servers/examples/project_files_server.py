from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("local-filesystem")
WORKSPACE = Path("./workspace").resolve()


def safe_path(relative_path: str) -> Path | None:
    target = (WORKSPACE / relative_path).resolve()
    if not str(target).startswith(str(WORKSPACE)):
        return None
    return target


@mcp.tool()
def list_workspace_files() -> dict:
    """List all files in the workspace directory."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    files = [str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob("*") if p.is_file()]
    return {"files": files, "count": len(files)}


@mcp.tool()
def read_workspace_file(relative_path: str) -> dict:
    """Read a file from the workspace. Max 1MB."""
    target = safe_path(relative_path)
    if target is None:
        return {"status": "error", "error": "Path traversal blocked"}
    if not target.exists():
        return {"status": "error", "error": "File not found"}
    if target.stat().st_size > 1_048_576:
        return {"status": "error", "error": "File exceeds 1MB limit"}
    content = target.read_text(errors="replace")
    return {"status": "success", "path": relative_path, "content": content}


@mcp.tool()
def write_workspace_file(relative_path: str, content: str) -> dict:
    """Write content to a file in the workspace. Creates parent dirs if needed."""
    target = safe_path(relative_path)
    if target is None:
        return {"status": "error", "error": "Path traversal blocked"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return {"status": "success", "path": relative_path, "bytes_written": len(content.encode())}


@mcp.tool()
def search_workspace_files(pattern: str) -> dict:
    """Search workspace files by glob pattern (e.g. '*.py', '**/*.json')."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    matches = [str(p.relative_to(WORKSPACE)) for p in WORKSPACE.glob(pattern) if p.is_file()]
    return {"pattern": pattern, "matches": matches, "count": len(matches)}


if __name__ == "__main__":
    mcp.run()
