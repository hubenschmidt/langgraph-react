# server.py — FastAPI + WebSocket (guard clauses only)
# Flow:
#   - accept WS
#   - loop: receive JSON -> log -> handle `init` ping or forward `message` to graph
#   - errors are logged; connection is closed on exit

import json
import logging
from datetime import datetime

from fastapi import FastAPI, WebSocket
from agent.graph import invoke_our_graph
from agent.logging_config import configure_logging

# -----------------------------------------------------------------------------
# App + logging
# -----------------------------------------------------------------------------
configure_logging()  # plain logging to stdout (Docker captures it)
logger = logging.getLogger("app.server")
app = FastAPI()


# -----------------------------------------------------------------------------
# WebSocket endpoint (frontend connects here)
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept any incoming WebSocket right away
    await websocket.accept()

    # We'll fill this once we see the client's UUID in their first message
    user_uuid = None

    try:
        while True:
            # 1) Receive text from client
            data = await websocket.receive_text()

            # 2) Parse JSON safely. If it fails, log and wait for next frame.
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "op": f"JSON encoding error - {e}"
                }))
                continue

            # 3) Log the raw payload exactly as received (after parsing)
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "received": payload
            }))

            # 4) Keep track of the user's conversation id if provided
            uid = payload.get("uuid")
            if uid:
                user_uuid = uid

            # 5) If this is an init-only ping, log and wait for the next frame
            if payload.get("init"):
                logger.info(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "op": "Initializing ws with client."
                }))
                continue

            # 6) No message? nothing to do (could be a heartbeat). Wait for next frame.
            message = payload.get("message")
            if not message:
                continue

            # 7) We have a user message: invoke the graph, which streams back over this WS
            await invoke_our_graph(websocket, message, user_uuid)

    except Exception as e:
        # Catch-all for unexpected errors during the loop
        logger.error(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "uuid": user_uuid,
            "op": f"Error: {e}"
        }))

    finally:
        # Attempt to close gracefully; log attempt if we know the uuid
        if user_uuid:
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "op": "Closing connection."
            }))

        try:
            await websocket.close()
        except RuntimeError as e:
            # If the socket is already closed, just log it
            logger.error(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "op": f"WebSocket close error: {e}"
            }))


# -----------------------------------------------------------------------------
# Local dev entrypoint (uvicorn)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    # Use log level "warning" to reduce noise in local dev logs
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
