# langgraph-react

Bootstrap that runs:

- **LangGraph**
- **FastAPI WebSocket server**
- **React client (Next.js)**
- **Langfuse** (web UI + ClickHouse + Postgres + Redis + MinIO)

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

## 3) Create Langfuse credentials

- navigate in a browser window to Langfuse at http://localhost:3000 and "Sign up" for a new Langfuse account (create local account)
- create New Organization
- add Organization members
- create New Project "langgraph-react"
- Configure tracing -> Create new API key
- Copy Secret Key and Public Key to /modules/app/.env PUBLIC_KEY and SECRET_KEY.. and maintain LANGFUSE_HOST="http://langfuse:3000"
- recreate the `app` container.. open a new WSL2 window, navigate to `langgraph-react` directory and run

```bash
docker compose up -d --no-deps --force-recreate app
```

## 4) Test everything is working

- navigate in a browser window to http://localhost:3001
- enter a message in the chat
- check the container log output.. it should emit something like

```bash
langfuse-worker-1  | 2025-10-23T23:34:33.552Z info      Starting ClickhouseWriter. Max interval: 1000 ms, Max batch size: 1000
```

- navigate to Langfuse at http://localhost:3000
- Select `Tracing` and you should see a Timestamped trace displayed for the most recent message in the chat
- Success! ✅🏆🎯💯🚀🎯 `langgraph-react` is working with self-hosted Langfuse observability tracing.

### Rebuild tips

- If you change Python deps in modules/app/pyproject.toml:

```bash
docker compose build app && docker compose up
```

- If you change the client deps:

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
