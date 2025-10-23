# graph.py — LangGraph + OpenAI (no LangChain models)

import sys, os, json, logging
from typing import Annotated, TypedDict, List, Union

from dotenv import load_dotenv
from openai import AsyncOpenAI

from langchain_core.callbacks import adispatch_custom_event   # only for event plumbing
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("app.graph")

# ======================================================================================
# Env + OpenAI client
# ======================================================================================

load_dotenv()
ENV_KEY = "OPENAI_API_KEY"
api_key = os.getenv(ENV_KEY)

if not api_key:
    logger.fatal(f"Fatal Error: The '{ENV_KEY}' environment variable is missing.")
    sys.exit(1)

try:
    # The OpenAI SDK reads OPENAI_API_KEY from env automatically
    oai = AsyncOpenAI()
except Exception as e:
    logger.fatal(f"Fatal Error: Failed to initialize OpenAI client: {e}")
    sys.exit(1)

# ======================================================================================
# Graph state
# ======================================================================================

class GraphsState(TypedDict):
    # We keep LangGraph's message aggregator but we'll convert to OpenAI format at the node
    messages: Annotated[List[AnyMessage], add_messages]
    # Add your own keys here, e.g. conversation_id: str

graph = StateGraph(GraphsState)

# ======================================================================================
# Helpers
# ======================================================================================

def _is_lc_msg(obj) -> bool:
    """
    Heuristic: detect LangChain message-like objects without importing LC types.
    """
    # LC messages typically have .type and .content attributes
    return hasattr(obj, "content") and hasattr(obj, "type")

def _to_openai_role(lc_type: str) -> str:
    # Map common LangChain message types to OpenAI roles
    # lc_type values often include "human", "ai", "system", "tool"
    t = lc_type.lower()
    if "human" in t or t == "user":
        return "user"
    if "ai" in t or t == "assistant":
        return "assistant"
    if "system" in t:
        return "system"
    if "tool" in t or "function" in t:
        return "tool"
    # Fallback
    return "user"

def _coerce_messages_for_openai(raw_messages: List[Union[AnyMessage, dict]]) -> List[dict]:
    """
    Accepts a heterogeneous list of LangGraph/LangChain messages or simple dicts
    and converts them into OpenAI Chat Completions message format.
    """
    oai_messages = []
    for m in raw_messages:
        if isinstance(m, dict):
            # Expecting {"role": "...", "content": "..."} etc.
            role = m.get("role", "user")
            content = m.get("content", "")
            name = m.get("name")
            # tool messages may include tool_call_id in OAI schema; we pass through if present
            oai_msg = {"role": role, "content": content}
            if name:
                oai_msg["name"] = name
            if "tool_call_id" in m:
                oai_msg["tool_call_id"] = m["tool_call_id"]
            oai_messages.append(oai_msg)
        elif _is_lc_msg(m):
            # LangChain-style message object
            role = _to_openai_role(getattr(m, "type", "user"))
            content = getattr(m, "content", "")
            # Tool messages sometimes store additional fields; keep minimal viable set
            oai_messages.append({"role": role, "content": content})
        else:
            # Fallback: treat as user text
            oai_messages.append({"role": "user", "content": str(m)})
    return oai_messages

async def _dispatch_stream_chunk(token: str, config: RunnableConfig):
    # Mirror LangChain's stream event name so your FE can keep listening for it
    await adispatch_custom_event("on_chat_model_stream", token, config=config)

async def _dispatch_stream_end(config: RunnableConfig):
    await adispatch_custom_event("on_chat_model_end", True, config=config)

# ======================================================================================
# Easter egg / conditional check node (unchanged)
# ======================================================================================

async def conditional_check(state: GraphsState, config: RunnableConfig):
    messages = state["messages"]
    if not messages:
        return
    last = messages[-1]
    msg_text = last["content"] if isinstance(last, dict) else getattr(last, "content", "")
    keywords = ["LangChain", "langchain", "Langchain", "LangGraph", "Langgraph", "langgraph"]
    if any(k in msg_text for k in keywords):
        await adispatch_custom_event("on_easter_egg", True, config=config)

# ======================================================================================
# Core LLM node — streams via OpenAI SDK, emits custom events, returns final message
# ======================================================================================

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o")  # allow override via env if desired
MODEL_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MODEL_MAX_TOKENS = os.getenv("OPENAI_MAX_TOKENS")  # None means model-default

