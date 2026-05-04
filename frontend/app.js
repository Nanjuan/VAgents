const API = "";  // same origin

// ── State ────────────────────────────────────────────────────────────────────
let projects = [];
let profiles = [];
let activeProject = null;
let sending = false;
let activeLmStudioModel = null;

// ── DOM refs ─────────────────────────────────────────────────────────────────
const chatList       = document.getElementById("chat-list");
const messages       = document.getElementById("messages");
const msgInput       = document.getElementById("msg-input");
const sendBtn        = document.getElementById("send-btn");
const chatHeader     = document.getElementById("chat-header");
const chatTitle      = document.getElementById("chat-title");
const chatBadge      = document.getElementById("chat-badge");
const newChatBtn     = document.getElementById("new-chat-btn");
const newChatForm    = document.getElementById("new-chat-form");
const newChatName    = document.getElementById("new-chat-name");
const newChatProfile = document.getElementById("new-chat-profile");
const newChatConfirm = document.getElementById("new-chat-confirm");
const newChatCancel  = document.getElementById("new-chat-cancel");

// LM Studio panel
const lmDot         = document.getElementById("lms-dot");
const lmRefresh     = document.getElementById("lms-refresh");
const lmSelect      = document.getElementById("lms-select");
const lmLoadBtn     = document.getElementById("lms-load-btn");
const lmUseBtn      = document.getElementById("lms-use-btn");
const lmMsg         = document.getElementById("lms-msg");
const lmActiveBadge = document.getElementById("lms-badge");

// ── Boot ─────────────────────────────────────────────────────────────────────
async function init() {
  [profiles, projects] = await Promise.all([fetchProfiles(), fetchProjects()]);
  populateProfileSelect();
  renderChatList();
}

// ── API helpers ───────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

async function fetchProfiles() {
  try { return (await api("GET", "/api/profiles")).profiles; }
  catch { return []; }
}
async function fetchProjects() {
  try { return (await api("GET", "/api/projects")).projects; }
  catch { return []; }
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
function renderChatList() {
  chatList.innerHTML = "";
  if (!projects.length) {
    chatList.innerHTML = `<div style="padding:16px 14px;color:var(--text2);font-size:12px;">No chats yet</div>`;
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
    chatList.appendChild(item);
  });
}

function populateProfileSelect() {
  newChatProfile.innerHTML = profiles.map(p =>
    `<option value="${esc(p)}">${esc(p)}</option>`
  ).join("");
}

// ── New chat form ─────────────────────────────────────────────────────────────
newChatBtn.addEventListener("click", () => {
  newChatForm.classList.toggle("hidden");
  if (!newChatForm.classList.contains("hidden")) newChatName.focus();
});
newChatCancel.addEventListener("click", () => {
  newChatForm.classList.add("hidden");
  newChatName.value = "";
});
newChatConfirm.addEventListener("click", createChat);
newChatName.addEventListener("keydown", e => { if (e.key === "Enter") createChat(); });

async function createChat() {
  const name = newChatName.value.trim();
  if (!name) { newChatName.focus(); return; }
  const profile = newChatProfile.value || profiles[0] || "general_assistant";
  try {
    const project = await api("POST", "/api/projects", { name, active_profile: profile });
    projects.unshift(project);
    newChatForm.classList.add("hidden");
    newChatName.value = "";
    renderChatList();
    selectProject(project);
  } catch (e) { alert("Could not create chat: " + e.message); }
}

// ── Select project ────────────────────────────────────────────────────────────
async function selectProject(project) {
  activeProject = project;
  renderChatList();

  chatTitle.textContent = project.name;
  chatBadge.textContent = activeLmStudioModel
    ? `LM Studio: ${activeLmStudioModel}`
    : project.active_profile;

  msgInput.disabled = false;
  sendBtn.disabled = false;

  messages.innerHTML = "";
  showEmptyIfNeeded();

  try {
    const { messages: history } = await api("GET", `/api/chat/${project.id}/history`);
    messages.innerHTML = "";
    history.forEach(msg => {
      if (msg.role === "user") appendUserBubble(msg.content);
      else if (msg.role === "assistant") appendAssistantBubble(msg.content);
    });
    scrollToBottom();
  } catch (e) {
    console.error("History load failed:", e);
  }

  msgInput.focus();
}

