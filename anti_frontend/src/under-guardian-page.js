import { applyGuardianRequest, decideGuardianRequest, deleteRelation, listGuardianRequests, listRelations, updateRelation } from "/ui/src/guardian-api.js";
import { showAlertModal, showPromptModal } from "/ui/src/modal-one.js";

const tbody = document.querySelector("table tbody");
const openBtn = document.getElementById("open-ward-modal-btn");
const summaryEl = document.getElementById("ward-pagination-summary");
const prevBtn = document.getElementById("ward-pagination-prev");
const nextBtn = document.getElementById("ward-pagination-next");
const pageBtn = document.getElementById("ward-pagination-page");
const searchNoteInput = document.getElementById("ward-search-note");
const searchUsernameInput = document.getElementById("ward-search-username");
const searchRelationSelect = document.getElementById("ward-search-relation");
const searchPhoneInput = document.getElementById("ward-search-phone");
const searchBtn = document.getElementById("ward-search-btn");
let currentPage = 1;
const pageSize = 10;
let totalPages = 1;
let totalItems = 0;
let allRelations = [];
let filteredRelations = [];

function showError(message) {
  showAlertModal(message);
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

function ensureModal() {
  const html = `
<div class="modal-one-backdrop hidden" id="guardian-modal-backdrop">
  <div aria-labelledby="guardian-modal-title" aria-modal="true" class="modal-one" role="dialog">
    <div class="modal-one-header">
      <h3 id="guardian-modal-title">添加被监护人</h3>
    </div>
    <form id="guardian-modal-form">
      <div>
        <label for="guardian-username-input">用户名</label>
        <input id="guardian-username-input" placeholder="请输入被监护人用户名" type="text"/>
      </div>
      <div>
        <label for="guardian-name-input">备注</label>
        <input id="guardian-name-input" placeholder="请输入被监护人备注" type="text"/>
      </div>
      <div>
        <label for="guardian-relation-select">关系</label>
        <select id="guardian-relation-select">
          <option value="">请选择关系</option>
          <option value="儿子">儿子</option>
          <option value="女儿">女儿</option>
          <option value="父亲">父亲</option>
          <option value="母亲">母亲</option>
          <option value="家属">家属</option>
          <option value="朋友">朋友</option>
          <option value="丈夫">丈夫</option>
          <option value="妻子">妻子</option>
        </select>
      </div>
      <div class="modal-one-actions">
        <button class="modal-one-btn-cancel" id="guardian-modal-cancel-btn" type="button">取消</button>
        <button class="modal-one-btn-add" type="submit">提交申请</button>
      </div>
    </form>
  </div>
</div>`;
  document.body.insertAdjacentHTML("beforeend", html);
}

function createRelationRow(item, index) {
  const row = document.createElement("tr");
  row.className = "hover:bg-surface-container-highest/30 transition-colors group";
  row.innerHTML = `
<td class="px-6 py-5 text-sm font-headline text-outline/80">${String((currentPage - 1) * pageSize + index + 1).padStart(2, "0")}</td>
<td class="px-6 py-5">
  <div class="flex items-center gap-3">
    <div class="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary font-bold text-xs border border-primary/20">${(item.note || "?").charAt(0)}</div>
    <span class="text-sm font-medium text-on-surface">${item.note || "-"}</span>
  </div>
</td>
<td class="px-6 py-5"><span class="text-xs text-on-surface-variant">${item.relationship || "-"}</span></td>
<td class="px-6 py-5"><span class="text-xs font-mono text-on-surface-variant">${item.monitor_username || item.monitor_id}</span></td>
<td class="px-6 py-5"><span class="text-xs text-on-surface-variant">${item.phone || "--"}</span></td>
<td class="px-6 py-5 text-right">
  <button class="ward-edit-btn p-2 text-primary hover:bg-primary/10 rounded-md transition-colors" title="编辑备注" type="button">
    <span class="material-symbols-outlined text-lg">edit</span>
  </button>
  <button class="ward-delete-btn p-2 text-error hover:bg-error/10 rounded-md transition-colors" title="删除" type="button">
    <span class="material-symbols-outlined text-lg">delete</span>
  </button>
</td>`;
  row.querySelector(".ward-edit-btn")?.addEventListener("click", async () => {
    try {
      const note = await showPromptModal("请输入新的备注", "编辑备注");
      if (!note) {
        showError("备注为必填项");
        return;
      }
      await updateRelation(item.id, note);
      await loadAll();
    } catch (err) {
      showError(err.message || "编辑备注失败");
    }
  });
  row.querySelector(".ward-delete-btn")?.addEventListener("click", async () => {
    try {
      await deleteRelation(item.id);
      await loadAll();
    } catch (err) {
      showError(err.message || "删除失败");
    }
  });
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
    const usernameMatched = matchesFilter(item.monitor_username || item.monitor_id, filters.username);
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
  pageList.forEach((item, index) => tbody.appendChild(createRelationRow(item, index)));
  renderPagination(pageList.length);
}

function renderRequests(requests) {
  let box = document.getElementById("linkage-requests-box");
  if (!box) {
    box = document.getElementById("requests-panel");
  }
  if (!box) return;

  if (!requests.length) {
    box.innerHTML = '<p class="text-sm text-on-surface-variant">暂无联动申请记录</p>';
    return;
  }

  box.innerHTML = requests
    .map(
      (req) => `
<div class="py-3 border-b border-outline-variant/10 last:border-0">
  <div class="flex items-center justify-between gap-2">
    <div class="text-sm">${req.monitor_username} → ${req.ward_username}</div>
    <span class="text-xs px-2 py-1 rounded border border-outline-variant/20">${requestStatusLabel(req, req._box === "incoming")}</span>
  </div>
  <div class="text-xs text-on-surface-variant mt-1">${req.relationship || "未填写关系"} · ${req._box === "incoming" ? "收到的申请" : "我发出的申请"}</div>
  <div class="flex gap-2 mt-2">
    ${
      req.status === "pending" && req._box === "incoming"
        ? `<button class="accept-request-btn px-3 py-1 bg-primary text-on-primary rounded text-xs" data-id="${req.id}" type="button">确认</button>
           <button class="reject-request-btn px-3 py-1 bg-surface-container-highest text-on-surface rounded text-xs border border-outline-variant/20" data-id="${req.id}" type="button">拒绝</button>`
        : ""
    }
  </div>
</div>`
    )
    .join("");
  box.querySelectorAll(".accept-request-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const note = await promptRequiredNote();
        if (!note) {
          return;
        }
        await decideGuardianRequest(Number(btn.dataset.id), "accept", note);
        await loadAll();
      } catch (err) {
        showError(err.message || "接受失败");
      }
    });
  });
  box.querySelectorAll(".reject-request-btn").forEach((btn) => {
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

async function loadAll() {
  if (!tbody) return;
  const [relationsPage, incomingAll, outgoingAll] = await Promise.all([
    listRelations("ward", 1, 100),
    listGuardianRequests("incoming", "all"),
    listGuardianRequests("outgoing", "all"),
  ]);
  allRelations = Array.isArray(relationsPage?.items) ? relationsPage.items : [];
  const requests = [
    ...incomingAll.map((r) => ({ ...r, _box: "incoming" })),
    ...outgoingAll.map((r) => ({ ...r, _box: "outgoing" })),
  ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  applyFilters();
  renderRequests(requests || []);
}

function renderPagination(currentCount) {
  if (!summaryEl || !prevBtn || !nextBtn || !pageBtn) return;
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = totalItems === 0 ? 0 : start + currentCount - 1;
  summaryEl.textContent = `显示 ${start}-${end} 条，共 ${totalItems} 条记录；共 ${totalPages} 页`;
  pageBtn.textContent = `${currentPage} / ${totalPages}`;
  prevBtn.disabled = currentPage <= 1;
  nextBtn.disabled = currentPage >= totalPages;
}

function bindModal() {
  const backdrop = document.getElementById("guardian-modal-backdrop");
  const form = document.getElementById("guardian-modal-form");
  const cancelBtn = document.getElementById("guardian-modal-cancel-btn");
  const usernameInput = document.getElementById("guardian-username-input");
  const nameInput = document.getElementById("guardian-name-input");
  const relationSelect = document.getElementById("guardian-relation-select");

  openBtn?.addEventListener("click", () => backdrop?.classList.remove("hidden"));
  cancelBtn?.addEventListener("click", () => backdrop?.classList.add("hidden"));
  backdrop?.addEventListener("click", (event) => {
    if (event.target === backdrop) {
      backdrop.classList.add("hidden");
    }
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
      await applyGuardianRequest("ward", usernameInput.value.trim(), nameInput.value.trim(), relationSelect.value);
      backdrop?.classList.add("hidden");
      form.reset();
      currentPage = 1;
      await loadAll();
    } catch (err) {
      showError(err.message || "申请失败");
    }
  });
}

ensureModal();
bindModal();
loadAll().catch((err) => showError(err.message || "加载失败"));
