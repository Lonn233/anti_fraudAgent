import { agentAlert, agentChat, agentDetect, deleteAgentChatSession, listAgentChatMessages, listAgentChatSessions } from "/ui/src/detect-api.js";

const historyListEl = document.getElementById("detect-history-list");
const messagesEl = document.getElementById("detect-chat-messages");
const inputEl = document.getElementById("detect-chat-input");
const sendBtn = document.getElementById("detect-send-btn");
const newChatBtn = document.getElementById("detect-new-chat-btn");
const attachBtn = document.getElementById("detect-attach-btn");
const fileInputEl = document.getElementById("detect-file-input");
const attachmentsWrapEl = document.getElementById("detect-attachments-wrap");
const attachmentsListEl = document.getElementById("detect-attachments-list");
const deleteChatModalEl = document.getElementById("delete-chat-modal");
const deleteChatModalTitleEl = document.getElementById("delete-chat-modal-title");
const deleteChatModalMessageEl = document.getElementById("delete-chat-modal-message");
const deleteChatConfirmBtn = document.getElementById("delete-chat-confirm-btn");
const modeButtons = Array.from(document.querySelectorAll("[data-mode]"));

let chats = [];
let activeChatId = null;
let currentMode = "chat";
let pendingAttachments = [];
let deletingChatId = null;
let pendingDeleteChatId = null;

function uid() {
  return `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function nowText() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${y}-${m}-${day} ${hh}:${mm}:${ss}`;
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createWelcomeAssistantMessage() {
  return {
    id: uid(),
    role: "assistant",
    content: "你好，我是 Sentinel AI。你可以输入短信、链接或对话内容，我会给出风险判断和建议。",
    created_at: new Date().toISOString(),
  };
}

function createChat() {
  const chat = {
    id: uid(),
    title: "新对话",
    created_at: new Date().toISOString(),
    messages: [createWelcomeAssistantMessage()],
  };
  chats.unshift(chat);
  activeChatId = chat.id;
  render();
}

async function loadChats() {
  chats = [];
  try {
    const sessions = await listAgentChatSessions(50);
    const sessionList = Array.isArray(sessions) ? sessions : [];
    for (const s of sessionList) {
      chats.push({
        id: s.session_id,
        title: `会话 ${String(s.session_id).slice(0, 8)}`,
        created_at: s.updated_at,
        messages: [],
      });
    }
    if (chats.length) {
      activeChatId = chats[0].id;
      await loadMessagesForActiveChat();
      return;
    }
  } catch (_err) {
    // fall back to empty chat
  }
  createChat();
}

function getActiveChat() {
  return chats.find((x) => x.id === activeChatId) || null;
}

function deriveTitleFromMessage(text) {
  const t = String(text || "").trim();
  return t ? t.slice(0, 16) : "新对话";
}

function renderHistory() {
  if (!historyListEl) return;
  const header = `
<div class="px-2 mb-2">
  <span class="text-[10px] font-bold text-outline uppercase tracking-wider">对话历史</span>
</div>`;
  const items = chats
    .map((chat) => {
      const active = chat.id === activeChatId;
      const deleting = deletingChatId === chat.id;
      const title = chat.title && chat.title !== "新对话" ? chat.title : `会话 ${String(chat.id).slice(0, 8)}`;
      const baseClass = active
        ? "bg-gradient-to-r from-[#5cbfff]/10 to-transparent text-[#5cbfff] border-l-4 border-[#5cbfff]"
        : "text-[#e1e5f3]/40 hover:bg-[#1f2633]/30 hover:translate-x-1";
      return `
<div class="group flex items-center gap-2 ${baseClass} transition-all duration-200">
  <a class="flex min-w-0 flex-1 items-center gap-3 px-3 py-3" href="#" data-chat-id="${chat.id}">
    <span class="material-symbols-outlined text-[18px]">chat_bubble</span>
    <span class="truncate">${escapeHtml(title)}</span>
  </a>
  <button class="mr-2 flex h-7 w-7 items-center justify-center rounded-full text-[#e1e5f3]/0 transition-all duration-200 group-hover:text-[#ff7b7b] hover:bg-[#ff7b7b]/10 disabled:cursor-not-allowed disabled:text-[#ff7b7b]/30"
    data-chat-delete="${chat.id}" type="button" aria-label="删除对话" ${deleting ? "disabled" : ""}>
    <span class="material-symbols-outlined text-[18px]">close</span>
  </button>
</div>`;
    })
    .join("");
  historyListEl.innerHTML = header + items;
  historyListEl.querySelectorAll("[data-chat-id]").forEach((el) => {
    el.addEventListener("click", async (e) => {
      e.preventDefault();
      activeChatId = el.getAttribute("data-chat-id");
      await loadMessagesForActiveChat();
      render();
    });
  });
  historyListEl.querySelectorAll("[data-chat-delete]").forEach((el) => {
    el.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();
      openDeleteChatModal(el.getAttribute("data-chat-delete"));
    });
  });
}

