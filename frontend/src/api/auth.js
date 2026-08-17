import { apiClient } from "./client";

export async function registerAccount(email, password) {
  const { data } = await apiClient.post("/api/auth/register", { email, password });
  return data;
}

export async function login(email, password) {
  const { data } = await apiClient.post("/api/auth/login", { email, password });
  return data;
}

export async function getMe() {
  const { data } = await apiClient.get("/api/auth/me");
  return data;
}

export async function logoutRequest(refreshToken) {
  await apiClient.post("/api/auth/logout", { refresh_token: refreshToken });
}
