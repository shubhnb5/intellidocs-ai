import { useCallback, useEffect, useRef, useState } from "react";

import { getAccessToken, notifyLoggedOut } from "../Auth/tokenStorage";
import { config } from "../config";

// Mirrors AUTH_FAILURE_CLOSE_CODE in backend/src/routes/chat_websocket.py --
// the app-specific WebSocket close code the server sends when the ?token=
// query param is missing or invalid.
const AUTH_FAILURE_CLOSE_CODE = 4401;

function appendToLastAssistant(messages, textDelta) {
  const last = messages[messages.length - 1];
  if (!last || last.role !== "assistant") {
    return messages;
  }
  return [...messages.slice(0, -1), { ...last, text: last.text + textDelta }];
}

function finalizeLastAssistant(messages, route, sources) {
  const last = messages[messages.length - 1];
  if (!last || last.role !== "assistant") {
    return messages;
  }
  return [...messages.slice(0, -1), { ...last, isStreaming: false, route, sources }];
}

function errorLastAssistant(messages, errorMessage) {
  const last = messages[messages.length - 1];
  if (!last || last.role !== "assistant") {
    return messages;
  }
  return [
    ...messages.slice(0, -1),
    { ...last, isStreaming: false, isError: true, text: last.text || errorMessage },
  ];
}

let messageCounter = 0;
function nextId() {
  messageCounter += 1;
  return `msg-${Date.now()}-${messageCounter}`;
}

/**
 * Owns the /ws/chat connection: reconnects on close, and translates the wire
 * protocol into React state -- a running message list plus a per-question
 * agent activity feed. Deliberately a plain browser WebSocket, not React
 * Query -- this is a stateful stream, not a cacheable request/response.
 */
export function useChatSocket() {
  const [messages, setMessages] = useState([]);
  const [activity, setActivity] = useState([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const shouldReconnectRef = useRef(true);

  useEffect(() => {
    shouldReconnectRef.current = true;

    function connect() {
      // No native WebSocket header support -- the token rides in the query
      // string instead (see websocket.py's module docstring). Read fresh
      // each call so a reconnect after a token refresh picks up the new one.
      const token = getAccessToken();
      if (!token) {
        return; // ProtectedRoute keeps this hook from ever mounting without one
      }

      const socket = new WebSocket(`${config.wsUrl}?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = (event) => {
        setConnected(false);
        if (event.code === AUTH_FAILURE_CLOSE_CODE) {
          // Session is dead (missing/expired/invalid token) -- let
          // AuthContext react the same way api/client.js's failed silent
          // refresh does, instead of retrying a connection that will just
          // get rejected again.
          notifyLoggedOut();
          return;
        }
        if (shouldReconnectRef.current) {
          setTimeout(connect, 2000);
        }
      };
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case "agent_activity":
            setActivity((current) => [
              ...current,
              { agent: data.agent, message: data.message, timestamp: data.timestamp },
            ]);
            break;
          case "answer_chunk":
            setMessages((current) => appendToLastAssistant(current, data.text));
            break;
          case "done":
            setMessages((current) => finalizeLastAssistant(current, data.route, data.sources));
            break;
          case "error":
            setMessages((current) => errorLastAssistant(current, data.message));
            break;
        }
      };
    }

    connect();

    return () => {
      shouldReconnectRef.current = false;
      socketRef.current?.close();
    };
  }, []);

  const sendQuestion = useCallback((question) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }
    setActivity([]);
    setMessages((current) => [
      ...current,
      { id: nextId(), role: "user", text: question },
      { id: nextId(), role: "assistant", text: "", isStreaming: true },
    ]);
    socket.send(JSON.stringify({ type: "ask", question, top_k: 5 }));
  }, []);

  return { messages, activity, connected, sendQuestion };
}
