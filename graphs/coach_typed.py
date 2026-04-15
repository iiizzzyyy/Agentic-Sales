"""Coach agent graph with typed contracts - roleplay, feedback, prep workflows.

Uses MCP tools for meeting prep (HubSpot data), direct tools for RAG and web search.
Outputs typed TaskOutput with RoleplayDebrief, MeetingPrepBrief artifacts.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Any

from llm_factory import get_llm
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from graphs.contracts import (
    TaskInput, TaskOutput, TaskStatus,
    RoleplayDebrief, MeetingPrepBrief,
    WorkflowType, AgentRole
)
from prompts.coach_prompts import (
    ROLEPLAY_SYSTEM_PROMPT,
    FEEDBACK_SYSTEM_PROMPT,
    PREP_SYSTEM_PROMPT,
    get_roleplay_system_prompt,
)
from tools.web_search import search_company_news
from tools.rag import search as rag_search, search_crm, search_crm_companies
from tools.methodology import load_methodology, build_scoring_prompt


# Initialize LLM via OpenRouter (base, will bind tools in build function)
coach_llm = get_llm()


def extract_scenario(message: str) -> str:
    """Extract scenario from coach command."""
    if message.startswith("/coach "):
        text = message.replace("/coach ", "").strip()
        if text.startswith("roleplay "):
            return text.replace("roleplay ", "").strip()
        if text.startswith("prep "):
            return text.replace("prep ", "").strip()
        if text.startswith("feedback "):
            return text.replace("feedback ", "").strip()
        return text
    return message.strip()


def roleplay_node_typed(state: dict) -> dict:
    """Start a roleplay session with typed output.

    Accepts state with TaskInput in task_input key.
    Returns TaskOutput with RoleplayDebrief artifact.
    """
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""

    # Get task input if available, otherwise extract from message
    task_input = state.get("task_input")
    if task_input and isinstance(task_input, TaskInput):
        scenario = task_input.goal
        methodology = task_input.constraints.get("methodology", "discovery")
    else:
        scenario = extract_scenario(last_message)
        methodology = "discovery"

    # Get RAG context for roleplay
    rag_context = rag_search(f"roleplay {scenario} objections sales")

    # Generate buyer persona
    persona_prompt = f"""Based on this scenario: "{scenario}"

Generate a realistic buyer persona for a sales roleplay. Include:
- Name (realistic business name)
- Title
- Company type
- Personality traits (communication style, decision-making)
- 2-3 hidden objections they might have
- What they care about most

Then start the roleplay by introducing yourself as this buyer.
Make your opening statement realistic - you're taking a sales call.

Format:
First, briefly describe the persona (2-3 lines).
Then write "---" on its own line.
Then write the buyer's opening statement in character."""

    system_prompt = f"""You are an AI sales coach running a roleplay session.

CONTEXT FROM PLAYBOOK:
{rag_context}

YOUR ROLE:
Generate a buyer persona based on the scenario, then play that buyer in a sales roleplay.
Stay in character. Be realistic - don't make it too easy for the rep.

After 3-4 exchanges from the rep, break character and provide a debrief with:
- Overall score (1-10)
- What they did well
- Areas to improve
- Recommended practice"""

    response = coach_llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=persona_prompt)
    ])

    # Parse response to extract persona and opening
    content = response.content
    persona_text = ""
    opening_statement = content

    if "---" in content:
        parts = content.split("---", 1)
        persona_text = parts[0].strip()
        opening_statement = parts[1].strip() if len(parts) > 1 else content

    # Create initial debrief structure (will be updated after roleplay)
    debrief = RoleplayDebrief(
        scenario=scenario,
        overall_score=0.0,  # Will be updated after debrief
        strengths=["Roleplay started - awaiting completion"],
        improvements=[],
        dimension_scores={},
        recommended_practice=[f"Practice {scenario} scenarios"],
        methodology=methodology
    )

    return {
        "messages": messages + [AIMessage(content=opening_statement)],
        "rag_context": rag_context,
        "persona_text": persona_text,
        "task_output": TaskOutput(
            status="success",
            artifacts={"roleplay_start": debrief},
            handoff_notes=f"Roleplay started: {scenario}. Persona: {persona_text[:100]}..."
        )
    }


