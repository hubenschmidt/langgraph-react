import React, { useEffect, useMemo, useState } from "react";

type ChatUser = "User" | "Bot";
type ChatMsg = { user: ChatUser; msg: string; streaming?: boolean };

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const [messages, setMessages] = useState<ChatMsg[]>([
    { user: "Bot", msg: "Welcome! How can I be of service today?" },
  ]);
  const [input, setInput] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const [ws, setWs] = useState<WebSocket | null>(null);
  const [composing, setComposing] = useState(false);
  const uuid = useMemo(() => crypto.randomUUID(), []);

  useEffect(() => {
    const socket = new WebSocket(WS_URL);
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

      // Try to parse as JSON; if not JSON, treat as plain text => new bot bubble
      let parsed: unknown;
      try {
        parsed = JSON.parse(event.data);
      } catch {
        setMessages((prev) => [...prev, { user: "Bot", msg: event.data }]);
        return;
      }
      if (parsed === null || typeof parsed !== "object") return;

      const obj = parsed as Record<string, unknown>;

      // Streaming token chunk
      if (typeof obj.on_chat_model_stream === "string") {
        const chunk = obj.on_chat_model_stream;
        if (!chunk) return;

        setMessages((prev) => {
          const last = prev[prev.length - 1] as ChatMsg | undefined;
          // Append to existing streaming bubble if present
          if (last?.user === "Bot" && last.streaming) {
            const next = prev.slice();
            next[next.length - 1] = { ...last, msg: last.msg + chunk };
            return next;
          }
          // Otherwise start a new streaming bot bubble
          return [...prev, { user: "Bot", msg: chunk, streaming: true }];
        });
        return;
      }

      // End of assistant turn: mark last bot message as non-streaming
      if (obj.on_chat_model_end === true) {
        setMessages((prev) => {
          const next = prev.slice();
          const last = next[next.length - 1] as ChatMsg | undefined;
          if (last?.user === "Bot" && last.streaming) {
            next[next.length - 1] = { ...last, streaming: false };
          }
          return next;
        });
        return;
      }

      // Any custom event => new bubble (for visibility)
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
  }, [uuid]);

  // Auto-scroll (simple)
  useEffect(() => {
    requestAnimationFrame(() =>
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })
    );
  }, [messages]);

  const sendUserMessage = () => {
    const text = input.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    setMessages((prev) => [...prev, { user: "User", msg: text }]);
    setInput("");

    ws.send(JSON.stringify({ uuid, message: text }));
  };

  const onSubmit: React.FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    sendUserMessage();
  };

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (composing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendUserMessage();
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          marginBottom: 12,
        }}
      >
        <div
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: isOpen ? "#16a34a" : "#dc2626",
          }}
          title={isOpen ? "Connected" : "Disconnected"}
        />
        <b>LangGraph (WS) 🤝 React</b>
      </div>

      <div
        style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}
      >
        <div style={{ display: "grid", gap: 8, minHeight: 240 }}>
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                alignSelf: m.user === "User" ? "end" : "start",
                background: m.user === "User" ? "#343434ff" : "#000000ff",
                border: "1px solid #e5e7eb",
                padding: "8px 10px",
                borderRadius: 8,
                whiteSpace: "pre-wrap",
                color: "#fff",
              }}
            >
              <strong>{m.user}:</strong>
              <div>{m.msg}</div>
            </div>
          ))}
        </div>

        <form
          onSubmit={onSubmit}
          style={{ display: "grid", gap: 8, marginTop: 12 }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)}
            placeholder="Type or paste your message..."
            rows={4}
            style={{ resize: "vertical", padding: 8 }}
            spellCheck
            autoFocus
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={!isOpen || !input.trim()}>
              Send
            </button>
            <button
              type="button"
              onClick={() =>
                setMessages([
                  {
                    user: "Bot",
                    msg: "Welcome! How can I be of service today?",
                  },
                ])
              }
            >
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
