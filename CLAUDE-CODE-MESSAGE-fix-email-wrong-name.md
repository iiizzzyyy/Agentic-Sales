# FIX: Email Drafts Wrong Contact Name ("Hi Marcus" Bug)

## Bug Description
When a user selects a contact from the contact picker (e.g., Wei Ahmed), the email header
correctly shows "To: Wei Ahmed" but the email BODY says "Hi Marcus" (or some other name
from the email thread history). The LLM never receives the selected contact's name.

## Root Cause
In `app.py` `handle_select_email_contact()` (line 1530), the handler extracts `contact_name`
and `contact_email` from the button action data, BUT:

1. The `app_graph.invoke()` call at line 1558 sends: `/draft-email {context_text}` — NO contact info
2. In `graphs/assistant.py` `email_node()` (line 231), the LLM prompt says "Draft a follow-up email for {company_name}" — NO contact info
3. The email_node loads `mock_crm.load_email_thread(company_name)` which returns the NovaTech email thread
4. That thread's last message is between Jordan and Marcus Williams
5. The LLM sees "Marcus" in the thread and writes "Hi Marcus" instead of "Hi Wei"

The contact_name is used ONLY for the Block Kit header (line 1586-1589) but NEVER passed to the LLM.

## Fix — Two Parts

### Part 1: Pass Contact Info Through the Graph State

In `graphs/router.py`, add two new fields to `AgentState`:

```python
class AgentState(MessagesState):
    """Shared state across the graph."""
    route: Literal["coach", "assistant", "direct"] | None
    workflow: str | None
    user_id: str
    channel_id: str
    thread_ts: str | None
    hubspot_context: dict | None
    rag_context: str | None
    web_context: str | None
    company_name: str | None
    contact_name: str | None    # ADD THIS — selected contact name
    contact_email: str | None   # ADD THIS — selected contact email
```

### Part 2: Update `handle_select_email_contact()` in `app.py`

At line 1558, pass the contact info to the graph:

```python
# BEFORE (line 1556-1566):
# Run the LLM to generate the email
context_text = deal_name if deal_name else company_name
result = app_graph.invoke({
    "messages": [HumanMessage(content=f"/draft-email {context_text}")],
    "route": "assistant",
    "workflow": "email",
    "user_id": user_id,
    "channel_id": channel,
    "thread_ts": None,
    "company_name": company_name,
})

# AFTER:
context_text = deal_name if deal_name else company_name
result = app_graph.invoke({
    "messages": [HumanMessage(content=f"/draft-email {context_text} TO {contact_name} ({contact_email})")],
    "route": "assistant",
    "workflow": "email",
    "user_id": user_id,
    "channel_id": channel,
    "thread_ts": None,
    "company_name": company_name,
    "contact_name": contact_name,      # ADD THIS
    "contact_email": contact_email,    # ADD THIS
})
```

### Part 3: Update `email_node()` in `graphs/assistant.py`

At line 231, update the email_node to use the contact info in the prompt:

```python
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

    if use_mock:
        crm_context = _get_mock_company_context(company_name)
        email_thread = mock_crm.load_email_thread(company_name)
        thread_context = ""
        if email_thread:
            thread_context = f"\nEXISTING EMAIL THREAD:\nSubject: {email_thread.get('subject', 'N/A')}\n"
            for msg in email_thread.get("messages", [])[-3:]:
                thread_context += f"\nFrom: {msg.get('from', 'Unknown')}\nDate: {msg.get('date', 'N/A')}\n{msg.get('body', '')[:300]}...\n"

        # Build contact instruction
        contact_instruction = ""
        if contact_name and contact_email:
            first_name = contact_name.split()[0]
            contact_instruction = f"""
CRITICAL — RECIPIENT:
You are writing this email TO: {contact_name} ({contact_email})
- Address the email to "{first_name}" — use "Hi {first_name}," as the greeting
- Do NOT use any other name in the greeting
- The email thread history is for CONTEXT ONLY — you are writing a NEW email to {contact_name}
"""

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

IMPORTANT: If there's an existing email thread, use it for CONTEXT about the deal status,
but write the email TO the specified recipient above.
If the deal is lost, write a win-back email. If in negotiation, acknowledge current status.

Format your response as:

*Draft Follow-Up Email*

*To:* {contact_name} ({contact_email})
*Subject:* [compelling subject line]

[email body - under 150 words, personalized, clear call-to-action]

---
_Edit as needed before sending._"""
    else:
        # Similar update for non-mock path
        contact_instruction = ""
        if contact_name and contact_email:
            first_name = contact_name.split()[0]
            contact_instruction = f"""
CRITICAL — RECIPIENT:
You are writing this email TO: {contact_name} ({contact_email})
- Address the email to "{first_name}" — use "Hi {first_name}," as the greeting
- Do NOT use any other name in the greeting
"""

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

*To:* [contact name and email]
*Subject:* [compelling subject line]

[email body - under 150 words, personalized, clear call-to-action]

---
_Edit as needed before sending._"""

    response = llm_with_tools.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Draft a follow-up email for {company_name}" + (f" to {contact_name}" if contact_name else ""))
    ])

    return {
        "messages": messages + [response],
        "rag_context": rag_context,
    }
```

### Part 4: Also Fix the Single-Contact Path

In `app.py` at line 677 (the single-contact path), also pass the contact info:

```python
# Exactly 1 contact — draft email directly
primary_contact = contacts[0]
say(f"Drafting follow-up email for *{company}*...", channel=channel_id)

result = app_graph.invoke({
    "messages": [HumanMessage(content=f"/draft-email {company}")],
    "route": "assistant",
    "workflow": "email",
    "user_id": user_id,
    "channel_id": channel_id,
    "thread_ts": None,
    "company_name": company,
    "contact_name": primary_contact.get("name", "Contact"),      # ADD
    "contact_email": primary_contact.get("email", ""),            # ADD
})
```

## Testing
1. `/draft-email NovaTech` → select Wei Ahmed → email should say "Hi Wei," NOT "Hi Marcus"
2. `/draft-email NovaTech` → select Rachel Dubois → email should say "Hi Rachel,"
3. `/draft-email Apex` → if single contact, email should use that contact's first name
4. Verify the email still references deal context from the thread (just with the correct greeting)

## DO NOT
- Do not remove the email thread loading — it provides valuable context for the email body
- Do not change the Block Kit formatting in format_email_draft
- Do not change the contact picker action_id or value format
