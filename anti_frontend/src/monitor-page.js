import { applyGuardianRequest, decideGuardianRequest, deleteRelation, listGuardianRequests, listRelations, updateRelation } from "/ui/src/guardian-api.js";
import { showAlertModal, showPromptModal } from "/ui/src/modal-one.js";

const tbody = document.querySelector("table tbody");
const form = document.getElementById("guardian-modal-form");
const openBtn = document.getElementById("open-guardian-modal-btn");
const backdrop = document.getElementById("guardian-modal-backdrop");
const cancelBtn = document.getElementById("guardian-modal-cancel-btn");
const titleEl = document.getElementById("guardian-modal-title");
const confirmBtn = document.getElementById("guardian-modal-confirm-btn");
const deleteMessage = document.getElementById("guardian-delete-message");
const usernameInput = document.getElementById("guardian-username-input");
const nameInput = document.getElementById("guardian-name-input");
const relationSelect = document.getElementById("guardian-relation-select");
const usernameField = document.getElementById("guardian-username-field");
const nameField = document.getElementById("guardian-name-field");
const relationField = document.getElementById("guardian-relation-field");
const summaryEl = document.getElementById("monitor-pagination-summary");
const prevBtn = document.getElementById("monitor-pagination-prev");
const nextBtn = document.getElementById("monitor-pagination-next");
const pageBtn = document.getElementById("monitor-pagination-page");
const requestsPanel = document.getElementById("requests-panel");
const searchNoteInput = document.getElementById("monitor-search-note");
const searchUsernameInput = document.getElementById("monitor-search-username");
const searchRelationSelect = document.getElementById("monitor-search-relation");
const searchPhoneInput = document.getElementById("monitor-search-phone");
const searchBtn = document.getElementById("monitor-search-btn");

let currentMode = "add";
let currentItem = null;
let currentPage = 1;
const pageSize = 10;
let totalPages = 1;
let totalItems = 0;
let allRelations = [];
let filteredRelations = [];

function showError(message) {
  showAlertModal(message);
}

function closeModal() {
  backdrop?.classList.add("hidden");
}

function setMode(mode) {
  currentMode = mode;
  if (!titleEl || !confirmBtn || !deleteMessage) return;
  if (mode === "add") {
    titleEl.textContent = "添加监护人";
    confirmBtn.textContent = "提交申请";
    deleteMessage.style.display = "none";
    usernameField.style.display = "";
    nameField.style.display = "";
    relationField.style.display = "";
    usernameInput.readOnly = false;
    usernameInput.value = "";
    nameInput.value = "";
    relationSelect.value = "";
  } else if (mode === "edit") {
    titleEl.textContent = "修改备注";
    confirmBtn.textContent = "保存";
    deleteMessage.style.display = "none";
    usernameField.style.display = "none";
    nameField.style.display = "";
    relationField.style.display = "none";
    nameInput.value = currentItem?.note || "";
  } else {
    titleEl.textContent = "删除监护关系";
    confirmBtn.textContent = "确认";
    deleteMessage.style.display = "block";
    usernameField.style.display = "none";
    nameField.style.display = "none";
    relationField.style.display = "none";
  }
}

function openModal(mode, item) {
  currentItem = item || null;
  setMode(mode);
  backdrop?.classList.remove("hidden");
}

function createRow(item) {
  const row = document.createElement("tr");
  row.className = "hover:bg-surface-container-highest/30 transition-colors";
  row.innerHTML = `
<td class="px-8 py-6">
  <div class="flex items-center gap-3">
    <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold font-headline border border-primary/20">${(item.note || "?").charAt(0)}</div>
    <div class="font-medium">${item.note || "-"}</div>
  </div>
</td>
<td class="px-8 py-6 text-on-surface-variant">${item.relationship || "-"}</td>
<td class="px-8 py-6 font-mono text-sm text-tertiary">${item.ward_username || item.ward_id}</td>
<td class="px-8 py-6 text-on-surface-variant">${item.phone || "--"}</td>
<td class="px-8 py-6 text-right">
  <div class="flex justify-end gap-2">
    <button class="monitor-edit-btn p-2 hover:bg-primary/10 text-primary rounded-lg transition-all active:scale-90" title="编辑" type="button">
      <span class="material-symbols-outlined text-lg">edit</span>
    </button>
    <button class="monitor-delete-btn p-2 hover:bg-error/10 text-error rounded-lg transition-all active:scale-90" title="删除" type="button">
      <span class="material-symbols-outlined text-lg">delete</span>
    </button>
  </div>
</td>`;
  row.querySelector(".monitor-edit-btn")?.addEventListener("click", () => openModal("edit", item));
  row.querySelector(".monitor-delete-btn")?.addEventListener("click", () => openModal("delete", item));
  return row;
}

function getSearchFilters() {
  return {
    note: (searchNoteInput?.value || "").trim().toLowerCase(),
    username: (searchUsernameInput?.value || "").trim().toLowerCase(),
    relation: (searchRelationSelect?.value || "").trim().toLowerCase(),
    phone: (searchPhoneInput?.value || "").trim().toLowerCase(),
  };
}

function matchesFilter(value, keyword) {
  if (!keyword) return true;
  return String(value || "").toLowerCase().includes(keyword);
}

function applyFilters() {
  const filters = getSearchFilters();
  filteredRelations = allRelations.filter((item) => {
    const noteMatched = matchesFilter(item.note, filters.note);
    const usernameMatched = matchesFilter(item.ward_username || item.ward_id, filters.username);
    const relationMatched = !filters.relation || String(item.relationship || "").toLowerCase() === filters.relation;
    const phoneMatched = matchesFilter(item.phone, filters.phone);
    return noteMatched && usernameMatched && relationMatched && phoneMatched;
  });
  totalItems = filteredRelations.length;
  totalPages = Math.max(Math.ceil(totalItems / pageSize), 1);
  if (currentPage > totalPages) currentPage = totalPages;
  if (currentPage < 1) currentPage = 1;
  renderCurrentPage();
}

