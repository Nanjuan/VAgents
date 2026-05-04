"use strict";

const API = "";
const APP_VERSION = "3";

let projects = [];
let profiles = [];
let activeProject = null;
let sending = false;
let activeLmStudioModel = null;
let activeServerName = null;
let editingServerName = null;

const dom = {};

const REQUIRED_IDS = [
  "chat-list", "messages", "msg-input", "send-btn",
  "chat-title", "chat-badge",
  "new-chat-btn", "new-chat-form", "new-chat-name",
  "new-chat-profile", "new-chat-confirm", "new-chat-cancel",
];

function $(id) {
  return dom[id] || null;
}

function bindClick(id, handler) {
  const el = $(id);
  if (el) el.addEventListener("click", handler);
}

function bindEvent(id, evt, handler) {
  const el = $(id);
  if (el) el.addEventListener(evt, handler);
}

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  if (res.status === 204 || res.headers.get("content-length") === "0") return {};
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}

async function fetchProfiles() {
  try { return (await api("GET", "/api/profiles")).profiles; }
  catch { return []; }
}
async function fetchProjects() {
  try { return (await api("GET", "/api/projects")).projects; }
  catch { return []; }
}

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(raw) {
  const parts = String(raw ?? "").split(/(```[\s\S]*?```)/g);
  return parts.map((part, i) => {
    if (i % 2 === 1) {
      const inner = part.replace(/^```\w*\n?/, "").replace(/```$/, "");
      return `<pre><code>${esc(inner.trimEnd())}</code></pre>`;
    }
    let t = esc(part);
    t = t.replace(/`([^`\n]+)`/g, (_, c) => `<code>${c}</code>`);
    t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    t = t.replace(/\n/g, "<br>");
    return t;
  }).join("");
}

function scrollToBottom() {
  const m = $("messages");
  if (m) m.scrollTop = m.scrollHeight;
}

function showEmptyIfNeeded() {
  const m = $("messages");
  if (!m) return;
  if (!m.children.length) {
    m.innerHTML = `<div class="empty-state"><div class="empty-icon">⬡</div><p>No messages yet</p></div>`;
  }
}

function appendUserBubble(text) {
  const m = $("messages");
  if (!m) return;
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `
    <div class="msg-label">You</div>
    <div class="msg-bubble">${esc(text)}</div>
  `;
  m.appendChild(row);
}

function appendAssistantBubble(text) {
  const m = $("messages");
  if (!m) return;
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  const agentName = activeProject?.active_profile ?? "agent";
  row.innerHTML = `
    <div class="msg-label">${esc(agentName)}</div>
    <div class="msg-bubble">${renderMarkdown(text)}</div>
  `;
  m.appendChild(row);
}

function appendToolCard(tc) {
  const m = $("messages");
  if (!m) return;
  const card = document.createElement("div");
  card.className = "tool-card";
  const durationText = tc.duration_ms ? `${tc.duration_ms}ms` : "";
  const resultStr = tc.result !== undefined ? JSON.stringify(tc.result, null, 2) : "";
  const bodyContent = resultStr || (tc.error ? `Error: ${tc.error}` : "(no output)");
  card.innerHTML = `
    <div class="tool-card-header">
      <div class="tool-dot"></div>
      <span class="tool-name">${esc(tc.tool_id)}</span>
      <span class="tool-status">${esc(durationText)}</span>
      <span class="tool-chevron">▶</span>
    </div>
    <div class="tool-card-body"><pre>${esc(bodyContent)}</pre></div>
  `;
  card.querySelector(".tool-card-header").addEventListener("click", () => card.classList.toggle("open"));
  m.appendChild(card);
}

function appendApprovalCard(req) {
  const m = $("messages");
  if (!m) return;
  const card = document.createElement("div");
  card.className = "approval-card";
  card.innerHTML = `
    <div class="approval-title">⚠ Approval Required</div>
    <div class="approval-tool">${esc(req.tool_id)}</div>
    <div class="approval-actions">
      <button class="btn-approve">Approve</button>
      <button class="btn-deny">Deny</button>
    </div>
  `;
  card.querySelector(".btn-approve").addEventListener("click", async () => {
    card.querySelector(".approval-actions").innerHTML = `<span class="status-muted">Approving…</span>`;
    try {
      const r = await api("POST", `/api/mcp/approvals/${req.approval_id}/approve`);
      card.querySelector(".approval-actions").innerHTML = `<span class="status-ok">✓ Approved</span>`;
      if (r?.tool_result) appendToolCard({ tool_id: req.tool_id, ...r.tool_result });
    } catch (e) {
      card.querySelector(".approval-actions").innerHTML = `<span class="status-error">Failed: ${esc(e.message)}</span>`;
    }
  });
  card.querySelector(".btn-deny").addEventListener("click", async () => {
    card.querySelector(".approval-actions").innerHTML = `<span class="status-muted">Denying…</span>`;
    try {
      await api("POST", `/api/mcp/approvals/${req.approval_id}/deny`);
      card.querySelector(".approval-actions").innerHTML = `<span class="status-error">✗ Denied</span>`;
    } catch (e) {
      card.querySelector(".approval-actions").innerHTML = `<span class="status-error">Failed: ${esc(e.message)}</span>`;
    }
  });
  m.appendChild(card);
}

function appendTyping() {
  const m = $("messages");
  if (!m) return null;
  const row = document.createElement("div");
  row.className = "typing-row";
  row.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div><span>Thinking…</span>`;
  m.appendChild(row);
  return row;
}

function renderChatList() {
  const list = $("chat-list");
  if (!list) return;
  list.innerHTML = "";
  if (!projects.length) {
    list.innerHTML = `<div class="sidebar-hint">No chats yet</div>`;
    return;
  }
  projects.forEach(p => {
    const item = document.createElement("div");
    item.className = "chat-item" + (activeProject?.id === p.id ? " active" : "");
    item.dataset.id = p.id;
    item.innerHTML = `
      <div class="chat-item-name">${esc(p.name)}</div>
      <div class="chat-item-meta">${esc(p.active_profile)}</div>
    `;
    item.addEventListener("click", () => selectProject(p));
    list.appendChild(item);
  });
}

function populateProfileSelect() {
  const sel = $("new-chat-profile");
  if (!sel) return;
  sel.innerHTML = profiles.map(p => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
}

async function createChat() {
  const nameEl = $("new-chat-name");
  const profileEl = $("new-chat-profile");
  if (!nameEl || !profileEl) return;
  const name = nameEl.value.trim();
  if (!name) { nameEl.focus(); return; }
  const profile = profileEl.value || profiles[0] || "general_assistant";
  try {
    const project = await api("POST", "/api/projects", { name, active_profile: profile });
    projects.unshift(project);
    $("new-chat-form")?.classList.add("hidden");
    nameEl.value = "";
    renderChatList();
    selectProject(project);
  } catch (e) {
    alert("Could not create chat: " + e.message);
  }
}

async function selectProject(project) {
  activeProject = project;
  renderChatList();

  const title = $("chat-title");
  const badge = $("chat-badge");
  if (title) title.textContent = project.name;
  if (badge) {
    badge.textContent = activeLmStudioModel
      ? `LM Studio: ${activeLmStudioModel}`
      : project.active_profile;
  }

  const input = $("msg-input");
  const send = $("send-btn");
  if (input) input.disabled = false;
  if (send) send.disabled = false;

  const m = $("messages");
  if (m) m.innerHTML = "";
  showEmptyIfNeeded();

  try {
    const { messages: history } = await api("GET", `/api/chat/${project.id}/history`);
    if (m) m.innerHTML = "";
    history.forEach(msg => {
      if (msg.role === "user") appendUserBubble(msg.content);
      else if (msg.role === "assistant" && msg.content) appendAssistantBubble(msg.content);
    });
    showEmptyIfNeeded();
    scrollToBottom();
  } catch (e) {
    console.error("[VAgents] history load failed:", e);
  }

  input?.focus();
}

async function sendMessage() {
  if (sending || !activeProject) return;
  const input = $("msg-input");
  const send = $("send-btn");
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;

  sending = true;
  input.value = "";
  input.style.height = "";
  if (send) send.disabled = true;
  input.disabled = true;

  const m = $("messages");
  const empty = m?.querySelector(".empty-state");
  if (empty) empty.remove();

  appendUserBubble(text);
  const typingEl = appendTyping();
  scrollToBottom();

  try {
    const chatBody = { message: text, profile_name: activeProject.active_profile };
    if (activeLmStudioModel) chatBody.lmstudio_model = activeLmStudioModel;
    const result = await api("POST", `/api/chat/${activeProject.id}`, chatBody);
    typingEl?.remove();

    if (result.tool_calls_made?.length) {
      result.tool_calls_made.forEach(tc => appendToolCard(tc));
    }
    if (result.requires_approval?.length) {
      result.requires_approval.forEach(req => appendApprovalCard(req));
    }
    if (result.content) appendAssistantBubble(result.content);
  } catch (e) {
    typingEl?.remove();
    appendAssistantBubble(`⚠️ Error: ${e.message}`);
  }

  sending = false;
  if (send) send.disabled = false;
  input.disabled = false;
  input.focus();
  scrollToBottom();
}

function switchTab(tab) {
  const tabChat = $("tab-chat");
  const tabTools = $("tab-tools");
  const chatPanel = $("chat-panel");
  const toolsPanel = $("tools-panel");
  const chatMain = $("chat-main");
  const toolsMain = $("tools-main");
  if (!tabChat || !tabTools || !chatPanel || !toolsPanel || !chatMain || !toolsMain) return;

  if (tab === "chat") {
    tabChat.classList.add("active");
    tabTools.classList.remove("active");
    chatPanel.classList.remove("hidden");
    toolsPanel.classList.add("hidden");
    chatMain.classList.remove("hidden");
    toolsMain.classList.add("hidden");
  } else {
    tabTools.classList.add("active");
    tabChat.classList.remove("active");
    toolsPanel.classList.remove("hidden");
    chatPanel.classList.add("hidden");
    toolsMain.classList.remove("hidden");
    chatMain.classList.add("hidden");
    loadToolsView();
  }
}

async function loadToolsView() {
  await Promise.all([loadServerList(), loadNativeTools()]);
}

async function loadServerList() {
  const list = $("server-list");
  if (!list) return;
  try {
    const data = await api("GET", "/api/mcp/servers");
    renderServerList(data.servers);
  } catch (e) {
    list.innerHTML = `<div class="sidebar-hint status-error">Failed to load: ${esc(e.message)}</div>`;
  }
}

function renderServerList(servers) {
  const list = $("server-list");
  if (!list) return;
  list.innerHTML = "";
  if (!servers.length) {
    list.innerHTML = `<div class="sidebar-hint">No servers configured</div>`;
    return;
  }
  servers.forEach(s => {
    const item = document.createElement("div");
    item.className = "server-item" + (activeServerName === s.name ? " active" : "");
    item.dataset.name = s.name;
    item.innerHTML = `
      <div class="server-dot ${s.enabled ? "on" : "off"}"></div>
      <div class="server-item-name">${esc(s.name)}</div>
      <div class="server-item-meta">${esc(s.transport || "")}</div>
      <label class="toggle" title="${s.enabled ? "Disable" : "Enable"}">
        <input type="checkbox" ${s.enabled ? "checked" : ""} />
        <span class="toggle-slider"></span>
      </label>
    `;
    item.querySelector("input[type=checkbox]").addEventListener("change", async (e) => {
      e.stopPropagation();
      try {
        await api("PATCH", `/api/mcp/servers/${s.name}/toggle`);
        await loadServerList();
      } catch (err) { alert("Toggle failed: " + err.message); }
    });
    item.addEventListener("click", (e) => {
      if (e.target.closest("label.toggle")) return;
      selectServer(s.name);
    });
    list.appendChild(item);
  });
}

async function selectServer(name) {
  activeServerName = name;
  editingServerName = null;
  const data = await api("GET", "/api/mcp/servers");
  renderServerList(data.servers);
  showPanel("detail");

  try {
    const s = await api("GET", `/api/mcp/servers/${name}`);
    const sdName = $("sd-name");
    const sdBadge = $("sd-badge");
    const sdMeta = $("sd-meta");
    const sdToolsList = $("sd-tools-list");
    if (sdName) sdName.textContent = s.name;
    if (sdBadge) sdBadge.textContent = s.transport;
    if (sdMeta) {
      sdMeta.innerHTML = `
        <div class="sd-meta-item"><strong>Enabled:</strong> ${s.enabled ? "yes" : "no"}</div>
        <div class="sd-meta-item"><strong>Approval:</strong> ${s.require_approval ? "required" : "auto"}</div>
        <div class="sd-meta-item"><strong>Timeout:</strong> ${s.timeout_seconds}s</div>
        <div class="sd-meta-item"><strong>Profiles:</strong> ${(s.allowed_profiles || []).join(", ") || "none"}</div>
        ${s.command ? `<div class="sd-meta-item"><strong>Command:</strong> <code>${esc(s.command)} ${(s.args || []).join(" ")}</code></div>` : ""}
        ${s.url ? `<div class="sd-meta-item"><strong>URL:</strong> ${esc(s.url)}</div>` : ""}
        <div class="sd-meta-item"><strong>Description:</strong> ${esc(s.description || "—")}</div>
      `;
    }
    if (sdToolsList) sdToolsList.innerHTML = `<div class="status-muted">Click "Discover tools" to connect and list tools.</div>`;
    const sdDiscoverBtn = $("sd-discover-btn");
    const sdEditBtn = $("sd-edit-btn");
    const sdDeleteBtn = $("sd-delete-btn");
    if (sdDiscoverBtn) sdDiscoverBtn.onclick = () => discoverTools(name);
    if (sdEditBtn) sdEditBtn.onclick = () => openEditForm(s);
    if (sdDeleteBtn) sdDeleteBtn.onclick = () => confirmDelete(name);
  } catch (e) {
    const sdMeta = $("sd-meta");
    if (sdMeta) sdMeta.innerHTML = `<span class="status-error">${esc(e.message)}</span>`;
  }
}

async function discoverTools(name) {
  const sdToolsList = $("sd-tools-list");
  if (!sdToolsList) return;
  sdToolsList.innerHTML = `<div class="status-muted">Connecting…</div>`;
  try {
    const result = await api("POST", `/api/mcp/servers/${name}/test`);
    if (result.status !== "ok") {
      sdToolsList.innerHTML = `<div class="status-error">Error: ${esc(result.error || "unknown")}</div>`;
      return;
    }
    if (!result.tools?.length) {
      sdToolsList.innerHTML = `<div class="status-muted">Server connected but no tools found.</div>`;
      return;
    }
    sdToolsList.innerHTML = "";
    result.tools.forEach(t => {
      const card = document.createElement("div");
      card.className = "tool-def-card";
      const schema = JSON.stringify(t.inputSchema || t.input_schema || {}, null, 2);
      card.innerHTML = `
        <div class="tool-def-name">${esc(t.name)}</div>
        <div class="tool-def-desc">${esc(t.description || "")}</div>
        <pre class="tool-def-schema">${esc(schema)}</pre>
      `;
      sdToolsList.appendChild(card);
    });
  } catch (e) {
    sdToolsList.innerHTML = `<div class="status-error">${esc(e.message)}</div>`;
  }
}

async function confirmDelete(name) {
  if (!confirm(`Delete server "${name}"? This cannot be undone.`)) return;
  try {
    await api("DELETE", `/api/mcp/servers/${name}`);
    activeServerName = null;
    showPanel("empty");
    await loadServerList();
  } catch (e) { alert("Delete failed: " + e.message); }
}

function openAddForm() {
  editingServerName = null;
  setFormValues({
    title: "Add MCP Server",
    name: "",
    nameDisabled: false,
    description: "",
    transport: "stdio",
    command: "python",
    args: [],
    url: "",
    allowed_profiles: profiles,
    env: {},
    require_approval: true,
    timeout_seconds: 60,
    tool_output_limit_chars: 20000,
  });
  toggleTransportFields("stdio");
  showPanel("form");
}

function openEditForm(s) {
  editingServerName = s.name;
  setFormValues({
    title: `Edit: ${s.name}`,
    name: s.name,
    nameDisabled: true,
    description: s.description || "",
    transport: s.transport || "stdio",
    command: s.command || "",
    args: s.args || [],
    url: s.url || "",
    allowed_profiles: s.allowed_profiles || [],
    env: s.env || {},
    require_approval: s.require_approval !== false,
    timeout_seconds: s.timeout_seconds || 60,
    tool_output_limit_chars: s.tool_output_limit_chars || 20000,
  });
  toggleTransportFields(s.transport || "stdio");
  showPanel("form");
}

function setFormValues(v) {
  const refs = {
    title: $("sf-title"),
    name: $("sf-name"),
    desc: $("sf-desc"),
    transport: $("sf-transport"),
    command: $("sf-command"),
    args: $("sf-args"),
    url: $("sf-url"),
    profiles: $("sf-profiles"),
    env: $("sf-env"),
    approval: $("sf-approval"),
    timeout: $("sf-timeout"),
    limit: $("sf-limit"),
    msg: $("sf-msg"),
  };
  if (refs.title) refs.title.textContent = v.title;
  if (refs.name) {
    refs.name.value = v.name;
    refs.name.disabled = !!v.nameDisabled;
  }
  if (refs.desc) refs.desc.value = v.description;
  if (refs.transport) refs.transport.value = v.transport;
  if (refs.command) refs.command.value = v.command;
  if (refs.args) refs.args.value = (v.args || []).join("\n");
  if (refs.url) refs.url.value = v.url;
  if (refs.profiles) refs.profiles.value = (v.allowed_profiles || []).join("\n");
  if (refs.env) {
    refs.env.value = Object.entries(v.env || {}).map(([k, x]) => `${k}=${x}`).join("\n");
  }
  if (refs.approval) refs.approval.checked = !!v.require_approval;
  if (refs.timeout) refs.timeout.value = String(v.timeout_seconds);
  if (refs.limit) refs.limit.value = String(v.tool_output_limit_chars);
  if (refs.msg) {
    refs.msg.textContent = "";
    refs.msg.className = "";
  }
}

function toggleTransportFields(transport) {
  const stdio = $("sf-stdio");
  const http = $("sf-http");
  if (!stdio || !http) return;
  if (transport === "stdio") {
    stdio.classList.remove("hidden");
    http.classList.add("hidden");
  } else {
    stdio.classList.add("hidden");
    http.classList.remove("hidden");
  }
}

async function saveServer() {
  const sfMsg = $("sf-msg");
  if (sfMsg) {
    sfMsg.textContent = "";
    sfMsg.className = "";
  }

  const sfName = $("sf-name");
  const sfTransport = $("sf-transport");
  const sfDesc = $("sf-desc");
  const sfCommand = $("sf-command");
  const sfArgs = $("sf-args");
  const sfUrl = $("sf-url");
  const sfProfiles = $("sf-profiles");
  const sfEnv = $("sf-env");
  const sfApproval = $("sf-approval");
  const sfTimeout = $("sf-timeout");
  const sfLimit = $("sf-limit");
  const sfSaveBtn = $("sf-save-btn");
  if (!sfName || !sfTransport) return;

  const name = sfName.value.trim();
  if (!editingServerName && !name) {
    if (sfMsg) {
      sfMsg.className = "error";
      sfMsg.textContent = "Name is required";
    }
    return;
  }

  const envObj = {};
  (sfEnv?.value || "").trim().split("\n").filter(Boolean).forEach(line => {
    const idx = line.indexOf("=");
    if (idx > 0) envObj[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  });

  const transport = sfTransport.value;
  const body = {
    enabled: true,
    description: sfDesc?.value.trim() || "",
    transport,
    command: transport === "stdio" ? (sfCommand?.value.trim() || null) : null,
    args: transport === "stdio"
      ? (sfArgs?.value || "").trim().split("\n").map(s => s.trim()).filter(Boolean)
      : [],
    url: transport !== "stdio" ? (sfUrl?.value.trim() || null) : null,
    headers_env: {},
    env: envObj,
    allowed_profiles: (sfProfiles?.value || "").trim().split("\n").map(s => s.trim()).filter(Boolean),
    require_approval: !!sfApproval?.checked,
    timeout_seconds: parseInt(sfTimeout?.value || "60") || 60,
    tool_output_limit_chars: parseInt(sfLimit?.value || "20000") || 20000,
  };

  if (sfSaveBtn) sfSaveBtn.disabled = true;
  try {
    if (editingServerName) {
      await api("PUT", `/api/mcp/servers/${editingServerName}`, body);
      if (sfMsg) { sfMsg.className = "ok"; sfMsg.textContent = "Saved ✓"; }
      activeServerName = editingServerName;
    } else {
      await api("POST", `/api/mcp/servers?name=${encodeURIComponent(name)}`, body);
      if (sfMsg) { sfMsg.className = "ok"; sfMsg.textContent = "Created ✓"; }
      activeServerName = name;
    }
    await loadServerList();
    setTimeout(() => selectServer(activeServerName), 400);
  } catch (e) {
    if (sfMsg) { sfMsg.className = "error"; sfMsg.textContent = e.message; }
  } finally {
    if (sfSaveBtn) sfSaveBtn.disabled = false;
  }
}

async function loadNativeTools() {
  const list = $("native-list");
  if (!list) return;
  try {
    const data = await api("GET", "/api/tools/native");
    list.innerHTML = "";
    data.tools.forEach(t => {
      const el = document.createElement("div");
      el.className = "native-tool-item";
      el.title = t.description;
      el.textContent = t.name;
      list.appendChild(el);
    });
  } catch { /* silent */ }
}

function showPanel(which) {
  const detail = $("server-detail");
  const form = $("server-form");
  const empty = $("tools-empty");
  if (!detail || !form || !empty) return;
  detail.classList.add("hidden");
  form.classList.add("hidden");
  empty.classList.add("hidden");
  if (which === "detail") detail.classList.remove("hidden");
  else if (which === "form") form.classList.remove("hidden");
  else empty.classList.remove("hidden");
}

async function lmRefreshModels() {
  const lmDot = $("lms-dot");
  const lmMsg = $("lms-msg");
  const lmSelect = $("lms-select");
  const lmLoadBtn = $("lms-load-btn");
  const lmUseBtn = $("lms-use-btn");
  if (!lmDot || !lmMsg || !lmSelect || !lmLoadBtn || !lmUseBtn) return;

  lmDot.className = "";
  lmMsg.className = "";
  lmMsg.textContent = "Connecting…";
  lmSelect.disabled = true;
  lmLoadBtn.disabled = true;
  lmUseBtn.disabled = true;
  lmSelect.innerHTML = "";

  try {
    const data = await api("GET", "/api/lmstudio/models");
    lmDot.className = "online";
    if (!data.models.length) {
      lmSelect.innerHTML = `<option value="">No models loaded in LM Studio</option>`;
      lmMsg.textContent = "Load a model in LM Studio first.";
      return;
    }
    lmSelect.innerHTML = data.models.map(m =>
      `<option value="${esc(m.id)}">${esc(m.id)}</option>`
    ).join("");
    lmSelect.disabled = false;
    lmLoadBtn.disabled = false;
    lmUseBtn.disabled = false;
    lmMsg.textContent = `${data.count} model${data.count !== 1 ? "s" : ""} available`;
    if (activeLmStudioModel) {
      const opt = [...lmSelect.options].find(o => o.value === activeLmStudioModel);
      if (opt) lmSelect.value = activeLmStudioModel;
    }
  } catch (e) {
    lmDot.className = "offline";
    lmSelect.innerHTML = `<option value="">— not connected —</option>`;
    lmMsg.className = "error";
    lmMsg.textContent = e.message.includes("503")
      ? "LM Studio not running or local server disabled"
      : `Error: ${e.message}`;
  }
}

async function lmLoadModel() {
  const lmSelect = $("lms-select");
  const lmMsg = $("lms-msg");
  const lmLoadBtn = $("lms-load-btn");
  if (!lmSelect || !lmMsg || !lmLoadBtn) return;
  const modelId = lmSelect.value;
  if (!modelId) return;
  lmMsg.className = "";
  lmMsg.textContent = `Loading ${modelId}…`;
  lmLoadBtn.disabled = true;
  try {
    const result = await api("POST", "/api/lmstudio/load", { model_id: modelId });
    if (result.status === "loaded") {
      lmMsg.className = "ok";
      lmMsg.textContent = "Loaded ✓";
    } else if (result.status === "load_api_unavailable") {
      lmMsg.className = "";
      lmMsg.textContent = "Load API unavailable — select model manually in LM Studio.";
    }
  } catch (e) {
    lmMsg.className = "error";
    lmMsg.textContent = `Load failed: ${e.message}`;
  } finally {
    lmLoadBtn.disabled = false;
  }
}

function lmUseModel() {
  const lmSelect = $("lms-select");
  const lmMsg = $("lms-msg");
  const badge = $("lms-badge");
  const chatBadge = $("chat-badge");
  if (!lmSelect || !lmMsg || !badge) return;
  const modelId = lmSelect.value;
  if (!modelId) return;
  activeLmStudioModel = modelId;
  badge.textContent = `Using: ${modelId}`;
  badge.classList.add("visible");
  lmMsg.className = "ok";
  lmMsg.textContent = "Active — next message will use this model";
  if (activeProject && chatBadge) chatBadge.textContent = `LM Studio: ${modelId}`;
}

async function autoProbeLm() {
  try {
    const status = await api("GET", "/api/lmstudio/status");
    if (status.available) {
      await lmRefreshModels();
    } else {
      const lmDot = $("lms-dot");
      const lmMsg = $("lms-msg");
      if (lmDot) lmDot.className = "offline";
      if (lmMsg) lmMsg.textContent = "Not running — click ⟳ to retry";
    }
  } catch { /* silent */ }
}

function bindAll() {
  bindClick("new-chat-btn", () => {
    const form = $("new-chat-form");
    const nameEl = $("new-chat-name");
    if (!form) return;
    form.classList.toggle("hidden");
    if (!form.classList.contains("hidden")) nameEl?.focus();
  });
  bindClick("new-chat-cancel", () => {
    $("new-chat-form")?.classList.add("hidden");
    const n = $("new-chat-name");
    if (n) n.value = "";
  });
  bindClick("new-chat-confirm", createChat);
  bindEvent("new-chat-name", "keydown", e => {
    if (e.key === "Enter") createChat();
  });

  bindClick("send-btn", sendMessage);
  bindEvent("msg-input", "keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendMessage();
    }
  });
  bindEvent("msg-input", "input", () => {
    const input = $("msg-input");
    if (!input) return;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });

  bindClick("tab-chat", () => switchTab("chat"));
  bindClick("tab-tools", () => switchTab("tools"));

  bindClick("add-server-btn", openAddForm);
  bindClick("sf-save-btn", saveServer);
  bindClick("sf-cancel-btn", () => {
    if (activeServerName) showPanel("detail");
    else showPanel("empty");
  });
  bindEvent("sf-transport", "change", () => {
    const t = $("sf-transport");
    if (t) toggleTransportFields(t.value);
  });

  bindClick("lms-refresh", lmRefreshModels);
  bindClick("lms-load-btn", lmLoadModel);
  bindClick("lms-use-btn", lmUseModel);
}

function checkRequiredDom() {
  const missing = REQUIRED_IDS.filter(id => !dom[id]);
  if (missing.length) {
    console.warn("[VAgents] Missing required DOM ids — likely a stale cached page. Hard-reload (Cmd+Shift+R). Missing:", missing);
    return false;
  }
  return true;
}

async function boot() {
  document.querySelectorAll("[id]").forEach(el => { dom[el.id] = el; });
  if (!checkRequiredDom()) return;

  bindAll();

  try {
    [profiles, projects] = await Promise.all([fetchProfiles(), fetchProjects()]);
  } catch (e) {
    console.error("[VAgents] init failed:", e);
    profiles = [];
    projects = [];
  }
  populateProfileSelect();
  renderChatList();
  autoProbeLm();
}

console.info(`[VAgents] app.js v${APP_VERSION} loaded`);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
