import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthContext";

/** Gates every route nested under it on AuthContext's status -- redirects
 * to /login once hydration confirms there's no valid session, and renders
 * nothing (not even a flash of the protected page) while that's still
 * being determined. */
export function ProtectedRoute() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-3 bg-slate-50 text-sm text-slate-500">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" />
        Loading…
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
