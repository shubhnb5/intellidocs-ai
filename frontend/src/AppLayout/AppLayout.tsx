import { useQuery } from "@tanstack/react-query";
import { Outlet } from "react-router-dom";

import { getHealth } from "../api/health";
import "./AppLayout.css";

/**
 * Persistent shell rendered on every route — header + backend connection
 * status. Page-specific content (chat, upload, agent activity panel in later
 * phases) renders into <Outlet /> below it. Mirrors AppLayout/AppLayout.js
 * in the reference admin-ui project, minus the nav sidebar/menu (nothing to
 * navigate to yet — Phase 7 adds real pages and this grows a nav).
 */
export function AppLayout() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    retry: 1,
  });

  const status = isPending ? "checking" : isError ? "offline" : "online";

  return (
    <div className="app-shell">
      <header>
        <h1>IntelliDocs AI</h1>
        <p className="tagline">Multi-Agent Document Intelligence &amp; Research Copilot</p>
        <div className={`status-badge status-${status}`}>
          Backend: {status}
          {data ? ` (${data.environment})` : ""}
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
