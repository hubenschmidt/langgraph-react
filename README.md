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
