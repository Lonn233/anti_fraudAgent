import {
  agentAlert,
  agentChat,
  agentDetect,
  agentSpeechTranscribe,
  deleteAgentChatSession,
  listAgentChatMessages,
  listAgentChatSessions,
} from "/ui/src/detect-api.js";

const historyListEl = document.getElementById("detect-history-list");
const messagesEl = document.getElementById("detect-chat-messages");
const inputEl = document.getElementById("detect-chat-input");
const sendBtn = document.getElementById("detect-send-btn");
const micBtn = document.getElementById("detect-mic-btn");
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
let mediaRecorder = null;
let recordingStream = null;
let recordingChunks = [];
let recordingStartAt = 0;
let recordingTimer = null;
let isRecording = false;

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

function _buildAttachmentsFromMaterials(materials) {
  if (!Array.isArray(materials) || !materials.length) return [];
  return materials.map((mat) => {
    const name = mat.file_name || (mat.url ? mat.url.split("/").pop() : "附件");
    const isImage = /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(mat.url || name);
    return { name, url: mat.url || null, isImage };
  });
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
        ? " activeLi to-transparent   "
        : " hover:bg-[#1f2633]/30 hover:translate-x-1 normalLi";
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
      materials: Array.isArray(m.materials) ? m.materials : [],
      attachments: _buildAttachmentsFromMaterials(m.materials),
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
                   (f) => {
                     const isImage = /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(f.name);
                     if (isImage && f.url) {
                       return `<div class="relative group max-w-[200px]">
                         <img src="${f.url}" alt="${escapeHtml(f.name)}" class="rounded-lg border border-primary/20 max-h-40 object-contain" />
                       </div>`;
                     }
                     return `<span class="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-md border border-primary/30 bg-primary/10 text-primary">
                        <span class="material-symbols-outlined text-[12px]">attach_file</span>${escapeHtml(f.name)}
                      </span>`;
                   }
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
    <span class="text-[10px] font-bold uppercase tracking-wider">Sentinel AI Assistant</span>
  </div>
  <div class="glass-card px-6 py-5 rounded-2xl rounded-tl-none border border-tertiary/10 ">
    <p class="leading-relaxed">${escapeHtml(m.content)}</p>
    ${switchPanel}
    ${_buildDetectResultPanel(m.detect_result)}
    ${m.alert_result ? _buildAlertPanel(m.alert_result) : ""}
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

function pushAssistantMessage(chat, content, suggestedMode = "none", detectResult = null, alertResult = null) {
  chat.messages.push({
    id: uid(),
    role: "assistant",
    content,
    suggested_mode: suggestedMode,
    detect_result: detectResult,
    alert_result: alertResult,
    created_at: new Date().toISOString(),
  });
}

async function requestByMode(mode, content, files = []) {
  if (mode === "chat") {
    const res = await agentChat(content, activeChatId || "default");
    return {
      reply: res?.reply || "对话模式未返回内容",
      suggested_mode: res?.suggested_mode || "none",
      detect_result: null,
    };
  }
  if (mode === "detect") {
    const res = await agentDetect(content, activeChatId || "default", files);
    if (typeof res?.reply === "string") {
      return {
        reply: res.reply,
        suggested_mode: "none",
        detect_result: res?.detect_result || null,
        candidate_materials: res?.candidate_materials || [],
      };
    }
    return { reply: JSON.stringify(res ?? {}), suggested_mode: "none", detect_result: null, candidate_materials: [] };
  }
  // alert 模式
  const res = await agentAlert(content, activeChatId || "default", files.length ? files : []);
  if (res) {
    const dr = res.detect_result || null;
    return {
      reply: res.reply || "预警处理完成",
      suggested_mode: "none",
      detect_result: dr,
      candidate_materials: res?.candidate_content ? [] : (res?.candidate_materials || []),
      alert_result: dr ? {
        risk_index: dr.risk_index ?? 0,
        risk_level: dr.risk_level ?? "none",
        guardian_notify: dr.guardian_notify ?? {},
      } : null,
    };
  }
  return { reply: "预警模式处理失败", suggested_mode: "none", alert_result: null, detect_result: null, candidate_materials: [] };
}

function setMicButtonState(recording) {
  if (!micBtn) return;
  const icon = micBtn.querySelector("span.material-symbols-outlined");
  if (recording) {
    micBtn.classList.add("text-error");
    micBtn.classList.remove("text-on-surface-variant");
    micBtn.title = "结束录音";
    if (icon) {
      icon.textContent = "stop_circle";
      icon.setAttribute("data-icon", "stop_circle");
    }
    return;
  }
  micBtn.classList.remove("text-error");
  micBtn.classList.add("text-on-surface-variant");
  micBtn.title = "开始录音";
  if (icon) {
    icon.textContent = "mic";
    icon.setAttribute("data-icon", "mic");
  }
}

function stopRecordingStreamTracks() {
  if (!recordingStream) return;
  recordingStream.getTracks().forEach((track) => track.stop());
  recordingStream = null;
}

function buildRecordedAudioFile(blob) {
  const ext = blob.type.includes("webm") ? "webm" : blob.type.includes("ogg") ? "ogg" : "wav";
  const stamp = new Date().toISOString().replaceAll(":", "-");
  return new File([blob], `record_${stamp}.${ext}`, {
    type: blob.type || "audio/webm",
  });
}

async function sendRecordedAudio(audioFile) {
  let chat = getActiveChat();
  if (!chat) {
    createChat();
    chat = getActiveChat();
  }
  if (!chat) return;
  sendBtn && (sendBtn.disabled = true);
  try {
    const asr = await agentSpeechTranscribe(audioFile, activeChatId || "default", currentMode);
    const transcript = String(asr?.text || "").trim();
    if (!transcript) {
      throw new Error("语音识别为空，请重试");
    }

    // 对话模式：仅发送识别文本；检测模式：文本+音频附件，处理方式对齐图片附件。
    if (currentMode === "detect") {
      await sendMessage({
        forcedContent: transcript,
        forcedFiles: [audioFile],
      });
    } else {
      await sendMessage({
        forcedContent: transcript,
        forcedFiles: [],
      });
    }
  } catch (err) {
    pushAssistantMessage(chat, `录音识别失败：${err?.message || "未知错误"}`);
    render();
  } finally {
    sendBtn && (sendBtn.disabled = false);
  }
}

async function startRecording() {
  if (isRecording) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    const chat = getActiveChat();
    if (chat) {
      pushAssistantMessage(chat, "当前浏览器不支持录音功能");
      render();
    }
    return;
  }
  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const prefer = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "";
    mediaRecorder = prefer ? new MediaRecorder(recordingStream, { mimeType: prefer }) : new MediaRecorder(recordingStream);
    recordingChunks = [];
    recordingStartAt = Date.now();
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordingChunks.push(event.data);
      }
    };
    mediaRecorder.onstop = async () => {
      clearInterval(recordingTimer);
      recordingTimer = null;
      isRecording = false;
      setMicButtonState(false);
      stopRecordingStreamTracks();

      if (!recordingChunks.length) return;
      const blob = new Blob(recordingChunks, { type: mediaRecorder?.mimeType || "audio/webm" });
      const audioFile = buildRecordedAudioFile(blob);
      await sendRecordedAudio(audioFile);
    };
    mediaRecorder.start(800);
    isRecording = true;
    setMicButtonState(true);
    {
      let chat = getActiveChat();
      if (!chat) {
        createChat();
        chat = getActiveChat();
      }
      if (chat) {
        pushAssistantMessage(chat, "录音已开始，请再次点击麦克风结束并提交识别。");
        render();
      }
    }
    recordingTimer = window.setInterval(() => {
      const sec = Math.floor((Date.now() - recordingStartAt) / 1000);
      if (inputEl && document.activeElement !== inputEl) {
        inputEl.placeholder = `录音中 ${sec}s，点击麦克风结束并识别...`;
      }
      if (sec >= 180 && mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
    }, 1000);
  } catch (err) {
    const chat = getActiveChat();
    if (chat) {
      pushAssistantMessage(chat, `无法开始录音：${err?.message || "请检查麦克风权限"}`);
      render();
    }
    stopRecordingStreamTracks();
    setMicButtonState(false);
    isRecording = false;
  }
}

