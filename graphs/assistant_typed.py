"""Assistant agent graph with typed contracts - research, deal, email, pipeline workflows.

Uses MCP tools (HubSpot, BigQuery, Gmail) when available.
Falls back to mock CRM data for local testing when MCP isn't connected.
Outputs typed TaskOutput with ResearchBrief, DealStatus, EmailDraft, PipelineDigest artifacts.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Any

from llm_factory import get_llm
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from graphs.contracts import (
    TaskInput, TaskOutput, TaskStatus,
    ResearchBrief, DealStatus, EmailDraft, PipelineDigest,
    WorkflowType, AgentRole
)
from prompts.assistant_prompts import (
    RESEARCH_SYSTEM_PROMPT,
    DEAL_SYSTEM_PROMPT,
    PIPELINE_SYSTEM_PROMPT,
    EMAIL_SYSTEM_PROMPT,
)
from tools.web_search import search_company_news
from tools.rag import search as rag_search, search_crm, search_crm_deals, search_crm_contacts
from tools import mock_crm


def extract_company_name(message: str) -> str:
    """Extract company name from the message."""
    if message.startswith("/research "):
        return message.replace("/research ", "").strip()
    if message.startswith("/deal "):
        return message.replace("/deal ", "").strip()
    if message.startswith("/draft-email "):
        return message.replace("/draft-email ", "").strip()
    return message.strip()


def create_research_node_typed(llm_with_tools, use_mock: bool = False):
    """Create the research node with typed output."""

    def research_node(state: dict) -> dict:
        """Generate a company research brief with typed output."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""

        task_input = state.get("task_input")
        if task_input and isinstance(task_input, TaskInput):
            company_name = task_input.goal.replace("research ", "").strip()
        else:
            company_name = state.get("company_name") or extract_company_name(last_message)

        # Smart web search
        if use_mock and mock_crm.is_known_mock_company(company_name):
            web_context = _generate_mock_news(company_name)
        else:
            web_context = search_company_news(company_name)

        # Get RAG context
        rag_context = rag_search(f"sales approach {company_name} ICP")

        # Get CRM context from RAG
        crm_rag_context = search_crm(company_name)

        # Apollo enrichment
        apollo_context = ""
        from tools.apollo_enrichment import (
            is_apollo_enabled, enrich_company, enrich_contacts,
            format_apollo_company_context, format_apollo_contacts_context
        )
        if is_apollo_enabled():
            apollo_company = enrich_company(company_name)
            apollo_contacts = enrich_contacts(company_name, limit=5)
            apollo_context = format_apollo_company_context(apollo_company)
            if apollo_contacts:
                apollo_context += "\n" + format_apollo_contacts_context(apollo_contacts)

        # Build system prompt
        if use_mock:
            crm_context = _get_mock_company_context(company_name)
            system_prompt = f"""You are a sales research assistant.

TASK: Generate a research brief for {company_name}.

CRM DATA:
{crm_context}

CRM DATA (from RAG):
{crm_rag_context}

WEB SEARCH RESULTS:
{web_context}

PLAYBOOK CONTEXT:
{rag_context}

Format your response as a concise research brief."""
        else:
            system_prompt = f"""You are a sales research assistant.

TASK: Generate a research brief for {company_name}.

CRM DATA (from RAG):
{crm_rag_context}

WEB SEARCH RESULTS:
{web_context}

PLAYBOOK CONTEXT:
{rag_context}

Use available tools to gather additional CRM data if needed."""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate a research brief for {company_name}")
        ])

        # Create typed artifact
        research_brief = ResearchBrief(
            company_name=company_name,
            overview=crm_context if use_mock else crm_rag_context or f"Research for {company_name}",
            recent_news=web_context.split("\n")[:5] if web_context else [],
            icp_fit=rag_context or "No ICP fit data available",
            talking_points=["Review company background", "Identify key challenges", "Prepare relevant case studies"],
            competitors=[],
            recommended_approach="Start with discovery questions about current challenges",
            sources=["web", "rag", "crm"]
        )

        return {
            "messages": messages + [response],
            "web_context": web_context,
            "rag_context": rag_context,
            "task_output": TaskOutput(
                status="success",
                artifacts={"research_brief": research_brief},
                handoff_notes=f"Research brief created for {company_name}. Sources: web, rag, crm."
            )
        }

    return research_node


