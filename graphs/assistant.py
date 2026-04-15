"""Assistant agent graph - research, deal, email, pipeline workflows.

Uses MCP tools (HubSpot, BigQuery, Gmail) when available.
Falls back to mock CRM data for local testing when MCP isn't connected.
"""

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from llm_factory import get_llm
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

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


def create_research_node(llm_with_tools, use_mock: bool = False):
    """Create the research node."""

    def research_node(state: dict) -> dict:
        """Generate a company research brief."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        company_name = state.get("company_name") or extract_company_name(last_message)

        # Smart web search — skip for known demo/synthetic companies
        if use_mock and mock_crm.is_known_mock_company(company_name):
            web_context = _generate_mock_news(company_name)
        else:
            web_context = search_company_news(company_name)

        # Get RAG context (playbooks)
        rag_context = rag_search(f"sales approach {company_name} ICP")

        # Get CRM context from RAG (pre-synced HubSpot data)
        crm_rag_context = search_crm(company_name)

        # Apollo.io enrichment (optional — disabled by default for demo)
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

        # Build Apollo section for prompt if data exists
        apollo_section = ""
        if apollo_context:
            apollo_section = f"""
APOLLO.IO ENRICHMENT:
{apollo_context}
"""

        # Get CRM context (mock or MCP)
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
{apollo_section}
PLAYBOOK CONTEXT:
{rag_context}

Format your response as:

*Research Brief: {company_name}*

*Company Overview:*
[What they do, size, industry, recent developments]

*Your Relationship:*
[Deal history, key contacts, last interaction from CRM]

*Recent News:*
[Relevant news and what it means for the deal]
{("*Apollo.io Intelligence:*" + chr(10) + "[LinkedIn profile, employee count, funding, tech stack, key contacts with verified emails]" + chr(10)) if apollo_context else ""}
*Talking Points:*
[3-5 actionable talking points]

Keep it concise. Reps need to scan this in 2 minutes."""
        else:
            # MCP tools available - let LLM call them
            system_prompt = f"""You are a sales research assistant with access to HubSpot CRM tools.

TASK: Generate a research brief for {company_name}.

CRM DATA (from RAG):
{crm_rag_context}

WEB SEARCH RESULTS:
{web_context}
{apollo_section}
PLAYBOOK CONTEXT:
{rag_context}

INSTRUCTIONS:
1. Use the HubSpot tools to search for the company and get their deals, contacts, and recent notes
2. Combine the CRM data with the web search results above
3. Generate a comprehensive research brief

Format your response as:

*Research Brief: {company_name}*

*Company Overview:*
[What they do, size, industry, recent developments]

*Your Relationship:*
[Deal history, key contacts, last interaction from HubSpot]

*Recent News:*
[Relevant news and what it means for the deal]
{("*Apollo.io Intelligence:*" + chr(10) + "[LinkedIn profile, employee count, funding, tech stack, key contacts with verified emails]" + chr(10)) if apollo_context else ""}
*Talking Points:*
[3-5 actionable talking points]

Keep it concise. Reps need to scan this in 2 minutes."""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Generate a research brief for {company_name}")
        ])

        return {
            "messages": messages + [response],
            "web_context": web_context,
            "rag_context": rag_context,
        }

    return research_node


def create_deal_node(llm_with_tools, use_mock: bool = False):
    """Create the deal node."""

    def deal_node(state: dict) -> dict:
        """Look up and summarize a deal."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        deal_name = extract_company_name(last_message)

        # Get deal and contact context from RAG (pre-synced HubSpot data)
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

Format your response as:

*Deal: [Deal Name]*

*Status:* [stage] | *Value:* [amount] | *Close Date:* [date]

*Key Contacts:*
[Contact names and roles]

*Recent Activity:*
[Last 3-5 activities/notes]

*Recommended Next Actions:*
[2-3 specific actions to move the deal forward]

*Risk Assessment:*
[Any concerns based on activity patterns or missing data]"""
        else:
            system_prompt = f"""You are a sales assistant with access to HubSpot CRM tools.

TASK: Look up the deal "{deal_name}" and provide a status summary.

CRM DATA (from RAG):
{crm_rag_context}

INSTRUCTIONS:
1. Use HubSpot tools to search for this deal by name
2. Get the deal details: stage, amount, close date, associated contacts
3. Get recent activities/notes for the deal
4. Provide a summary with recommended next actions

Format your response as:

*Deal: [Deal Name]*

*Status:* [stage] | *Value:* [amount] | *Close Date:* [date]

*Key Contacts:*
[Contact names and roles]

*Recent Activity:*
[Last 3-5 activities/notes]

*Recommended Next Actions:*
[2-3 specific actions to move the deal forward]

*Risk Assessment:*
[Any concerns based on activity patterns or missing data]"""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Look up the deal: {deal_name}")
        ])

        return {
            "messages": messages + [response],
        }

    return deal_node


