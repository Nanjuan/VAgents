# VAgents

Local-first AI agent platform with MCP tool support. Primary profile: cybersecurity agent (Sentinel).

## Quick start

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY or OPENAI_API_KEY

uv pip install -e .
uvicorn app.main:app --reload
```

API available at http://localhost:8000. Docs at http://localhost:8000/docs.

## Docker

```bash
docker-compose up --build
```

## Project structure

```
app/
  config/       YAML configs (models, tools, profiles, MCP servers, safety)
  agent/        Orchestrator, memory, prompts, profile manager
  llm/          Anthropic, OpenAI, Ollama, OpenAI-compatible providers
  tools/        Native tool registry, runner, gateway
  mcp_client/   MCP SDK client — connects to MCP servers
  mcp_servers/  Example FastMCP servers (notes, files, cybersecurity, design)
  security/     Approvals, audit, permissions, sandbox
  api/          FastAPI routes
  db/           SQLModel models + SQLite
workspace/      Files accessible to agents
```

## Profiles

| Profile | Name | Default Model |
|---------|------|---------------|
| cybersecurity_agent | Sentinel | claude-sonnet-4-6 |
| general_assistant | Atlas | llama3.2 (local) |
| coding_agent | Dev | claude-sonnet-4-6 |

## Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/projects | Create a project |
| POST | /api/chat/{project_id} | Send a message |
| GET | /api/chat/{project_id}/history | Chat history |
| GET | /api/profiles | List profiles |
| GET | /api/mcp/servers | List MCP servers |
| POST | /api/mcp/approvals/{id}/approve | Approve a tool call |

See PROGRESS.md for architecture notes and next steps.
