# FIX: Add Deal Picker Before Email Drafting

## Bug Description
When a user runs `/draft-email NovaTech`, the bot shows a contact picker but no deal picker.
NovaTech has 5 active deals. The LLM picks whichever deal it finds in the CRM context or
email thread, leading to emails that reference the wrong deal. The user should be able to
choose which deal the email is about.

## Current Flow
```
/draft-email NovaTech
    → get contacts for NovaTech (multiple found)
    → show contact picker
    → user selects contact
    → LLM drafts email (picks deal randomly from CRM context)
```

## New Flow
```
/draft-email NovaTech
    → get deals for NovaTech (multiple found)
    → show deal picker
    → user selects deal
    → get contacts for that deal/company (multiple found)
    → show contact picker (with deal context stored)
    → user selects contact
    → LLM drafts email with BOTH deal + contact specified
```

If only 1 deal exists, skip the deal picker. If only 1 contact exists, skip the contact picker.

## What to Build

### Step 1: Create Deal Picker Formatter

In `formatters/email.py`, add a `format_deal_picker` function:

```python
def format_deal_picker(company_name: str, deals: list, email_context: dict = None) -> tuple:
    """Format a deal picker for email drafting.

    Args:
        company_name: Company name
        deals: List of deal dicts with name, stage, value, id
        email_context: Context to pass through to the next step

    Returns:
        (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Which deal is this email about?*\n_{company_name}_ has {len(deals)} active deals:"
            }
        },
        {"type": "divider"},
    ]

    for deal in deals[:10]:  # Cap at 10
        deal_name = deal.get("name", "Unknown Deal")
        stage = deal.get("stage", "unknown")
        value = deal.get("value", 0)
        deal_id = deal.get("id", "")

        # Format value
        if isinstance(value, (int, float)) and value > 0:
            value_str = f"${value:,.0f}"
        else:
            value_str = "N/A"

        action_value = json.dumps({
            "deal_name": deal_name,
            "deal_id": deal_id,
            "company_name": company_name,
            "stage": stage,
            "value": value_str,
            **(email_context or {}),
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{deal_name}*\nStage: {stage} | Value: {value_str}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Select Deal"},
                "action_id": f"select_email_deal",
                "value": action_value,
            }
        })

    fallback = f"Select a deal for {company_name} email"
    return blocks, fallback
```

Also add it to `formatters/__init__.py`:
```python
from .email import format_deal_picker
```

### Step 2: Update `/draft-email` Handler in `app.py`

Replace the current handler (lines 643-719) with a deal-first flow:

```python
@app.command("/draft-email")
def handle_draft_email(ack, say, command):
    """Draft a follow-up email for a company/deal."""
    ack()
    company = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not company:
        say("Please provide a company name: `/draft-email [company_name]`")
        return

    # Step 1: Check how many deals this company has
    matching_deals = extract_all_matching_deals(company)

    if len(matching_deals) == 0:
        # No deals — fall through to contact-only flow
        contacts = get_contacts_for_deal_or_company(deal_name=company, company_name=company)
        if len(contacts) == 0:
            say(text=f"⚠️ No deals or contacts found for *{company}*.", channel=channel_id)
            return
        elif len(contacts) > 1:
            from formatters import format_contact_picker
            blocks, fallback = format_contact_picker(
                company_name=company,
                contacts=contacts,
                email_context={"company_name": company, "deal_name": "", "trigger": "draft_email"},
            )
            say(text=fallback, blocks=blocks, channel=channel_id)
            return
        else:
            # Single contact, no deals — draft directly
            primary_contact = contacts[0]
            _draft_email_direct(say, app_graph, company, "", primary_contact, user_id, channel_id)
            return

    elif len(matching_deals) == 1:
        # Single deal — skip deal picker, go to contact picker
        deal = matching_deals[0]
        deal_name = deal.get("name", company)
        contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company)

        if len(contacts) == 0:
            say(text=f"⚠️ No contacts found for *{company}*.", channel=channel_id)
            return
        elif len(contacts) > 1:
            from formatters import format_contact_picker
            blocks, fallback = format_contact_picker(
                company_name=company,
                contacts=contacts,
                email_context={
                    "company_name": company,
                    "deal_name": deal_name,
                    "deal_id": deal.get("id", ""),
                    "trigger": "draft_email",
                },
            )
            say(text=fallback, blocks=blocks, channel=channel_id)
            return
        else:
            primary_contact = contacts[0]
            _draft_email_direct(say, app_graph, company, deal_name, primary_contact, user_id, channel_id)
            return

    else:
        # Multiple deals — show deal picker
        from formatters import format_deal_picker
        blocks, fallback = format_deal_picker(
            company_name=company,
            deals=matching_deals,
            email_context={"trigger": "draft_email"},
        )
        say(text=fallback, blocks=blocks, channel=channel_id)
        return
```

### Step 3: Add Helper Function `_draft_email_direct`

Add this helper near the `/draft-email` handler to avoid code duplication:

```python
def _draft_email_direct(say, graph, company_name, deal_name, contact, user_id, channel_id):
    """Draft an email directly (no pickers needed)."""
    contact_name = contact.get("name", "Contact")
    contact_email = contact.get("email", "")

    say(f"Drafting follow-up email for *{company_name}*...", channel=channel_id)

    context_text = deal_name if deal_name else company_name
    result = graph.invoke({
        "messages": [HumanMessage(content=f"/draft-email {context_text}")],
        "route": "assistant",
        "workflow": "email",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": contact_email,
    })

    llm_response = result["messages"][-1].content

    subject = f"Following up - {company_name}"
    body = llm_response
    if "Subject:" in llm_response:
        parts = llm_response.split("Subject:")
        if len(parts) > 1:
            subject_line = parts[1].split("\n")[0].strip()
            subject = subject_line
            body = "\n".join(parts[1].split("\n")[1:]).strip()

    body = body.replace("*", "").strip()
    if len(body) > 2000:
        body = body[:2000]

    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=contact_name,
        to_email=contact_email,
        subject=subject,
        body=body,
    )
    say(text=fallback, blocks=blocks, channel=channel_id)
```

### Step 4: Add Deal Selection Action Handler

```python
@app.action("select_email_deal")
def handle_select_email_deal(ack, body, client):
    """User selected a deal — now show contact picker for that deal."""
    ack()

    action_data = json.loads(body["actions"][0]["value"])
    deal_name = action_data.get("deal_name", "")
    deal_id = action_data.get("deal_id", "")
    company_name = action_data.get("company_name", "")
    stage = action_data.get("stage", "")
    value = action_data.get("value", "")

    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    message_ts = body["message"]["ts"]

    # Get contacts for this deal/company
    contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company_name)

    if len(contacts) == 0:
        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"⚠️ No contacts found for {deal_name}.",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"⚠️ No contacts found for *{deal_name}*."}}],
        )
        return

    elif len(contacts) == 1:
        # Single contact — draft directly
        contact = contacts[0]
        contact_name = contact.get("name", "Contact")
        contact_email = contact.get("email", "")

        client.chat_update(
            channel=channel,
            ts=message_ts,
            text=f"✉️ Drafting email to {contact_name} about {deal_name}...",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"✉️ Drafting email to *{contact_name}* about *{deal_name}*..."}}],
        )

        context_text = deal_name if deal_name else company_name
        result = app_graph.invoke({
            "messages": [HumanMessage(content=f"/draft-email {context_text}")],
            "route": "assistant",
            "workflow": "email",
            "user_id": user_id,
            "channel_id": channel,
            "thread_ts": None,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": contact_email,
        })

        llm_response = result["messages"][-1].content
        subject = f"Following up - {company_name}"
        body_text = llm_response
        if "Subject:" in llm_response:
            lines = llm_response.split("\n")
            for i, line in enumerate(lines):
                if "Subject:" in line:
                    subject = line.split("Subject:")[-1].strip().strip("*")
                    body_text = "\n".join(lines[i+1:]).strip()
                    break

        if len(body_text) > 2000:
            body_text = body_text[:2000]

        from formatters import format_email_draft
        blocks, fallback = format_email_draft(
            company_name=company_name,
            to_name=contact_name,
            to_email=contact_email,
            subject=subject,
            body=body_text,
        )
        client.chat_update(channel=channel, ts=message_ts, text=fallback, blocks=blocks)

    else:
        # Multiple contacts — show contact picker with deal context
        from formatters import format_contact_picker
        blocks, fallback = format_contact_picker(
            company_name=company_name,
            contacts=contacts,
            email_context={
                "company_name": company_name,
                "deal_name": deal_name,
                "deal_id": deal_id,
                "trigger": "draft_email",
            },
        )
        client.chat_update(channel=channel, ts=message_ts, text=fallback, blocks=blocks)
```

### Step 5: Update `handle_select_email_contact` to Pass Deal Context

In the existing `handle_select_email_contact` (line 1530), the `deal_name` is already
extracted from `action_data` (line 1539). Make sure it's passed to the LLM:

```python
# Line 1557-1559, update to include deal context in the message:
context_text = deal_name if deal_name else company_name
result = app_graph.invoke({
    "messages": [HumanMessage(content=f"/draft-email {context_text}")],
    "route": "assistant",
    "workflow": "email",
    "user_id": user_id,
    "channel_id": channel,
    "thread_ts": None,
    "company_name": company_name,
    "contact_name": contact_name,
    "contact_email": contact_email,
})
```

This part should already work if Fix A (CLAUDE-CODE-MESSAGE-fix-email-wrong-name.md) is applied first.

## Testing

1. `/draft-email NovaTech` → should show deal picker with 5 deals
2. Select "NovaTech Solutions — Annual Platform License" → should show contact picker
3. Select a contact → email should reference the Annual Platform License deal, NOT the Enterprise Expansion
4. `/draft-email Apex` → if only 1 deal, should skip deal picker and go to contact picker
5. Verify the email body references the selected deal's stage and context

## Build Order
- Apply CLAUDE-CODE-MESSAGE-fix-email-wrong-name.md FIRST (adds contact_name/contact_email to state)
- Then apply this file (adds deal picker on top)

## DO NOT
- Do not remove the existing contact picker — it still works, just add the deal picker before it
- Do not break the `/email-sequence` command — it has its own contact picker flow
- Do not change the `select_email_contact` action_id — other handlers may depend on it
