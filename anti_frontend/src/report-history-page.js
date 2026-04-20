import { listDetectRecords } from "/ui/src/detect-api.js";

const listEl = document.getElementById("report-history-list");
const totalEl = document.getElementById("report-total-scans");
const activeEl = document.getElementById("report-active-threats");
const summaryEl = document.getElementById("report-history-summary");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${y}.${m}.${d} ${hh}:${mm}`;
}

function getRiskMeta(riskIndex) {
  const n = Number(riskIndex || 0);
  if (n >= 0.8) {
    return { label: "高危风险", bar: "bg-error", tag: "bg-error/20 text-error", iconBg: "bg-error/10", icon: "warning", iconText: "text-error" };
  }
  if (n >= 0.5) {
    return { label: "中等风险", bar: "bg-primary", tag: "bg-primary/20 text-primary", iconBg: "bg-primary/10", icon: "info", iconText: "text-primary" };
  }
  return { label: "安全", bar: "bg-tertiary", tag: "bg-tertiary/20 text-tertiary", iconBg: "bg-tertiary/10", icon: "verified_user", iconText: "text-tertiary" };
}

function renderItem(item) {
  const risk = getRiskMeta(item.risk_index);
  const title = item.kind ? `${item.kind} 检测` : "风险检测记录";
  const content = item.detect_content || "无检测内容";
  const timeText = formatTime(item.created_at);
  const idText = `ST-${item.id}`;
  return `
<div class="group relative overflow-hidden bg-surface-container-low hover:bg-surface-container transition-colors duration-300 rounded-xl">
  <div class="absolute left-0 top-0 bottom-0 w-1 ${risk.bar}"></div>
  <div class="p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
    <div class="flex items-start gap-5 max—widthLi">
      <div class="p-4 ${risk.iconBg} rounded-xl">
        <span class="material-symbols-outlined ${risk.iconText}" style='font-variation-settings: "FILL" 1;'>${risk.icon}</span>
      </div>
      <div>
        <div class="flex items-center gap-3 mb-1">
          <h3 class="text-lg font-bold font-headline">${escapeHtml(title)}</h3>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${risk.tag}">${risk.label}</span>
        </div>
        <p class="text-on-surface-variant text-sm mb-2">${escapeHtml(content)}</p>
        <div class="flex items-center gap-4 text-[11px] text-outline font-label tracking-wide uppercase">
          <span class="flex items-center gap-1"><span class="material-symbols-outlined text-xs">schedule</span> ${timeText}</span>
          <span class="flex items-center gap-1"><span class="material-symbols-outlined text-xs">fingerprint</span> ID: ${idText}</span>
        </div>
      </div>
    </div>
    <div class="flex items-center gap-3">
      <a class="px-6 py-2 border border-outline-variant/30 hover:border-primary/50 text-on-surface text-sm font-semibold rounded-lg transition-all active:scale-95" href="/ui/reportDetail.html?detect_id=${encodeURIComponent(item.id)}">查看详情</a>
    </div>
  </div>
</div>`;
}

function renderList(items) {
  if (!listEl) return;
  if (!items.length) {
    listEl.innerHTML = '<div class="text-sm text-on-surface-variant p-6 bg-surface-container-low rounded-xl">暂无检测记录</div>';
    return;
  }
  listEl.innerHTML = items.map(renderItem).join("");
}

async function init() {
  const items = await listDetectRecords(200);
  const rows = Array.isArray(items) ? items : [];
  const activeCount = rows.filter((x) => Number(x.risk_index || 0) >= 0.8).length;
  if (totalEl) totalEl.textContent = String(rows.length);
  if (activeEl) activeEl.textContent = String(activeCount).padStart(2, "0");
  if (summaryEl) summaryEl.textContent = `SHOWING ${rows.length} OF ${rows.length} RECORDS`;
  renderList(rows);
}

init().catch(() => {
  if (listEl) listEl.innerHTML = '<div class="text-sm text-error p-6 bg-error/10 rounded-xl">加载检测记录失败，请稍后重试</div>';
});
