import { createContext, useContext, useEffect, useState } from "react";

import { getMe, login as loginRequest, logoutRequest, registerAccount } from "../api/auth";
import {
  AUTH_LOGOUT_EVENT,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./tokenStorage";

const AuthContext = createContext(null);

/** Single source of truth for "who's logged in" -- ProtectedRoute reads
 * `status` to gate routes, AppLayout reads `user` to show who's logged in.
 * Hydrates from a stored token on mount (calling /me both confirms it's
 * still valid and fetches the user it belongs to) and also reacts to
 * AUTH_LOGOUT_EVENT, fired by api/client.js (a failed silent refresh) or
 * Chat/useChatSocket.js (the WebSocket's own auth rejection) -- neither of
 * those has a React tree to update state through directly. */
export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading");
  const [user, setUser] = useState(null);

  useEffect(() => {
    async function hydrate() {
      if (!getAccessToken()) {
        setStatus("unauthenticated");
        return;
      }
      try {
        setUser(await getMe());
        setStatus("authenticated");
      } catch {
        clearTokens();
        setStatus("unauthenticated");
      }
    }
    hydrate();
  }, []);

  useEffect(() => {
    function handleLoggedOut() {
      setUser(null);
      setStatus("unauthenticated");
    }
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLoggedOut);
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, handleLoggedOut);
  }, []);

  async function login(email, password) {
    const pair = await loginRequest(email, password);
    setTokens({ accessToken: pair.access_token, refreshToken: pair.refresh_token });
    setUser(await getMe());
    setStatus("authenticated");
  }

  async function register(email, password) {
    const pair = await registerAccount(email, password);
    setTokens({ accessToken: pair.access_token, refreshToken: pair.refresh_token });
    setUser(await getMe());
    setStatus("authenticated");
  }

  async function logout() {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // Best-effort revoke -- clear local state regardless (e.g. offline,
        // or the token was already expired/rotated out).
      }
    }
    clearTokens();
    setUser(null);
    setStatus("unauthenticated");
  }

  return (
    <AuthContext.Provider value={{ status, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
