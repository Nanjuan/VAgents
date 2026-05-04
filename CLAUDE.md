# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (requires uv)
uv pip install -e .

# Run the API server
uvicorn app.main:app --reload --port 8000

# Docker
docker-compose up --build

# Run a single MCP server manually (for testing)
python app/mcp_servers/examples/cybersecurity_lab_server.py

# Lint
ruff check app/
ruff format app/

# Interactive API docs
open http://localhost:8000/docs
```

No test suite yet — see PROGRESS.md for pending items.

## Architecture

VAgents is a local-first AI agent platform. Agents are configured via YAML profiles and communicate with LLMs through a model router. All tool access — both native Python tools and external MCP tools — flows exclusively through `ToolGateway`.

### Request data flow

```
POST /api/chat/{project_id}
  → AgentOrchestrator.run_turn()
    → ProfileManager (loads profile from profiles.yaml)
    → ModelRouter → LLMProvider (Anthropic / OpenAI / Ollama)
    → if tool_calls returned:
        → ToolGateway.request_tool_call()
            → if requires_approval: store in _pending dict, return approval_id
            → else: ToolGateway.execute_tool_call()
                → native:{name}  → NativeToolRunner
                → mcp:{server}.{tool} → MCPClientManager → stdio/http MCP server
        → result appended to messages, model called again (max 10 iterations)
    → final content saved via AgentMemory → returned to caller
```

### Tool ID format

All tools have a namespaced ID used throughout the system:
- Native: `native:http_get_headers`, `native:dns_lookup`, `native:check_ssl_cert`
- MCP: `mcp:cybersecurity_lab_tools.summarize_security_headers`

When passed to LLMs, `:` and `.` are replaced with `_` (e.g. `mcp_cybersecurity_lab_tools_summarize_security_headers`) and mapped back via `tool_id_map` in `orchestrator.py`.

### Profile system

Profiles in `app/config/profiles.yaml` define the agent's identity, model, and permissions. They control:
- `allowed_tool_groups` — which native tool groups are accessible
- `allowed_mcp_servers` — which MCP servers can be connected
- `allowed_mcp_tools` — explicit allowlist of `server.tool` pairs

The cybersecurity profile (`cybersecurity_agent`) is the primary profile. Its persona is "Sentinel" and it exclusively uses `cybersecurity_lab_tools` and `local_filesystem` MCP servers.

### MCP integration

MCP servers run as subprocesses (`stdio` transport). Each tool call opens a fresh `ClientSession` via the MCP Python SDK, calls the tool, and closes the session. There is no persistent connection — this avoids zombie processes but adds ~100ms overhead per call.

MCP servers are defined in `app/config/mcp_servers.yaml`. `cybersecurity_lab_tools` is enabled by default; `website_design_tools` is disabled.

### Approval workflow

Tools with `require_approval: true` in their MCP config, or native tools in sensitive groups, are intercepted by `ToolGateway.request_tool_call()`. The pending call is stored in `ToolGateway._pending` (in-memory, per-process). The orchestrator returns `requires_approval` list to the API caller. The caller must POST to `/api/mcp/approvals/{id}/approve` to execute.

### LLM provider routing

`ModelRouter` maps model keys (e.g. `paid-anthropic`, `local-default`) from `models.yaml` to provider instances. Anthropic provider uses prompt caching (`cache_control: ephemeral` on system message). Ollama has no native tool calling — the orchestrator falls back to JSON block detection in the model's text output.

## Key files for cybersecurity agent

| Purpose | File |
|---|---|
| Profile config | `app/config/profiles.yaml` → `cybersecurity_agent` |
| MCP server impl | `app/mcp_servers/examples/cybersecurity_lab_server.py` |
| MCP config | `app/config/mcp_servers.yaml` → `cybersecurity_lab_tools` |
| Safety rules | `app/config/safety.yaml` |
| Native security tools | `app/tools/runner.py` → `parse_nmap_xml`, `check_ssl_cert`, `dns_lookup` |

## Extending the platform

**Add a new LLM provider:**
1. Create `app/llm/{name}_provider.py` implementing `BaseLLMProvider` (`app/llm/base.py`)
2. Register in `ModelRouter._build_provider()` (`app/llm/router.py`)
3. Add model entry to `app/config/models.yaml`

**Add a new MCP server:**
1. Create `app/mcp_servers/examples/{name}_server.py` using `FastMCP` from `mcp.server.fastmcp`
2. Add a config block to `app/config/mcp_servers.yaml`
3. Add the server and tool names to `allowed_mcp_servers` / `allowed_mcp_tools` in the relevant profile(s) in `app/config/profiles.yaml`

**Add a new native tool:**
1. Implement the function in `app/tools/runner.py` returning `{"status": "success"|"error", "result": ..., "error": ...}`
2. Add a tool group entry in `app/config/tools.yaml`
3. Add to `allowed_tool_groups` in the profile

## Config files quick reference

| File | Purpose |
|---|---|
| `app/config/models.yaml` | Model key → provider + model_id mapping |
| `app/config/profiles.yaml` | Agent personas, permissions, rules |
| `app/config/mcp_servers.yaml` | MCP server definitions and enable/disable |
| `app/config/tools.yaml` | Native tool group definitions |
| `app/config/safety.yaml` | MCP transport and behavior safety rules |

## Local models (Ollama — 75GB GPU)

With 75GB VRAM you can run 70B models at Q4 quantization (~40GB). Pull the model once:

```bash
ollama pull llama3.3:70b        # recommended — best tool calling
ollama pull qwen2.5:72b         # alternative — strong reasoning
ollama pull deepseek-r1:70b     # best reasoning, no tool calling (slow)
```

Model keys in `app/config/models.yaml`:

| Key | Model | VRAM | Tool calling |
|---|---|---|---|
| `local-llama70b` | llama3.3:70b | ~40GB | Yes |
| `local-qwen72b` | qwen2.5:72b | ~41GB | Yes |
| `local-deepseek70b` | deepseek-r1:70b | ~40GB | No (text only) |
| `local-default` | llama3.2 | ~3GB | No |

The cybersecurity profile defaults to `local-llama70b`. To switch model:
```yaml
# app/config/profiles.yaml
cybersecurity_agent:
  default_model: local-qwen72b   # change here