def create_deal_node_typed(llm_with_tools, use_mock: bool = False):
    """Create the deal node with typed output."""

    def deal_node(state: dict) -> dict:
        """Look up and summarize a deal with typed output."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""

        task_input = state.get("task_input")
        if task_input and isinstance(task_input, TaskInput):
            deal_name = task_input.goal.replace("deal ", "").strip()
        else:
            deal_name = extract_company_name(last_message)

        # Get deal context from RAG
        deal_rag_context = search_crm_deals(deal_name)
        contact_rag_context = search_crm_contacts(deal_name)
        crm_rag_context = f"Deal matches:\n{deal_rag_context}\n\nRelated contacts:\n{contact_rag_context}"

        if use_mock:
            deal_context = _get_mock_deal_context(deal_name)
            system_prompt = f"""You are a sales assistant.

TASK: Provide a status summary for the deal matching "{deal_name}".

DEAL DATA:
{deal_context}

CRM DATA (from RAG):
{crm_rag_context}

Format your response as a deal status summary."""
        else:
            system_prompt = f"""You are a sales assistant with access to HubSpot CRM tools.

TASK: Look up the deal "{deal_name}" and provide a status summary.

CRM DATA (from RAG):
{crm_rag_context}

Use HubSpot tools to get deal details if needed."""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Look up the deal: {deal_name}")
        ])

        # Parse deal info and create typed artifact
        deal_status = _parse_deal_info(deal_name, deal_rag_context)

        return {
            "messages": messages + [response],
            "task_output": TaskOutput(
                status="success",
                artifacts={"deal_status": deal_status},
                handoff_notes=f"Deal status retrieved for {deal_name}. Stage: {deal_status.stage}."
            )
        }

    return deal_node


def _parse_deal_info(deal_name: str, deal_context: str) -> DealStatus:
    """Parse deal context into typed DealStatus."""
    # Simple parsing - production would use LLM for better extraction
    stage = "unknown"
    amount = None
    close_date = None
    owner = "unknown"
    health = "yellow"

    # Try to extract from context
    if "stage" in deal_context.lower():
        if "closed won" in deal_context.lower():
            stage = "closed won"
            health = "green"
        elif "closed lost" in deal_context.lower():
            stage = "closed lost"
            health = "red"
        elif "commit" in deal_context.lower():
            stage = "verbal commit"
            health = "green"
        elif "negotiat" in deal_context.lower():
            stage = "negotiation"
            health = "yellow"

    return DealStatus(
        deal_name=deal_name,
        company_name=deal_name,
        amount=amount,
        stage=stage,
        close_date=close_date,
        owner=owner,
        health=health,
        next_steps=["Follow up on deal status"],
        risks=[],
        recent_activity=[deal_context[:200] if deal_context else "No recent activity"]
    )


def create_email_node_typed(llm_with_tools, use_mock: bool = False):
    """Create the email draft node with typed output."""

    def email_node(state: dict) -> dict:
        """Draft a follow-up email with typed output."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""

        task_input = state.get("task_input")
        if task_input and isinstance(task_input, TaskInput):
            company_name = task_input.goal.replace("email for ", "").replace("draft email ", "").strip()
            constraints = task_input.constraints
        else:
            company_name = extract_company_name(last_message)
            constraints = {}

        contact_name = state.get("contact_name") or constraints.get("to_name")
        contact_email = state.get("contact_email") or constraints.get("to_email")

        # Get RAG context for email templates
        rag_context = rag_search("follow-up email template sales")

        # Get CRM context
        crm_rag_context = search_crm(company_name)

        # Build contact instruction
        contact_instruction = ""
        if contact_name and contact_email:
            first_name = contact_name.split()[0]
            contact_instruction = f"Address the email to {first_name} ({contact_name})."

        if use_mock:
            crm_context = _get_mock_company_context(company_name)
            email_thread = mock_crm.load_email_thread(company_name)
            thread_context = ""
            if email_thread:
                thread_context = f"\nEXISTING EMAIL THREAD:\nSubject: {email_thread.get('subject', 'N/A')}\n"
                for msg in email_thread.get("messages", [])[-3:]:
                    thread_context += f"\nFrom: {msg.get('from', 'Unknown')}\n{msg.get('body', '')[:200]}...\n"

            system_prompt = f"""You are a sales email copywriter.

TASK: Draft a follow-up email for {company_name}.
{contact_instruction}
CRM DATA:
{crm_context}
{thread_context}

EMAIL TEMPLATE CONTEXT:
{rag_context}

Draft a personalized follow-up email."""
        else:
            system_prompt = f"""You are a sales email copywriter.

TASK: Draft a follow-up email for {company_name}.
{contact_instruction}
CRM DATA (from RAG):
{crm_rag_context}

EMAIL TEMPLATE CONTEXT:
{rag_context}

Draft a personalized follow-up email."""

        human_msg = f"Draft a follow-up email for {company_name}"
        if contact_name:
            human_msg += f" to {contact_name}"

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_msg)
        ])

        # Create typed artifact
        email_draft = EmailDraft(
            to_name=contact_name or "[Contact name]",
            to_email=contact_email or "",
            subject="Following up on our conversation",
            body=response.content,
            tone=constraints.get("tone", "professional"),
            purpose=constraints.get("purpose", "follow-up")
        )

        return {
            "messages": messages + [response],
            "rag_context": rag_context,
            "task_output": TaskOutput(
                status="success",
                artifacts={"email_draft": email_draft},
                handoff_notes=f"Email draft created for {contact_name or company_name}"
            )
        }

    return email_node


