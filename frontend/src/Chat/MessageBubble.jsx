const ROUTE_LABELS = {
  rag: "Answered from your documents",
  tools: "Answered using a tool",
  both: "Answered from documents + tools",
  direct: "Answered directly",
};

export function MessageBubble({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm ${
          isUser
            ? "bg-gradient-to-br from-indigo-600 to-violet-600 text-white"
            : message.isError
              ? "border border-rose-200 bg-rose-50 text-rose-700"
              : "border border-slate-200 bg-white text-slate-800"
        }`}
      >
        <p className="whitespace-pre-wrap">
          {message.text}
          {message.isStreaming ? <span className="animate-pulse">▍</span> : null}
        </p>
        {!isUser && message.route ? (
          <p className="mt-1.5 text-xs text-slate-400">
            {ROUTE_LABELS[message.route] ?? message.route}
          </p>
        ) : null}
        {!isUser && message.sources && message.sources.length > 0 ? (
          <ul className="mt-1.5 space-y-1 border-t border-slate-100 pt-1.5">
            {message.sources.map((source, index) => (
              <li
                key={`${source.filename}-${source.chunk_index}-${index}`}
                className="text-xs text-slate-500"
              >
                <span className="font-medium text-slate-600">{source.filename}</span> (chunk{" "}
                {source.chunk_index}, score {source.score.toFixed(2)})
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
