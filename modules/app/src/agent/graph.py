import os, sys, json, logging, uuid, asyncio
from typing import Annotated, TypedDict, List, Union, Callable, Awaitable, Optional, Dict, Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver  # used for WS runtime (not for module-exported graph)

logger = logging.getLogger("app.graph")
load_dotenv(override=True)

# ----------------------------
# Env + OpenAI client settings
# ----------------------------
if not os.getenv("OPENAI_API_KEY"):
    logger.fatal("Fatal Error: OPENAI_API_KEY is missing.")
    sys.exit(1)

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o")
MODEL_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MODEL_MAX_TOKENS = os.getenv("OPENAI_MAX_TOKENS")

# --------------------------------
# Shared state & message coercion
# --------------------------------
class GraphsState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    # add more keys if needed later

def _coerce_messages_for_openai(raw_messages: List[Union[AnyMessage, dict]]) -> List[dict]:
    oai_messages: List[dict] = []
    for m in raw_messages:
        if isinstance(m, dict):
            role = m.get("role") or "user"
            content = m.get("content") or ""
            msg = {"role": role, "content": content}
            if "name" in m: msg["name"] = m["name"]
            if "tool_call_id" in m: msg["tool_call_id"] = m["tool_call_id"]
            oai_messages.append(msg)
        else:
            # Generic LangGraph/LangChain-ish message object
            content = getattr(m, "content", str(m))
            oai_messages.append({"role": "user", "content": content})
    return oai_messages

# ==========================
# Class-based Sidekick-style
# ==========================
class ChatGraph:
    """
    Mirrors Sidekick's structure:
      - __init__/setup
      - build_graph(send_ws?)  -> returns compiled graph
      - conditional_check node
      - model_node (streaming if send_ws; otherwise non-stream)
      - run_superstep(...) helper (non-WS)
    """

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.memory = MemorySaver()  # only used for graphs you build at runtime (e.g., WS)
        self._client: Optional[AsyncOpenAI] = None

    async def setup(self):
        # nothing heavy here, but matches the Sidekick "setup" feel
        self._client = AsyncOpenAI()

    # -------- nodes --------
    async def conditional_check(self, state: GraphsState, send_ws: Optional[Callable[[str], Awaitable[None]]] = None):
        messages = state.get("messages") or []
        if not messages:
            return
        last = messages[-1]
        text = last["content"] if isinstance(last, dict) else getattr(last, "content", "")
        if not text:
            return
        keywords = ["LangChain", "langchain", "Langchain", "LangGraph", "Langgraph", "langgraph"]
        if send_ws and any(k in text for k in keywords):
            await send_ws(json.dumps({"on_easter_egg": True}))

    async def model_node(
        self,
        state: GraphsState,
        *,
        send_ws: Optional[Callable[[str], Awaitable[None]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """If send_ws is provided and stream=True, stream tokens to WS; else return full text."""
        assert self._client is not None, "Call setup() first"
        raw_messages = state["messages"]
        oai_messages = _coerce_messages_for_openai(raw_messages)

        final_chunks: List[str] = []
        try:
            if stream and send_ws:
                # Streaming path for WebSocket usage
                resp_stream = await self._client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=oai_messages,
                    temperature=MODEL_TEMPERATURE,
                    max_tokens=int(MODEL_MAX_TOKENS) if MODEL_MAX_TOKENS else None,
                    stream=True,
                )
                async for event in resp_stream:
                    try:
                        choices = getattr(event, "choices", [])
                        if not choices:
                            continue
                        delta = getattr(choices[0], "delta", None)
                        if delta is None:
                            continue
                        addition = getattr(delta, "content", None)
                        if addition:
                            final_chunks.append(addition)
                            await send_ws(json.dumps({"on_chat_model_stream": addition}))
                    except Exception as inner_e:
                        logger.debug(f"Stream parse warning: {inner_e}")
                await send_ws(json.dumps({"on_chat_model_end": True}))
            else:
                # Non-streaming path (one-shot)
                resp = await self._client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=oai_messages,
                    temperature=MODEL_TEMPERATURE,
                    max_tokens=int(MODEL_MAX_TOKENS) if MODEL_MAX_TOKENS else None,
                    stream=False,
                )
                text = resp.choices[0].message.content or ""
                final_chunks.append(text)

        except Exception as e:
            logger.exception(f"OpenAI generation failed: {e}")
            final_chunks.append("Sorry—there was an error generating the response.")
            if send_ws and stream:
                await send_ws(json.dumps({"on_chat_model_end": True}))

        final_text = "".join(final_chunks) if final_chunks else ""
        return {"messages": [{"role": "assistant", "content": final_text}]}

    # -------- builder --------
    async def build_graph(self, send_ws: Optional[Callable[[str], Awaitable[None]]] = None, *, stream: bool = False):
        """
        Build a graph (like Sidekick.build_graph). If send_ws is provided with stream=True,
        the model_node will stream to WS; otherwise it does non-streaming.
        """
        if self._client is None:
            await self.setup()

        sg = StateGraph(GraphsState)

        # wrap node callables so they close over send_ws/stream
        async def _conditional(state: GraphsState):
            return await self.conditional_check(state, send_ws)

        async def _model(state: GraphsState):
            return await self.model_node(state, send_ws=send_ws, stream=stream)

        sg.add_node("conditional_check", _conditional)
        sg.add_node("modelNode", _model)
        sg.add_edge(START, "conditional_check")
        sg.add_edge("conditional_check", "modelNode")
        sg.add_edge("modelNode", END)

        # Use MemorySaver here (runtime graph). This is NOT the module-level export.
        return sg.compile(checkpointer=self.memory)

    # -------- helper like Sidekick.run_superstep --------
    async def run_superstep(self, message: str, history: List[Dict[str, str]]):
        """
        Non-WS helper: runs one turn and returns updated history.
        Mirrors Sidekick.run_superstep shape.
        """
        graph = await self.build_graph(send_ws=None, stream=False)
        config = {"configurable": {"thread_id": self.id}}

        state: GraphsState = {"messages": history + [{"role": "user", "content": message}]}
        result = await graph.ainvoke(state, config=config)
        reply_text = result["messages"][-1]["content"] if result.get("messages") else ""
        return history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply_text}]

