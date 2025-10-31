# server.py — FastAPI + WebSocket
# Flow:
#   - accept WS
#   - async-iterate frames
#   - handle each frame via a helper
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
    await websocket.accept()
    user_uuid: str | None = None

    async def handle_frame(raw: str, uid: str | None) -> str | None:
        # Parse JSON; on error, log and return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": uid,
                "op": f"JSON encoding error - {e}"
            }))
            return uid

        # Log what we received
        logger.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "uuid": uid,
            "received": payload
        }))

        # Track conversation id if provided
        new_uid = payload.get("uuid") or uid

        # Init ping? Just log and return
        if payload.get("init"):
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": new_uid,
                "op": "Initializing ws with client."
            }))
            return new_uid

        # No message? Nothing to do
        message = payload.get("message")
        if not message:
            return new_uid

        # We have a message: invoke the graph (it streams back over this WS)
        await invoke_our_graph(websocket, message, new_uid)
        return new_uid

    try:
        async for data in websocket.iter_text():
            user_uuid = await handle_frame(data, user_uuid)

    except Exception as e:
        logger.error(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "uuid": user_uuid,
            "op": f"Error: {e}"
        }))

    finally:
        if user_uuid:
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "op": "Closing connection."
            }))
        try:
            await websocket.close()
        except RuntimeError as e:
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
