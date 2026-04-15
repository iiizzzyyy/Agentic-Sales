"""Coach agent graph - roleplay, feedback, prep workflows.

Uses MCP tools for meeting prep (HubSpot data), direct tools for RAG and web search.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from llm_factory import get_llm
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

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


def roleplay_node(state: dict) -> dict:
    """Start or continue a roleplay session."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    scenario = extract_scenario(last_message)

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

    return {
        "messages": messages + [AIMessage(content=response.content)],
        "rag_context": rag_context,
    }


def continue_roleplay(state: dict, turn_count: int, max_turns: int = 4, methodology: str = "discovery") -> dict:
    """Continue an ongoing roleplay conversation.

    Args:
        state: Roleplay state with messages and rag_context
        turn_count: Current turn number
        max_turns: Maximum turns before debrief
        methodology: Scoring methodology key (discovery, meddic, spin, challenger, bant, etc.)
    """
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

FORMAT YOUR DEBRIEF LIKE THIS:
---
*Roleplay Debrief*

*Overall Score: X/10*

*What You Did Well:*
• [specific strength with example from the conversation]
• [specific strength with example]

*Areas to Improve:*
• [specific area with concrete suggestion]
• [specific area with concrete suggestion]

*Recommended Practice:*
• [next roleplay scenario to work on]
---

Be specific. Reference actual moments from the conversation.

CRITICAL — After the narrative debrief above, you MUST output a structured JSON block on its own line, fenced with ```json and ```. This JSON is parsed programmatically. Format:

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


def create_prep_node(llm_with_tools):
    """Create the prep node with tool-calling LLM for HubSpot access."""

    def prep_node(state: dict) -> dict:
        """Generate a meeting prep brief using MCP tools."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        company_name = extract_scenario(last_message)

        # Gather web context (direct tool)
        web_context = search_company_news(company_name)

        # Gather RAG context (direct tool)
        rag_context = rag_search(f"meeting prep discovery call {company_name}")

        # Get CRM context for company background
        crm_rag_context = search_crm(company_name)

        system_prompt = f"""You are an AI sales coach helping a rep prepare for a meeting.

COMPANY NEWS (from web search):
{web_context}

PLAYBOOK CONTEXT (from RAG):
{rag_context}

CRM DATA (from RAG):
{crm_rag_context}

TASK: Create a meeting prep brief for {company_name}.

INSTRUCTIONS:
1. Use HubSpot tools to get context about this company
2. Find their deals, contacts, and recent notes
3. Combine with the news and playbook context above
4. Generate a comprehensive prep brief

Available HubSpot tools:
- search_companies or search_crm_objects: Find the company
- get_deals: Get their deals
- get_contacts: Get contacts
- get_engagements: Get recent notes

Format your response as:

*Meeting Prep: {company_name}*

*Account Summary:*
[Key details from HubSpot — deal stage, value, key contacts, recent activity]

*Recent News & Intel:*
[Relevant company news from web search]

*Key Talking Points:*
[3-5 specific talking points based on deal context and playbook]

*Potential Objections & Responses:*
[Likely objections based on deal stage and persona, with suggested responses]

*Questions to Ask:*
[Strategic questions to advance the deal]

*Risk Areas:*
[Things to watch out for based on deal history]"""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a meeting prep brief for {company_name}")
        ])

        return {
            "messages": messages + [response],
            "web_context": web_context,
            "rag_context": rag_context,
        }

    return prep_node


def feedback_node(state: dict) -> dict:
    """Analyze a call/meeting and provide feedback."""
    messages = state.get("messages", [])
    last_message = messages[-1].content if messages else ""
    call_notes = extract_scenario(last_message)

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

    return {
        "messages": messages + [AIMessage(content=response.content)],
        "rag_context": rag_context,
    }


def should_continue(state: dict) -> str:
    """Check if the LLM wants to call more tools or is done."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "end"


def workflow_router(state: dict) -> str:
    """Route to the appropriate workflow node."""
    workflow = state.get("workflow", "roleplay")

    if workflow == "prep":
        return "prep"
    elif workflow == "feedback":
        return "feedback"
    else:
        return "roleplay"


def build_coach_subgraph(mcp_tools=None):
    """Build the coach subgraph with optional MCP tools.

    Args:
        mcp_tools: List of MCP tools (HubSpot, etc.) for prep workflow.
                   Roleplay and feedback don't need MCP tools (they use RAG only).
    """
    # Create LLM with tools for prep node
    all_tools = list(mcp_tools) if mcp_tools else []
    base_llm = get_llm()
    llm_with_tools = base_llm.bind_tools(all_tools) if all_tools else base_llm

    # Create prep node with tool-calling LLM
    prep_node_fn = create_prep_node(llm_with_tools)

    # Create tool execution node
    tool_node = ToolNode(all_tools) if all_tools else None

    # Build the graph
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("roleplay", roleplay_node)
    graph.add_node("prep", prep_node_fn)
    graph.add_node("feedback", feedback_node)

    if tool_node:
        graph.add_node("tools", tool_node)

    # Route based on workflow
    graph.add_conditional_edges(START, workflow_router, {
        "roleplay": "roleplay",
        "prep": "prep",
        "feedback": "feedback",
    })

    # Roleplay and feedback don't use tools, just end
    graph.add_edge("roleplay", END)
    graph.add_edge("feedback", END)

    # Prep may use tools
    if tool_node:
        graph.add_conditional_edges("prep", should_continue, {
            "tools": "tools",
            "end": END,
        })
        graph.add_conditional_edges("tools", should_continue, {
            "tools": "tools",
            "end": END,
        })
    else:
        graph.add_edge("prep", END)

    return graph.compile()
