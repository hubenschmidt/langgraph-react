"""LangGraph single-node graph template with a simple test output."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph
from langgraph.runtime import Runtime

# If you want to test Langfuse+OpenAI later, uncomment these and ensure API keys are set
# from langfuse.openai import AsyncOpenAI
# client = AsyncOpenAI()

class Context(TypedDict):
    my_configurable_param: str

@dataclass
class State:
    changeme: str = "example"

async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    # 🔧 For now, return a fixed value to prove the server works.
    return {
        "changeme": (
            "Hello from call_model! "
            f"Config: {(runtime.context or {}).get('my_configurable_param')}"
        )
    }

graph = (
    StateGraph(State, context_schema=Context)
    .add_node("call_model", call_model)
    .add_edge("__start__", "call_model")
    .compile(name="New Graph")
)
