import { useQuery } from "@tanstack/react-query";
import { Outlet, useNavigate } from "react-router-dom";

import { getHealth } from "../api/health";
import { useAuth } from "../Auth/AuthContext";
import { BrandMark } from "../components/BrandMark";

const STATUS_STYLES = {
  checking: { dot: "bg-slate-400 animate-pulse", bg: "bg-slate-100", text: "text-slate-600" },
  online: { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700" },
  offline: { dot: "bg-rose-500", bg: "bg-rose-50", text: "text-rose-700" },
};

/**
 * Persistent shell rendered on every route — header + backend connection
 * status. Page-specific content (chat, upload, agent activity panel) renders
 * into <Outlet /> below it. Mirrors AppLayout/AppLayout.js in the reference
 * admin-ui project, minus the nav sidebar/menu (nothing to navigate to yet).
 */
export function AppLayout() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: 1,
  });
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const status = isPending ? "checking" : isError ? "offline" : "online";
  const statusStyle = STATUS_STYLES[status];

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-svh flex-col bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <BrandMark className="h-9 w-9" />
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-slate-900">IntelliDocs AI</h1>
              <p className="text-xs text-slate-500">
                Multi-Agent Document Intelligence &amp; Research Copilot
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${statusStyle.bg} ${statusStyle.text}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
              Backend: {status}
              {data ? ` (${data.environment})` : ""}
            </span>
            {user ? (
              <div className="flex items-center gap-3 border-l border-slate-200 pl-3 text-sm text-slate-600">
                <span className="hidden sm:inline">{user.email}</span>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-slate-400 hover:bg-slate-100"
                >
                  Log out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
