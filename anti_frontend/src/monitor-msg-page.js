import { listGuardianAlerts, markGuardianAlertsRead } from "/ui/src/guardian-api.js";

function escapeHtml(text) {
  return String(text || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const REVERSE_RELATION = {
  父亲: "子女", 母亲: "子女",
  儿子: "父亲", 女儿: "母亲",
  丈夫: "妻子", 妻子: "丈夫",
  家属: "家属", 朋友: "朋友",
};
function reverseRelationship(rel) {
  return rel ? (REVERSE_RELATION[rel] || rel) : null;
}

const _alertLevelCfg = {
  high: { label: "高风险", color: "#ef4444", bg: "rgba(239,68,68,0.08)", badge_color: "error" },
  medium: { label: "中风险", color: "#f59e0b", bg: "rgba(245,158,11,0.08)", badge_color: "primary" },
  low: { label: "低风险", color: "#3b82f6", bg: "rgba(59,130,246,0.08)", badge_color: "tertiary" },
  none: { label: "无风险", color: "#22c55e", bg: "rgba(34,197,94,0.08)", badge_color: "tertiary" },
};

const tbody = document.getElementById("alert-tbody");
const emptyState = document.getElementById("alert-empty-state");
const paginationSummary = document.getElementById("alert-pagination-summary");
const prevBtn = document.getElementById("alert-pagination-prev");
const nextBtn = document.getElementById("alert-pagination-next");
const pageBtn = document.getElementById("alert-pagination-page");
const markAllBtn = document.getElementById("alert-mark-all-btn");

// Stats elements
const statIntercept = document.getElementById("stat-intercept");
const statHighRisk = document.getElementById("stat-high-risk");
const statActive = document.getElementById("stat-active");

let allAlerts = [];
let currentPage = 1;
const pageSize = 10;
let totalPages = 1;
let totalItems = 0;
let alertPollTimer = null;



function _timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  return `${days} 天前`;
}

function _createAlertRow(alert) {
  const cfg = _alertLevelCfg[alert.risk_level] || _alertLevelCfg.none;
  const time = alert.created_at ? new Date(alert.created_at).toLocaleString("zh-CN") : "";
  const shortTime = alert.created_at ? _timeAgo(alert.created_at) : "";
  const content = escapeHtml(alert.content || "");
  const wardName = escapeHtml(alert.ward_username || "未知用户");
  const relationship = escapeHtml(alert.relationship || "--");
  const wardChar = wardName.charAt(0);

  const row = document.createElement("tr");
  row.className = `hover:bg-surface-variant/30 transition-colors group ${!alert.is_read ? "bg-surface-container-low/30" : ""}`;
  row.dataset.alertId = alert.id;

  row.innerHTML = `
<td class="px-6 py-5">
  <div class="flex items-center gap-3">
    <div class="w-8 h-8 rounded bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">${wardChar}</div>
    <div>
      <span class="text-on-surface font-medium">${wardName}</span>
      ${!alert.is_read ? '<span class="ml-2 w-2 h-2 rounded-full bg-error inline-block shadow-[0_0_6px_#ff716c]"></span>' : ""}
    </div>
  </div>
</td>
<td class="px-6 py-5 text-sm text-on-surface-variant">${relationship}</td>
<td class="px-6 py-5">
  <div class="max-w-xs" title="${content}">
    <p class="text-sm text-on-surface bg-surface-container/50 px-2 py-1 rounded truncate">${content}</p>
  </div>
</td>
<td class="px-6 py-5">
  <span class="whitespace-nowrap px-2 py-1 rounded bg-${cfg.badge_color}/10 text-${cfg.badge_color} text-[10px] font-bold uppercase">${cfg.label}</span>
</td>
<td class="px-6 py-5">
  <div class="flex items-center justify-center gap-3">
    <span class="font-headline font-bold" style="color:${cfg.color}">${Number(alert.risk_index || 0).toFixed(1)}</span>
    <div class="w-16 h-1 bg-surface-container rounded-full overflow-hidden">
      <div class="h-full" style="width:${Math.min((alert.risk_index || 0) / 10 * 100, 100)}%;background:${cfg.color}"></div>
    </div>
  </div>
</td>
<td class="px-6 py-5">
  <div class="text-xs text-on-surface-variant font-label" title="${time}">${shortTime || time}</div>
</td>
<td class="px-6 py-5">
  <div class="flex items-center justify-end gap-3">
    <button class="alert-view-btn px-3 py-1.5 bg-surface-container-highest text-primary text-xs font-bold rounded border border-primary/10 hover:bg-primary hover:text-on-primary transition-all" data-id="${alert.id}" data-report="${alert.detect_report_id || ""}" type="button">查看详情</button>
    <button class="text-outline hover:text-error transition-colors p-1" data-id="${alert.id}" type="button">
      <span class="material-symbols-outlined text-lg">delete</span>
    </button>
  </div>
</td>`;

  // View detail button
  row.querySelector(".alert-view-btn")?.addEventListener("click", () => {
    const reportId = row.querySelector(".alert-view-btn")?.dataset.report;
    if (reportId) {
      window.location.href = `/ui/reportDetail.html?detect_id=${encodeURIComponent(reportId)}`;
    }
  });

  // Mark as read on click
  row.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    if (!alert.is_read) {
      markGuardianAlertsRead([alert.id]).then(() => {
        alert.is_read = true;
        row.classList.remove("bg-surface-container-low/30");
        const dot = row.querySelector(".rounded-full.bg-error");
        if (dot) dot.remove();
        updateNavBadge();
      });
    }
  });

  return row;
}