function stopRecording() {
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;
  mediaRecorder.stop();
  {
    let chat = getActiveChat();
    if (!chat) {
      createChat();
      chat = getActiveChat();
    }
    if (chat) {
      pushAssistantMessage(chat, "录音已结束，正在识别语音内容...");
      render();
    }
  }
  if (inputEl) {
    inputEl.placeholder = "输入短信内容、链接或上传文件进行实时风险分析...";
  }
}

function _buildDetectResultPanel(dr) {
  if (!dr) return "";
  const level = dr.risk_level || "none";
  const riskIndex = dr.risk_index || 0;
  const reportId = dr.report_id || "";

  // 配色映射
  const levelConfig = {
    none: {
      label: "无风险",
      borderColor: "#22c55e",
      bgColor: "rgba(34,197,94,0.08)",
      textColor: "#22c55e",
      icon: "check_circle",
      dotBg: "#22c55e",
    },
    low: {
      label: "低风险",
      borderColor: "#3b82f6",
      bgColor: "rgba(59,130,246,0.08)",
      textColor: "#3b82f6",
      icon: "info",
      dotBg: "#3b82f6",
    },
    medium: {
      label: "中风险",
      borderColor: "#f59e0b",
      bgColor: "rgba(245,158,11,0.08)",
      textColor: "#f59e0b",
      icon: "warning",
      dotBg: "#f59e0b",
    },
    high: {
      label: "高风险",
      borderColor: "#ef4444",
      bgColor: "rgba(239,68,68,0.08)",
      textColor: "#ef4444",
      icon: "dangerous",
      dotBg: "#ef4444",
    },
  };

  const cfg = levelConfig[level] || levelConfig.none;
  const reportLink = reportId
    ? `<a href="/ui/reportDetail.html?detect_id=${encodeURIComponent(reportId)}" target="_blank"
        class="inline-flex items-center gap-2 mt-3 px-4 py-2 rounded-lg border text-xs font-medium transition-all duration-200 hover:brightness-110 active:scale-[0.98]"
        style="border-color:${cfg.borderColor};color:${cfg.textColor};background:${cfg.bgColor};">
        <span class="material-symbols-outlined text-[14px]" style="color:${cfg.textColor}">description</span>
        查看完整报告（ID：${escapeHtml(String(reportId))}）
       </a>`
    : "";

  return `
<div class="mt-3">
  <div class="flex items-center gap-2 mb-2">
    <span class="w-2 h-2 rounded-full" style="background:${cfg.dotBg}"></span>
    <span class="text-xs font-bold uppercase tracking-wider" style="color:${cfg.textColor}">${cfg.label}</span>
    <span class="text-xs" style="color:${cfg.textColor}">·</span>
    <span class="text-xs font-mono" style="color:${cfg.textColor}">${Number(riskIndex).toFixed(1)} / 10.0</span>
  </div>
  ${reportLink}
</div>`;
}