def create_pipeline_node_typed(llm_with_tools, use_mock: bool = False):
    """Create the pipeline health node with typed output."""

    def pipeline_node(state: dict) -> dict:
        """Generate a pipeline health digest with typed output."""
        messages = state.get("messages", [])

        # Get pipeline context
        if use_mock:
            pipeline_context = _get_mock_pipeline_context()
            analytics_context = _get_mock_analytics_context()
            system_prompt = f"""You are a sales operations analyst.

TASK: Generate a pipeline health digest.

PIPELINE DATA:
{pipeline_context}

ANALYTICS DATA:
{analytics_context}

Format your response as a pipeline health summary."""
        else:
            crm_rag_context = search_crm_deals("open deals pipeline")
            system_prompt = f"""You are a sales operations analyst.

TASK: Generate a pipeline health digest.

CRM DEAL DATA:
{crm_rag_context}

Use available tools to get current pipeline data."""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate a pipeline health digest")
        ])

        # Create typed artifact
        pipeline_digest = _create_pipeline_digest(use_mock)

        return {
            "messages": messages + [response],
            "task_output": TaskOutput(
                status="success",
                artifacts={"pipeline_digest": pipeline_digest},
                handoff_notes=f"Pipeline digest created. Total deals: {pipeline_digest.total_deals}."
            )
        }

    return pipeline_node


def _create_pipeline_digest(use_mock: bool = False) -> PipelineDigest:
    """Create PipelineDigest artifact."""
    if use_mock:
        open_deals = mock_crm.get_all_open_deals()
        total_deals = len(open_deals)
        total_value = sum(
            float(d.get("properties", {}).get("amount", 0) or 0)
            for d in open_deals
        )

        by_stage = {}
        for deal in open_deals:
            stage = deal.get("properties", {}).get("dealstage", "Unknown")
            if stage not in by_stage:
                by_stage[stage] = {"count": 0, "value": 0}
            by_stage[stage]["count"] += 1
            by_stage[stage]["value"] += float(deal.get("properties", {}).get("amount", 0) or 0)

        return PipelineDigest(
            total_deals=total_deals,
            total_value=total_value,
            by_stage=by_stage,
            at_risk_deals=[],
            won_this_period=[],
            recommendations=["Review at-risk deals", "Focus on closing end-of-period deals"]
        )

    return PipelineDigest(
        total_deals=0,
        total_value=0,
        by_stage={},
        at_risk_deals=[],
        won_this_period=[],
        recommendations=["Connect to CRM for pipeline data"]
    )


