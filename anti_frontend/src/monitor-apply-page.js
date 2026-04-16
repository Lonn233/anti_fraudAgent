import { decideGuardianRequest, listGuardianRequests } from "/ui/src/guardian-api.js";
import { showAlertModal, showPromptModal } from "/ui/src/modal-one.js";

const listBox = document.getElementById("monitor-apply-list");

function statusLabel(item) {
  if (item.status === "accepted") return "已通过";
  if (item.status === "rejected") return "已拒绝";
  return item._box === "incoming" ? "待处理" : "未处理";
}

function showError(message) {
  showAlertModal(message);
}

async function promptRequiredNote() {
  while (true) {
    const note = await showPromptModal("请输入给对方的备注", "确认并填写备注");
    if (!note) {
      return null;
    }
    const trimmed = note.trim();
    if (trimmed) {
      return trimmed;
    }
  }
}

function bindDecisionButtons() {
  listBox?.querySelectorAll(".accept-request-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const note = await promptRequiredNote();
        if (!note) {
          return;
        }
        await decideGuardianRequest(Number(btn.dataset.id), "accept", note);
        await loadRequests();
      } catch (err) {
        showError(err.message || "确认失败");
      }
    });
  });
  listBox?.querySelectorAll(".reject-request-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await decideGuardianRequest(Number(btn.dataset.id), "reject");
        await loadRequests();
      } catch (err) {
        showError(err.message || "拒绝失败");
      }
    });
  });
}

function renderRequests(items) {
  if (!listBox) return;
  if (!items.length) {
    listBox.innerHTML = '<p class="text-sm text-on-surface-variant">暂无申请消息</p>';
    return;
  }

  listBox.innerHTML = items
    .map(
      (item) => `
<div class="glass-panel rounded-lg p-4 border border-outline-variant/10">
  <div class="flex items-center justify-between gap-2">
    <div class="text-sm font-medium">${item.monitor_username} → ${item.ward_username}</div>
    <span class="text-xs px-2 py-1 rounded border border-outline-variant/20">${statusLabel(item)}</span>
  </div>
  <div class="text-xs text-on-surface-variant mt-2">${item.relationship || "未填写关系"} · ${item._box === "incoming" ? "收到申请" : "发出申请"}</div>
  ${
    item._box === "incoming" && item.status === "pending"
      ? `<div class="flex gap-2 mt-3">
           <button class="accept-request-btn px-3 py-1 bg-primary text-on-primary rounded text-xs" data-id="${item.id}" type="button">确认</button>
           <button class="reject-request-btn px-3 py-1 bg-surface-container-highest text-on-surface rounded text-xs border border-outline-variant/20" data-id="${item.id}" type="button">拒绝</button>
         </div>`
      : ""
  }
</div>`
    )
    .join("");
  bindDecisionButtons();
}

async function loadRequests() {
  const [incoming, outgoing] = await Promise.all([
    listGuardianRequests("incoming", "all"),
    listGuardianRequests("outgoing", "all"),
  ]);
  const items = [
    ...incoming.map((x) => ({ ...x, _box: "incoming" })),
    ...outgoing.map((x) => ({ ...x, _box: "outgoing" })),
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  renderRequests(items);
}

loadRequests().catch((err) => showError(err.message || "加载申请消息失败"));