async def call_openai_and_stream(state: GraphsState, config: RunnableConfig):
    """
    - Converts state messages to OpenAI format
    - Calls chat.completions with stream=True
    - Emits 'on_chat_model_stream' tokens and 'on_chat_model_end'
    - Returns the full assistant message back into graph state
    """
    raw_messages = state["messages"]
    oai_messages = _coerce_messages_for_openai(raw_messages)

    final_text_parts: List[str] = []
    try:
        # NOTE: Using Chat Completions API for broad model support and simplicity here.
        # If you prefer Responses API, wire similarly with client.responses.stream(...)
        stream = oai.chat.completions.create(
            model=MODEL_NAME,
            messages=oai_messages,
            temperature=MODEL_TEMPERATURE,
            max_tokens=int(MODEL_MAX_TOKENS) if MODEL_MAX_TOKENS else None,
            stream=True,
        )
        async for event in stream:
            # Each event is a chunk with .choices[0].delta.content (when present)
            try:
                choices = getattr(event, "choices", [])
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue
                addition = getattr(delta, "content", None)
                if addition:
                    final_text_parts.append(addition)
                    await _dispatch_stream_chunk(addition, config)
            except Exception as inner_e:
                # Continue on parsing mishaps; don't break the stream for minor issues
                logger.debug(f"Stream parse warning: {inner_e}")
        # Stream is finished
        await _dispatch_stream_end(config)

    except Exception as e:
        logger.exception(f"OpenAI streaming failed: {e}")
        # Surface a short error and still complete the node
        final_text_parts.append("Sorry—there was an error generating the response.")

    final_text = "".join(final_text_parts) if final_text_parts else ""
    # Return as a new assistant message into the graph state
    return {"messages": [{"role": "assistant", "content": final_text}]}

# ======================================================================================
# Wire up graph
# ======================================================================================

graph.add_node("conditional_check", conditional_check)
graph.add_node("modelNode", call_openai_and_stream)
graph.add_edge(START, "conditional_check")
graph.add_edge("conditional_check", "modelNode")
graph.add_edge("modelNode", END)

memory = MemorySaver()
graph_runnable = graph.compile(checkpointer=memory)

# ======================================================================================
# Invocation + WebSocket streaming
# ======================================================================================
# You said the part below is flexible; we keep your shape and
# make sure both LC stream events (if any) and our custom events work.

import json
from datetime import datetime
from fastapi import WebSocket
from langfuse import observe

@observe()
async def invoke_our_graph(websocket: WebSocket, data: Union[str, List[dict]], user_uuid: str):
    """
    `data` may be a plain string (user text) or a pre-baked list of {role, content} dicts.
    We normalize it to the graph state's `messages` list.
    """
    if isinstance(data, str):
        initial_input = {"messages": [{"role": "user", "content": data}]}
    elif isinstance(data, list):
        initial_input = {"messages": data}
    else:
        # Fallback
        initial_input = {"messages": [{"role": "user", "content": str(data)}]}

    thread_config = {"configurable": {"thread_id": user_uuid}}
    final_text = ""

    async for event in graph_runnable.astream_events(initial_input, thread_config, version="v2"):
        kind = event["event"]

        # 1) If *somehow* a LangChain model were used upstream, keep compatibility:
        if kind == "on_chat_model_stream":
            addition = event.get("data", {}).get("chunk", {}).get("content", "")
            final_text += addition or ""
            if addition:
                await websocket.send_text(json.dumps({"on_chat_model_stream": addition}))

        elif kind == "on_chat_model_end":
            await websocket.send_text(json.dumps({"on_chat_model_end": True}))
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "llm_method": kind,
                "sent": final_text
            }))

        # 2) Our OpenAI-direct path emits *custom* events with the same names:
        elif kind == "on_custom_event":
            name = event.get("name")
            payload = event.get("data")
            # Mirror the same accumulation & messages for streaming tokens:
            if name == "on_chat_model_stream":
                token = payload or ""
                final_text += token
                await websocket.send_text(json.dumps({"on_chat_model_stream": token}))
            elif name == "on_chat_model_end":
                await websocket.send_text(json.dumps({"on_chat_model_end": True}))
                logger.info(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "llm_method": name,
                    "sent": final_text
                }))
            else:
                # Other custom events, e.g. easter egg
                msg = json.dumps({name: payload})
                logger.info(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "uuid": user_uuid,
                    "llm_method": kind,
                    "sent": msg
                }))
                await websocket.send_text(msg)
