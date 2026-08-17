import axios from "axios";

import { config } from "../config";
import {
  getAccessToken,
  getRefreshToken,
  notifyLoggedOut,
  setTokens,
} from "../Auth/tokenStorage";

/**
 * Shared axios instance. Every domain's api/*.js file imports this instead
 * of calling axios directly, so auth headers and 401-refresh handling only
 * need to be wired up in one place.
 */
export const apiClient = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 10_000,
});

apiClient.interceptors.request.use((requestConfig) => {
  const token = getAccessToken();
  if (token) {
    requestConfig.headers.Authorization = `Bearer ${token}`;
  }
  return requestConfig;
});

// These endpoints return their own meaningful 401s (wrong password, an
// already-used/expired refresh token) -- the retry-after-refresh logic
// below must never intercept those as "session needs refreshing".
const AUTH_ENDPOINTS = ["/api/auth/login", "/api/auth/register", "/api/auth/refresh"];

// A bare axios call, not apiClient -- going through apiClient here would
// route a failed refresh back into this same interceptor.
async function requestNewAccessToken(refreshToken) {
  const { data } = await axios.post(
    `${config.apiBaseUrl}/api/auth/refresh`,
    { refresh_token: refreshToken },
  );
  setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
  return data.access_token;
}

// Concurrent 401s share one in-flight refresh instead of each firing their
// own -- refresh tokens rotate on use (see backend/services/auth.py), so a
// "refresh stampede" would invalidate all but the last rotation and log
// every other in-flight request out.
let refreshPromise = null;

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }
  try {
    return await requestNewAccessToken(refreshToken);
  } catch {
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isAuthEndpoint = AUTH_ENDPOINTS.some((path) => originalRequest?.url?.includes(path));

    if (error.response?.status !== 401 || isAuthEndpoint || originalRequest._retry) {
      return Promise.reject(error);
    }
    originalRequest._retry = true;

    refreshPromise ??= refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
    const newAccessToken = await refreshPromise;

    if (!newAccessToken) {
      notifyLoggedOut();
      return Promise.reject(error);
    }

    originalRequest.headers = originalRequest.headers ?? {};
    originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
    return apiClient(originalRequest);
  },
);