function renderPage() {
  if (!tbody) return;
  const startIndex = (currentPage - 1) * pageSize;
  const pageList = allAlerts.slice(startIndex, startIndex + pageSize);

  if (!pageList.length) {
    tbody.innerHTML = "";
    if (emptyState) emptyState.classList.remove("hidden");
    renderPagination(0);
    return;
  }

  if (emptyState) emptyState.classList.add("hidden");
  tbody.innerHTML = "";
  pageList.forEach((item) => tbody.appendChild(_createAlertRow(item)));
  renderPagination(pageList.length);
}

function renderPagination(currentCount) {
  if (!paginationSummary || !prevBtn || !nextBtn || !pageBtn) return;
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = totalItems === 0 ? 0 : start + currentCount - 1;
  paginationSummary.textContent = `显示 ${start} 到 ${end} 条，共 ${totalItems} 条；共 ${totalPages} 页`;
  pageBtn.textContent = `${currentPage} / ${totalPages}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
}

function updateStats() {
  const highRiskCount = allAlerts.filter((a) => a.risk_level === "high").length;
  if (statHighRisk) statHighRisk.textContent = String(highRiskCount);
  // TODO: intercept rate and active members from separate API if needed
}

async function loadAlerts() {
  try {
    const data = await listGuardianAlerts("monitor");
    console.log(data);
    allAlerts = Array.isArray(data?.alerts) ? data.alerts : [];
    totalItems = allAlerts.length;
    totalPages = Math.max(Math.ceil(totalItems / pageSize), 1);
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    renderPage();
    updateStats();
    updateNavBadge();
  } catch (err) {
    console.warn("加载联动消息失败:", err);
  }
}

function updateNavBadge() {
  const unreadCount = allAlerts.filter((a) => !a.is_read).length;

  // Top nav notification bell
  const navBadge = document.getElementById("topnav-alert-badge");
  if (navBadge) {
    if (unreadCount > 0) {
      navBadge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
      navBadge.classList.remove("hidden");
    } else {
      navBadge.classList.add("hidden");
    }
  }

  // Sidebar "风险联动消息" dot
  const sidebarDot = document.getElementById("sidebar-msg-dot");
  if (sidebarDot) {
    sidebarDot.classList.toggle("hidden", unreadCount === 0);
  }

  // Sidebar "监护人管理" dot (same count)
  const monitorDot = document.getElementById("sidebar-monitor-dot");
  if (monitorDot) {
    monitorDot.classList.toggle("hidden", unreadCount === 0);
  }
}

prevBtn?.addEventListener("click", () => {
  if (currentPage <= 1) return;
  currentPage -= 1;
  renderPage();
});

nextBtn?.addEventListener("click", () => {
  if (currentPage >= totalPages) return;
  currentPage += 1;
  renderPage();
});

markAllBtn?.addEventListener("click", async () => {
  try {
    await markGuardianAlertsRead(null, true, "monitor");
    allAlerts.forEach((a) => (a.is_read = true));
    renderPage();
    updateNavBadge();
  } catch (err) {
    console.warn("标记全部已读失败:", err);
  }
});

// Kick off
loadAlerts();
setInterval(loadAlerts, 10000);
