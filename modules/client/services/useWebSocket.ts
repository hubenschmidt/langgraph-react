import { useEffect, useMemo, useState, useCallback } from "react";

export type ChatUser = "User" | "Bot";
export type ChatMsg = { user: ChatUser; msg: string; streaming?: boolean };

type UseWebSocketReturn = {
  isOpen: boolean;
  messages: ChatMsg[];
  sendMessage: (text: string) => void;
  reset: () => void;
};

export function useWebSocket(url: string): UseWebSocketReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([
    { user: "Bot", msg: "Welcome! How can I be of service today?" },
  ]);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Stable per-session id
  const uuid = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    const socket = new WebSocket(url);
    setWs(socket);

    socket.onopen = () => {
      setIsOpen(true);
      socket.send(JSON.stringify({ uuid, init: true }));
    };

    socket.onclose = () => {
      setIsOpen(false);
      setWs(null);
    };

    socket.onerror = () => setIsOpen(false);

    socket.onmessage = (event) => {
      if (typeof event.data !== "string") return;

      // Try JSON; if not JSON, treat as plain text => new Bot bubble
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        setMessages((prev) => [...prev, { user: "Bot", msg: event.data }]);
        return;
      }
      if (parsed === null || typeof parsed !== "object") return;

      const obj = parsed as Record<string, unknown>;

      // Stream chunk
      if (typeof obj.on_chat_model_stream === "string") {
        const chunk = obj.on_chat_model_stream;
        if (!chunk) return;

        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.user === "Bot" && last.streaming) {
            // append to active streaming bubble
            const next = prev.slice();
            next[next.length - 1] = { ...last, msg: last.msg + chunk };
            return next;
          }
          // start a new streaming bubble
          return [...prev, { user: "Bot", msg: chunk, streaming: true }];
        });
        return;
      }

      // End of assistant turn → mark last as not streaming (if it is)
      if (obj.on_chat_model_end === true) {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.user !== "Bot" || !last.streaming) return prev;
          const next = prev.slice();
          next[next.length - 1] = { ...last, streaming: false };
          return next;
        });
        return;
      }

      // Custom events → new bubble
      const keys = Object.keys(obj).filter(
        (k) => k !== "on_chat_model_stream" && k !== "on_chat_model_end"
      );
      if (keys.length > 0) {
        const k = keys[0];
        setMessages((prev) => [
          ...prev,
          { user: "Bot", msg: `🔔 ${k}: ${JSON.stringify(obj[k])}` },
        ]);
      }
    };

    return () => {
      try {
        socket.close();
      } catch {}
      setWs(null);
    };
  }, [url, uuid]);

  const sendMessage = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t || !ws || ws.readyState !== WebSocket.OPEN) return;

      // Push user bubble
      setMessages((prev) => [...prev, { user: "User", msg: t }]);

      // Let server start a fresh assistant turn (hook will create/append accordingly)
      ws.send(JSON.stringify({ uuid, message: t }));
    },
    [ws, uuid]
  );

  const reset = useCallback(() => {
    setMessages([
      { user: "Bot", msg: "Welcome! How can I be of service today?" },
    ]);
  }, []);

  return { isOpen, messages, sendMessage, reset };
}
