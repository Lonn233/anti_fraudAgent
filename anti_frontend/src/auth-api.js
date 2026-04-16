import { postJson } from "/ui/src/http.js";

export async function login(payload) {
  return postJson("/auth/login/json", payload);
}

export async function register(payload) {
  return postJson("/auth/register", payload);
}

export async function checkRegisterAvailability(payload) {
  return postJson("/auth/check", payload);
}
