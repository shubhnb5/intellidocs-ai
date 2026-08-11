import axios from "axios";

import { config } from "../config";

/**
 * Shared axios instance. Every domain's api/*.ts file (api/health.ts today;
 * api/documents.ts, api/chat.ts in later phases) imports this instead of
 * calling axios directly, so auth headers (Phase 8) and error handling only
 * need to be wired up in one place.
 */
export const apiClient = axios.create({
  baseURL: config.apiBaseUrl,
  timeout: 10_000,
});