function closeDeleteChatModal() {
  pendingDeleteChatId = null;
  if (!deleteChatModalEl) return;
  deleteChatModalEl.classList.add("hidden");
  deleteChatModalEl.classList.remove("flex");
}

function openDeleteChatModal(chatId) {
  if (!chatId || deletingChatId) return;
  const chat = chats.find((item) => item.id === chatId);
  if (!chat || !deleteChatModalEl || !deleteChatModalTitleEl || !deleteChatModalMessageEl) return;
  const title = chat.title && chat.title !== "新对话" ? chat.title : `会话 ${String(chat.id).slice(0, 8)}`;
  pendingDeleteChatId = chatId;
  deleteChatModalTitleEl.textContent = title;
  deleteChatModalMessageEl.textContent = `删除后将同步清空“${title}”及其全部消息记录，此操作不可撤销。`;
  deleteChatModalEl.classList.remove("hidden");
  deleteChatModalEl.classList.add("flex");
}

async function handleDeleteChat(chatId) {
  if (!chatId || deletingChatId) return;
  const chat = chats.find((item) => item.id === chatId);
  if (!chat) return;

  deletingChatId = chatId;
  if (deleteChatConfirmBtn) {
    deleteChatConfirmBtn.disabled = true;
    deleteChatConfirmBtn.textContent = "删除中...";
  }
  renderHistory();
  try {
    await deleteAgentChatSession(chatId);
    chats = chats.filter((item) => item.id !== chatId);
    closeDeleteChatModal();
    if (activeChatId === chatId) {
      activeChatId = chats[0]?.id || null;
      if (activeChatId) {
        await loadMessagesForActiveChat();
      }
    }
    if (!chats.length) {
      createChat();
      return;
    }
    render();
  } catch (err) {
    if (deleteChatModalMessageEl) {
      deleteChatModalMessageEl.textContent = `删除失败：${err?.message || "未知错误"}`;
    }
  } finally {
    deletingChatId = null;
    if (deleteChatConfirmBtn) {
      deleteChatConfirmBtn.disabled = false;
      deleteChatConfirmBtn.textContent = "确认删除";
    }
    renderHistory();
  }
}

async function loadMessagesForActiveChat() {
  const chat = getActiveChat();
  if (!chat) return;
  try {
    const rows = await listAgentChatMessages(chat.id, 100);
    const list = Array.isArray(rows) ? rows : [];
    chat.messages = list.map((m) => ({
      id: uid(),
      role: m.role,
      content: m.content,
      created_at: m.created_at,
    }));
    const firstUser = chat.messages.find((m) => m.role === "user");
    if (firstUser && chat.title === `会话 ${String(chat.id).slice(0, 8)}`) {
      chat.title = deriveTitleFromMessage(firstUser.content);
    }
  } catch (_err) {
    chat.messages = chat.messages || [];
  }
}

