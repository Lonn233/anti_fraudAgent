import { deleteJson, getJson, postJsonWithToken, putJson } from "/ui/src/http.js";

function tokenOrThrow() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("请先登录");
  }
  return token;
}

export async function listRelations(role, page = null, pageSize = null) {
  const token = tokenOrThrow();
  const qs = new URLSearchParams();
  qs.set("role", role);
  if (page != null && pageSize != null) {
    qs.set("page", String(page));
    qs.set("page_size", String(pageSize));
  }
  const data = await getJson(`/guardians/relations?${qs.toString()}`, token);
  // Backward compatibility: old pages expect an array.
  if (page == null || pageSize == null) {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.items)) return data.items;
    return [];
  }
  // New pagination callers expect an object.
  if (Array.isArray(data)) {
    const safePage = Number(page) || 1;
    const safeSize = Number(pageSize) || 10;
    const total = data.length;
    return {
      items: data,
      page: safePage,
      page_size: safeSize,
      total,
      total_pages: Math.max(Math.ceil(total / safeSize), 1),
    };
  }
  return data;
}

export async function applyGuardianRequest(mode, targetUsername, name, relationship) {
  const token = tokenOrThrow();
  return postJsonWithToken(
    "/guardians/requests/apply",
    { mode, target_username: targetUsername, name, relationship },
    token
  );
}

export async function listGuardianRequests(box, status) {
  const token = tokenOrThrow();
  const qs = new URLSearchParams();
  if (box) qs.set("box", box);
  if (status) qs.set("status", status);
  return getJson(`/guardians/requests?${qs.toString()}`, token);
}

export async function decideGuardianRequest(requestId, decision, note = null) {
  const token = tokenOrThrow();
  return postJsonWithToken(
    `/guardians/requests/${encodeURIComponent(requestId)}/decision`,
    { decision, note },
    token
  );
}

export async function deleteRelation(guardianId) {
  const token = tokenOrThrow();
  return deleteJson(`/guardians/${guardianId}`, token);
}

export async function updateRelation(guardianId, note) {
  const token = tokenOrThrow();
  return putJson(`/guardians/${guardianId}`, { note }, token);
}

export async function listGuardianAlerts() {
  const token = tokenOrThrow();
  return getJson("/guardians/alerts", token);
}

export async function markGuardianAlertsRead(alertIds = null, markAll = false) {
  const token = tokenOrThrow();
  const body = markAll ? { mark_all: true } : { alert_ids: alertIds || [] };
  return postJsonWithToken("/guardians/alerts/read", body, token);
}
