import React, { useEffect, useState } from "react";
import { useWebSocket, ChatMsg } from "../services/useWebSocket";

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const { isOpen, messages, sendMessage, reset } = useWebSocket(WS_URL);
  const [input, setInput] = useState("");
  const [composing, setComposing] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() =>
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })
    );
  }, [messages]);

  const onSubmit: React.FormEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage(input);
    setInput("");
  };

  const onKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (e) => {
    if (composing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(e as unknown as React.FormEvent<HTMLFormElement>);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <div
          style={{
            width: 10, height: 10, borderRadius: "50%",
            background: isOpen ? "#16a34a" : "#dc2626",
          }}
          title={isOpen ? "Connected" : "Disconnected"}
        />
        <b>LangGraph (WS) 🤝 React</b>
      </div>

      <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
        <div style={{ display: "grid", gap: 8, minHeight: 240 }}>
          {messages.map((m: ChatMsg, i: number) => (
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

        <form onSubmit={onSubmit} style={{ display: "grid", gap: 8, marginTop: 12 }}>
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
            <button type="button" onClick={reset}>
              Reset
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
