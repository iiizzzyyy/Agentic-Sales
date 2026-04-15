"""Router graph - classifies intent and routes to Coach or Assistant."""

import json
from typing import Literal
from langchain_core.messages import SystemMessage, HumanMessage

from llm_factory import get_llm
from langgraph.graph import StateGraph, MessagesState, START, END

from prompts.router_prompt import ROUTER_PROMPT


class AgentState(MessagesState):
    """Shared state across the graph."""
    route: Literal["coach", "assistant", "direct"] | None  # Router decision
    workflow: str | None  # e.g., "roleplay", "research", "pipeline"
    user_id: str  # Slack user ID
    channel_id: str  # Slack channel ID
    thread_ts: str | None  # Slack thread timestamp
    hubspot_context: dict | None  # Cached HubSpot data for current request
    rag_context: str | None  # Retrieved RAG chunks
    web_context: str | None  # Web search results
    company_name: str | None  # Extracted company name from request
    contact_name: str | None  # Selected contact name (for email drafts)
    contact_email: str | None  # Selected contact email (for email drafts)


# Initialize LLM via OpenRouter
router_llm = get_llm()


def parse_router_response(response_text: str) -> dict:
    """Parse the JSON response from the router LLM."""
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Default fallback
        return {"route": "assistant", "workflow": "research"}


def router_node(state: AgentState) -> dict:
    """Classify the user's intent and choose a route."""
    last_message = state["messages"][-1].content

    response = router_llm.invoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=last_message)
    ])

    parsed = parse_router_response(response.content)
    return {"route": parsed.get("route", "assistant"), "workflow": parsed.get("workflow", "research")}


def route_decision(state: AgentState) -> str:
    """Conditional edge: which subgraph to invoke."""
    if state.get("route") == "coach":
        return "coach"
    return "assistant"


def build_router_graph(mcp_tools=None):
    """Build the main router graph with conditional edges.

    Args:
        mcp_tools: List of MCP tools (HubSpot, BigQuery, Gmail) to pass to subgraphs.
    """
    from graphs.coach import build_coach_subgraph
    from graphs.assistant import build_assistant_subgraph

    graph = StateGraph(AgentState)

    # Add nodes - pass mcp_tools to subgraphs
    graph.add_node("router", router_node)
    graph.add_node("coach", build_coach_subgraph(mcp_tools))
    graph.add_node("assistant", build_assistant_subgraph(mcp_tools))

    # Add edges
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", route_decision, {
        "coach": "coach",
        "assistant": "assistant"
    })
    graph.add_edge("coach", END)
    graph.add_edge("assistant", END)

    return graph.compile()


def build_main_graph(mcp_tools=None):
    """Build the main graph with MCP tools.

    This is the entry point called from app.py after loading MCP tools.
    """
    return build_router_graph(mcp_tools)
