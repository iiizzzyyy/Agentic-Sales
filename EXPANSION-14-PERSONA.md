# Claude Code Instructions: `/persona` — Buyer Persona Generator

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/mock_crm.py`, `tools/rag.py`, and `data/playbooks/ideal_customer_profiles.md` first.**

---

## CONTEXT — WHAT AND WHY

Before any outreach, a rep needs to understand WHO they're selling to. `/persona` generates a detailed buyer persona based on the company's industry, size, deal stage, and past interactions. It includes likely pain points, decision-making style, preferred communication tone, and what messaging will resonate.

This combines ICP playbook data with actual CRM data to produce personalized, contextual personas — not generic templates.

---

## WHAT IT DOES

1. User types `/persona NovaTech` or `/persona Horizon Education CFO`
2. Bot loads: company data, contacts, deal history, ICP playbook, and any past interactions
3. LLM generates a rich persona profile tailored to this specific company and role
4. Bot posts Block Kit with: persona card, pain points, messaging do's and don'ts, conversation starters

---

## STEP 1: Create `formatters/persona.py`

```python
"""Block Kit formatting for /persona command."""
from formatters.helpers import timestamp, truncate


def format_persona_response(
    company_name: str,
    persona_name: str,
    persona_title: str,
    persona_profile: dict,
    messaging_guide: dict,
    conversation_starters: list,
) -> tuple[list, str]:
    """Format a buyer persona as Block Kit.

    Args:
        company_name: Company name
        persona_name: Contact name (or "Typical [Title]" if no specific contact)
        persona_title: Job title
        persona_profile: Dict with 'background', 'pain_points', 'priorities', 'decision_style', 'communication_pref'
        messaging_guide: Dict with 'do', 'dont', 'value_props'
        conversation_starters: List of opening questions/topics

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"👤 Buyer Persona: {persona_title}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"{persona_name} at {company_name} • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Background
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 Background:*\n{truncate(persona_profile.get('background', 'N/A'), 500)}"
            }
        },

        {"type": "divider"},

        # Pain points and priorities
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*🎯 Pain Points:*\n{chr(10).join(['• ' + p for p in persona_profile.get('pain_points', [])[:4]])}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*📌 Priorities:*\n{chr(10).join(['• ' + p for p in persona_profile.get('priorities', [])[:4]])}"
                },
            ]
        },

        # Decision style and communication
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*🧠 Decision Style:*\n{persona_profile.get('decision_style', 'N/A')}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*💬 Communication:*\n{persona_profile.get('communication_pref', 'N/A')}"
                },
            ]
        },

        {"type": "divider"},

        # Messaging dos and don'ts
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*✅ Do:*\n{chr(10).join(['• ' + d for d in messaging_guide.get('do', [])[:4]])}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*❌ Don't:*\n{chr(10).join(['• ' + d for d in messaging_guide.get('dont', [])[:4]])}"
                },
            ]
        },

        {"type": "divider"},
    ]

    # Value props
    if messaging_guide.get("value_props"):
        vp_text = "\n".join([f"• 💎 {v}" for v in messaging_guide["value_props"][:3]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Value Props That Resonate:*\n{vp_text}"}
        })

    # Conversation starters
    if conversation_starters:
        starters_text = "\n".join([f"• 💬 _{s}_" for s in conversation_starters[:4]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Conversation Starters:*\n{starters_text}"}
        })

    # Action buttons
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Draft Email", "emoji": True},
                "action_id": "draft_email_from_persona",
                "value": f"{company_name}||{persona_name}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Practice Call", "emoji": True},
                "action_id": "roleplay_from_persona",
                "value": f"{company_name}||{persona_title}",
            },
        ]
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Buyer Persona • {timestamp()}"}
        ]
    })

    fallback = f"Buyer Persona: {persona_name} ({persona_title}) at {company_name}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.persona import format_persona_response
```

And add `"format_persona_response"` to `__all__`.

---

## STEP 3: Add `/persona` Command Handler to `app.py`

```python
@app.command("/persona")
def handle_persona(ack, say, command):
    """Generate a buyer persona for a company contact."""
    ack()
    text = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not text:
        say(
            "Generate a buyer persona: `/persona [company] [role — optional]`\n"
            "Examples:\n• `/persona NovaTech`\n"
            "• `/persona Horizon Education CFO`\n"
            "• `/persona Apex VP of Engineering`",
            channel=channel_id,
        )
        return

    # Parse company and optional role
    parts = text.split(maxsplit=1)
    company_query = parts[0]
    target_role = parts[1] if len(parts) > 1 else None

    say(f"👤 Building buyer persona for *{text}*...", channel=channel_id)

    # 1. Find company
    company = mock_crm.search_company(company_query)
    if not company:
        say(f"Could not find company matching '{company_query}'.", channel=channel_id)
        return

    company_name = company.get("properties", {}).get("name", company_query)
    company_id = company.get("id", "")
    company_props = company.get("properties", {})

    # 2. Find matching contact (if role specified)
    contacts = mock_crm.get_contacts_for_company(company_id)
    matched_contact = None

    if target_role and contacts:
        for c in contacts:
            c_title = c.get("properties", {}).get("jobtitle", "").lower()
            if target_role.lower() in c_title:
                matched_contact = c
                break

    if not matched_contact and contacts:
        matched_contact = contacts[0]

    if matched_contact:
        c_props = matched_contact.get("properties", {})
        persona_name = f"{c_props.get('firstname', '')} {c_props.get('lastname', '')}".strip()
        persona_title = c_props.get("jobtitle", target_role or "Decision Maker")
    else:
        persona_name = f"Typical {target_role or 'Decision Maker'}"
        persona_title = target_role or "Decision Maker"

    # 3. Load context
    deals = mock_crm.get_deals_for_company(company_id)
    deal_context = ""
    for d in deals[:3]:
        dp = d.get("properties", {})
        deal_context += f"Deal: {dp.get('dealname', '?')}, Stage: {dp.get('dealstage', '?')}, ${float(dp.get('amount', 0) or 0):,.0f}\n"
        for a in d.get("activities", [])[:2]:
            deal_context += f"  Note: {a.get('body', a.get('note', ''))[:100]}\n"

    from tools.rag import search_playbooks
    icp_context = search_playbooks(f"ideal customer profile {company_props.get('industry', '')} {persona_title} buyer persona pain points", n_results=5)
    methodology_context = search_playbooks(f"sales methodology {persona_title} stakeholder discovery", n_results=3)

    # 4. LLM generates persona
    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Generate a detailed buyer persona for selling to this contact.

CONTACT: {persona_name} — {persona_title}
COMPANY: {company_name}
INDUSTRY: {company_props.get('industry', 'Technology')}
SIZE: {company_props.get('numberofemployees', 'Unknown')} employees
LOCATION: {company_props.get('city', '')}, {company_props.get('state', '')}

DEAL HISTORY:
{deal_context or 'No deals yet'}

ICP PLAYBOOK:
{icp_context}

SALES METHODOLOGY:
{methodology_context}

Generate EXACTLY this format:

BACKGROUND: [2-3 sentences about what this persona cares about, their daily challenges, and what success looks like for them]

PAIN_POINT_1: [Specific pain point relevant to their role and industry]
PAIN_POINT_2: [Another pain point]
PAIN_POINT_3: [Another pain point]

PRIORITY_1: [What they're prioritizing right now]
PRIORITY_2: [Another priority]
PRIORITY_3: [Another priority]

DECISION_STYLE: [How they make decisions — data-driven, consensus-builder, gut-feel, risk-averse, etc. 1-2 sentences]
COMMUNICATION_PREF: [How they prefer to communicate — formal emails, quick Slack, detailed presentations, executive summaries. 1-2 sentences]

DO_1: [Messaging approach that will resonate]
DO_2: [Another do]
DO_3: [Another do]

DONT_1: [Messaging mistake to avoid]
DONT_2: [Another don't]
DONT_3: [Another don't]

VALUE_PROP_1: [Specific value prop that will resonate with this persona]
VALUE_PROP_2: [Another value prop]

STARTER_1: [Conversation opening question that shows you understand their world]
STARTER_2: [Another starter]
STARTER_3: [Another starter]

Be specific to {company_name} and {persona_title}'s role. Use deal context if available. Don't be generic.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    # 5. Parse
    persona_profile = {"background": "", "pain_points": [], "priorities": [], "decision_style": "", "communication_pref": ""}
    messaging_guide = {"do": [], "dont": [], "value_props": []}
    conversation_starters = []

    for line in llm_response.split("\n"):
        line = line.strip()
        if line.upper().startswith("BACKGROUND:"):
            persona_profile["background"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("PAIN_POINT_"):
            persona_profile["pain_points"].append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("PRIORITY_"):
            persona_profile["priorities"].append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("DECISION_STYLE:"):
            persona_profile["decision_style"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("COMMUNICATION_PREF:"):
            persona_profile["communication_pref"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("DO_"):
            messaging_guide["do"].append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("DONT_"):
            messaging_guide["dont"].append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("VALUE_PROP_"):
            messaging_guide["value_props"].append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("STARTER_"):
            conversation_starters.append(line.split(":", 1)[1].strip() if ":" in line else line)

    if not persona_profile["background"]:
        persona_profile["background"] = llm_response[:500]

    # 6. Format and send
    from formatters import format_persona_response
    blocks, fallback = format_persona_response(
        company_name=company_name,
        persona_name=persona_name,
        persona_title=persona_title,
        persona_profile=persona_profile,
        messaging_guide=messaging_guide,
        conversation_starters=conversation_starters,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add Action Handlers

```python
@app.action("draft_email_from_persona")
def handle_draft_from_persona(ack, body, client):
    """Draft an email tailored to this persona."""
    ack()
    user_id = body["user"]["id"]
    value = body["actions"][0]["value"]
    company = value.split("||")[0] if "||" in value else value
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/draft-email {company}` to draft an email tailored to this contact.",
    )


@app.action("roleplay_from_persona")
def handle_roleplay_from_persona(ack, body, client):
    """Start a roleplay with this persona."""
    ack()
    user_id = body["user"]["id"]
    value = body["actions"][0]["value"]
    company, title = value.split("||", 1) if "||" in value else (value, "decision maker")
    client.chat_postMessage(
        channel=user_id,
        text=f"Try: `/coach roleplay discovery call with {title} at {company}`",
    )
```

---

## REGISTER IN SLACK

Add `/persona` slash command in api.slack.com:
- **Command:** `/persona`
- **Description:** `Generate a buyer persona for a company contact`
- **Usage Hint:** `[company] [role — optional]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/persona.py` | New formatter for persona Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_persona_response` export |
| EDIT | `app.py` | Add `handle_persona()`, `handle_draft_from_persona()`, `handle_roleplay_from_persona()` |