def create_email_node(llm_with_tools, use_mock: bool = False):
    """Create the email draft node."""

    def email_node(state: dict) -> dict:
        """Draft a follow-up email."""
        messages = state.get("messages", [])
        last_message = messages[-1].content if messages else ""
        company_name = extract_company_name(last_message)

        # Get selected contact info (from contact picker flow)
        contact_name = state.get("contact_name")
        contact_email = state.get("contact_email")

        # Get RAG context for email templates
        rag_context = rag_search("follow-up email template sales")

        # Get CRM context for personalization
        crm_rag_context = search_crm(company_name)

        # Build contact instruction if we have a selected contact
        contact_instruction = ""
        if contact_name and contact_email:
            first_name = contact_name.split()[0]
            contact_instruction = f"""
CRITICAL — RECIPIENT:
You are writing this email TO: {contact_name} ({contact_email})
- Address the email to "{first_name}" — use "Hi {first_name}," as the greeting
- Do NOT use any other name from the email thread in the greeting
- The email thread history is for CONTEXT ONLY — you are writing a NEW email to {contact_name}
"""

        if use_mock:
            crm_context = _get_mock_company_context(company_name)
            email_thread = mock_crm.load_email_thread(company_name)
            thread_context = ""
            if email_thread:
                thread_context = f"\nEXISTING EMAIL THREAD (for context only):\nSubject: {email_thread.get('subject', 'N/A')}\n"
                for msg in email_thread.get("messages", [])[-3:]:
                    thread_context += f"\nFrom: {msg.get('from', 'Unknown')}\nDate: {msg.get('date', 'N/A')}\n{msg.get('body', '')[:300]}...\n"

            to_line = f"{contact_name} ({contact_email})" if contact_name else "[contact name and email if available]"
            system_prompt = f"""You are a sales email copywriter.

TASK: Draft a follow-up email for {company_name}.
{contact_instruction}
CRM DATA:
{crm_context}
{thread_context}

CRM DATA (from RAG):
{crm_rag_context}

EMAIL TEMPLATE CONTEXT (from playbook):
{rag_context}

IMPORTANT: Use the email thread for CONTEXT about deal status, but write the email TO the specified recipient.
If the deal is lost, write a win-back email. If in negotiation, acknowledge current status.

Format your response as:

*Draft Follow-Up Email*

*To:* {to_line}
*Subject:* [compelling subject line]

[email body - under 150 words, personalized, clear call-to-action]

---
_Edit as needed before sending._"""
        else:
            to_line = f"{contact_name} ({contact_email})" if contact_name else "[contact name and email if available]"
            system_prompt = f"""You are a sales email copywriter with access to HubSpot CRM tools.

TASK: Draft a follow-up email for {company_name}.
{contact_instruction}
CRM DATA (from RAG):
{crm_rag_context}

EMAIL TEMPLATE CONTEXT (from playbook):
{rag_context}

INSTRUCTIONS:
1. Use HubSpot tools to get context about this company/deal
2. Find the latest deal, recent notes, and primary contact
3. Draft a personalized follow-up email to the specified recipient

Format your response as:

*Draft Follow-Up Email*

*To:* {to_line}
*Subject:* [compelling subject line]

[email body - under 150 words, personalized, clear call-to-action]

---
_Edit as needed before sending._"""

        human_msg = f"Draft a follow-up email for {company_name}"
        if contact_name:
            human_msg += f" to {contact_name}"

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_msg)
        ])

        return {
            "messages": messages + [response],
            "rag_context": rag_context,
        }

    return email_node


