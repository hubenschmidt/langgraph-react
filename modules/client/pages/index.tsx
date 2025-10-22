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
    <div className="app">
      <header className="header">
        <div
          className={`status ${isOpen ? "status--online" : "status--offline"}`}
          title={isOpen ? "Connected" : "Disconnected"}
        />
        <b className="title">LangGraph-React</b>
      </header>

      <main className="chat-card">
        <section className="msg-list">
          {messages.map((m: ChatMsg, i: number) => {
            const isUser = m.user === "User";
            return (
              <div
                key={i}
                className={`msg-row ${
                  isUser ? "msg-row--user" : "msg-row--bot"
                }`}
              >
                <div
                  className={`bubble ${
                    isUser ? "bubble--user" : "bubble--bot"
                  }`}
                >
                  <div
                    className={`bubble__author ${
                      isUser ? "bubble__author--right" : "bubble__author--left"
                    }`}
                  >
                    <strong>{m.user}</strong>
                  </div>
                  <div className="bubble__text">{m.msg.trim()}</div>
                </div>
              </div>
            );
          })}
        </section>

        <form className="input-form" onSubmit={onSubmit}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={() => setComposing(false)}
            placeholder="Type or paste your message..."
            rows={3}
            spellCheck
            autoFocus
            className="input-form__textarea"
          />
          <div className="input-form__actions">
            <button
              type="submit"
              className="btn"
              disabled={!isOpen || !input.trim()}
            >
              Send
            </button>
            <button type="button" className="btn btn--ghost" onClick={reset}>
              Reset
            </button>
          </div>
        </form>
      </main>
    </div>
  );
};

export default App;