function renderMessages() {
  if (!messagesEl) return;
  const chat = getActiveChat();
  if (!chat) return;
  const msgHtml = chat.messages
    .map((m) => {
      if (m.role === "user") {
        const attachments = Array.isArray(m.attachments) && m.attachments.length
          ? `<div class="flex flex-wrap gap-2 mt-2">
               ${m.attachments
                 .map(
                   (f) =>
                     `<span class="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border border-primary/30 bg-primary/10 text-primary">
                        <span class="material-symbols-outlined text-[12px]">attach_file</span>${escapeHtml(f.name)}
                      </span>`
                 )
                 .join("")}
             </div>`
          : "";
        return `
<div class="flex flex-col items-end gap-2 max-w-[80%] ml-auto">
  <div class="flex items-center gap-2 mb-1">
    <span class="text-[10px] font-bold text-outline-variant uppercase tracking-wider">User Terminal</span>
  </div>
  <div class="px-5 py-3 bg-surface-container-high rounded-2xl rounded-tr-none text-on-surface border-l border-primary/20 shadow-xl">
    <div>${escapeHtml(m.content)}</div>
    ${attachments}
  </div>
</div>`;
      }
      const switchHandled = Boolean(m.switch_handled);
      const switchPanel =
        m.suggested_mode === "detect" || m.suggested_mode === "alert"
          ? `<div class="mt-3 p-3 rounded-lg border border-primary/20 bg-primary/10">
               <div class="text-xs text-on-surface mb-2">${switchHandled ? "已确认切换模式" : (m.suggested_mode === "detect" ? "检测模式更适合该请求，是否开启？" : "预警模式更适合该请求，是否开启？")}</div>
               <div class="flex gap-2">
                 <button class="px-3 py-1 text-xs rounded bg-primary text-on-primary disabled:opacity-50" ${switchHandled ? "disabled" : ""} data-switch-mode="${m.suggested_mode}" data-switch-msg-id="${m.id}" type="button">开启${m.suggested_mode === "detect" ? "检测" : "预警"}模式</button>
                 <button class="px-3 py-1 text-xs rounded border border-outline-variant/30 text-on-surface-variant disabled:opacity-50" ${switchHandled ? "disabled" : ""} type="button">暂不切换</button>
               </div>
             </div>`
          : "";
      return `
<div class="flex flex-col items-start gap-2 max-w-[85%]">
  <div class="flex items-center gap-2 mb-1">
    <div class="w-6 h-6 rounded bg-tertiary/20 flex items-center justify-center border border-tertiary/40">
      <span class="material-symbols-outlined text-[14px] text-tertiary">bolt</span>
    </div>
    <span class="text-[10px] font-bold text-tertiary uppercase tracking-wider">Sentinel AI Assistant</span>
  </div>
  <div class="glass-card px-6 py-5 rounded-2xl rounded-tl-none border border-tertiary/10 shadow-[0_10px_40px_rgba(0,0,0,0.3)]">
    <p class="leading-relaxed">${escapeHtml(m.content)}</p>
    ${switchPanel}
  </div>
</div>`;
    })
    .join("");

  messagesEl.innerHTML = `
<div class="flex justify-center">
  <span class="text-[10px] font-bold text-outline-variant uppercase tracking-[0.3em]">Session Initialized: ${nowText()}</span>
</div>
${msgHtml}`;
  messagesEl.querySelectorAll("[data-switch-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetMode = btn.getAttribute("data-switch-mode");
      const msgId = btn.getAttribute("data-switch-msg-id");
      if (targetMode === "detect" || targetMode === "alert") {
        currentMode = targetMode;
        renderModeButtons();
        const chat = getActiveChat();
        const msg = chat?.messages?.find((x) => x.id === msgId);
        if (msg) {
          msg.switch_handled = true;
        }
        renderMessages();
      }
    });
  });
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function render() {
  renderHistory();
  renderMessages();
  renderAttachments();
  renderModeButtons();
}

function pushAssistantMessage(chat, content, suggestedMode = "none") {
  chat.messages.push({
    id: uid(),
    role: "assistant",
    content,
    suggested_mode: suggestedMode,
    created_at: new Date().toISOString(),
  });
}

async function requestByMode(mode, content, files = []) {
  if (mode === "chat") {
    const res = await agentChat(content, activeChatId || "default");
    return {
      reply: res?.reply || "对话模式未返回内容",
      suggested_mode: res?.suggested_mode || "none",
    };
  }
  if (mode === "detect") {
    const res = await agentDetect(content, activeChatId || "default", files);
    if (typeof res?.reply === "string") return { reply: res.reply, suggested_mode: "none" };
    return { reply: JSON.stringify(res ?? {}), suggested_mode: "none" };
  }
  const res = await agentAlert(content, true);
  if (typeof res?.reply === "string") return { reply: res.reply, suggested_mode: "none" };
  return { reply: JSON.stringify(res ?? {}), suggested_mode: "none" };
}