def create_pipeline_node(llm_with_tools, use_mock: bool = False):
    """Create the pipeline health node."""

    def pipeline_node(state: dict) -> dict:
        """Generate a pipeline health digest."""
        messages = state.get("messages", [])

        # Get all deals from RAG for pipeline context
        crm_rag_context = search_crm_deals("open deals pipeline")

        if use_mock:
            pipeline_context = _get_mock_pipeline_context()
            analytics_context = _get_mock_analytics_context()

            system_prompt = f"""You are a sales operations analyst.

TASK: Generate a pipeline health digest.

PIPELINE DATA:
{pipeline_context}

ANALYTICS DATA:
{analytics_context}

CRM DEAL DATA (from RAG):
{crm_rag_context}

Format your response as:

*Pipeline Health Digest*

*Summary:*
[Total pipeline value, deal count, weighted forecast]

*By Stage:*
[Deal count and value per stage]

*Flagged Deals:*
[Deals with issues — explain why each is flagged]
• Stale: no activity in 14+ days
• Overdue: past projected close date
• At risk: missing key data

*Recommended Actions:*
[Top 3-5 specific actions the team should take this week]"""
        else:
            system_prompt = f"""You are a sales operations analyst with access to HubSpot CRM tools.

TASK: Generate a pipeline health digest.

CRM DEAL DATA (from RAG):
{crm_rag_context}

INSTRUCTIONS:
1. Use HubSpot tools to get all open deals
2. Analyze the pipeline: total value, deals by stage
3. Flag problematic deals:
   - Stale: no activity in 14+ days
   - Overdue: past projected close date
   - At risk: missing key data or stalled
4. Provide recommended actions

Format your response as:

*Pipeline Health Digest*

*Summary:*
[Total pipeline value, deal count, weighted forecast]

*By Stage:*
[Deal count and value per stage]

*Flagged Deals:*
[Deals with issues — explain why each is flagged]

*Recommended Actions:*
[Top 3-5 specific actions the team should take this week]"""

        response = llm_with_tools.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate a pipeline health digest")
        ])

        return {
            "messages": messages + [response],
        }

    return pipeline_node


# Helper functions for mock data formatting

def _generate_mock_news(company_name: str) -> str:
    """Generate plausible mock news for demo companies.

    Instead of hitting real web search (which returns irrelevant results for
    fictional companies), generate demo-appropriate news snippets based on
    the company's CRM data.
    """
    company = mock_crm.search_company(company_name)
    if not company:
        return "No recent news found."

    props = company.get("properties", {})
    full_name = props.get("name", company_name)
    industry = props.get("industry", "technology")
    city = props.get("city", "")
    state = props.get("state", "")
    num_employees = props.get("numberofemployees", "")

    # Get deals for context
    company_id = company.get("id")
    deals = mock_crm.get_deals_for_company(company_id) if company_id else []

    # Build plausible news items based on company data
    news_items = []

    if num_employees:
        news_items.append(
            f"• *{full_name} Expands Workforce* — The {industry} company "
            f"has grown to {num_employees} employees, signaling continued investment "
            f"in their product and go-to-market teams."
        )

    if city and state:
        news_items.append(
            f"• *{full_name} Strengthens {city} Presence* — Headquartered in "
            f"{city}, {state}, the company continues to attract top talent in the region."
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
                f"deals in pipeline indicate growing demand for their solutions."
            )

    if not news_items:
        news_items.append(f"• *{full_name}* — Active in the {industry} space with ongoing market presence.")

    return "\n\n".join(news_items)


