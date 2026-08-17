import { useEffect, useRef, useState } from "react";

import { MessageBubble } from "./MessageBubble";

/** Purely prop-driven -- the socket/state lives in useChatSocket, owned by
 * the page, so the same messages/activity can feed this panel and the
 * agent activity panel next to it without opening two connections. */
export function ChatWindow({ messages, connected, onSend }) {
  const [input, setInput] = useState("");
  const bottomRef = useRef(null);
  const isStreaming = messages[messages.length - 1]?.isStreaming ?? false;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSubmit(event) {
    event.preventDefault();
    const question = input.trim();
    if (!question || isStreaming || !connected) {
      return;
    }
    onSend(question);
    setInput("");
  }

  return (
    <div className="flex h-[70vh] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm shadow-slate-200/50">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Conversation</h2>
        <span
          className={`flex items-center gap-1.5 text-xs ${connected ? "text-emerald-600" : "text-slate-400"}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
          {connected ? "Connected" : "Connecting…"}
        </span>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50/50 p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
            <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8" aria-hidden="true">
              <path
                d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7a2.5 2.5 0 0 1-2.5 2.5H9l-4 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-7Z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
            </svg>
            <p className="max-w-xs text-sm">
              Ask about an uploaded document, or try a tool question like &quot;What is 12% of
              850?&quot;
            </p>
          </div>
        ) : (
          messages.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-200 bg-white p-3">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={connected ? "Ask a question…" : "Connecting…"}
          disabled={!connected || isStreaming}
          className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm shadow-sm outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={!connected || isStreaming || !input.trim()}
          className="rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-indigo-600/20 transition hover:from-indigo-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none"
        >
          Send
        </button>
      </form>
    </div>
  );
}
