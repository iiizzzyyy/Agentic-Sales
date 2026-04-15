# Claude Code Instructions: `/handoff` — Deal Handoff Brief

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `tools/mock_crm.py`, `tools/rag.py`, and `formatters/deal.py` first.**

---

## CONTEXT — WHAT AND WHY

When a rep leaves, goes on vacation, or a deal moves to a new AE, the new person needs to get up to speed fast. `/handoff` generates a comprehensive briefing doc covering everything about a deal: history, contacts, conversation tone, objections raised, competitor mentions, and recommended next steps.

This is the "AI as institutional memory" moment. It shows the AI doesn't just answer questions — it preserves and transfers tribal knowledge.

---

## WHAT IT DOES

1. User types `/handoff NovaTech` or `/handoff Horizon Education`
2. Bot loads ALL data for that deal: CRM record, contacts, activity notes, call transcripts, email threads, meeting notes
3. LLM synthesizes everything into a structured handoff brief
4. Bot posts Block Kit with: deal summary, key contacts, conversation history, risk factors, recommended next steps, and a "Copy as Doc" button

---

## STEP 1: Create `formatters/handoff.py`

```python
"""Block Kit formatting for /handoff command."""
from formatters.helpers import timestamp, format_currency, truncate


def format_handoff_response(
    deal_name: str,
    company_name: str,
    deal_summary: dict,
    key_contacts: list,
    conversation_history: str,
    risk_factors: list,
    next_steps: list,
    competitor_mentions: list,
) -> tuple[list, str]:
    """Format a deal handoff brief as Block Kit.

    Args:
        deal_name: Name of the deal
        company_name: Company name
        deal_summary: Dict with 'stage', 'amount', 'close_date', 'owner', 'created'
        key_contacts: List of dicts with 'name', 'title', 'email', 'role_in_deal'
        conversation_history: LLM-generated narrative of deal history
        risk_factors: List of risk strings
        next_steps: List of recommended next step strings
        competitor_mentions: List of competitor names mentioned in notes

    Returns:
        tuple: (blocks, fallback_text)
    """
    stage = deal_summary.get("stage", "Unknown")
    amount = deal_summary.get("amount", 0)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📋 Deal Handoff: {truncate(deal_name, 50)}", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Comprehensive brief for deal transition • {timestamp()}"}
            ]
        },

        {"type": "divider"},

        # Deal snapshot
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Company:*\n{company_name}"},
                {"type": "mrkdwn", "text": f"*Stage:*\n{stage}"},
                {"type": "mrkdwn", "text": f"*Value:*\n{format_currency(amount)}"},
                {"type": "mrkdwn", "text": f"*Close Date:*\n{deal_summary.get('close_date', 'N/A')}"},
            ]
        },

        {"type": "divider"},
    ]

    # Key contacts
    if key_contacts:
        contacts_text = ""
        for c in key_contacts[:5]:
            role = f" — _{c.get('role_in_deal', '')}_" if c.get('role_in_deal') else ""
            contacts_text += f"• *{c['name']}* ({c.get('title', 'N/A')}){role}\n  {c.get('email', '')}\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*👥 Key Contacts:*\n{contacts_text}"}
        })
        blocks.append({"type": "divider"})

    # Conversation history (narrative)
    if conversation_history:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📜 Deal Story:*\n{truncate(conversation_history, 2500)}"}
        })
        blocks.append({"type": "divider"})

    # Competitor mentions
    if competitor_mentions:
        comp_text = ", ".join([f"*{c}*" for c in competitor_mentions])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*⚔️ Competitors Mentioned:* {comp_text}"}
        })

    # Risk factors
    if risk_factors:
        risk_text = "\n".join([f"• ⚠️ {r}" for r in risk_factors[:5]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*🚨 Risk Factors:*\n{risk_text}"}
        })

    # Next steps
    if next_steps:
        steps_text = "\n".join([f"• ✅ {s}" for s in next_steps[:5]])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📌 Recommended Next Steps:*\n{steps_text}"}
        })

    # Action buttons
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Deal Card", "emoji": True},
                "action_id": "view_deal_from_handoff",
                "value": deal_name,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Draft Introduction Email", "emoji": True},
                "action_id": "draft_handoff_email",
                "value": f"{deal_name}||{company_name}",
            },
        ]
    })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Generated by SalesCoach AI • Deal Handoff • {timestamp()}"}
        ]
    })

    fallback = f"Deal Handoff: {deal_name} — {stage} — {format_currency(amount)}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.handoff import format_handoff_response
```

