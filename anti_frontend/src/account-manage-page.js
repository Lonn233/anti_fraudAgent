import { showAlertModal } from "/ui/src/modal-one.js";
import { changeMyPassword } from "/ui/src/user-api.js";

function ensurePasswordModal() {
  let backdrop = document.getElementById("account-password-backdrop");
  if (backdrop) return backdrop;

  const html = `
<div class="fixed inset-0 z-[70] hidden items-center justify-center bg-black/60" id="account-password-backdrop">
  <div class="w-[92vw] max-w-md rounded-xl border border-outline-variant/40 bg-surface-container p-6 shadow-2xl">
    <h3 class="font-headline text-lg font-bold text-on-surface mb-4">修改密码</h3>
    <form id="account-password-form" class="space-y-4">
      <div>
        <label class="block text-sm text-on-surface-variant mb-1" for="account-current-password">当前密码</label>
        <input id="account-current-password" type="password" class="w-full rounded-lg border border-outline-variant/50 bg-surface px-3 py-2 text-on-surface focus:border-primary focus:outline-none" />
      </div>
      <div>
        <label class="block text-sm text-on-surface-variant mb-1" for="account-new-password">要修改的密码</label>
        <input id="account-new-password" type="password" class="w-full rounded-lg border border-outline-variant/50 bg-surface px-3 py-2 text-on-surface focus:border-primary focus:outline-none" />
      </div>
      <div id="account-password-error" class="min-h-[1.2rem] text-sm text-error"></div>
      <div class="flex justify-end gap-2 pt-2">
        <button id="account-password-cancel" type="button" class="px-4 py-2 rounded-lg border border-outline-variant/50 text-on-surface-variant hover:bg-surface-variant/30">取消</button>
        <button id="account-password-confirm" type="submit" class="px-4 py-2 rounded-lg bg-primary text-on-primary font-semibold hover:brightness-110">确认</button>
      </div>
    </form>
  </div>
</div>`;
  document.body.insertAdjacentHTML("beforeend", html);
  backdrop = document.getElementById("account-password-backdrop");
  return backdrop;
}

function openPasswordModal() {
  const backdrop = ensurePasswordModal();
  const currentInput = document.getElementById("account-current-password");
  const nextInput = document.getElementById("account-new-password");
  const errorEl = document.getElementById("account-password-error");
  const form = document.getElementById("account-password-form");
  const cancelBtn = document.getElementById("account-password-cancel");
  const confirmBtn = document.getElementById("account-password-confirm");

  if (!backdrop || !currentInput || !nextInput || !errorEl || !form || !cancelBtn || !confirmBtn) {
    showAlertModal("页面初始化失败，请刷新后重试");
    return;
  }

  const close = () => {
    backdrop.classList.add("hidden");
    backdrop.classList.remove("flex");
  };

  currentInput.value = "";
  nextInput.value = "";
  errorEl.textContent = "";
  confirmBtn.disabled = false;
  backdrop.classList.remove("hidden");
  backdrop.classList.add("flex");
  currentInput.focus();

  cancelBtn.onclick = () => close();
  backdrop.onclick = (event) => {
    if (event.target === backdrop) close();
  };

  form.onsubmit = async (event) => {
    event.preventDefault();
    const currentPassword = currentInput.value.trim();
    const newPassword = nextInput.value.trim();
    if (!currentPassword || !newPassword) {
      errorEl.textContent = "请填写当前密码和新密码";
      return;
    }
    if (newPassword.length < 6) {
      errorEl.textContent = "新密码至少 6 位";
      return;
    }

    errorEl.textContent = "";
    confirmBtn.disabled = true;
    try {
      await changeMyPassword(currentPassword, newPassword);
      close();
      showAlertModal("密码修改成功");
    } catch (err) {
      errorEl.textContent = err?.message || "修改失败";
    } finally {
      confirmBtn.disabled = false;
    }
  };
}

function bindPasswordAction() {
  const btn = document.getElementById("account-change-password-btn");
  if (!btn) return;
  btn.addEventListener("click", openPasswordModal);
}

function bindLogoutAction() {
  const logoutBtn = document.getElementById("account-logout-btn");
  if (!logoutBtn) return;
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("access_token");
    window.location.href = "/ui/Login.html";
  });
}

bindPasswordAction();
bindLogoutAction();