function showEmptyIfNeeded() {
  if (!messages.children.length) {
    messages.innerHTML = `<div class="empty-state"><div class="empty-icon">⬡</div><p>No messages yet</p></div>`;
  }
}

// ── Send message ──────────────────────────────────────────────────────────────
sendBtn.addEventListener("click", sendMessage);
msgInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); sendMessage(); }
});

async function sendMessage() {
  if (sending || !activeProject) return;
  const text = msgInput.value.trim();
  if (!text) return;

  sending = true;
  msgInput.value = "";
  msgInput.style.height = "";
  sendBtn.disabled = true;
  msgInput.disabled = true;

  const empty = messages.querySelector(".empty-state");
  if (empty) empty.remove();

  appendUserBubble(text);
  const typingEl = appendTyping();
  scrollToBottom();

  try {
    const chatBody = { message: text, profile_name: activeProject.active_profile };
    if (activeLmStudioModel) chatBody.lmstudio_model = activeLmStudioModel;
    const result = await api("POST", `/api/chat/${activeProject.id}`, chatBody);

    typingEl.remove();

    if (result.tool_calls_made?.length) {
      result.tool_calls_made.forEach(tc => appendToolCard(tc));
    }
    if (result.requires_approval?.length) {
      result.requires_approval.forEach(req => appendApprovalCard(req));
    }
    if (result.content) appendAssistantBubble(result.content);

  } catch (e) {
    typingEl.remove();
    appendAssistantBubble(`⚠️ Error: ${e.message}`);
  }

  sending = false;
  sendBtn.disabled = false;
  msgInput.disabled = false;
  msgInput.focus();
  scrollToBottom();
}

// ── Message rendering ─────────────────────────────────────────────────────────
function appendUserBubble(text) {
  const row = document.createElement("div");
  row.className = "msg-row user";
  row.innerHTML = `
    <div class="msg-label">You</div>
    <div class="msg-bubble">${esc(text)}</div>
  `;
  messages.appendChild(row);
}

function appendAssistantBubble(text) {
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  const agentName = activeProject?.active_profile ?? "agent";
  row.innerHTML = `
    <div class="msg-label">${esc(agentName)}</div>
    <div class="msg-bubble">${renderMarkdown(text)}</div>
  `;
  messages.appendChild(row);
}

function appendToolCard(tc) {
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
  messages.appendChild(card);
}

function appendApprovalCard(req) {
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
    card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--text2);font-size:11px">Approving…</span>`;
    try {
      await api("POST", `/api/mcp/approvals/${req.approval_id}/approve`);
      card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--green)">✓ Approved</span>`;
    } catch (e) {
      card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--red)">Failed: ${esc(e.message)}</span>`;
    }
  });
  card.querySelector(".btn-deny").addEventListener("click", async () => {
    card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--text2);font-size:11px">Denying…</span>`;
    try {
      await api("POST", `/api/mcp/approvals/${req.approval_id}/deny`);
      card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--red)">✗ Denied</span>`;
    } catch (e) {
      card.querySelector(".approval-actions").innerHTML = `<span style="color:var(--red)">Failed: ${esc(e.message)}</span>`;
    }
  });
  messages.appendChild(card);
}

