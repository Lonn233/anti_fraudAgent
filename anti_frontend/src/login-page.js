import { login } from "/ui/src/auth-api.js";

const form = document.getElementById("login-form");
const usernameInput = document.getElementById("login-username");
const passwordInput = document.getElementById("login-password");
const errorBox = document.getElementById("login-error");

if (form && usernameInput && passwordInput) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (errorBox) errorBox.textContent = "";

    try {
      const token = await login({
        username: usernameInput.value.trim(),
        password: passwordInput.value,
      });
      localStorage.setItem("access_token", token.access_token);
      window.location.href = "/ui/detectAgent.html";
    } catch (err) {
      if (errorBox) errorBox.textContent = err.message || "登录失败，请重试";
    }
  });
}
