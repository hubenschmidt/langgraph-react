import { useEffect, useMemo, useState, useCallback } from "react";

export type ChatUser = "User" | "Bot";
export type ChatMsg = { user: ChatUser; msg: string; streaming?: boolean };

type UseWebSocketReturn = {
  isOpen: boolean;
  messages: ChatMsg[];
  sendMessage: (text: string) => void;
  reset: () => void;
};

/** Apply a streaming chunk to chat state (guard-clause style). */
const applyStreamChunk = (prev: ChatMsg[], chunk: string): ChatMsg[] => {
  const last = prev.at(-1);
  const isStreamingBot = !!(last && last.user === "Bot" && last.streaming);

  // if there isn't an active streaming bot bubble, start one
  if (!isStreamingBot) {
    return [...prev, { user: "Bot", msg: chunk, streaming: true }];
  }

  // otherwise append to the current streaming bubble
  const next = prev.slice();
  next[next.length - 1] = { ...last!, msg: last!.msg + chunk };
  return next;
};

/** Close the active streaming bubble if one exists (guard-clause style). */
const applyEndOfTurn = (prev: ChatMsg[]): ChatMsg[] => {
  const last = prev.at(-1);
  // nothing to do if last isn't a streaming bot bubble
  if (!(last && last.user === "Bot" && last.streaming)) return prev;

  const next = prev.slice();
  next[next.length - 1] = { ...last, streaming: false };
  return next;
};

export const useWs = (url: string): UseWebSocketReturn => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([
    { user: "Bot", msg: "Welcome! How can I be of service today?" },
  ]);
  const [ws, setWs] = useState<WebSocket | null>(null);

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
      // must be text
      if (typeof event.data !== "string") return;

      // try JSON; if it fails, treat as plain text -> new bot bubble
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        setMessages((prev) => [...prev, { user: "Bot", msg: event.data }]);
        return;
      }

      // must be an object
      if (parsed === null || typeof parsed !== "object") return;
      const obj = parsed as Record<string, unknown>;

      // --- stream chunk path ---
      const chunk = obj.on_chat_model_stream;
      if (typeof chunk === "string" && chunk.length > 0) {
        setMessages((prev) => applyStreamChunk(prev, chunk));
        return;
      }

      // --- end of assistant turn ---
      if (obj.on_chat_model_end === true) {
        setMessages((prev) => applyEndOfTurn(prev));
        return;
      }

      // --- custom event -> new bubble ---
      const payloadKeys = Object.keys(obj).filter(
        (k) => k !== "on_chat_model_stream" && k !== "on_chat_model_end"
      );
      if (payloadKeys.length === 0) return;

      const k = payloadKeys[0];
      setMessages((prev) => [
        ...prev,
        { user: "Bot", msg: `🔔 ${k}: ${JSON.stringify(obj[k])}` },
      ]);
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
      if (!t) return;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      setMessages((prev) => [...prev, { user: "User", msg: t }]);
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
};