def _get_mock_company_context(company_name: str) -> str:
    """Get formatted mock CRM context for a company."""
    company = mock_crm.search_company(company_name)
    if not company:
        return f"No company found matching '{company_name}' in CRM."

    lines = [mock_crm.format_company_for_display(company)]

    # Get deals
    company_id = company.get("id")
    deals = mock_crm.get_deals_for_company(company_id)
    if deals:
        lines.append(f"\n*Deals ({len(deals)}):*")
        for deal in deals[:5]:
            lines.append(mock_crm.format_deal_for_display(deal))

    # Get contacts
    contacts = mock_crm.get_contacts_for_company(company_id)
    if contacts:
        lines.append(f"\n*Contacts ({len(contacts)}):*")
        for contact in contacts[:5]:
            lines.append(mock_crm.format_contact_for_display(contact))

    # Get meeting notes if available
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

    # Get associated company
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

    # Calculate totals
    total_value = sum(
        float(d.get("properties", {}).get("amount", 0) or 0)
        for d in open_deals
    )

    # Group by stage
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

    lines.append(f"\n*Stale Deals (14+ days no activity):* {len(stale_deals)}")
    for deal in stale_deals[:5]:
        name = deal.get("properties", {}).get("dealname", "Unknown")
        lines.append(f"  - {name}")

    lines.append(f"\n*Overdue Deals (past close date):* {len(overdue_deals)}")
    for deal in overdue_deals[:5]:
        name = deal.get("properties", {}).get("dealname", "Unknown")
        close_date = deal.get("properties", {}).get("closedate", "N/A")
        lines.append(f"  - {name} (was due: {close_date[:10] if close_date else 'N/A'})")

    return "\n".join(lines)


def _get_mock_analytics_context() -> str:
    """Get formatted mock analytics data."""
    pipeline_analytics = mock_crm.load_pipeline_analytics()
    win_loss = mock_crm.load_win_loss_analysis()

    lines = ["*Historical Analytics:*"]

    if win_loss:
        latest = win_loss[-1] if win_loss else {}
        lines.append(f"  - Win Rate (latest quarter): {latest.get('win_rate', 'N/A')}%")
        lines.append(f"  - Avg Sales Cycle: {latest.get('avg_sales_cycle_days', 'N/A')} days")
        lines.append(f"  - Top Loss Reason: {latest.get('top_loss_reason', 'N/A')}")

    return "\n".join(lines)


def should_continue(state: dict) -> str:
    """Check if the LLM wants to call more tools or is done."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "end"


def build_assistant_subgraph(mcp_tools=None):
    """Build the assistant subgraph.

    Args:
        mcp_tools: List of MCP tools (HubSpot, BigQuery, Gmail) loaded at startup.
                   If None or empty, uses mock CRM data for local testing.
    """
    # Determine if we should use mock data
    use_mock = not mcp_tools or len(mcp_tools) == 0

    if use_mock:
        print("  [Assistant] Using mock CRM data (no MCP tools available)")
    else:
        print(f"  [Assistant] Using {len(mcp_tools)} MCP tools")

    # Create LLM with tools bound (if available)
    base_llm = get_llm()
    llm_with_tools = base_llm.bind_tools(mcp_tools) if mcp_tools else base_llm

    # Create workflow-specific nodes
    research_node = create_research_node(llm_with_tools, use_mock)
    deal_node = create_deal_node(llm_with_tools, use_mock)
    email_node = create_email_node(llm_with_tools, use_mock)
    pipeline_node = create_pipeline_node(llm_with_tools, use_mock)

    # Create tool execution node (only if MCP tools available)
    tool_node = ToolNode(mcp_tools) if mcp_tools else None

    def workflow_router(state: dict) -> str:
        """Route to the appropriate workflow node."""
        workflow = state.get("workflow", "research")
        if workflow == "deal":
            return "deal"
        elif workflow == "email":
            return "email"
        elif workflow == "pipeline":
            return "pipeline"
        return "research"

    # Build the graph
    graph = StateGraph(dict)

    # Add workflow entry nodes
    graph.add_node("research", research_node)
    graph.add_node("deal", deal_node)
    graph.add_node("email", email_node)
    graph.add_node("pipeline", pipeline_node)

    # Add tool execution node if tools available
    if tool_node:
        graph.add_node("tools", tool_node)

    # Route from START to workflow
    graph.add_conditional_edges(START, workflow_router, {
        "research": "research",
        "deal": "deal",
        "email": "email",
        "pipeline": "pipeline",
    })

    # After each workflow node, check if tools need to be called
    if tool_node:
        for node_name in ["research", "deal", "email", "pipeline"]:
            graph.add_conditional_edges(node_name, should_continue, {
                "tools": "tools",
                "end": END,
            })
        graph.add_conditional_edges("tools", should_continue, {
            "tools": "tools",
            "end": END,
        })
    else:
        # No tools, just end after workflow
        graph.add_edge("research", END)
        graph.add_edge("deal", END)
        graph.add_edge("email", END)
        graph.add_edge("pipeline", END)

    return graph.compile()
