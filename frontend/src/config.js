/**
 * Central place for environment-derived config, mirroring config.js in the
 * reference admin-ui project. Everything that reads import.meta.env lives
 * here — components import from this file, never from import.meta.env
 * directly, so there's exactly one place to check when an env var changes.
 */
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const config = {
  apiBaseUrl,
  // /ws/chat rides the same host/port as the REST API, just over ws(s)://
  // instead of http(s):// — derive it instead of adding a second env var.
  wsUrl: `${apiBaseUrl.replace(/^http/, "ws")}/ws/chat`,
};