function _isDetectionResult(content) {
  return typeof content === "string" && content.includes("已完成检测。");
}

// --------------------------------------------------------------------------- //
// 预警相关
// --------------------------------------------------------------------------- //

function _alertLevelConfig(level) {
  const configs = {
    none: { label: "无风险", color: "#22c55e", icon: "check_circle", bg: "rgba(34,197,94,0.1)" },
    low: { label: "低风险", color: "#3b82f6", icon: "info", bg: "rgba(59,130,246,0.1)" },
    medium: { label: "中风险", color: "#f59e0b", icon: "warning", bg: "rgba(245,158,11,0.1)" },
    high: { label: "高风险", color: "#ef4444", icon: "dangerous", bg: "rgba(239,68,68,0.1)" },
  };
  return configs[level] || configs.none;
}

function _buildAlertPanel(alertResult) {
  if (!alertResult) return "";
  const { risk_index, risk_level, guardian_notify = {} } = alertResult;
  const cfg = _alertLevelConfig(risk_level || "none");
  const gn = guardian_notify || {};
  const notified = gn.notified ? "已通知" : "未通知";
  const guardianText = gn.notified
    ? `已通知 ${gn.guardians_count || 0} 位监护人`
    : "暂无绑定监护人，未发送通知";
  return `
<div class="mt-3 p-3 rounded-xl border" style="border-color:${cfg.color}40;background:${cfg.bg};">
  <div class="flex items-center gap-2 mb-2">
    <span class="material-symbols-outlined text-[16px]" style="color:${cfg.color}">${cfg.icon}</span>
    <span class="text-xs font-bold uppercase tracking-wider" style="color:${cfg.color}">${cfg.label}</span>
    <span class="text-xs font-mono" style="color:${cfg.color}">${Number(risk_index || 0).toFixed(1)} / 10.0</span>
  </div>
  <div class="flex items-center gap-2 text-[11px]" style="color:${cfg.color}80">
    <span class="material-symbols-outlined text-[12px]">person</span>
    <span>${guardianText}</span>
  </div>
</div>`;
}

