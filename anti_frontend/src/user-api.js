import { getJson, putJson } from "/ui/src/http.js";

export async function getMe() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("未登录");
  }
  return getJson("/users/me", token);
}

export async function updateMeProfile(payload) {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("未登录");
  }
  return putJson("/users/me/profile", payload, token);
}

export async function changeMyPassword(currentPassword, newPassword) {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw new Error("未登录");
  }
  return putJson(
    "/users/me/password",
    {
      current_password: currentPassword,
      new_password: newPassword,
    },
    token
  );
}
