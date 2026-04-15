# Claude Code Instructions: `/meeting-prep` — Comprehensive Meeting Preparation

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `graphs/coach.py` (the `prep_node`), `formatters/research.py`, and `tools/rag.py` first.**

---

## CONTEXT — WHAT AND WHY

The existing `/coach prep` generates a meeting prep brief, but it goes through the coach graph and is one of several coach workflows. `/meeting-prep` is a **standalone, enhanced** version that generates a full pre-meeting packet: company research + deal context + key contacts + suggested agenda + objection prep + competitive positioning — all in one comprehensive Block Kit message.

Think of `/research` as "tell me about this company" and `/meeting-prep` as "I have a meeting with them in 30 minutes — prepare me."

---

## WHAT IT DOES

1. User types `/meeting-prep [company name]`
2. Bot pulls everything:
   - HubSpot via RAG: company, contacts, deals, notes, last interactions
   - Tavily: recent company news (last 7 days)
   - RAG: playbooks (objection handling, battle cards, ICPs)
3. LLM generates a comprehensive prep packet
4. Bot posts a multi-section Block Kit message with everything the rep needs

---

## STEP 1: Create `formatters/meeting_prep.py`

```python
"""Block Kit formatting for /meeting-prep command."""
from formatters.helpers import timestamp, format_currency, truncate


def format_meeting_prep_response(
    company_name: str,
    attendees: list,
    deal_context: dict,
    account_summary: str,
    recent_news: str,
    talking_points: list,
    objection_prep: list,
    questions_to_ask: list,
    risk_areas: list,
    suggested_agenda: list,
) -> tuple[list, str]:
    """Format a comprehensive meeting prep packet as Block Kit.

    Args:
        company_name: Company name
        attendees: List of dicts with 'name', 'title', 'email', 'notes'
        deal_context: Dict with 'name', 'stage', 'amount', 'close_date'
        account_summary: LLM-generated account summary string
        recent_news: Formatted recent news string
        talking_points: List of talking point strings
        objection_prep: List of dicts with 'objection' and 'response'
        questions_to_ask: List of strategic question strings
        risk_areas: List of risk strings
        suggested_agenda: List of agenda item strings

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Attendees
    if attendees:
        attendees_str = "\n".join([
            f"• *{a.get('name', 'Unknown')}* — {a.get('title', 'N/A')}"
            + (f"\n  _{a.get('notes', '')}_" if a.get('notes') else "")
            for a in attendees[:5]
        ])
    else:
        attendees_str = "_No contacts found — research before the meeting_"

    # Deal context
    deal_name = deal_context.get("name", "N/A")
    deal_stage = deal_context.get("stage", "N/A")
    deal_amount = format_currency(deal_context.get("amount", 0))
    deal_close = deal_context.get("close_date", "N/A")

    # Talking points
    tp_str = "\n".join([f"• {tp}" for tp in talking_points[:6]]) if talking_points else "_Ask AI to generate_"

    # Objection prep
    if objection_prep:
        obj_str = "\n".join([
            f"• *\"{o.get('objection', '')}\"*\n  → {o.get('response', '')}"
            for o in objection_prep[:4]
        ])
    else:
        obj_str = "_No likely objections identified_"

    # Questions to ask
    q_str = "\n".join([f"• {q}" for q in questions_to_ask[:5]]) if questions_to_ask else "_N/A_"

    # Risk areas
    risk_str = "\n".join([f"• ⚠️ {r}" for r in risk_areas[:4]]) if risk_areas else "_No major risks identified_"

    # Suggested agenda
    if suggested_agenda:
        agenda_str = "\n".join([f"{i+1}. {item}" for i, item in enumerate(suggested_agenda[:6])])
    else:
        agenda_str = "_No agenda generated_"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 Meeting Prep: {company_name}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Deal: *{deal_name}* • {deal_stage} • {deal_amount} • Close: {deal_close}"}
            ]
        },

        {"type": "divider"},

        # Account summary
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Account Summary:*\n{account_summary}"}
        },

        {"type": "divider"},

        # Attendees
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Key Contacts:*\n{attendees_str}"}
        },

        {"type": "divider"},

        # Recent news
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Recent News & Intel:*\n{recent_news if recent_news else '_No recent news found_'}"}
        },

        {"type": "divider"},

        # Suggested agenda
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Suggested Agenda:*\n{agenda_str}"}
        },

        {"type": "divider"},

        # Talking points
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Talking Points:*\n{tp_str}"}
        },

        {"type": "divider"},

        # Objection prep
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Likely Objections & Responses:*\n{obj_str}"}
        },

        {"type": "divider"},

        # Two columns: Questions to Ask + Risk Areas
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Questions to Ask:*\n{q_str}"},
                {"type": "mrkdwn", "text": f"*Risk Areas:*\n{risk_str}"},
            ]
        },

        # Action buttons
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start Roleplay", "emoji": True},
                    "action_id": "start_roleplay_from_research",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Draft Follow-Up Email", "emoji": True},
                    "action_id": "draft_email_from_research",
                    "value": company_name,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Competitor Intel", "emoji": True},
                    "action_id": "competitor_from_prep",
                    "value": company_name,
                },
            ]
        },

        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • HubSpot + Web Search + Playbooks • {timestamp()}"}
            ]
        },
    ]

    fallback = f"Meeting Prep: {company_name} — {deal_stage} — {deal_amount}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.meeting_prep import format_meeting_prep_response
```