And add `"format_handoff_response"` to `__all__`.

---

## STEP 3: Add `/handoff` Command Handler to `app.py`

```python
@app.command("/handoff")
def handle_handoff(ack, say, command):
    """Generate a comprehensive deal handoff brief."""
    ack()
    query = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not query:
        say(
            "Specify a deal or company: `/handoff [company or deal name]`\n"
            "Examples:\n• `/handoff NovaTech`\n• `/handoff Horizon Education`",
            channel=channel_id,
        )
        return

    say(f"📋 Building handoff brief for *{query}*...", channel=channel_id)

    # 1. Find the deal and company
    deal = mock_crm.search_deal(query)
    company = mock_crm.search_company(query)

    if not deal and not company:
        say(f"Could not find a deal or company matching '{query}'. Try the exact name.", channel=channel_id)
        return

    # If we found company but not deal, get the first deal for that company
    if company and not deal:
        company_id = company.get("id", "")
        company_deals = mock_crm.get_deals_for_company(company_id)
        if company_deals:
            deal = company_deals[0]  # Use the first/primary deal

    if not deal:
        say(f"Found company '{query}' but no associated deals.", channel=channel_id)
        return

    props = deal.get("properties", {})
    deal_name = props.get("dealname", "Unknown")
    company_id = deal.get("associations", {}).get("company", "")

    if not company:
        company = mock_crm.get_company_by_id(company_id)

    company_name = company.get("properties", {}).get("name", "Unknown") if company else "Unknown"

    # 2. Load ALL data for this deal
    # Contacts
    contact_id = deal.get("associations", {}).get("contact", "")
    deal_contact = mock_crm.get_contact_by_id(contact_id) if contact_id else None
    company_contacts = mock_crm.get_contacts_for_company(company_id) if company_id else []

    key_contacts = []
    if deal_contact:
        c_props = deal_contact.get("properties", {})
        key_contacts.append({
            "name": f"{c_props.get('firstname', '')} {c_props.get('lastname', '')}".strip(),
            "title": c_props.get("jobtitle", ""),
            "email": c_props.get("email", ""),
            "role_in_deal": "Primary deal contact",
        })
    for cc in company_contacts:
        cc_props = cc.get("properties", {})
        cc_name = f"{cc_props.get('firstname', '')} {cc_props.get('lastname', '')}".strip()
        if not any(kc["name"] == cc_name for kc in key_contacts):
            key_contacts.append({
                "name": cc_name,
                "title": cc_props.get("jobtitle", ""),
                "email": cc_props.get("email", ""),
                "role_in_deal": "Company stakeholder",
            })

    # Activity notes
    activities = deal.get("activities", [])
    activity_text = ""
    for a in activities:
        activity_text += f"[{a.get('timestamp', 'N/A')[:10]}] {a.get('type', 'NOTE')}: {a.get('body', a.get('note', ''))}\n\n"

    # Call transcripts
    transcript = mock_crm.load_call_transcript(company_name)

    # Email threads
    email_thread = mock_crm.load_email_thread(company_name)

    # Meeting notes
    meeting_notes = mock_crm.load_meeting_notes(company_name)

    # RAG search for additional context
    from tools.rag import search_playbooks
    rag_context = search_playbooks(f"{company_name} {deal_name}", n_results=5)

    # 3. LLM synthesizes the handoff brief
    full_context = f"""DEAL: {deal_name}
COMPANY: {company_name}
STAGE: {props.get('dealstage', 'unknown')}
AMOUNT: ${float(props.get('amount', 0) or 0):,.0f}
CLOSE DATE: {props.get('closedate', 'N/A')}

ACTIVITY NOTES:
{activity_text or 'No activity notes.'}

CALL TRANSCRIPTS:
{transcript[:2000] if transcript else 'No transcripts available.'}

EMAIL THREADS:
{json.dumps(email_thread, indent=2)[:2000] if email_thread else 'No email threads.'}

MEETING NOTES:
{meeting_notes[:2000] if meeting_notes else 'No meeting notes.'}

RAG CONTEXT:
{rag_context[:1000]}"""

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Generate a deal handoff brief for a new rep taking over this deal.

{full_context}

Respond in EXACTLY this format:

DEAL_STORY: [3-5 sentences narrating the deal from start to current state. Include key milestones, decisions, and tone of the relationship. Write it like you're briefing a colleague over coffee.]

RISK_1: [A specific risk factor with context]
RISK_2: [Another risk]
RISK_3: [Another risk — if applicable]

NEXT_STEP_1: [Specific, actionable next step with timing]
NEXT_STEP_2: [Another next step]
NEXT_STEP_3: [Another next step]

COMPETITORS: [Comma-separated list of competitors mentioned, or "None"]

CONTACT_ROLES: [For each contact, describe their role in the deal: decision maker, champion, blocker, technical evaluator, etc. Format: Name=Role, Name=Role]

Be specific — use names, dates, dollar amounts from the data.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    llm_response = result["messages"][-1].content

    # 4. Parse structured response
    conversation_history = ""
    risk_factors = []
    next_steps = []
    competitor_mentions = []

    for line in llm_response.split("\n"):
        line = line.strip()
        if line.upper().startswith("DEAL_STORY:"):
            conversation_history = line.split(":", 1)[1].strip()
        elif line.upper().startswith("RISK_"):
            risk_factors.append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("NEXT_STEP_"):
            next_steps.append(line.split(":", 1)[1].strip() if ":" in line else line)
        elif line.upper().startswith("COMPETITORS:"):
            comps = line.split(":", 1)[1].strip()
            if comps.lower() != "none":
                competitor_mentions = [c.strip() for c in comps.split(",") if c.strip()]
        elif line.upper().startswith("CONTACT_ROLES:"):
            # Update contact roles from LLM analysis
            roles_str = line.split(":", 1)[1].strip()
            for role_pair in roles_str.split(","):
                if "=" in role_pair:
                    name_part, role_part = role_pair.split("=", 1)
                    name_part = name_part.strip()
                    role_part = role_part.strip()
                    for kc in key_contacts:
                        if name_part.lower() in kc["name"].lower():
                            kc["role_in_deal"] = role_part

    if not conversation_history:
        conversation_history = llm_response[:2500]

    # 5. Format and send
    deal_summary = {
        "stage": props.get("dealstage", "Unknown").replace("_", " ").title(),
        "amount": float(props.get("amount", 0) or 0),
        "close_date": props.get("closedate", "N/A")[:10],
        "owner": props.get("hubspot_owner_id", "N/A"),
        "created": props.get("createdate", "N/A")[:10],
    }

    from formatters import format_handoff_response
    blocks, fallback = format_handoff_response(
        deal_name=deal_name,
        company_name=company_name,
        deal_summary=deal_summary,
        key_contacts=key_contacts,
        conversation_history=conversation_history,
        risk_factors=risk_factors,
        next_steps=next_steps,
        competitor_mentions=competitor_mentions,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add Action Handlers

```python
@app.action("view_deal_from_handoff")
def handle_view_deal_from_handoff(ack, body, client):
    """View the deal card from a handoff brief."""
    ack()
    deal_name = body["actions"][0]["value"]
    user_id = body["user"]["id"]
    client.chat_postMessage(
        channel=user_id,
        text=f"Use `/deal {deal_name}` to view the full deal card.",
    )