function appendTyping() {
  const row = document.createElement("div");
  row.className = "typing-row";
  row.innerHTML = `<div class="typing-dots"><span></span><span></span><span></span></div><span>Thinking…</span>`;
  messages.appendChild(row);
  return row;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(raw) {
  const parts = raw.split(/(```[\s\S]*?```)/g);
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

msgInput.addEventListener("input", () => {
  msgInput.style.height = "auto";
  msgInput.style.height = Math.min(msgInput.scrollHeight, 140) + "px";
});

// ── Tab switching ─────────────────────────────────────────────────────────────
const tabChat     = document.getElementById("tab-chat");
const tabTools    = document.getElementById("tab-tools");
const chatPanel   = document.getElementById("chat-panel");
const toolsPanel  = document.getElementById("tools-panel");
const chatMainEl  = document.getElementById("chat-main");
const toolsMainEl = document.getElementById("tools-main");
const serverList  = document.getElementById("server-list");
const nativeList  = document.getElementById("native-list");
const addServerBtn = document.getElementById("add-server-btn");

const serverDetail  = document.getElementById("server-detail");
const serverForm    = document.getElementById("server-form");
const toolsEmpty    = document.getElementById("tools-empty");
const sdName        = document.getElementById("sd-name");
const sdBadge       = document.getElementById("sd-badge");
const sdMeta        = document.getElementById("sd-meta");
const sdToolsList   = document.getElementById("sd-tools-list");
const sdDiscoverBtn = document.getElementById("sd-discover-btn");
const sdEditBtn     = document.getElementById("sd-edit-btn");
const sdDeleteBtn   = document.getElementById("sd-delete-btn");

const sfTitle       = document.getElementById("sf-title");
const sfName        = document.getElementById("sf-name");
const sfDesc        = document.getElementById("sf-desc");
const sfTransport   = document.getElementById("sf-transport");
const sfStdioFields = document.getElementById("sf-stdio");
const sfHttpFields  = document.getElementById("sf-http");
const sfCommand     = document.getElementById("sf-command");
const sfArgs        = document.getElementById("sf-args");
const sfUrl         = document.getElementById("sf-url");
const sfProfiles    = document.getElementById("sf-profiles");
const sfEnv         = document.getElementById("sf-env");
const sfApproval    = document.getElementById("sf-approval");
const sfTimeout     = document.getElementById("sf-timeout");
const sfOutputLimit = document.getElementById("sf-limit");
const sfSaveBtn     = document.getElementById("sf-save-btn");
const sfCancelBtn   = document.getElementById("sf-cancel-btn");
const sfMsg         = document.getElementById("sf-msg");

let activeServerName = null;
let editingServerName = null;

tabChat.addEventListener("click", () => switchTab("chat"));
tabTools.addEventListener("click", () => switchTab("tools"));

function switchTab(tab) {
  if (tab === "chat") {
    tabChat.classList.add("active");
    tabTools.classList.remove("active");
    chatPanel.classList.remove("hidden");
    toolsPanel.classList.add("hidden");
    chatMainEl.classList.remove("hidden");
    toolsMainEl.classList.add("hidden");
  } else {
    tabTools.classList.add("active");
    tabChat.classList.remove("active");
    toolsPanel.classList.remove("hidden");
    chatPanel.classList.add("hidden");
    toolsMainEl.classList.remove("hidden");
    chatMainEl.classList.add("hidden");
    loadToolsView();
  }
}

async function loadToolsView() {
  await Promise.all([loadServerList(), loadNativeTools()]);
}

// ── Server list ───────────────────────────────────────────────────────────────
async function loadServerList() {
  try {
    const data = await api("GET", "/api/mcp/servers");
    renderServerList(data.servers);
  } catch (e) {
    serverList.innerHTML = `<div style="padding:10px 12px;color:var(--red);font-size:12px;">Failed to load: ${esc(e.message)}</div>`;
  }
}

function renderServerList(servers) {
  serverList.innerHTML = "";
  if (!servers.length) {
    serverList.innerHTML = `<div style="padding:10px 12px;color:var(--text2);font-size:12px;">No servers configured</div>`;
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
    serverList.appendChild(item);
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
    sdName.textContent = s.name;
    sdBadge.textContent = s.transport;
    sdMeta.innerHTML = `
      <div class="sd-meta-item"><strong>Enabled:</strong> ${s.enabled ? "yes" : "no"}</div>
      <div class="sd-meta-item"><strong>Approval:</strong> ${s.require_approval ? "required" : "auto"}</div>
      <div class="sd-meta-item"><strong>Timeout:</strong> ${s.timeout_seconds}s</div>
      <div class="sd-meta-item"><strong>Profiles:</strong> ${(s.allowed_profiles || []).join(", ") || "none"}</div>
      ${s.command ? `<div class="sd-meta-item"><strong>Command:</strong> <code style="font-size:11px">${esc(s.command)} ${(s.args || []).join(" ")}</code></div>` : ""}
      ${s.url ? `<div class="sd-meta-item"><strong>URL:</strong> ${esc(s.url)}</div>` : ""}
      <div class="sd-meta-item"><strong>Description:</strong> ${esc(s.description || "—")}</div>
    `;
    sdToolsList.innerHTML = `<div style="color:var(--text2);font-size:12px;">Click "Discover Tools" to connect and list tools.</div>`;
    sdDiscoverBtn.onclick = () => discoverTools(name);
    sdEditBtn.onclick = () => openEditForm(s);
    sdDeleteBtn.onclick = () => confirmDelete(name);
  } catch (e) {
    sdMeta.innerHTML = `<span style="color:var(--red)">${esc(e.message)}</span>`;
  }
}

async function discoverTools(name) {
  sdToolsList.innerHTML = `<div style="color:var(--text2);font-size:12px;">Connecting…</div>`;
  try {
    const result = await api("POST", `/api/mcp/servers/${name}/test`);
    if (result.status !== "ok") {
      sdToolsList.innerHTML = `<div style="color:var(--red);font-size:12px;">Error: ${esc(result.error || "unknown")}</div>`;
      return;
    }
    if (!result.tools?.length) {
      sdToolsList.innerHTML = `<div style="color:var(--text2);font-size:12px;">Server connected but no tools found.</div>`;
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
    sdToolsList.innerHTML = `<div style="color:var(--red);font-size:12px;">${esc(e.message)}</div>`;
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

// ── Add / Edit server form ────────────────────────────────────────────────────
addServerBtn.addEventListener("click", () => openAddForm());

function openAddForm() {
  editingServerName = null;
  sfTitle.textContent = "Add MCP Server";
  sfName.value = "";
  sfName.disabled = false;
  sfDesc.value = "";
  sfTransport.value = "stdio";
  sfCommand.value = "python";
  sfArgs.value = "";
  sfUrl.value = "";
  sfProfiles.value = profiles.join("\n");
  sfEnv.value = "";
  sfApproval.checked = true;
  sfTimeout.value = "60";
  sfOutputLimit.value = "20000";
  sfMsg.textContent = "";
  sfMsg.className = "";
  toggleTransportFields("stdio");
  showPanel("form");
}

function openEditForm(s) {
  editingServerName = s.name;
  sfTitle.textContent = `Edit: ${s.name}`;
  sfName.value = s.name;
  sfName.disabled = true;
  sfDesc.value = s.description || "";
  sfTransport.value = s.transport || "stdio";
  sfCommand.value = s.command || "";
  sfArgs.value = (s.args || []).join("\n");
  sfUrl.value = s.url || "";
  sfProfiles.value = (s.allowed_profiles || []).join("\n");
  sfEnv.value = Object.entries(s.env || {}).map(([k, v]) => `${k}=${v}`).join("\n");
  sfApproval.checked = s.require_approval !== false;
  sfTimeout.value = String(s.timeout_seconds || 60);
  sfOutputLimit.value = String(s.tool_output_limit_chars || 20000);
  sfMsg.textContent = "";
  sfMsg.className = "";
  toggleTransportFields(s.transport || "stdio");
  showPanel("form");
}

sfTransport.addEventListener("change", () => toggleTransportFields(sfTransport.value));

function toggleTransportFields(transport) {
  if (transport === "stdio") {
    sfStdioFields.classList.remove("hidden");
    sfHttpFields.classList.add("hidden");
  } else {
    sfStdioFields.classList.add("hidden");
    sfHttpFields.classList.remove("hidden");
  }
}

sfCancelBtn.addEventListener("click", () => {
  if (activeServerName) showPanel("detail");
  else showPanel("empty");
});

sfSaveBtn.addEventListener("click", saveServer);

async function saveServer() {
  sfMsg.textContent = "";
  sfMsg.className = "";

  const name = sfName.value.trim();
  if (!editingServerName && !name) { sfMsg.className = "error"; sfMsg.textContent = "Name is required"; return; }

  const envObj = {};
  sfEnv.value.trim().split("\n").filter(Boolean).forEach(line => {
    const idx = line.indexOf("=");
    if (idx > 0) envObj[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
  });

  const body = {
    enabled: true,
    description: sfDesc.value.trim(),
    transport: sfTransport.value,
    command: sfTransport.value === "stdio" ? sfCommand.value.trim() || null : null,
    args: sfTransport.value === "stdio"
      ? sfArgs.value.trim().split("\n").map(s => s.trim()).filter(Boolean)
      : [],
    url: sfTransport.value !== "stdio" ? sfUrl.value.trim() || null : null,
    headers_env: {},
    env: envObj,
    allowed_profiles: sfProfiles.value.trim().split("\n").map(s => s.trim()).filter(Boolean),
    require_approval: sfApproval.checked,
    timeout_seconds: parseInt(sfTimeout.value) || 60,
    tool_output_limit_chars: parseInt(sfOutputLimit.value) || 20000,
  };

  sfSaveBtn.disabled = true;
  try {
    if (editingServerName) {
      await api("PUT", `/api/mcp/servers/${editingServerName}`, body);
      sfMsg.className = "ok";
      sfMsg.textContent = "Saved ✓";
      activeServerName = editingServerName;
    } else {
      await api("POST", `/api/mcp/servers?name=${encodeURIComponent(name)}`, body);
      sfMsg.className = "ok";
      sfMsg.textContent = "Created ✓";
      activeServerName = name;
    }
    await loadServerList();
    setTimeout(() => selectServer(activeServerName), 400);
  } catch (e) {
    sfMsg.className = "error";
    sfMsg.textContent = e.message;
  } finally {
    sfSaveBtn.disabled = false;
  }
}

// ── Native tools ──────────────────────────────────────────────────────────────
async function loadNativeTools() {
  try {
    const data = await api("GET", "/api/tools/native");
    nativeList.innerHTML = "";
    data.tools.forEach(t => {
      const el = document.createElement("div");
      el.className = "native-tool-item";
      el.title = t.description;
      el.textContent = t.name;
      nativeList.appendChild(el);
    });
  } catch { /* silent */ }
}

// ── Panel switcher ────────────────────────────────────────────────────────────
function showPanel(which) {
  serverDetail.classList.add("hidden");
  serverForm.classList.add("hidden");
  toolsEmpty.classList.add("hidden");
  if (which === "detail") serverDetail.classList.remove("hidden");
  else if (which === "form") serverForm.classList.remove("hidden");
  else toolsEmpty.classList.remove("hidden");
}

// ── LM Studio panel ───────────────────────────────────────────────────────────
async function lmRefreshModels() {
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
  const modelId = lmSelect.value;
  if (!modelId) return;
  activeLmStudioModel = modelId;
  lmActiveBadge.textContent = `Using: ${modelId}`;
  lmActiveBadge.classList.add("visible");
  lmMsg.className = "ok";
  lmMsg.textContent = "Active — next message will use this model";
  if (activeProject) chatBadge.textContent = `LM Studio: ${modelId}`;
}

lmRefresh.addEventListener("click", lmRefreshModels);
lmLoadBtn.addEventListener("click", lmLoadModel);
lmUseBtn.addEventListener("click", lmUseModel);

// Auto-probe on load
(async () => {
  try {
    const status = await api("GET", "/api/lmstudio/status");
    if (status.available) {
      await lmRefreshModels();
    } else {
      lmDot.className = "offline";
      lmMsg.textContent = "Not running — click ⟳ to retry";
    }
  } catch { /* silent */ }
})();

// ── Start ─────────────────────────────────────────────────────────────────────
init();