function showLocalAlert(content, alertResult) {
  const ar = alertResult || {};
  const level = ar.risk_level || "medium";
  const cfg = _alertLevelConfig(level);
  const ri = Number(ar.risk_index || 0).toFixed(1);
  const gn = ar.guardian_notify || {};
  const guardianInfo = gn.notified
    ? `已通知监护人（共 ${gn.guardians_count || 0} 位）`
    : "未绑定监护人";

  const overlay = document.createElement("div");
  overlay.id = "local-alert-overlay";
  overlay.style.cssText = `
    position:fixed;inset:0;z-index:9999;
    background:rgba(0,0,0,0.6);
    display:flex;align-items:center;justify-content:center;
    animation:fadeIn 0.2s ease-out;
  `;
  overlay.innerHTML = `
<div style="
  max-width:420px;width:90%;
  background:#141a25;border-radius:16px;
  border:1px solid ${cfg.color}40;
  box-shadow:0 20px 60px rgba(0,0,0,0.5);
  animation:slideUp 0.3s ease-out;overflow:hidden;
">
  <div style="
    background:${cfg.bg};
    border-bottom:1px solid ${cfg.color}30;
    padding:16px 20px;
    display:flex;align-items:center;gap:12px;
  ">
    <span class="material-symbols-outlined text-[28px]" style="color:${cfg.color}">${cfg.icon}</span>
    <div>
      <div style="color:${cfg.color};font-weight:700;font-size:16px;">风险预警</div>
      <div style="color:${cfg.color}99;font-size:12px;margin-top:2px;">风险等级：${cfg.label}（${ri}/10.0）</div>
    </div>
  </div>
  <div style="padding:20px;">
    <div style="color:#e1e5f3;font-size:14px;line-height:1.7;margin-bottom:16px;">
      ${escapeHtml(content)}
    </div>
    <div style="display:flex;align-items:center;gap:8px;padding:10px 12px;border-radius:8px;background:rgba(255,255,255,0.05);margin-bottom:16px;">
      <span class="material-symbols-outlined text-[16px]" style="color:#a6abb7">notifications_active</span>
      <span style="color:#a6abb7;font-size:12px;">${guardianInfo}</span>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;">
      <button id="alert-ack-btn" style="
        background:${cfg.color}22;color:${cfg.color};
        border:1px solid ${cfg.color}44;
        padding:8px 20px;border-radius:8px;
        font-size:13px;cursor:pointer;
        transition:all 0.2s;
      ">我已知悉</button>
    </div>
  </div>
</div>`;
  document.body.appendChild(overlay);
  document.getElementById("alert-ack-btn").addEventListener("click", () => {
    overlay.style.animation = "fadeOut 0.2s ease-out forwards";
    setTimeout(() => overlay.remove(), 200);
  });
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      overlay.style.animation = "fadeOut 0.2s ease-out forwards";
      setTimeout(() => overlay.remove(), 200);
    }
  });

  // 语音播报（中高风险）
  if (level === "high" || level === "medium") {
    _speakAlert(content, cfg.label);
  }

  // 自动关闭（15s）
  setTimeout(() => {
    if (document.getElementById("local-alert-overlay")) {
      overlay.style.animation = "fadeOut 0.2s ease-out forwards";
      setTimeout(() => overlay.remove(), 200);
    }
  }, 15000);
}

