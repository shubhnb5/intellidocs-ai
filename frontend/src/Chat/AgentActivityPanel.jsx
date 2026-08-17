const AGENT_COLORS = {
  router: "bg-slate-400",
  retrieval: "bg-blue-500",
  tool: "bg-amber-500",
  summarizer: "bg-rose-500",
};
const DEFAULT_AGENT_COLOR = "bg-slate-400";

/** Live feed of which agent (router/retrieval/tool/summarizer) is running,
 * fed by the WebSocket's agent_activity messages -- the visual proof, during
 * a demo, that this is a multi-agent pipeline and not one prompt to Claude. */
export function AgentActivityPanel({ activity, isActive }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/50">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Agent activity</h2>
        {isActive ? (
          <span className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
            Working…
          </span>
        ) : null}
      </div>
      {activity.length === 0 ? (
        <p className="mt-3 text-xs text-slate-400">Ask a question to see the agents at work.</p>
      ) : (
        <ol className="mt-3 space-y-2.5">
          {activity.map((event, index) => (
            <li key={index} className="flex items-start gap-2.5 text-xs">
              <span
                className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                  AGENT_COLORS[event.agent] ?? DEFAULT_AGENT_COLOR
                }`}
              />
              <div>
                <span className="font-medium text-slate-700 capitalize">{event.agent}</span>{" "}
                <span className="text-slate-500">{event.message}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
