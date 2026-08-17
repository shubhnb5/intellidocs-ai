/**
 * Raw token persistence -- localStorage, not React state, so both the
 * axios interceptor (api/client.js, which runs outside any component) and
 * AuthContext can read/write the same tokens without prop-drilling a store
 * through every call site. localStorage over an httpOnly cookie is a
 * deliberate trade-off for this project: simpler (no cookie/CORS/CSRF
 * wiring), at the cost of tokens being readable by any script on the page
 * (XSS) -- worth naming explicitly rather than leaving implicit.
 */

const ACCESS_TOKEN_KEY = "intellidocs_access_token";
const REFRESH_TOKEN_KEY = "intellidocs_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(pair) {
  localStorage.setItem(ACCESS_TOKEN_KEY, pair.accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, pair.refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// Fired whenever something decides the session is over -- a failed silent
// refresh (api/client.js) or an auth-rejected WebSocket (Chat/useChatSocket.js).
// AuthContext listens for this so every part of the app reacts the same way
// (drop to "unauthenticated", ProtectedRoute redirects to /login) regardless
// of which subsystem noticed first.
export const AUTH_LOGOUT_EVENT = "intellidocs:auth-logout";

export function notifyLoggedOut() {
  clearTokens();
  window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
}