def continue_roleplay_typed(state: dict, turn_count: int, max_turns: int = 4, methodology: str = "discovery") -> dict:
    """Continue an ongoing roleplay conversation with typed output."""
    messages = state.get("messages", [])
    rag_context = state.get("rag_context", "")

    # Check if we should do debrief
    if turn_count >= max_turns:
        # Build methodology-specific scoring instructions
        scoring_section = build_scoring_prompt(methodology)
        method_data = load_methodology(methodology)
        dimension_keys = [d["key"] for d in method_data["dimensions"]]
        dimension_json = ", ".join(f'"{k}": 7' for k in dimension_keys)

        system_prompt = f"""You are an AI sales coach. The roleplay is complete.

CONTEXT FROM PLAYBOOK:
{rag_context}

Based on the conversation so far, provide a detailed debrief.

SCORING METHODOLOGY:
{scoring_section}

CRITICAL — After the narrative debrief, you MUST output a structured JSON block on its own line, fenced with ```json and ```. This JSON is parsed programmatically. Format:

```json
{{
  "overall_score": 7.2,
  "dimensions": {{
    {dimension_json}
  }},
  "strengths": ["Specific strength 1", "Specific strength 2"],
  "improvements": ["Area to improve 1", "Area to improve 2"],
  "scenario_type": "{methodology}",
  "recommended_next": "suggested_next_practice"
}}
```"""

        response = coach_llm.invoke([
            SystemMessage(content=system_prompt),
            *messages,
            HumanMessage(content="Provide the roleplay debrief now.")
        ])

        # Parse debrief from response
        debrief = _parse_debrief_response(response.content, methodology)

        return {
            "messages": messages + [AIMessage(content=response.content)],
            "rag_context": rag_context,
            "task_output": TaskOutput(
                status="success",
                artifacts={"roleplay_debrief": debrief},
                handoff_notes=f"Roleplay complete. Score: {debrief.overall_score}/10. Strengths: {len(debrief.strengths)}. Improvements: {len(debrief.improvements)}"
            )
        }
    else:
        system_prompt = f"""You are an AI sales coach playing a buyer in a roleplay.

CONTEXT FROM PLAYBOOK:
{rag_context}

Stay in character as the buyer. Respond naturally to the rep's last message.
Be realistic - raise objections, ask clarifying questions, don't make it too easy.
Keep responses conversational (2-4 sentences)."""

        response = coach_llm.invoke([
            SystemMessage(content=system_prompt),
            *messages
        ])

        return {
            "messages": messages + [AIMessage(content=response.content)],
            "rag_context": rag_context,
        }


def _parse_debrief_response(response_text: str, methodology: str) -> RoleplayDebrief:
    """Parse debrief response to extract RoleplayDebrief artifact."""
    import json
    import re

    # Try to extract JSON block
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return RoleplayDebrief(
                scenario="",  # Will be filled by caller
                overall_score=float(data.get("overall_score", 0)),
                strengths=data.get("strengths", []),
                improvements=data.get("improvements", []),
                dimension_scores=data.get("dimensions", {}),
                recommended_practice=[data.get("recommended_next", "Continue practicing")],
                methodology=methodology
            )
        except json.JSONDecodeError:
            pass

    # Fallback: create minimal debrief
    return RoleplayDebrief(
        scenario="",
        overall_score=5.0,
        strengths=["Completed roleplay session"],
        improvements=["Review conversation for specific feedback"],
        dimension_scores={},
        recommended_practice=["Continue practicing"],
        methodology=methodology
    )


def create_prep_node_typed(llm_with_tools):
    """Create the prep node with typed output."""

    def prep_node(state: dict) -> dict:
        """Generate a meeting prep brief with typed output."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""

        task_input = state.get("task_input")
        if task_input and isinstance(task_input, TaskInput):
            company_name = task_input.goal.replace("prep for ", "").replace("meeting at ", "").strip()
        else:
            company_name = extract_scenario(last_message)

        # Gather web context
        web_context = search_company_news(company_name)

        # Gather RAG context
        rag_context = rag_search(f"meeting prep discovery call {company_name}")

        # Get CRM context
        crm_rag_context = search_crm(company_name)

        system_prompt = f"""You are an AI sales coach helping a rep prepare for a meeting.

COMPANY NEWS (from web search):
{web_context}

PLAYBOOK CONTEXT (from RAG):
{rag_context}

CRM DATA (from RAG):
{crm_rag_context}

TASK: Create a meeting prep brief for {company_name}.

