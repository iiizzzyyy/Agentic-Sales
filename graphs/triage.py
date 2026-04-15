"""Triage graph for Hive Mind orchestration.

Replaces router.py with three-way classification:
- DIRECT: Single tool call (e.g., "Show pipeline")
- WORKFLOW: Single workflow execution (e.g., "Roleplay discovery call")
- COMPLEX: Multi-step task requiring decomposition (e.g., "Prepare for QBR")
"""

import json
from typing import Literal
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage

from llm_factory import get_llm

load_dotenv()
from langgraph.graph import StateGraph, MessagesState, START, END

from graphs.contracts import TriageState, Complexity, WorkflowType
from tools.executor import execute_direct_task, get_executor
from prompts.triage_prompt import TRIAGE_PROMPT


# Initialize LLM via OpenRouter
triage_llm = get_llm()


def parse_triage_response(response_text: str) -> dict:
    """Parse the JSON response from the triage LLM."""
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(text)
        # Validate response
        return {
            "complexity": parsed.get("complexity", "workflow"),
            "workflow": parsed.get("workflow"),
            "target_tool": parsed.get("target_tool"),
            "route": parsed.get("route"),
        }
    except json.JSONDecodeError:
        # Default fallback
        return {"complexity": "workflow", "workflow": "research", "route": "assistant"}


def triage_node(state: TriageState) -> dict:
    """Classify the user's intent into DIRECT, WORKFLOW, or COMPLEX."""
    last_message = state["messages"][-1].content

    response = triage_llm.invoke([
        SystemMessage(content=TRIAGE_PROMPT),
        HumanMessage(content=last_message)
    ])

    parsed = parse_triage_response(response.content)

    result = {
        "complexity": parsed.get("complexity", "workflow"),
    }

    # Add workflow-specific fields
    if parsed.get("workflow"):
        result["workflow"] = parsed["workflow"]

    if parsed.get("route"):
        result["route"] = parsed["route"]

    if parsed.get("target_tool"):
        result["target_tool"] = parsed["target_tool"]

    # Extract company name if present
    company_name = _extract_company_name(last_message)
    if company_name:
        result["company_name"] = company_name

    return result


def _extract_company_name(message: str) -> str | None:
    """Extract company name from message."""
    # Check for common prefixes
    prefixes = ["/research", "/deal", "research", "company", "about", "for"]
    for prefix in prefixes:
        if message.lower().startswith(prefix):
            parts = message.split(prefix, 1)
            if len(parts) > 1:
                name = parts[1].strip().split(" ")[0].strip()
                if name and not name.startswith("/"):
                    return name

    # Check for "with <Company>" pattern (common in roleplay)
    if " with " in message.lower():
        parts = message.lower().split(" with ")
        if len(parts) > 1:
            # Get the part after "with"
            after_with = parts[1].strip()
            # Extract first capitalized word(s)
            words = after_with.split()
            if words:
                # Return first 1-2 capitalized words
                company = words[0].capitalize()
                if len(words) > 1 and words[1][0].isupper():
                    company += " " + words[1]
                return company

    return None


def triage_decision(state: TriageState) -> str:
    """Conditional edge: which path to take."""
    complexity = state.get("complexity", "workflow")
    route = state.get("route", "assistant")

    if complexity == Complexity.DIRECT:
        return "direct_executor"
    elif complexity == Complexity.WORKFLOW:
        # Route directly to coach or assistant based on triage classification
        return route if route in ["coach", "assistant"] else "assistant"
    else:  # COMPLEX
        return "pm_agent"


def direct_executor_node(state: TriageState) -> dict:
    """Execute a direct (single tool call) task."""
    from graphs.contracts import TaskInput

    last_message = state["messages"][-1].content

    # Determine tool and input based on message
    goal = last_message
    target_tool = state.get("target_tool")

    # Build file_scope based on what tools might be needed
    file_scope = []
    if "research" in goal.lower() or "company" in goal.lower():
        file_scope = ["web", "rag", "crm"]
    elif "pipeline" in goal.lower():
        file_scope = ["crm"]
    elif "deal" in goal.lower():
        file_scope = ["crm"]
    else:
        file_scope = ["web", "rag"]

    # Create task input
    task_input = TaskInput(
        goal=goal,
        role="researcher",
        file_scope=file_scope
    )

    # Get MCP tools if available
    mcp_tools = state.get("_mcp_tools", [])

    # Execute
    try:
        executor = get_executor(mcp_tools)
        output = executor.execute_single_task(task_input)

        # Convert artifacts to messages
        content = _format_direct_output(output)

        return {
            "messages": state["messages"] + [HumanMessage(content=content)],
            "rag_context": output.artifacts.get("research_brief", {}).get("icp_fit", "") if output.artifacts else "",
        }
    except Exception as e:
        return {
            "messages": state["messages"] + [HumanMessage(content=f"Error: {str(e)}")],
        }