@app.action("draft_handoff_email")
def handle_draft_handoff_email(ack, body, say):
    """Draft an introduction email for the new rep taking over."""
    ack()
    value = body["actions"][0]["value"]
    deal_name, company_name = value.split("||", 1) if "||" in value else (value, "")
    channel = body["channel"]["id"]
    user_id = body["user"]["id"]

    say(f"✉️ Drafting handoff introduction email...", channel=channel)

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""Draft a professional introduction email from a new sales rep taking over the deal "{deal_name}" at {company_name}.

The email should:
- Introduce themselves as the new point of contact
- Acknowledge the existing relationship
- Reference where the deal stands
- Propose a brief sync call to get aligned
- Be warm but professional

Keep it under 150 words. No subject line needed — just the body.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel,
        "thread_ts": None,
    })

    say(text=result["messages"][-1].content, channel=channel)
```

---

## REGISTER IN SLACK

Add `/handoff` slash command in api.slack.com:
- **Command:** `/handoff`
- **Description:** `Generate a deal handoff brief for rep transitions`
- **Usage Hint:** `[company or deal name]`

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/handoff.py` | New formatter for handoff brief Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_handoff_response` export |
| EDIT | `app.py` | Add `handle_handoff()`, `handle_view_deal_from_handoff()`, `handle_draft_handoff_email()` |
