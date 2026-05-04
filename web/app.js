const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendBtn = document.querySelector("#sendBtn");
const clearBtn = document.querySelector("#clearBtn");
const statusText = document.querySelector("#statusText");
const settingsBtn = document.querySelector("#settingsBtn");
const closeSettingsBtn = document.querySelector("#closeSettingsBtn");
const settingsPanel = document.querySelector("#settingsPanel");
const drawerOverlay = document.querySelector("#drawerOverlay");

const defaultGroqBaseUrl = "https://api.groq.com/openai/v1";
const defaultGroqChatModel = "llama-3.1-8b-instant";
const legacyOpenAiChatModel = "gpt-4o-mini";
const stored = JSON.parse(localStorage.getItem("uetKgSettings") || "{}");
if (stored.chatModel === legacyOpenAiChatModel) {
  stored.chatModel = defaultGroqChatModel;
}
const settingIds = [
  "neo4jUri",
  "neo4jUser",
  "neo4jDatabase",
  "baseUrl",
  "chatModel",
  "embeddingModel",
  "embeddingBaseUrl",
  "esUrl",
  "esChunksIndex",
  "vectorSearch",
  "neo4jVector",
  "graphHops",
  "entityK",
  "chunkK",
];
const secretIds = ["neo4jPassword", "apiKey", "embeddingApiKey", "esApiKey"];
const suggestions = [
  "Điểm chuẩn ngành Khoa học máy tính 2024",
  "Học phí ngành Trí tuệ nhân tạo năm 2024",
  "Chỉ tiêu tuyển sinh CN8",
  "Tổ hợp xét tuyển ngành Công nghệ thông tin",
];
let history = [];

function applyStoredSettings() {
  for (const id of settingIds) {
    const el = document.querySelector(`#${id}`);
    if (!el || stored[id] === undefined) continue;
    if (el.type === "checkbox") {
      el.checked = Boolean(stored[id]);
    } else {
      el.value = stored[id];
    }
  }
}

function persistSettings() {
  const next = {};
  for (const id of settingIds) {
    const el = document.querySelector(`#${id}`);
    if (!el) continue;
    next[id] = el.type === "checkbox" ? el.checked : el.value;
  }
  localStorage.setItem("uetKgSettings", JSON.stringify(next));
}

function collectSettings() {
  const settings = {};
  for (const id of [...settingIds, ...secretIds]) {
    const el = document.querySelector(`#${id}`);
    if (!el) continue;
    settings[id] = el.type === "checkbox" ? el.checked : el.value.trim();
  }
  settings.vectorSearch = document.querySelector("#vectorSearch").checked;
  if (settings.apiKey.startsWith("gsk_")) {
    settings.baseUrl = settings.baseUrl || defaultGroqBaseUrl;
    if (!settings.chatModel || settings.chatModel === legacyOpenAiChatModel) {
      settings.chatModel = defaultGroqChatModel;
    }
  }
  return settings;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderAnswer(text) {
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(S\d+)\]/g, '<span class="citation">[$1]</span>');
}

function setStatus(text) {
  statusText.textContent = text;
}

function resizeComposer() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
}

function openSettings() {
  settingsPanel.classList.add("open");
  settingsPanel.setAttribute("aria-hidden", "false");
  drawerOverlay.hidden = false;
}

function closeSettings() {
  settingsPanel.classList.remove("open");
  settingsPanel.setAttribute("aria-hidden", "true");
  drawerOverlay.hidden = true;
  inputEl.focus();
}

function renderEmptyState() {
  if (history.length > 0) return;
  const buttons = suggestions
    .map((text) => `<button class="prompt-chip" type="button" data-prompt="${escapeHtml(text)}">${escapeHtml(text)}</button>`)
    .join("");
  messagesEl.innerHTML = `
    <div class="empty-state">
      <h2>UET KG BigData</h2>
      <div class="prompt-grid">${buttons}</div>
    </div>
  `;
}

function clearEmptyState() {
  const empty = messagesEl.querySelector(".empty-state");
  if (empty) empty.remove();
}

function appendMessage(role, content, options = {}) {
  clearEmptyState();
  const item = document.createElement("article");
  item.className = `message ${role}${options.error ? " error" : ""}`;

  const body = document.createElement("div");
  body.className = "message-body";
  body.innerHTML = role === "assistant" ? renderAnswer(content) : escapeHtml(content);
  item.appendChild(body);

  if (options.meta) {
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.textContent = options.meta;
    item.appendChild(meta);
  }

  if (options.sources?.length) {
    const sources = document.createElement("details");
    sources.className = "sources";
    const summary = document.createElement("summary");
    summary.textContent = `Nguồn tham chiếu (${options.sources.length})`;
    sources.appendChild(summary);
    for (const source of options.sources) {
      const row = document.createElement("div");
      row.className = "source-row";
      row.textContent = `[${source.source_id}] ${source.chunk_id} | ${source.file_path || ""}`;
      sources.appendChild(row);
    }
    item.appendChild(sources);
  }

  messagesEl.appendChild(item);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return item;
}

function setLoading(loading) {
  sendBtn.disabled = loading;
  inputEl.disabled = loading;
  setStatus(loading ? "Đang xử lý" : "Sẵn sàng");
}

async function sendMessage(message) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      settings: collectSettings(),
      history,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function submitMessage(message) {
  const text = message.trim();
  if (!text) return;

  persistSettings();
  closeSettings();
  appendMessage("user", text);
  history.push({ role: "user", content: text });
  inputEl.value = "";
  resizeComposer();
  setLoading(true);
  const pending = appendMessage("assistant", "Đang truy xuất dữ liệu và tạo câu trả lời...");

  try {
    const data = await sendMessage(text);
    const retrieval = data.retrieval || {};
    const vectorLabel = retrieval.vector_used ? retrieval.vector_db || "vector" : "off";
    const meta = `entities ${retrieval.entity_count ?? 0} · relations ${retrieval.relation_count ?? 0} · chunks ${retrieval.chunk_count ?? 0} · semantic ${retrieval.semantic_chunk_count ?? 0} · hops ${retrieval.graph_hops ?? 1} · vector ${vectorLabel}`;
    pending.remove();
    appendMessage("assistant", data.answer || "", { sources: data.sources || [], meta });
    history.push({ role: "assistant", content: data.answer || "" });
  } catch (error) {
    pending.remove();
    appendMessage("assistant", `Lỗi: ${error.message}`, { error: true });
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessage(inputEl.value);
});

inputEl.addEventListener("input", resizeComposer);

inputEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    formEl.requestSubmit();
  }
});

messagesEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-prompt]");
  if (!button) return;
  inputEl.value = button.dataset.prompt || "";
  resizeComposer();
  formEl.requestSubmit();
});

clearBtn.addEventListener("click", () => {
  history = [];
  messagesEl.innerHTML = "";
  renderEmptyState();
  inputEl.focus();
});

settingsBtn.addEventListener("click", openSettings);
closeSettingsBtn.addEventListener("click", closeSettings);
drawerOverlay.addEventListener("click", closeSettings);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && settingsPanel.classList.contains("open")) {
    closeSettings();
  }
});

for (const id of settingIds) {
  const el = document.querySelector(`#${id}`);
  if (el) el.addEventListener("change", persistSettings);
}

applyStoredSettings();
renderEmptyState();
resizeComposer();
inputEl.focus();