# ==========================================================
# Module-level minimal graph export for langgraph_api / Studio
# (non-streaming, and IMPORTANTLY: compiled WITHOUT custom checkpointer)
# ==========================================================
_default_instance = ChatGraph()
# we build a tiny non-streaming graph for the loader at import time
# (safe because it doesn’t connect to WS, and we compile without MemorySaver)
async def _build_default_graph():
    await _default_instance.setup()
    sg = StateGraph(GraphsState)

    async def _conditional(state: GraphsState):
        await _default_instance.conditional_check(state, send_ws=None)

    async def _model(state: GraphsState):
        return await _default_instance.model_node(state, send_ws=None, stream=False)

    sg.add_node("conditional_check", _conditional)
    sg.add_node("modelNode", _model)
    sg.add_edge(START, "conditional_check")
    sg.add_edge("conditional_check", "modelNode")
    sg.add_edge("modelNode", END)
    return sg

# Build the non-streaming graph synchronously at import time
# (langgraph_api imports `graph` when the app starts)
# We cannot await here, so we create a small event loop if needed.
try:
    loop = asyncio.get_running_loop()
    _sg = loop.run_until_complete(_build_default_graph())  # type: ignore
except RuntimeError:
    _sg = asyncio.run(_build_default_graph())

# <-- This is what langgraph_api expects:
graph = _sg.compile()  # NO custom checkpointer here

# ======================================
# Public WS entrypoint (server.py uses it)
# ======================================
from fastapi import WebSocket
from langfuse import observe

@observe()
async def invoke_our_graph(websocket: WebSocket, data: Union[str, List[dict]], user_uuid: str):
    """
    server.py passes the plain string message here.
    We build a streaming graph instance bound to this WebSocket.
    """
    async def _send_ws(payload: str):
        await websocket.send_text(payload)

    # Build a streaming graph bound to this WS
    runtime = ChatGraph()
    await runtime.setup()
    graph_runnable = await runtime.build_graph(send_ws=_send_ws, stream=True)

    # Normalize input into state
    if isinstance(data, str):
        initial_input: GraphsState = {"messages": [{"role": "user", "content": data}]}
    elif isinstance(data, list):
        initial_input = {"messages": data}
    else:
        initial_input = {"messages": [{"role": "user", "content": str(data)}]}

    # Per-user memory via thread_id (this is the in-memory saver in ChatGraph)
    config = {"configurable": {"thread_id": user_uuid}}

    await graph_runnable.ainvoke(initial_input, config)
