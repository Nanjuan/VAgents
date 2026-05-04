# VAgents Build Progress

## Status: Phase 1 Complete — Backend Core

## Completed
- [x] pyproject.toml + .env.example + Dockerfile + docker-compose.yml
- [x] app/config/settings.py + all YAML configs
- [x] app/db/database.py + app/db/models.py
- [x] app/llm/ — base, router, anthropic, openai, ollama, openai_compatible providers
- [x] app/tools/ — schemas, registry, runner, validators, manager, gateway
- [x] app/mcp_client/ — schemas, permissions, result_normalizer, tool_adapter, client_manager, server_registry
- [x] app/mcp_servers/examples/ — notes, project_files, cybersecurity_lab, website_design
- [x] app/agent/ — context, memory, prompts, profile_manager, orchestrator
- [x] app/security/ — permissions, approvals, audit, sandbox
- [x] app/api/ — chat, tools, mcp, profiles, projects, audit
- [x] app/main.py
- [x] examples/ — profile YAMLs, example MCP server

## Completed (continued)
- [x] frontend/ — index.html, style.css, app.js (dark theme, split layout)
- [x] app/main.py updated to serve /ui/* static files, / redirects to /ui/index.html

## Completed (continued)
- [x] app/api/mcp.py — full CRUD: list, get, create, update, delete, toggle, discover tools per server
- [x] app/api/tools.py — GET /api/tools/native catalog endpoint
- [x] frontend — Tools tab: server list with toggles, server detail, tool discovery, add/edit form, native tool list

## Pending / Next Steps
- [ ] Tests (pytest) — tool validators, MCP result normalizer, profile permission checks
- [ ] CLI runner (`python -m vagents chat --profile cybersecurity_agent`)
- [ ] Rate limiting + auth middleware for API
- [ ] Streaming chat responses (SSE)
- [ ] README.md

## Architecture Notes (for LLM handoff)

### Data flow
User → POST /api/chat/{project_id} → AgentOrchestrator.run_turn() → ModelRouter → LLMProvider
→ if tool_calls → ToolGateway → NativeToolManager or MCPClientManager → result back to model
→ final content → save via AgentMemory → return to caller

### Tool ID format
- Native: `native:{tool_name}` e.g. `native:http_get_headers`
- MCP: `mcp:{server_name}.{tool_name}` e.g. `mcp:cybersecurity_lab_tools.summarize_security_headers`

### Profile permission chain
profiles.yaml allowed_mcp_tools → PermissionChecker.check_profile_can_use_tool() → ToolGateway → MCPClientManager

### Approval flow
ToolGateway.request_tool_call() → if requires_approval → ApprovalManager.create_request() → return pending
→ user calls POST /api/mcp/approvals/{id}/approve → ToolGateway.approve_tool_call() → execute

### Adding a new LLM provider
1. Create app/llm/{name}_provider.py implementing BaseLLMProvider
2. Add to ModelRouter._build_provider()
3. Add model entry to models.yaml

### Adding a new MCP server
1. Create server in app/mcp_servers/examples/{name}_server.py using FastMCP
2. Add config block to app/config/mcp_servers.yaml
3. Add to allowed_mcp_servers/allowed_mcp_tools in relevant profiles in profiles.yaml

### Key files for cybersecurity agent
- Profile config: app/config/profiles.yaml → cybersecurity_agent
- MCP server: app/mcp_servers/examples/cybersecurity_lab_server.py
- MCP config: app/config/mcp_servers.yaml → cybersecurity_lab_tools
- Safety rules: app/config/safety.yaml
