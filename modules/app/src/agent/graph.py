# graph.py — clear & simple LangGraph + OpenAI
# - One tiny default graph export (non-streaming, no memory) for loaders
# - One streaming builder for your WebSocket path (with memory)
# - Plain comments and small helpers

import os, sys, json, logging, uuid
from typing import TypedDict, List, Dict, Any, Optional, Callable, Awaitable, Union

from dotenv import load_dotenv
from openai import AsyncOpenAI

from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver  # used only for streaming/WS graphs

# -----------------------------------------------------------------------------
# Setup
# -----------------------------------------------------------------------------
logger = logging.getLogger("app.graph")
load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    logger.fatal("Fatal Error: OPENAI_API_KEY is missing.")
    sys.exit(1)

# You can change these with env vars if needed.
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MAX_TOKENS_ENV = os.getenv("OPENAI_MAX_TOKENS")
MAX_TOKENS = int(MAX_TOKENS_ENV) if MAX_TOKENS_ENV else None

# -----------------------------------------------------------------------------
# State type: LangGraph passes a dict-like state to each node.
# We store a simple chat history list under "messages" (list of {role, content}).
# -----------------------------------------------------------------------------
class ChatState(TypedDict):
    messages: List[Dict[str, str]]  # e.g. [{"role": "user", "content": "hi"}]

# -----------------------------------------------------------------------------
# Helper: make sure messages are in OpenAI format.
# We accept either {"role","content"} dicts or generic objects with .content
# -----------------------------------------------------------------------------
def to_openai_messages(messages: List[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for m in messages:
        if isinstance(m, dict) and "role" in m and "content" in m:
            out.append({"role": m["role"], "content": m["content"]})
        else:
            text = getattr(m, "content", str(m))
            out.append({"role": "user", "content": text})
    return out

# -----------------------------------------------------------------------------
# Class that builds graphs. Client is lazy so building a graph is synchronous.
# -----------------------------------------------------------------------------
class SimpleChatGraph:
    def __init__(self, *, use_memory: bool):
        self.id = str(uuid.uuid4())
        self._client: Optional[AsyncOpenAI] = None
        self._memory = MemorySaver() if use_memory else None  # only for WS graphs

    def _client_or_create(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    # --- Node 1: optional easter-egg ping to the frontend (if WS is present)
    async def node_conditional(self, state: ChatState, send_ws: Optional[Callable[[str], Awaitable[None]]]):
        if not state.get("messages"):
            return
        last = state["messages"][-1]
        text = last.get("content", "")
        if not text:
            return
        if send_ws and any(k in text for k in ("LangChain", "langchain", "LangGraph", "langgraph")):
            await send_ws(json.dumps({"on_easter_egg": True}))

    # --- Node 2: call OpenAI. Stream if a websocket sender is provided.
    async def node_model(
        self,
        state: ChatState,
        *,
        send_ws: Optional[Callable[[str], Awaitable[None]]],
        stream: bool,
    ) -> Dict[str, Any]:
        client = self._client_or_create()
        msgs = to_openai_messages(state["messages"])

        pieces: List[str] = []
        try:
            if stream and send_ws:
                # Streaming path: send tokens to the frontend as they arrive
                resp_stream = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=msgs,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=True,
                )
                async for ev in resp_stream:
                    if ev.choices:
                        delta = ev.choices[0].delta
                        if delta and delta.content:
                            pieces.append(delta.content)
                            await send_ws(json.dumps({"on_chat_model_stream": delta.content}))
                await send_ws(json.dumps({"on_chat_model_end": True}))
            else:
                # Non-streaming path: return one complete message
                resp = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=msgs,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=False,
                )
                pieces.append(resp.choices[0].message.content or "")
        except Exception as e:
            logger.exception(f"OpenAI call failed: {e}")
            pieces.append("Sorry—there was an error generating the response.")
            if stream and send_ws:
                await send_ws(json.dumps({"on_chat_model_end": True}))

        return {"messages": [{"role": "assistant", "content": "".join(pieces)}]}

    # --- Builder: wire the two nodes together
    def build(self, *, send_ws: Optional[Callable[[str], Awaitable[None]]], stream: bool):
        """
        Build and compile a graph:
          START -> conditional -> model -> END
        If send_ws is provided and stream=True, tokens stream to the frontend.
        """
        g = StateGraph(ChatState)

        async def _conditional(s: ChatState):
            return await self.node_conditional(s, send_ws)

        async def _model(s: ChatState):
            return await self.node_model(s, send_ws=send_ws, stream=stream)

        g.add_node("conditional", _conditional)
        g.add_node("model", _model)
        g.add_edge(START, "conditional")
        g.add_edge("conditional", "model")
        g.add_edge("model", END)

        return g.compile(checkpointer=self._memory)  # None for default graph; MemorySaver for WS graph


# =============================================================================
# DEFAULT EXPORT for loaders (non-streaming, NO memory)
# =============================================================================
def build_default_graph():
    """
    Used by any runtime that auto-imports `graph` from this module.
    - Non-streaming (single reply)
    - No custom checkpointer (keeps platforms like langgraph_api happy)
    """
    return SimpleChatGraph(use_memory=False).build(send_ws=None, stream=False)

# The loader will look for this name:
graph = build_default_graph()


# =============================================================================
# WEBSOCKET ENTRYPOINT used by your FastAPI server
# =============================================================================
from fastapi import WebSocket
from langfuse import observe

def build_streaming_graph(send_ws: Callable[[str], Awaitable[None]]):
    """
    Build a streaming graph that:
      - streams tokens to `send_ws`
      - uses MemorySaver for per-conversation state
    """
    return SimpleChatGraph(use_memory=True).build(send_ws=send_ws, stream=True)

@observe()
async def invoke_our_graph(websocket: WebSocket, data: Union[str, List[Dict[str, str]]], user_uuid: str):
    """
    server.py calls this. We:
      1) Build a streaming graph bound to this websocket
      2) Normalize input into state
      3) Invoke the graph (which streams tokens during the run)
    """
    async def _send_ws(payload: str):
        await websocket.send_text(payload)

    graph_runnable = build_streaming_graph(_send_ws)

    # Build the initial state from `data`
    if isinstance(data, str):
        state: ChatState = {"messages": [{"role": "user", "content": data}]}
    else:
        state = {"messages": data}

    # Memory scopes by user_uuid
    config = {"configurable": {"thread_id": user_uuid}}
    await graph_runnable.ainvoke(state, config)
