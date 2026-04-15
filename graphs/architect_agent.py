"""Architect Agent for Hive Mind orchestration.

Pre-execution data source review that produces ArchitectureBrief.
Used by PM Agent to inform task decomposition.
"""

from dataclasses import dataclass
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage

from llm_factory import get_llm
from graphs.contracts import ArchitectureBrief, AgentRole
from prompts.architect_prompt import ARCHITECT_PROMPT


# Initialize LLM
architect_llm = get_llm()


def parse_architect_response(response_text: str) -> dict:
    """Parse the JSON response from Architect agent."""
    import json

    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Return minimal valid structure
        return {
            "data_sources_needed": [],
            "rag_collections_relevant": [],
            "mcp_tools_required": [],
            "estimated_complexity": "medium",
            "potential_blockers": [],
            "recommendations": []
        }


def architect_node(state: dict) -> dict:
    """Review request and produce ArchitectureBrief.

    Args:
        state: ArchitectState with request, user_id

    Returns:
        dict with architecture_brief populated
    """
    request = state.get("request", "")
    user_id = state.get("user_id", "")

    # Build prompt
    prompt = ARCHITECT_PROMPT.format(request=request)

    response = architect_llm.invoke([
        SystemMessage(content="You are an Architect agent that reviews data requirements before execution."),
        HumanMessage(content=prompt)
    ])

    parsed = parse_architect_response(response.content)

    # Create ArchitectureBrief
    brief = ArchitectureBrief(
        data_sources_needed=parsed.get("data_sources_needed", []),
        rag_collections_relevant=parsed.get("rag_collections_relevant", []),
        mcp_tools_required=parsed.get("mcp_tools_required", []),
        estimated_complexity=parsed.get("estimated_complexity", "medium"),
        potential_blockers=parsed.get("potential_blockers", []),
        recommendations=parsed.get("recommendations", [])
    )

    return {"architecture_brief": brief}


def analyze_request(request: str) -> ArchitectureBrief:
    """Analyze a request and produce ArchitectureBrief.

    Args:
        request: Natural language request

    Returns:
        ArchitectureBrief with data source analysis
    """
    state = {
        "request": request,
        "user_id": "",
        "messages": []
    }

    result = architect_node(state)
    return result.get("architecture_brief")


def get_data_source_requirements(brief: ArchitectureBrief) -> dict[str, bool]:
    """Convert ArchitectureBrief to data source requirements.

    Args:
        brief: ArchitectureBrief from architect agent

    Returns:
        Dict of data source -> required
    """
    return {
        "hubspot": any("hubspot" in s.lower() or "crm" in s.lower() for s in brief.data_sources_needed),
        "bigquery": any("bigquery" in s.lower() or "analytics" in s.lower() for s in brief.data_sources_needed),
        "gmail": any("gmail" in s.lower() or "email" in s.lower() for s in brief.data_sources_needed),
        "rag": any("rag" in s.lower() or "playbook" in s.lower() for s in brief.rag_collections_relevant),
        "web": any("web" in s.lower() or "search" in s.lower() or "news" in s.lower() for s in brief.data_sources_needed),
        "apollo": any("apollo" in s.lower() for s in brief.data_sources_needed)
    }


def estimate_complexity(brief: ArchitectureBrief) -> int:
    """Estimate task complexity as number of parallel execution batches.

    Args:
        brief: ArchitectureBrief from architect agent

    Returns:
        Estimated number of execution batches (1 = simple, 5+ = complex)
    """
    score = 0

    # Data source complexity
    score += len(brief.data_sources_needed)

    # Tool complexity
    score += len(brief.mcp_tools_required) * 2

    # Blockers add complexity
    score += len(brief.potential_blockers)

    # Map to batch count
    if score <= 2:
        return 1  # Simple - single batch
    elif score <= 5:
        return 2  # Medium - 2 batches
    elif score <= 8:
        return 3  # Complex - 3 batches
    else:
        return 4  # Very complex - 4+ batches


# ─────────────────────────────────────────────────────────────────────────────
# RAG Collection Discovery
# ─────────────────────────────────────────────────────────────────────────────

def get_relevant_rag_collections(request: str) -> list[str]:
    """Get RAG collections relevant to a request.

    Args:
        request: Natural language request

    Returns:
        List of relevant RAG collection names
    """
    # Map keywords to RAG collections
    collections = []

    request_lower = request.lower()

    if any(word in request_lower for word in ["roleplay", "practice", "objection"]):
        collections.append("playbooks/roleplay_scenarios")
        collections.append("playbooks/objection_handling")

    if any(word in request_lower for word in ["discovery", "qualif", "question"]):
        collections.append("playbooks/discovery_questions")
        collections.append("playbooks/qualification")

    if any(word in request_lower for word in ["meddic", "spin", "challenger", "bant"]):
        collections.append("methodologies")

    if any(word in request_lower for word in ["email", "follow-up", "outreach"]):
        collections.append("templates/email_templates")

    if any(word in request_lower for word in ["battlecard", "competitor"]):
        collections.append("battlecards")

    if any(word in request_lower for word in ["qbr", "quarterly", "review"]):
        collections.append("templates/qbr_templates")

    if any(word in request_lower for word in ["pricing", "negotiat", "discount"]):
        collections.append("playbooks/negotiation")

    return collections


# ─────────────────────────────────────────────────────────────────────────────
# Build Architect Graph
# ─────────────────────────────────────────────────────────────────────────────

def build_architect_graph():
    """Build the architect agent graph."""
    from langgraph.graph import StateGraph, START, END
    from graphs.contracts import ArchitectState

    graph = StateGraph(ArchitectState)

    # Add nodes
    graph.add_node("architect", architect_node)

    # Add edges
    graph.add_edge(START, "architect")
    graph.add_edge("architect", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Integration with PM Agent
# ─────────────────────────────────────────────────────────────────────────────

def architect_for_pm(request: str) -> tuple[ArchitectureBrief, list[str]]:
    """Run architect analysis for PM agent task decomposition.

    Args:
        request: Natural language request

    Returns:
        (ArchitectureBrief, list of relevant RAG collections)
    """
    # Get architecture brief
    brief = analyze_request(request)

    # Get RAG collections
    rag_collections = get_relevant_rag_collections(request)
    brief.rag_collections_relevant = rag_collections

    return brief, rag_collections
