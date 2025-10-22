import json, os, logging
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from agent.graph import invoke_our_graph

# Simple, plain logging to stdout (Docker will capture it)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI()

set_files_message_color('purple')  # Set log message color for this file to 'purple'

# WebSocket endpoint for real-time communication with the frontend
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # unless described (error) logging is in {"timestamp": "YYYY-MM-DDTHH:MM:SS.MS", "uuid": "", "op": ""} format,
    # {timestamp, designated uuid, and what operation was done}

    await websocket.accept()  # Accept ANY WebSocket connection
    user_uuid = None  # Placeholder for the conversation UUID
    try:
        while True:
            data = await websocket.receive_text()  # Receive message from client
            # Log the received data in {"timestamp": "YYYY-MM-DDTHH:MM:SS.MS", "uuid": "", "received": {"uuid": "", "init": bool}} format
            logger.info(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "received": json.loads(data)}))

            try:
                # parse the data extracting the UUID and Message and if its the first message of the conversation
                payload = json.loads(data)
                user_uuid = payload.get("uuid")
                message = payload.get("message")
                init = payload.get("init", False)

                # If it's the first message, log the conversation initialization process
                if init:
                    logger.info(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "op": "Initializing ws with client."}))
                else:
                    if message:
                        # If a message is provided, invoke the LangGraph, websocket for send, user message, and passing conversation ID
                        await invoke_our_graph(websocket, message, user_uuid)
            except json.JSONDecodeError as e:
                logger.error(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "op": f"JSON encoding error - {e}"}))
    except Exception as e:
        # Catch all other unexpected exceptions and log the error
        logger.error(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "op": f"Error: {e}"}))
    finally:
        # before the connection is closed, check if its already closed from the client side before trying to close from our side
        if user_uuid:
            logger.info(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "op": "Closing connection."}))
        try:
            await websocket.close()
        except RuntimeError as e:
            # uncaught connection was already closed error
            logger.error(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "op": f"WebSocket close error: {e}"}))

# Main entry point for running the FastAPI app using Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
