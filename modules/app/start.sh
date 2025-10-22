#!/usr/bin/env bash
set -euo pipefail

# Forward signals to children
_term() {
  echo "Caught SIGTERM, shutting down..."
  kill -TERM "$LG_PID" 2>/dev/null || true
  kill -TERM "$API_PID" 2>/dev/null || true
}
trap _term TERM INT

# Start LangGraph dev API (2024)
uv run langgraph dev --host 0.0.0.0 --port 2024 &
LG_PID=$!

# Start your FastAPI websocket server (8000)
uv run python -m uvicorn agent.server:app --host 0.0.0.0 --port 8000 --log-level warning &
API_PID=$!

# Wait on either to exit, then exit with that code
wait -n $LG_PID $API_PID
exit $?
