# langgraph-react

A batteries-included starter that runs:

- **LangGraph dev API** (Python) – `http://localhost:2024`
- **FastAPI WebSocket server** (Python) – `ws://localhost:8000/ws`
- **React client (Next.js)** – `http://localhost:3001`
- **Langfuse** (web + worker + ClickHouse + Postgres + Redis + MinIO) – `http://localhost:3000`

Everything is wired together with **Docker Compose**.

---

## 0) Prerequisites

- Docker & Docker Compose
- (Optional) Node 18+ if you want to run the client locally outside Docker

---

## 1) Environment variables

There are **two places** to configure env vars.

### A) Root env (for Docker Compose + Langfuse stack)

Create a root `.env` from the example and fill any `# CHANGEME` values:

```bash
cp .env.example .env
```

### B) App env (Python app)

#### modules/app/.env

OPENAI_API_KEY=sk-...

#### Optional but recommended for Langfuse tracing

LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://langfuse:3000

---

## 2) Start everything

```bash
docker compose up
```

### Rebuild tips

If you change Python deps in modules/app/pyproject.toml:

```bash
docker compose build app && docker compose up
```

If you change the client deps:

```bash
docker compose build client && docker compose up
```

## 3) What's running (ports)

| Service                       | URL / Port             | Notes                                                      |
| ----------------------------- | ---------------------- | ---------------------------------------------------------- |
| LangGraph API (dev)           | http://localhost:2024  | OpenAPI docs at `/docs`.                                   |
| FastAPI WebSocket server      | ws://localhost:8000/ws | React client connects here for streaming tokens.           |
| React client (Next.js)        | http://localhost:3001  | Chat UI that talks to the WS server.                       |
| Langfuse Web                  | http://localhost:3000  | UI for traces; initialize on first run.                    |
| MinIO (S3 API)                | http://localhost:9090  | Used by Langfuse for storage.                              |
| Postgres / ClickHouse / Redis | _loopback only_        | Bound to `127.0.0.1` inside Compose; not publicly exposed. |

## 4) Verify it works

### Client UI

1. Open http://localhost:3001
2. Send a message.

You should see:

- **User** bubble on the **right**
- **Bot** streaming response on the **left**

---

### LangGraph API

- Open http://localhost:2024/docs for the dev API docs.

---

### Langfuse UI

- Open http://localhost:3000
- Complete the initial setup
- Watch traces populate as you chat from the client

---

### WebSocket quick test (browser console)

Open your browser devtools console and run:

```js
// 1) Connect
const ws = new WebSocket("ws://localhost:8000/ws");

// 2) Log any server messages
ws.onmessage = (e) => console.log("WS message:", e.data);

// 3) On open, init a session and send a test user message
ws.onopen = () => {
  ws.send(JSON.stringify({ uuid: "test-123", init: true }));
  ws.send(JSON.stringify({ uuid: "test-123", message: "hello websocket" }));
};

// 4) To close later
// ws.close();
```

## Project layout

.
├─ docker-compose.yml
├─ .env.example # copy to .env (root)
├─ modules/
│ └─ app/
│ ├─ Dockerfile
│ ├─ langgraph.json
│ ├─ pyproject.toml
│ ├─ start.sh
│ └─ src/agent/
│ ├─ graph.py # LangGraph definition
│ ├─ server.py # FastAPI WebSocket server (port 8000)
│ └─ cust_logger.py
└─ modules/
└─ client/
├─ package.json
├─ app/ or src/
│ └─ index.tsx # React chat UI
└─ styles/globals.css # Tailwind v4 entry (`@import "tailwindcss";`)