function renderModeButtons() {
  modeButtons.forEach((btn) => {
    const mode = btn.getAttribute("data-mode");
    const active = mode === currentMode;
    if (active) {
      btn.classList.add("bg-primary", "text-on-primary", "shadow-[0_0_10px_rgba(92,191,255,0.4)]");
      btn.classList.remove("text-on-surface-variant");
    } else {
      btn.classList.remove("bg-primary", "text-on-primary", "shadow-[0_0_10px_rgba(92,191,255,0.4)]");
      btn.classList.add("text-on-surface-variant");
    }
  });
}

function renderAttachments() {
  if (!attachmentsWrapEl || !attachmentsListEl) return;
  if (!pendingAttachments.length) {
    attachmentsWrapEl.classList.add("hidden");
    attachmentsListEl.innerHTML = "";
    return;
  }
  attachmentsWrapEl.classList.remove("hidden");
  attachmentsListEl.innerHTML = pendingAttachments
    .map(
      (f, index) => `
<span class="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border border-tertiary/30 bg-tertiary/10 text-tertiary">
  <span class="material-symbols-outlined text-[12px]">description</span>${escapeHtml(f.name)}
  <button class="text-on-surface-variant hover:text-error" data-attach-remove="${index}" type="button">×</button>
</span>`
    )
    .join("");
  attachmentsListEl.querySelectorAll("[data-attach-remove]").forEach((el) => {
    el.addEventListener("click", () => {
      const idx = Number(el.getAttribute("data-attach-remove"));
      pendingAttachments.splice(idx, 1);
      renderAttachments();
    });
  });
}

async function sendMessage() {
  const chat = getActiveChat();
  if (!chat || !inputEl) return;
  const content = inputEl.value.trim();
  if (!content && pendingAttachments.length === 0) return;
  const sendFiles = [...pendingAttachments];
  const userContent = content || "（发送了附件）";

  chat.messages.push({
    id: uid(),
    role: "user",
    content: userContent,
    mode: currentMode,
    attachments: sendFiles.map((f) => ({ name: f.name })),
    created_at: new Date().toISOString(),
  });
  if (chat.title === "新对话") {
    chat.title = deriveTitleFromMessage(userContent);
  }
  const modeLabel = currentMode === "chat" ? "对话模式" : currentMode === "detect" ? "检测模式" : "预警模式";
  inputEl.value = "";
  pendingAttachments = [];
  sendBtn && (sendBtn.disabled = true);
  render();
  try {
    const result = await requestByMode(currentMode, userContent, sendFiles);
    pushAssistantMessage(chat, result.reply || `已收到（${modeLabel}）`, result.suggested_mode || "none");
  } catch (err) {
    pushAssistantMessage(chat, `${modeLabel}请求失败：${err?.message || "未知错误"}`);
  } finally {
    sendBtn && (sendBtn.disabled = false);
    render();
  }
}

newChatBtn?.addEventListener("click", () => {
  createChat();
});
sendBtn?.addEventListener("click", sendMessage);
attachBtn?.addEventListener("click", () => {
  fileInputEl?.click();
});
fileInputEl?.addEventListener("change", () => {
  const files = Array.from(fileInputEl.files || []);
  if (!files.length) return;
  pendingAttachments = [...pendingAttachments, ...files].slice(0, 10);
  fileInputEl.value = "";
  renderAttachments();
});
modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    currentMode = btn.getAttribute("data-mode") || "chat";
    renderModeButtons();
  });
});
if (deleteChatModalEl) {
  deleteChatModalEl.querySelectorAll("[data-delete-chat-cancel]").forEach((el) => {
    el.addEventListener("click", () => {
      if (!deletingChatId) {
        closeDeleteChatModal();
      }
    });
  });
}

deleteChatConfirmBtn?.addEventListener("click", async () => {
  if (!pendingDeleteChatId || deletingChatId) return;
  await handleDeleteChat(pendingDeleteChatId);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && deleteChatModalEl && !deleteChatModalEl.classList.contains("hidden") && !deletingChatId) {
    closeDeleteChatModal();
  }
});

inputEl?.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

loadChats().then(render);
