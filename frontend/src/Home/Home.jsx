import { useState } from "react";

import { AgentActivityPanel } from "../Chat/AgentActivityPanel";
import { ChatWindow } from "../Chat/ChatWindow";
import { useChatSocket } from "../Chat/useChatSocket";
import { DocumentList } from "../Documents/DocumentList";
import { UploadPanel } from "../Documents/UploadPanel";

/** Three columns, one WebSocket: documents (upload + list) on the left,
 * the chat itself in the middle, and the agent activity feed on the right
 * so a reviewer can watch the Router/Retrieval/Tool/Summarizer pipeline run
 * next to the answer it produces, instead of just seeing a chat box. */
export function Home() {
  const [autoExpandId, setAutoExpandId] = useState(null);
  const { messages, activity, connected, sendQuestion } = useChatSocket();
  const isStreaming = messages[messages.length - 1]?.isStreaming ?? false;

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[300px_1fr_300px]">
      <section className="space-y-4">
        <UploadPanel onUploaded={setAutoExpandId} />
        <DocumentList autoExpandId={autoExpandId} />
      </section>
      <section>
        <ChatWindow messages={messages} connected={connected} onSend={sendQuestion} />
      </section>
      <section>
        <AgentActivityPanel activity={activity} isActive={isStreaming} />
      </section>
    </div>
  );
}