Format your response as a structured brief with:
- Account Summary
- Recent News & Intel
- Key Talking Points
- Potential Objections & Responses
- Questions to Ask
- Risk Areas"""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a meeting prep brief for {company_name}")
        ])

        # Create typed artifact
        prep_brief = MeetingPrepBrief(
            company_name=company_name,
            meeting_type="discovery",
            attendees=[],
            account_health="unknown",
            recent_activity=web_context.split("\n")[:3] if web_context else [],
            open_deals=[],
            talking_points=["Review account history", "Prepare discovery questions", "Identify key stakeholders"],
            recommended_agenda=["Introductions", "Current challenges", "Next steps"]
        )

        return {
            "messages": messages + [response],
            "web_context": web_context,
            "rag_context": rag_context,
            "task_output": TaskOutput(
                status="success",
                artifacts={"meeting_prep": prep_brief},
                handoff_notes=f"Meeting prep created for {company_name}"
            )
        }

    return prep_node


def feedback_node_typed(state: dict) -> dict:
    """Analyze a call/meeting and provide typed feedback output."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""

    task_input = state.get("task_input")
    if task_input and isinstance(task_input, TaskInput):
        call_notes = task_input.goal
        methodology = task_input.constraints.get("methodology", "discovery")
    else:
        call_notes = extract_scenario(last_message)
        methodology = "discovery"

    # Get RAG context
    rag_context = rag_search("sales call best practices feedback")

    prompt = FEEDBACK_SYSTEM_PROMPT.format(
        rag_context=rag_context,
        call_notes=call_notes,
    )

    response = coach_llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content="Analyze this sales interaction and provide specific feedback.")
    ])

    # Create typed debrief
    debrief = RoleplayDebrief(
        scenario="feedback",
        overall_score=5.0,  # Would need LLM to extract actual score
        strengths=["Analysis complete"],
        improvements=["Review feedback details"],
        dimension_scores={},
        recommended_practice=["Practice based on feedback"],
        methodology=methodology
    )

    return {
        "messages": messages + [AIMessage(content=response.content)],
        "rag_context": rag_context,
        "task_output": TaskOutput(
            status="success",
            artifacts={"feedback_debrief": debrief},
            handoff_notes=f"Feedback provided for: {call_notes[:50]}..."
        )
    }


def workflow_router_typed(state: dict) -> str:
    """Route to the appropriate workflow node."""
    workflow = state.get("workflow", "roleplay")

    if workflow == "prep":
        return "prep"
    elif workflow == "feedback":
        return "feedback"
    else:
        return "roleplay"


def build_coach_subgraph_typed(mcp_tools=None):
    """Build the coach subgraph with typed contracts.

    Args:
        mcp_tools: List of MCP tools (HubSpot, etc.) for prep workflow.
    """
    # Create LLM with tools for prep node
    all_tools = list(mcp_tools) if mcp_tools else []
    base_llm = get_llm()
    llm_with_tools = base_llm.bind_tools(all_tools) if all_tools else base_llm

    # Create prep node with tool-calling LLM
    prep_node_fn = create_prep_node_typed(llm_with_tools)

    # Create tool execution node
    tool_node = ToolNode(all_tools) if all_tools else None

    # Build the graph
    graph = StateGraph(dict)

    # Add nodes with typed versions
    graph.add_node("roleplay", roleplay_node_typed)
    graph.add_node("prep", prep_node_fn)
    graph.add_node("feedback", feedback_node_typed)

    if tool_node:
        graph.add_node("tools", tool_node)

    # Route based on workflow
    graph.add_conditional_edges(START, workflow_router_typed, {
        "roleplay": "roleplay",
        "prep": "prep",
        "feedback": "feedback",
    })

    # All nodes end (typed output in task_output)
    graph.add_edge("roleplay", END)
    graph.add_edge("feedback", END)

    if tool_node:
        graph.add_conditional_edges("prep", lambda s: "tools" if hasattr(s.get("messages", [])[-1], "tool_calls") and s["messages"][-1].tool_calls else "end", {
            "tools": "tools",
            "end": END,
        })
        graph.add_conditional_edges("tools", lambda s: "tools" if hasattr(s.get("messages", [])[-1], "tool_calls") and s["messages"][-1].tool_calls else "end", {
            "tools": "tools",
            "end": END,
        })
    else:
        graph.add_edge("prep", END)

    return graph.compile()
