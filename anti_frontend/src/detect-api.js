import { getJson, postFormDataWithToken, postJsonWithToken, deleteJson } from "/ui/src/http.js";

function tokenOrThrow() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("请先登录");
  }
  return token;
}

export async function listDetectRecords(limit = 100) {
  const token = tokenOrThrow();
  return getJson(`/detect/records?limit=${encodeURIComponent(limit)}`, token);
}

export async function getDetectReportDetail(detectId) {
  const token = tokenOrThrow();
  return getJson(`/detect/reports/${encodeURIComponent(detectId)}`, token);
}

export async function agentChat(message, sessionId) {
  const token = tokenOrThrow();
  return postJsonWithToken("/agent/chat", { session_id: sessionId, message }, token);
}

export async function agentDetect(text, sessionId, files = []) {
  const token = tokenOrThrow();
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("text", text || "");
  files.forEach((file) => {
    formData.append("files", file);
  });
  return postFormDataWithToken("/agent/detect", formData, token);
}

export async function agentAlert(text, notify = true) {
  const token = tokenOrThrow();
  return postJsonWithToken("/agent/alert", { text, notify }, token);
}

export async function listAgentChatSessions(limit = 50) {
  const token = tokenOrThrow();
  return getJson(`/agent/chat/sessions?limit=${encodeURIComponent(limit)}`, token);
}

export async function listAgentChatMessages(sessionId, limit = 100) {
  const token = tokenOrThrow();
  return getJson(
    `/agent/chat/sessions/${encodeURIComponent(sessionId)}/messages?limit=${encodeURIComponent(limit)}`,
    token
  );
}

export async function deleteAgentChatSession(sessionId) {
  const token = tokenOrThrow();
  return deleteJson(`/agent/chat/sessions/${encodeURIComponent(sessionId)}`, token);
}
