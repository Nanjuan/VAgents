from mcp.server.fastmcp import FastMCP

mcp = FastMCP("local-notes")
NOTES: list[dict] = [{"title": "Welcome", "content": "This is your local notes store."}]


@mcp.tool()
def search_notes(query: str) -> list[dict]:
    """Search notes by keyword."""
    q = query.lower()
    return [n for n in NOTES if q in n["title"].lower() or q in n["content"].lower()]


@mcp.tool()
def add_note(title: str, content: str) -> dict:
    """Add a note."""
    note = {"title": title, "content": content}
    NOTES.append(note)
    return {"status": "success", "note": note}


@mcp.tool()
def list_notes() -> list[dict]:
    """List all notes."""
    return NOTES


if __name__ == "__main__":
    mcp.run()