function _speakAlert(text, levelLabel) {
  if (!window.speechSynthesis) return;
  const clean = text.replace(/[^\u4e00-\u9fa5a-zA-Z0-9，。！？、：；""''（）《》【】\s]/g, "").trim();
  const msg = new SpeechSynthesisUtterance(`风险预警，${levelLabel}，${clean}`);
  msg.lang = "zh-CN";
  msg.rate = 1.0;
  msg.pitch = 1.0;
  msg.volume = 1.0;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(msg);
}

// CSS 动画
const _alertStyle = document.createElement("style");
_alertStyle.textContent = `
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes fadeOut{from{opacity:1}to{opacity:0}}
@keyframes slideUp{from{transform:translateY(20px);opacity:0}to{transform:translateY(0);opacity:1}}
`;
document.head.appendChild(_alertStyle);

function renderModeButtons() {
  modeButtons.forEach((btn) => {
    const mode = btn.getAttribute("data-mode");
    const active = mode === currentMode;
    if (active) {
      btn.classList.add("active", "bg-primary", "text-on-primary", "shadow-[0_0_10px_rgba(92,191,255,0.4)]");
      btn.classList.remove("text-on-surface-variant");
    } else {
      btn.classList.remove("active", "bg-primary", "text-on-primary", "shadow-[0_0_10px_rgba(92,191,255,0.4)]");
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

async function sendMessage(options = {}) {
  const chat = getActiveChat();
  if (!chat || !inputEl) return;
  const forcedContent = typeof options.forcedContent === "string" ? options.forcedContent : null;
  const forcedFiles = Array.isArray(options.forcedFiles) ? options.forcedFiles : null;
  const content = forcedContent != null ? forcedContent.trim() : inputEl.value.trim();
  const sendFiles = forcedFiles != null ? [...forcedFiles] : [...pendingAttachments];
  if (!content && sendFiles.length === 0) return;
  const userContent = content || "（发送了附件）";

  // 生成本地预览URL
  const attachmentsWithPreview = sendFiles.map((f) => {
    const isImage = /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(f.name);
    return {
      name: f.name,
      url: isImage && f instanceof File ? URL.createObjectURL(f) : null,
    };
  });

  const msgId = uid();
  chat.messages.push({
    id: msgId,
    role: "user",
    content: userContent,
    mode: currentMode,
    attachments: attachmentsWithPreview,
    created_at: new Date().toISOString(),
  });
  if (chat.title === "新对话") {
    chat.title = deriveTitleFromMessage(userContent);
  }
  const modeLabel = currentMode === "chat" ? "对话模式" : currentMode === "detect" ? "检测模式" : "预警模式";
  if (forcedContent == null) {
    inputEl.value = "";
  }
  if (forcedFiles == null) {
    pendingAttachments = [];
  }
  sendBtn && (sendBtn.disabled = true);
  render();
  try {
    const result = await requestByMode(currentMode, userContent, sendFiles);
    // 用检测返回的 candidate_materials 更新消息中的附件（含服务端 URL）
    // if (result?.candidate_materials?.length && chat.messages.length) {
    //   const lastMsg = chat.messages[chat.messages.length - 1];
    //   if (lastMsg.role === "user" && lastMsg.id === msgId) {
    //     lastMsg.attachments = result.candidate_materials.map((mat) => {
    //       const name = mat.file_name || (mat.url ? mat.url.split("/").pop() : "附件");
    //       const isImage = /\.(jpg|jpeg|png|gif|webp|bmp)$/i.test(mat.url || name) || mat.type === "image";
    //       return { name, url: mat.url || null, isImage };
    //     });
    //   }
    // }
    pushAssistantMessage(
      chat,
      result.reply || `已收到（${modeLabel}）`,
      result.suggested_mode || "none",
      result.detect_result || null,
      result.alert_result || null
    );
    // 预警模式下触发本地弹窗+语音播报
    if (result.alert_result) {
      const ar = result.alert_result;
      if (ar.risk_level === "high" || ar.risk_level === "medium") {
        showLocalAlert(result.reply || "", ar);
      }
    }
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
micBtn?.addEventListener("click", async () => {
  if (isRecording) {
    stopRecording();
    return;
  }
  await startRecording();
});
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