```

Check what's pulled and reachable: `GET /api/models/ollama`

**How tool calling works with Ollama:** The provider sends tools in OpenAI-compatible format. Models with `supports_tools: true` return structured `tool_calls` in the response. Models with `supports_tools: false` fall back to JSON block detection in the text output. The `deepseek-r1` model uses `<think>` blocks — don't set `supports_tools: true` for it.

## Environment variables

Copy `.env.example` to `.env`. For fully local operation no API keys are needed:
```
OLLAMA_BASE_URL=http://localhost:11434
```

For Anthropic/OpenAI fallback:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Frontend

Served at `http://localhost:8000/ui/index.html` (or `/` redirects there). Three static files — no build step required:

| File | Purpose |
|---|---|
| `frontend/index.html` | Shell — sidebar + main layout |
| `frontend/style.css` | Dark theme (CSS variables in `:root`) |
| `frontend/app.js` | Vanilla JS — all API calls, message rendering, approval cards |

FastAPI mounts the directory via `StaticFiles(directory="frontend")` at `/ui`.

The agent label in assistant bubbles comes from `activeProject.active_profile` (set at runtime).

## LM Studio integration (primary local backend)

Set `LM_STUDIO_BASE_URL=http://localhost:1234/v1` in `.env` (default value — change if LM Studio runs on a different port).

**In LM Studio:** Settings → Local Server → enable "Start Server on Launch". The `/v1/models` endpoint lists models that are currently loaded into memory.

**API endpoints:**
- `GET /api/lmstudio/status` — reachability check + loaded model list
- `GET /api/lmstudio/models` — full model list (used by sidebar panel)
- `POST /api/lmstudio/load` — body `{model_id, context_length?, gpu_offload?}` — calls LM Studio 0.3+ management API; returns `load_api_unavailable` if the endpoint doesn't exist (older builds)

**Provider type `lmstudio` in models.yaml** — all profiles default to `lmstudio-default`. This uses `OpenAICompatibleProvider` pointed at `LM_STUDIO_BASE_URL` (default `http://localhost:1234/v1`) and calls `POST /v1/chat/completions` — the correct OpenAI-compatible endpoint. The `model_id` in the yaml is a placeholder; LM Studio uses whatever model is loaded. The "Use" button in the sidebar overrides the model_id via `AgentContext.lmstudio_model_id` → `ModelRouter.route_dynamic()`.

**Do NOT point `OLLAMA_BASE_URL` at LM Studio's port.** The Ollama provider calls `/api/chat` (Ollama format); LM Studio only understands `/v1/chat/completions` (OpenAI format). They are incompatible.

**Frontend flow:** The LM Studio panel at the bottom of the sidebar auto-probes on page load. Click ⟳ to refresh. "Load" calls the load API. "Use" sets the global `activeLmStudioModel` variable — all subsequent messages include `lmstudio_model` in the request body until the page is refreshed or the model is cleared.

## What's pending

See `PROGRESS.md` for current build status. Tests, streaming (SSE), and CLI runner are pending.
