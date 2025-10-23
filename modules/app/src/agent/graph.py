# graph.py — LangGraph + OpenAI, no langchain_* imports used directly

import sys, os, json, logging
from typing import Annotated, TypedDict, List, Union, Callable, Awaitable

from dotenv import load_dotenv
from openai import AsyncOpenAI

from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("app.graph")

# ======================================================================================
# Env + OpenAI client
# ======================================================================================

load_dotenv()
ENV_KEY = "OPENAI_API_KEY"
if not os.getenv(ENV_KEY):
    logger.fatal(f"Fatal Error: The '{ENV_KEY}' environment variable is missing.")
    sys.exit(1)

oai = AsyncOpenAI()  # reads OPENAI_API_KEY from env

# ======================================================================================
# Graph state
# ======================================================================================

class GraphsState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
    # you can add more keys if you want

# ======================================================================================
# Helpers to coerce messages into OpenAI format
# ======================================================================================

def _coerce_messages_for_openai(raw_messages: List[Union[AnyMessage, dict]]) -> List[dict]:
    oai_messages = []
    for m in raw_messages:
        if isinstance(m, dict):
            role = m.get("role") or "user"
            content = m.get("content") or ""
            oai_messages.append({"role": role, "content": content})
        else:
            # LangGraph AnyMessage can be various shapes; we just read .content if present
            content = getattr(m, "content", str(m))
            # Default to 'user' for unknown message types
            oai_messages.append({"role": "user", "content": content})
    return oai_messages

# ======================================================================================
# Build a graph bound to a specific WebSocket (so nodes can stream directly)
# ======================================================================================

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o")
MODEL_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MODEL_MAX_TOKENS = os.getenv("OPENAI_MAX_TOKENS")

def build_graph(send_ws: Callable[[str], Awaitable[None]]):
    """
    send_ws: async function that accepts a JSON string to send over the WebSocket.
             Example: lambda s: websocket.send_text(s)
    We construct the graph with nodes that close over this sender,
    so we don't need any LangChain event plumbing.
    """

    graph = StateGraph(GraphsState)

    async def conditional_check(state: GraphsState):
        messages = state.get("messages") or []
        if not messages:
            return
        last = messages[-1]
        text = last["content"] if isinstance(last, dict) else getattr(last, "content", "")
        if not text:
            return
        # If the easter egg triggers, notify the FE directly over WS.
        keywords = ["LangChain", "langchain", "Langchain", "LangGraph", "Langgraph", "langgraph"]
        if any(k in text for k in keywords):
            await send_ws(json.dumps({"on_easter_egg": True}))

    async def call_openai_and_stream(state: GraphsState):
        """
        Streams tokens straight to the WebSocket using send_ws.
        Returns the final assistant message into the graph state.
        """
        raw_messages = state["messages"]
        oai_messages = _coerce_messages_for_openai(raw_messages)

        final_chunks: List[str] = []
        try:
            stream = await oai.chat.completions.create(
                model=MODEL_NAME,
                messages=oai_messages,
                temperature=MODEL_TEMPERATURE,
                max_tokens=int(MODEL_MAX_TOKENS) if MODEL_MAX_TOKENS else None,
                stream=True,
            )
            async for event in stream:
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
                        # stream token to FE
                        await send_ws(json.dumps({"on_chat_model_stream": addition}))
                except Exception as inner_e:
                    logger.debug(f"Stream parse warning: {inner_e}")

            # indicate stream done
            await send_ws(json.dumps({"on_chat_model_end": True}))

        except Exception as e:
            logger.exception(f"OpenAI streaming failed: {e}")
            final_chunks.append("Sorry—there was an error generating the response.")
            await send_ws(json.dumps({"on_chat_model_end": True}))

        final_text = "".join(final_chunks) if final_chunks else ""
        return {"messages": [{"role": "assistant", "content": final_text}]}

    # Wire graph
    graph.add_node("conditional_check", conditional_check)
    graph.add_node("modelNode", call_openai_and_stream)
    graph.add_edge(START, "conditional_check")
    graph.add_edge("conditional_check", "modelNode")
    graph.add_edge("modelNode", END)

    memory = MemorySaver()  # still works fine
    return graph.compile(checkpointer=memory)

# =============================================================================
# Minimal top-level graph export for langgraph_api / Studio / health checks
# This satisfies loaders that expect `graph` to be present in this module.
# =============================================================================

_default_graph = StateGraph(GraphsState)

async def _call_openai_full(state: GraphsState):
    """
    Non-streaming node for the default export.
    Used by langgraph_api when it imports `graph` at startup.
    Your WS flow still uses invoke_our_graph -> build_graph(send_ws).
    """
    raw_messages = state["messages"]
    oai_messages = _coerce_messages_for_openai(raw_messages)

    resp = await oai.chat.completions.create(
        model=MODEL_NAME,
        messages=oai_messages,
        temperature=MODEL_TEMPERATURE,
        max_tokens=int(MODEL_MAX_TOKENS) if MODEL_MAX_TOKENS else None,
        stream=False,  # return one-shot completion here
    )
    text = resp.choices[0].message.content or ""
    return {"messages": [{"role": "assistant", "content": text}]}

_default_graph.add_node("modelNode", _call_openai_full)
_default_graph.add_edge(START, "modelNode")
_default_graph.add_edge("modelNode", END)

# <-- THIS is what langgraph_api looks for.
graph = _default_graph.compile()


# ======================================================================================
# Public entry point used by your server.py
# ======================================================================================

import json
from datetime import datetime
from fastapi import WebSocket
from langfuse import observe

@observe()
async def invoke_our_graph(websocket: WebSocket, data: Union[str, List[dict]], user_uuid: str):
    """
    You keep your server.py unchanged. Here we build a graph bound to this websocket.
    """
    # This function is how the node will send messages out:
    async def _send_ws(payload: str):
        await websocket.send_text(payload)

    graph_runnable = build_graph(_send_ws)

    # Normalize input
    if isinstance(data, str):
        initial_input = {"messages": [{"role": "user", "content": data}]}
    elif isinstance(data, list):
        initial_input = {"messages": data}
    else:
        initial_input = {"messages": [{"role": "user", "content": str(data)}]}

    # We can still scope memory by thread_id (conversation id)
    config = {"configurable": {"thread_id": user_uuid}}

    # One-shot invoke (streaming happens inside the node directly to WS)
    await graph_runnable.ainvoke(initial_input, config)