def _format_direct_output(output) -> str:
    """Format direct executor output for Slack."""
    if output.status == "failed":
        return f"Error: {output.error}"

    artifacts = output.artifacts or {}

    if "research_brief" in artifacts:
        brief = artifacts["research_brief"]
        return f"""*Research: {brief.company_name}*

{brief.overview}

*Recent News:*
{chr(10).join(f"• {news}" for news in (brief.recent_news or []))}

*Talking Points:*
{chr(10).join(f"• {point}" for point in (brief.talking_points or []))}
"""

    if "pipeline_digest" in artifacts:
        digest = artifacts["pipeline_digest"]
        by_stage_str = chr(10).join(
            f"• {stage}: {data['count']} deals (${data['value']:,.0f})"
            for stage, data in (digest.by_stage or {}).items()
        )
        return f"""*Pipeline Overview*

Total: {digest.total_deals} deals (${digest.total_value:,.0f})

*By Stage:*
{by_stage_str}

*At Risk:* {len(digest.at_risk_deals or [])} deals
"""

    if "deal_status" in artifacts:
        deal = artifacts["deal_status"]
        health_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(deal.health, "⚪")
        return f"""*Deal: {deal.deal_name}*

{health_emoji} Stage: {deal.stage}
Company: {deal.company_name}
Owner: {deal.owner}

*Next Steps:*
{chr(10).join(f"• {step}" for step in (deal.next_steps or []))}
"""

    return "Task completed successfully."


def workflow_router(state: TriageState) -> str:
    """Route to appropriate workflow subgraph."""
    route = state.get("route", "assistant")
    return route


def build_triage_graph(mcp_tools=None):
    """Build the triage graph with conditional edges.

    Args:
        mcp_tools: List of MCP tools (HubSpot, BigQuery, Gmail) to pass to subgraphs.
    """
    # Use typed subgraphs
    from graphs.coach_typed import build_coach_subgraph_typed
    from graphs.assistant_typed import build_assistant_subgraph_typed
    from graphs.pm_agent import create_task_graph
    from graphs.dag_executor import select_batch, dag_executor_node, should_continue

    graph = StateGraph(TriageState)

    # Add nodes
    graph.add_node("triage", triage_node)
    graph.add_node("direct_executor", direct_executor_node)
    graph.add_node("coach", build_coach_subgraph_typed(mcp_tools))
    graph.add_node("assistant", build_assistant_subgraph_typed(mcp_tools))
    graph.add_node("pm_agent", create_task_graph)
    graph.add_node("dag_executor", lambda state: dag_executor_node(state, mcp_tools))

    # Add edges
    graph.add_edge(START, "triage")
    graph.add_conditional_edges("triage", triage_decision, {
        "direct_executor": "direct_executor",
        "coach": "coach",
        "assistant": "assistant",
        "pm_agent": "pm_agent",
    })

    # Direct executor returns to END
    graph.add_edge("direct_executor", END)
    graph.add_edge("coach", END)
    graph.add_edge("assistant", END)

    # PM agent -> DAG executor with loop
    graph.add_edge("pm_agent", "select_batch")
    graph.add_node("select_batch", select_batch)
    graph.add_edge("select_batch", "dag_executor")
    graph.add_conditional_edges(
        "dag_executor",
        lambda state: "continue" if should_continue(state) else "done",
        {
            "continue": "select_batch",
            "done": END
        }
    )

    return graph.compile()


def build_main_graph(mcp_tools=None):
    """Build the main graph with MCP tools.

    This is the entry point called from app.py after loading MCP tools.
    """
    return build_triage_graph(mcp_tools)