And add `"format_meeting_prep_response"` to `__all__`.

---

## STEP 3: Add `/meeting-prep` Command Handler to `app.py`

```python
@app.command("/meeting-prep")
def handle_meeting_prep(ack, say, command):
    """Generate a comprehensive meeting preparation packet."""
    ack()
    company_name = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not company_name:
        say("Please provide a company name: `/meeting-prep [company]`", channel=channel_id)
        return

    say(f"📋 Preparing for your meeting with *{company_name}*... (gathering data from 4 sources)", channel=channel_id)

    # 1. Pull ALL data sources
    from tools.rag import search_crm, search_crm_contacts, search_crm_deals, search_playbooks
    from tools.web_search import search_company_news

    crm_context = search_crm(company_name, n_results=8)
    contacts_raw = search_crm_contacts(company_name, n_results=5)
    deals_raw = search_crm_deals(company_name, n_results=3)
    playbook_context = search_playbooks(
        f"meeting preparation objection handling {company_name}",
        n_results=5,
    )
    web_results = search_company_news(company_name)

    # 2. Extract structured data from mock CRM
    company_data = mock_crm.search_company(company_name)
    contacts = []
    deal_context = {"name": "N/A", "stage": "N/A", "amount": 0, "close_date": "N/A"}

    if company_data:
        company_id = company_data.get("id", "")
        raw_contacts = mock_crm.get_contacts_for_company(company_id)
        for c in raw_contacts:
            props = c.get("properties", {})
            contacts.append({
                "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                "title": props.get("jobtitle", "N/A"),
                "email": props.get("email", ""),
                "notes": "",
            })

        raw_deals = mock_crm.get_deals_for_company(company_id)
        if raw_deals:
            # Use the most active/recent deal
            deal = raw_deals[0]
            deal_props = deal.get("properties", {})
            deal_context = {
                "name": deal_props.get("dealname", "N/A"),
                "stage": deal_props.get("dealstage", "N/A"),
                "amount": deal_props.get("amount", 0),
                "close_date": deal_props.get("closedate", "N/A"),
            }

    # 3. Run LLM for the comprehensive prep
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Generate a comprehensive meeting preparation packet for {company_name}.

CRM DATA:
{crm_context}

CONTACTS:
{contacts_raw}

DEAL INFO:
{deals_raw}

RECENT NEWS:
{web_results}

PLAYBOOK / BATTLE CARDS:
{playbook_context}

Generate ALL of the following (be specific, use the data):

ACCOUNT_SUMMARY: [2-3 sentences summarizing the relationship, deal status, last interaction]

AGENDA:
1. [suggested agenda item]
2. [suggested agenda item]
3. [suggested agenda item]
4. [suggested agenda item]

TALKING_POINTS:
- [specific talking point based on deal context]
- [specific talking point based on news]
- [specific talking point based on playbook]
- [specific talking point]
- [specific talking point]

OBJECTIONS:
OBJECTION: "[likely objection]" | RESPONSE: "[how to respond]"
OBJECTION: "[likely objection]" | RESPONSE: "[how to respond]"
OBJECTION: "[likely objection]" | RESPONSE: "[how to respond]"

QUESTIONS:
- [strategic question to advance the deal]
- [strategic question about their needs]
- [strategic question about timeline/budget]

RISKS:
- [risk area to watch for]
- [risk area to watch for]

Be specific and practical. The rep is using this in 15 minutes.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    # 4. Parse LLM response
    prep_data = parse_meeting_prep_response(llm_response)

    # 5. Format and send
    from formatters import format_meeting_prep_response
    blocks, fallback = format_meeting_prep_response(
        company_name=company_name,
        attendees=contacts,
        deal_context=deal_context,
        account_summary=prep_data.get("account_summary", ""),
        recent_news=web_results[:500] if web_results else "",
        talking_points=prep_data.get("talking_points", []),
        objection_prep=prep_data.get("objections", []),
        questions_to_ask=prep_data.get("questions", []),
        risk_areas=prep_data.get("risks", []),
        suggested_agenda=prep_data.get("agenda", []),
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add Parsing Helper

```python
def parse_meeting_prep_response(llm_text: str) -> dict:
    """Parse the LLM meeting prep response into structured sections."""
    result = {
        "account_summary": "",
        "agenda": [],
        "talking_points": [],
        "objections": [],
        "questions": [],
        "risks": [],
    }

    current_section = ""

    for line in llm_text.split("\n"):
        line_stripped = line.strip()
        line_upper = line_stripped.upper()

        # Detect section headers
        if line_upper.startswith("ACCOUNT_SUMMARY:"):
            result["account_summary"] = line_stripped.split(":", 1)[1].strip()
            current_section = "account_summary"
            continue
        elif "AGENDA" in line_upper and (":" in line_upper or "#" in line_upper):
            current_section = "agenda"
            continue
        elif "TALKING_POINT" in line_upper or "TALKING POINT" in line_upper:
            current_section = "talking_points"
            continue
        elif "OBJECTION" in line_upper and (":" in line_upper or "#" in line_upper) and "RESPONSE" not in line_upper:
            current_section = "objections"
            continue
        elif "QUESTION" in line_upper and (":" in line_upper or "#" in line_upper):
            current_section = "questions"
            continue
        elif "RISK" in line_upper and (":" in line_upper or "#" in line_upper):
            current_section = "risks"
            continue

        # Parse content based on current section
        cleaned = line_stripped.lstrip("•-*0123456789. ")
        if not cleaned:
            continue

        if current_section == "account_summary":
            result["account_summary"] += " " + cleaned
        elif current_section == "agenda":
            if cleaned:
                result["agenda"].append(cleaned)
        elif current_section == "talking_points":
            if cleaned:
                result["talking_points"].append(cleaned)
        elif current_section == "objections":
            if "OBJECTION:" in line_stripped and "RESPONSE:" in line_stripped:
                parts = line_stripped.split("RESPONSE:")
                objection = parts[0].replace("OBJECTION:", "").strip().strip('"').strip("|- ")
                response = parts[1].strip().strip('"')
                result["objections"].append({"objection": objection, "response": response})
            elif "|" in line_stripped and "RESPONSE" in line_stripped.upper():
                parts = line_stripped.split("|")
                if len(parts) >= 2:
                    result["objections"].append({
                        "objection": parts[0].strip().strip('"').strip("•- "),
                        "response": parts[1].replace("RESPONSE:", "").strip().strip('"'),
                    })
        elif current_section == "questions":
            if cleaned:
                result["questions"].append(cleaned)
        elif current_section == "risks":
            if cleaned:
                result["risks"].append(cleaned)

    result["account_summary"] = result["account_summary"].strip()
    return result
```

---

## STEP 5: Add Action Handler

```python
@app.action("competitor_from_prep")
def handle_competitor_from_prep(ack, body, say):
    """Suggest running /competitor from meeting prep."""
    ack()
    company = body["actions"][0]["value"]
    channel = body["channel"]["id"]
    say(
        text=f"Try: `/competitor [competitor name]` to get competitive intel for your meeting with *{company}*.",
        channel=channel,
    )
```

---

## REGISTER IN SLACK

Add `/meeting-prep` slash command in api.slack.com:
- **Command:** `/meeting-prep`
- **Description:** `Get a comprehensive meeting preparation packet`
- **Usage Hint:** `[company name]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/meeting_prep.py` | New formatter for meeting prep Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_meeting_prep_response` export |
| EDIT | `app.py` | Add `handle_meeting_prep()`, `parse_meeting_prep_response()`, `handle_competitor_from_prep()` |