function renderCurrentPage() {
  if (!tbody) return;
  const startIndex = (currentPage - 1) * pageSize;
  const pageList = filteredRelations.slice(startIndex, startIndex + pageSize);
  tbody.innerHTML = "";
  pageList.forEach((item) => tbody.appendChild(createRow(item)));
  renderPagination(pageList.length);
}

async function loadRelations() {
  const result = await listRelations("monitor", 1, 100);
  allRelations = Array.isArray(result?.items) ? result.items : [];
  applyFilters();
}

function renderPagination(currentCount) {
  if (!summaryEl || !prevBtn || !nextBtn || !pageBtn) return;
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = totalItems === 0 ? 0 : start + currentCount - 1;
  summaryEl.textContent = `显示 ${start} 到 ${end} 条数据，共 ${totalItems} 条；共 ${totalPages} 页`;
  pageBtn.textContent = `${currentPage} / ${totalPages}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
}

function requestStatusLabel(req, isIncoming) {
  if (req.status === "accepted") return "已通过";
  if (req.status === "rejected") return "已拒绝";
  if (!isIncoming) return "未处理";
  return "待确认";
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

function bindRequestButtons() {
  requestsPanel?.querySelectorAll(".accept-request-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const note = await promptRequiredNote();
        if (!note) return;
        await decideGuardianRequest(Number(btn.dataset.id), "accept", note);
        await loadAll();
      } catch (err) {
        showError(err.message || "接受失败");
      }
    });
  });
  requestsPanel?.querySelectorAll(".reject-request-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await decideGuardianRequest(Number(btn.dataset.id), "reject");
        await loadAll();
      } catch (err) {
        showError(err.message || "拒绝失败");
      }
    });
  });
}

function renderRequests(requests) {
  if (!requestsPanel) return;
  if (!requests.length) {
    requestsPanel.innerHTML = '<p class="text-sm text-on-surface-variant">暂无联动申请记录</p>';
    return;
  }

  requestsPanel.innerHTML = requests
    .map(
      (req) => `
<div class="py-3 border-b border-outline-variant/10 last:border-0">
  <div class="flex items-center justify-between gap-2">
    <div class="text-sm">${req.monitor_username} → ${req.ward_username}</div>
    <span class="text-xs px-2 py-1 rounded border border-outline-variant/20">${requestStatusLabel(req, req._box === "incoming")}</span>
  </div>
  <div class="text-xs text-on-surface-variant mt-1">${req.relationship || "未填写关系"} · ${req._box === "incoming" ? "收到的申请" : "我发出的申请"}</div>
  ${
    req.status === "pending" && req._box === "incoming"
      ? `<div class="flex gap-2 mt-2">
           <button class="accept-request-btn px-3 py-1 bg-primary text-on-primary rounded text-xs" data-id="${req.id}" type="button">确认</button>
           <button class="reject-request-btn px-3 py-1 bg-surface-container-highest text-on-surface rounded text-xs border border-outline-variant/20" data-id="${req.id}" type="button">拒绝</button>
         </div>`
      : ""
  }
</div>`
    )
    .join("");
  bindRequestButtons();
}

async function loadAll() {
  const [incomingAll, outgoingAll] = await Promise.all([
    listGuardianRequests("incoming", "all"),
    listGuardianRequests("outgoing", "all"),
  ]);
  const requests = [
    ...incomingAll.map((r) => ({ ...r, _box: "incoming" })),
    ...outgoingAll.map((r) => ({ ...r, _box: "outgoing" })),
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  await loadRelations();
  renderRequests(requests);
}

async function submitApply() {
  const targetUsername = usernameInput.value.trim();
  const name = nameInput.value.trim();
  const relationship = relationSelect.value;
  if (!targetUsername || !name || !relationship) {
    throw new Error("请填写完整申请信息");
  }
  await applyGuardianRequest("monitor", targetUsername, name, relationship);
}

async function submitDelete() {
  if (!currentItem?.id) {
    throw new Error("缺少待删除的监护关系");
  }
  await deleteRelation(currentItem.id);
}

async function submitEdit() {
  if (!currentItem?.id) {
    throw new Error("缺少待修改的监护关系");
  }
  const note = (nameInput.value || "").trim();
  if (!note) {
    throw new Error("备注为必填项");
  }
  await updateRelation(currentItem.id, note);
}

openBtn?.addEventListener("click", () => openModal("add"));
cancelBtn?.addEventListener("click", closeModal);
backdrop?.addEventListener("click", (event) => {
  if (event.target === backdrop) closeModal();
});
searchBtn?.addEventListener("click", () => {
  currentPage = 1;
  applyFilters();
});
prevBtn?.addEventListener("click", async () => {
  if (currentPage <= 1) return;
  currentPage -= 1;
  renderCurrentPage();
});
nextBtn?.addEventListener("click", async () => {
  if (currentPage >= totalPages) return;
  currentPage += 1;
  renderCurrentPage();
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    if (currentMode === "delete") {
      await submitDelete();
    } else if (currentMode === "edit") {
      await submitEdit();
    } else {
      await submitApply();
    }
    closeModal();
    currentPage = 1;
    await loadAll();
  } catch (err) {
    showError(err.message || "操作失败");
  }
});

loadAll().catch((err) => showError(err.message || "加载失败"));
