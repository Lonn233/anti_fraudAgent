import { checkRegisterAvailability } from "/ui/src/auth-api.js?v=20260414";

const form = document.getElementById("register-form");
const usernameInput = document.getElementById("reg1-username");
const phoneInput = document.getElementById("reg1-phone");
const passwordInput = document.getElementById("reg1-password");
const errorBox = document.getElementById("register1-error");
const usernameError = document.getElementById("reg1-username-error");
const phoneError = document.getElementById("reg1-phone-error");
const passwordError = document.getElementById("reg1-password-error");

function isValidUsername(username) {
  return /^[\s\S]{4,8}$/.test(username);
}

function isValidPhone(phone) {
  return /^\d{11}$/.test(phone);
}

function clearFieldErrors() {
  if (usernameError) usernameError.textContent = "";
  if (phoneError) phoneError.textContent = "";
  if (passwordError) passwordError.textContent = "";
}

function setFieldError(field, message) {
  const map = {
    username: usernameError,
    phone: phoneError,
    password: passwordError,
  };
  const target = map[field];
  if (target) target.textContent = message;
}

if (form && usernameInput && phoneInput && passwordInput) {
  usernameInput.addEventListener("input", () => setFieldError("username", ""));
  phoneInput.addEventListener("input", () => setFieldError("phone", ""));
  passwordInput.addEventListener("input", () => setFieldError("password", ""));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorBox) errorBox.textContent = "";
    clearFieldErrors();

    const draft = {
      username: usernameInput.value.trim(),
      phone: phoneInput.value.trim(),
      password: passwordInput.value,
    };

    if (!draft.username) {
      setFieldError("username", "用户名不能为空");
      return;
    }
    if (!draft.phone) {
      setFieldError("phone", "手机号不能为空");
      return;
    }
    if (!draft.password) {
      setFieldError("password", "密码不能为空");
      return;
    }
    if (!isValidUsername(draft.username)) {
      setFieldError("username", "用户名需为4-8位");
      return;
    }
    if (!isValidPhone(draft.phone)) {
      setFieldError("phone", "手机号需为11位数字");
      return;
    }

    try {
      const check = await checkRegisterAvailability({
        username: draft.username,
        phone: draft.phone,
      });
      if (check?.username_exists) {
        setFieldError("username", "用户名已存在");
        return;
      }
      if (check?.phone_exists) {
        setFieldError("phone", "手机号已存在");
        return;
      }
    } catch (err) {
      if (errorBox) errorBox.textContent = err?.message || "校验失败，请稍后重试";
      return;
    }

    sessionStorage.setItem("register_draft", JSON.stringify(draft));
    window.location.href = "/ui/register2.html";
  });
}
