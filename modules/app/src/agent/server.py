# server.py — FastAPI + WebSocket (guard clauses, no `while True`)
# Flow:
#   - accept WS
#   - async-iterate incoming messages
#   - parse → log → handle `init` or forward `message` to graph
#   - errors logged; socket closed on exit

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

    user_uuid = None  # set once we see a 'uuid' from the client

    try:
        # Iterate over incoming text frames; exits when client disconnects
        async for data in websocket.iter_text():
            # Parse JSON safely; skip bad frames
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "op": f"JSON encoding error - {e}"
                }))
                continue

            # Log exactly what we received
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "received": payload
            }))

            # Track conversation id if provided
            uid = payload.get("uuid")
            if uid:
                user_uuid = uid

            # Init ping? Log and wait for next frame
            if payload.get("init"):
                logger.info(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "op": "Initializing ws with client."
                }))
                continue

            # No message content? Nothing to do
            message = payload.get("message")
            if not message:
                continue

            # We have a user message: invoke the graph (streams back over this WS)
            await invoke_our_graph(websocket, message, user_uuid)

    except Exception as e:
        # Catch-all for unexpected errors during iteration
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
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