def should_continue_typed(state: dict) -> str:
    """Check if the LLM wants to call more tools or is done."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "end"


def workflow_router_typed(state: dict) -> str:
    """Route to the appropriate workflow node."""
    workflow = state.get("workflow", "research")

    if workflow == "deal":
        return "deal"
    elif workflow == "email":
        return "email"
    elif workflow == "pipeline":
        return "pipeline"
    return "research"


def build_assistant_subgraph_typed(mcp_tools=None):
    """Build the assistant subgraph with typed contracts.

    Args:
        mcp_tools: List of MCP tools (HubSpot, BigQuery, Gmail) loaded at startup.
    """
    use_mock = not mcp_tools or len(mcp_tools) == 0

    if use_mock:
        print("  [Assistant Typed] Using mock CRM data (no MCP tools available)")
    else:
        print(f"  [Assistant Typed] Using {len(mcp_tools)} MCP tools")

    # Create LLM with tools
    base_llm = get_llm()
    llm_with_tools = base_llm.bind_tools(mcp_tools) if mcp_tools else base_llm

    # Create typed nodes
    research_node = create_research_node_typed(llm_with_tools, use_mock)
    deal_node = create_deal_node_typed(llm_with_tools, use_mock)
    email_node = create_email_node_typed(llm_with_tools, use_mock)
    pipeline_node = create_pipeline_node_typed(llm_with_tools, use_mock)

    # Tool node
    tool_node = ToolNode(mcp_tools) if mcp_tools else None

    # Build graph
    graph = StateGraph(dict)

    # Add nodes
    graph.add_node("research", research_node)
    graph.add_node("deal", deal_node)
    graph.add_node("email", email_node)
    graph.add_node("pipeline", pipeline_node)

    if tool_node:
        graph.add_node("tools", tool_node)

    # Route from START
    graph.add_conditional_edges(START, workflow_router_typed, {
        "research": "research",
        "deal": "deal",
        "email": "email",
        "pipeline": "pipeline",
    })

    # Handle tool calls
    if tool_node:
        for node_name in ["research", "deal", "email", "pipeline"]:
            graph.add_conditional_edges(node_name, should_continue_typed, {
                "tools": "tools",
                "end": END,
            })
        graph.add_conditional_edges("tools", should_continue_typed, {
            "tools": "tools",
            "end": END,
        })
    else:
        graph.add_edge("research", END)
        graph.add_edge("deal", END)
        graph.add_edge("email", END)
        graph.add_edge("pipeline", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions (from original assistant.py)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_mock_news(company_name: str) -> str:
    """Generate plausible mock news for demo companies."""
    company = mock_crm.search_company(company_name)
    if not company:
        return "No recent news found."

    props = company.get("properties", {})
    full_name = props.get("name", company_name)
    industry = props.get("industry", "technology")
    city = props.get("city", "")
    state = props.get("state", "")
    num_employees = props.get("numberofemployees", "")

    company_id = company.get("id")
    deals = mock_crm.get_deals_for_company(company_id) if company_id else []

    news_items = []

    if num_employees:
        news_items.append(
            f"• *{full_name} Expands Workforce* — The {industry} company "
            f"has grown to {num_employees} employees."
        )

    if city and state:
        news_items.append(
            f"• *{full_name} Strengthens {city} Presence* — Headquartered in "
            f"{city}, {state}."
        )

    if len(deals) >= 2:
        total_value = sum(
            float(d.get("properties", {}).get("amount", 0) or 0)
            for d in deals
            if d.get("properties", {}).get("amount")
        )
        if total_value:
            news_items.append(
                f"• *{full_name} in Active Evaluation Phase* — Multiple enterprise "
                f"deals in pipeline indicate growing demand."
            )

    if not news_items:
        news_items.append(f"• *{full_name}* — Active in the {industry} space.")

    return "\n\n".join(news_items)


def _get_mock_company_context(company_name: str) -> str:
    """Get formatted mock CRM context for a company."""
    company = mock_crm.search_company(company_name)
    if not company:
        return f"No company found matching '{company_name}' in CRM."

    lines = [mock_crm.format_company_for_display(company)]

    company_id = company.get("id")
    deals = mock_crm.get_deals_for_company(company_id)
    if deals:
        lines.append(f"\n*Deals ({len(deals)}):*")
        for deal in deals[:5]:
            lines.append(mock_crm.format_deal_for_display(deal))

    contacts = mock_crm.get_contacts_for_company(company_id)
    if contacts:
        lines.append(f"\n*Contacts ({len(contacts)}):*")
        for contact in contacts[:5]:
            lines.append(mock_crm.format_contact_for_display(contact))

    notes = mock_crm.load_meeting_notes(company_name)
    if notes:
        lines.append(f"\n*Meeting Notes:*\n{notes[:1000]}...")

    return "\n".join(lines)


def _get_mock_deal_context(deal_name: str) -> str:
    """Get formatted mock CRM context for a deal."""
    deal = mock_crm.search_deal(deal_name)
    if not deal:
        return f"No deal found matching '{deal_name}' in CRM."

    lines = [mock_crm.format_deal_for_display(deal)]

    company_id = deal.get("associations", {}).get("company")
    if company_id:
        company = mock_crm.get_company_by_id(company_id)
        if company:
            lines.append(f"\n*Company:*\n{mock_crm.format_company_for_display(company)}")

        contacts = mock_crm.get_contacts_for_company(company_id)
        if contacts:
            lines.append(f"\n*Contacts:*")
            for contact in contacts[:3]:
                lines.append(mock_crm.format_contact_for_display(contact))

    return "\n".join(lines)


def _get_mock_pipeline_context() -> str:
    """Get formatted mock pipeline data."""
    open_deals = mock_crm.get_all_open_deals()
    stale_deals = mock_crm.get_stale_deals()
    overdue_deals = mock_crm.get_overdue_deals()

    total_value = sum(
        float(d.get("properties", {}).get("amount", 0) or 0)
        for d in open_deals
    )

    by_stage = {}
    for deal in open_deals:
        stage = deal.get("properties", {}).get("dealstage", "Unknown")
        if stage not in by_stage:
            by_stage[stage] = {"count": 0, "value": 0}
        by_stage[stage]["count"] += 1
        by_stage[stage]["value"] += float(deal.get("properties", {}).get("amount", 0) or 0)

    lines = [
        f"*Open Deals:* {len(open_deals)}",
        f"*Total Pipeline Value:* ${total_value:,.2f}",
        "",
        "*By Stage:*",
    ]

    for stage, data in by_stage.items():
        lines.append(f"  - {stage}: {data['count']} deals (${data['value']:,.2f})")

    lines.append(f"\n*Stale Deals:* {len(stale_deals)}")
    lines.append(f"\n*Overdue Deals:* {len(overdue_deals)}")

    return "\n".join(lines)


def _get_mock_analytics_context() -> str:
    """Get formatted mock analytics data."""
    win_loss = mock_crm.load_win_loss_analysis()

    lines = ["*Historical Analytics:*"]

    if win_loss:
        latest = win_loss[-1] if win_loss else {}
        lines.append(f"  - Win Rate: {latest.get('win_rate', 'N/A')}%")
        lines.append(f"  - Avg Sales Cycle: {latest.get('avg_sales_cycle_days', 'N/A')} days")

    return "\n".join(lines)
