"""Module 15: the Module 11 agent rebuilt with LangGraph, the framework KARMO uses.

Compare this file with ../11-native-tools/tools_agent.py. Same tools, same model,
same loop. LangGraph gives you the loop as a graph: a "model" node, a "tools"
node, and an edge that goes back to the model until no tool is requested.

Needs the course virtual environment (see Module 15 steps).
Usage: python3 langgraph_agent.py "How many Pink Black Velvet are still growing?"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
from plant_data import cultivar_summary, list_cultivars as _list_cultivars  # noqa: E402

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


@tool
def get_plant_stock(cultivar: str) -> dict:
    """Units, status counts, landed cost per unit and sales for one cultivar."""
    return cultivar_summary(cultivar)


@tool
def list_cultivars() -> list:
    """Names of every cultivar in the BloomBoss data."""
    return _list_cultivars()


TOOLS = [get_plant_stock, list_cultivars]
llm = ChatOllama(
    model=os.environ.get("KARMO_MODEL", "llama3.2:3b"),
    base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    temperature=0,
).bind_tools(TOOLS)

SYSTEM = SystemMessage("You are KARMO's plant assistant. Use tools for every number. Never guess.")


def call_model(state: MessagesState) -> dict:
    return {"messages": [llm.invoke([SYSTEM] + state["messages"])]}


graph = StateGraph(MessagesState)
graph.add_node("model", call_model)
graph.add_node("tools", ToolNode(TOOLS))
graph.add_edge(START, "model")
graph.add_conditional_edges("model", tools_condition)  # tool request -> "tools", else END
graph.add_edge("tools", "model")
app = graph.compile()


def main() -> int:
    question = " ".join(sys.argv[1:]) or input("Question: ")
    result = app.invoke({"messages": [HumanMessage(question)]}, {"recursion_limit": 12})
    for message in result["messages"]:
        kind = type(message).__name__.replace("Message", "")
        text = message.content or getattr(message, "tool_calls", "")
        print(f"[{kind}] {str(text)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
