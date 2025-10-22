import React, { useEffect, useState } from "react";
import { useWebSocket, ChatMsg } from "../services/useWebSocket";

const WS_URL = "ws://localhost:8000/ws";

const App = () => {
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
    const text = input.trim();
    if (!text) return;
    sendMessage(text);
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
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 8,
          padding: 12,
          background: "#0b0b0b",
        }}
      >
        {/* message list */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minHeight: 240,
          }}
        >
          {messages.map((m: ChatMsg, i: number) => {
            const isUser = m.user === "User";
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: isUser ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "75%",
                    background: isUser ? "#1f2937" : "#111827",
                    border: "1px solid #2b2b2b",
                    padding: "6px 10px",
                    borderRadius: 10,
                    color: "#fff",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      opacity: 0.75,
                      marginBottom: 2,
                      textAlign: isUser ? "right" : "left",
                    }}
                  >
                    <strong>{m.user}</strong>
                  </div>
                  <div>{m.msg.trim()}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* input */}
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
            rows={3}
            style={{
              resize: "vertical",
              padding: 8,
              background: "#0f1115",
              color: "#fff",
              border: "1px solid #2b2b2b",
              borderRadius: 8,
            }}
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
};

export default App;
