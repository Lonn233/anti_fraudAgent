function ensureAlertModal() {
  let backdrop = document.getElementById("modal-one-alert-backdrop");
  if (backdrop) {
    return backdrop;
  }

  const html = `
<div class="modal-one-backdrop hidden" id="modal-one-alert-backdrop">
  <div aria-labelledby="modal-one-alert-title" aria-modal="true" class="modal-one" role="dialog">
    <div class="modal-one-header">
      <h3 id="modal-one-alert-title">提示</h3>
    </div>
    <form id="modal-one-alert-form">
      <p class="text-sm text-on-surface-variant" id="modal-one-alert-message"></p>
      <div class="modal-one-actions">
        <button class="modal-one-btn-add" id="modal-one-alert-ok" type="submit">确定</button>
      </div>
    </form>
  </div>
</div>`;
  document.body.insertAdjacentHTML("beforeend", html);
  backdrop = document.getElementById("modal-one-alert-backdrop");
  return backdrop;
}

export function showAlertModal(message) {
  const backdrop = ensureAlertModal();
  const msgEl = document.getElementById("modal-one-alert-message");
  const form = document.getElementById("modal-one-alert-form");

  if (!backdrop || !msgEl || !form) {
    return;
  }

  msgEl.textContent = normalizeModalMessage(message);
  backdrop.classList.remove("hidden");

  const close = () => backdrop.classList.add("hidden");
  form.onsubmit = (event) => {
    event.preventDefault();
    close();
  };
  backdrop.onclick = (event) => {
    if (event.target === backdrop) {
      close();
    }
  };
}

function ensurePromptModal() {
  let backdrop = document.getElementById("modal-one-prompt-backdrop");
  if (backdrop) {
    return backdrop;
  }

  const html = `
<div class="modal-one-backdrop hidden" id="modal-one-prompt-backdrop">
  <div aria-labelledby="modal-one-prompt-title" aria-modal="true" class="modal-one" role="dialog">
    <div class="modal-one-header">
      <h3 id="modal-one-prompt-title">请输入内容</h3>
    </div>
    <form id="modal-one-prompt-form">
      <p class="text-sm text-on-surface-variant" id="modal-one-prompt-message"></p>
      <div>
        <label for="modal-one-prompt-input">内容</label>
        <input id="modal-one-prompt-input" type="text"/>
      </div>
      <div class="modal-one-actions">
        <button class="modal-one-btn-cancel" id="modal-one-prompt-cancel" type="button">取消</button>
        <button class="modal-one-btn-add" type="submit">确定</button>
      </div>
    </form>
  </div>
</div>`;
  document.body.insertAdjacentHTML("beforeend", html);
  return document.getElementById("modal-one-prompt-backdrop");
}

export function showPromptModal(message, title = "请输入内容") {
  return new Promise((resolve) => {
    const backdrop = ensurePromptModal();
    const titleEl = document.getElementById("modal-one-prompt-title");
    const messageEl = document.getElementById("modal-one-prompt-message");
    const inputEl = document.getElementById("modal-one-prompt-input");
    const form = document.getElementById("modal-one-prompt-form");
    const cancelBtn = document.getElementById("modal-one-prompt-cancel");
    if (!backdrop || !titleEl || !messageEl || !inputEl || !form || !cancelBtn) {
      resolve("");
      return;
    }

    titleEl.textContent = title;
    messageEl.textContent = normalizeModalMessage(message);
    inputEl.value = "";
    backdrop.classList.remove("hidden");
    inputEl.focus();

    const close = (value) => {
      backdrop.classList.add("hidden");
      resolve(value);
    };
    form.onsubmit = (event) => {
      event.preventDefault();
      close((inputEl.value || "").trim());
    };
    cancelBtn.onclick = () => close("");
    backdrop.onclick = (event) => {
      if (event.target === backdrop) {
        close("");
      }
    };
  });
}

function normalizeModalMessage(message) {
  if (typeof message === "string") {
    return message;
  }
  if (Array.isArray(message)) {
    return message
      .map((item) => normalizeModalMessage(item))
      .filter(Boolean)
      .join("；");
  }
  if (message && typeof message === "object") {
    if (typeof message.msg === "string") {
      return message.msg;
    }
    if (Array.isArray(message.detail)) {
      return normalizeModalMessage(message.detail);
    }
    try {
      return JSON.stringify(message);
    } catch (_err) {
      return String(message);
    }
  }
  return String(message || "");
}
