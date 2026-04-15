# Task: Contact Picker for Email Drafts — Fix Wrong Contact + Add Selection UX

> **Read these files FIRST before writing any code:**
> 1. `app.py` — read the ENTIRE file. Pay close attention to: `extract_contacts()` (line ~103), `handle_draft_email()` (line ~546), `handle_draft_email_from_research()` (line ~735), `handle_draft_email_from_deal()` (line ~940), `handle_regenerate_email()` (line ~1044), and `handle_draft_followup_email()` if it exists. These are ALL the places that draft emails and pick contacts.
> 2. `formatters/email.py` — current email draft formatter
> 3. `formatters/deal.py` — reference for `format_deal_picker()` pattern (multi-select with `chat_update`)
> 4. `tools/mock_crm.py` — `get_contacts_for_company()`, `search_company()`
> 5. `data/mock_crm/contacts.json` — understand contact structure and associations
> 6. `data/mock_crm/deals.json` — understand deal-to-contact associations

---

## THE BUG

Currently, when the bot drafts a follow-up email, it calls `extract_contacts(company_name)` which does a RAG semantic search for contacts. This is unreliable:

1. **It can return the WRONG contact** — RAG semantic search is fuzzy. Searching "Horizon Education" might return contacts from other companies with similar text.
2. **It can HALLUCINATE contacts** — when `extract_contacts()` returns nothing, the code falls back to `{"name": "Contact", "email": "contact@example.com"}`, and the LLM sometimes invents a name entirely (e.g., "Emma Ahmed" who doesn't exist in the CRM at all).
3. **It ignores the deal association** — deal `deal_642093` (Horizon Education — Professional Services Add-On) is explicitly associated with `contact_575512` (David Okafor), but the bot never looks at this association. It searches by company name instead.
4. **It always picks `contacts[0]`** — even when multiple contacts exist for a company, the user has no say in who the email goes to.

---

## THE FIX — TWO PARTS

### Part 1: Fix Contact Resolution (use deal associations, not just RAG)

Create a new function `get_contacts_for_deal_or_company()` that properly resolves contacts:

```python
def get_contacts_for_deal_or_company(
    deal_name: str = None,
    company_name: str = None,
) -> list:
    """Get contacts associated with a deal first, then fall back to company contacts.

    Priority order:
    1. Contact directly associated with the deal (from deals.json associations.contact)
    2. All contacts associated with the company (from contacts.json associations.company_id)
    3. RAG search as last resort (existing extract_contacts behavior)

    Returns list of dicts with: name, title, email, source ("deal" or "company")
    """
    contacts = []
    seen_ids = set()

    # 1. Get the deal's directly associated contact
    if deal_name:
        deal = mock_crm.search_deal(deal_name)
        if deal:
            deal_contact_id = deal.get("associations", {}).get("contact", "")
            if deal_contact_id:
                # Look up this contact in contacts.json
                all_contacts_data = mock_crm._load_contacts()  # May need to add this helper
                for c in all_contacts_data:
                    if c["id"] == deal_contact_id:
                        props = c.get("properties", {})
                        contact = {
                            "id": c["id"],
                            "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                            "title": props.get("jobtitle", "N/A"),
                            "email": props.get("email", ""),
                            "source": "deal",
                        }
                        contacts.append(contact)
                        seen_ids.add(c["id"])
                        break

            # Also get the company from the deal for step 2
            if not company_name:
                company_id = deal.get("associations", {}).get("company", "")
                if company_id:
                    company_data = mock_crm.get_company_by_id(company_id)
                    if company_data:
                        company_name = company_data.get("properties", {}).get("name", "")

    # 2. Get all contacts for the company
    if company_name:
        company_data = mock_crm.search_company(company_name)
        if company_data:
            company_id = company_data.get("id", "")
            company_contacts = mock_crm.get_contacts_for_company(company_id)
            for c in company_contacts:
                if c["id"] in seen_ids:
                    continue
                seen_ids.add(c["id"])
                props = c.get("properties", {})
                contacts.append({
                    "id": c["id"],
                    "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
                    "title": props.get("jobtitle", "N/A"),
                    "email": props.get("email", ""),
                    "source": "company",
                })

    # 3. Fall back to RAG search if nothing found
    if not contacts:
        contacts = extract_contacts(company_name or deal_name or "")
        for c in contacts:
            c["source"] = "rag"

    return contacts
```

**IMPORTANT:** Check if `mock_crm` has a function to look up a contact by ID. If `get_contacts_for_company()` already loads all contacts, you can reuse that. If not, you may need to add a `get_contact_by_id(contact_id)` helper to `tools/mock_crm.py`:

```python
def get_contact_by_id(contact_id: str) -> dict | None:
    """Look up a contact by its ID."""
    data = _load_data()
    for contact in data.get("contacts", []):
        if contact["id"] == contact_id:
            return contact
    return None
```

---

### Part 2: Contact Picker UX (when multiple contacts exist)

Add a contact picker formatter similar to the deal picker pattern. When there are 2+ contacts, show a selection list. When there's only 1, skip the picker and go straight to the email draft.

#### Create `format_contact_picker()` in `formatters/email.py`:

```python
def format_contact_picker(
    company_name: str,
    contacts: list,
    email_context: dict,
) -> tuple[list, str]:
    """Format a contact selection list before drafting an email.

    Args:
        company_name: Company name for the header
        contacts: List of dicts with 'name', 'title', 'email', 'source'
        email_context: Dict with context to pass through to the email draft action.
            Must include 'company_name' and optionally 'deal_name', 'trigger'.
            This gets JSON-encoded into the button value.

    Returns:
        tuple: (blocks, fallback_text)
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"✉️ Who should this email go to?", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Drafting follow-up for *{company_name}* — select a recipient."}
            ]
        },
        {"type": "divider"},
    ]

    for contact in contacts[:10]:
        name = contact.get("name", "Unknown")
        title = contact.get("title", "")
        email = contact.get("email", "")
        source = contact.get("source", "")

        # Show where this contact came from
        source_tag = ""
        if source == "deal":
            source_tag = " · 📌 _Deal contact_"
        elif source == "company":
            source_tag = " · 🏢 _Company contact_"

        # Build button value with contact info + email context
        button_value = json.dumps({
            "contact_name": name,
            "contact_email": email,
            "company_name": email_context.get("company_name", company_name),
            "deal_name": email_context.get("deal_name", ""),
            "trigger": email_context.get("trigger", "direct"),
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{name}*\n{title} · {email}{source_tag}"
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Select", "emoji": True},
                "action_id": "select_email_contact",
                "value": button_value,
            }
        })

    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"SalesCoach AI • {timestamp()}"}
        ]
    })

    fallback = f"Select a contact for email draft: {company_name}"
    return blocks, fallback
```

#### Update `formatters/__init__.py`:

Add `format_contact_picker` to the imports from `formatters.email` and to `__all__`.

---

### Part 3: Update ALL Email Drafting Paths in `app.py`

There are **6 places** in `app.py` that draft emails and blindly pick `contacts[0]`. ALL of them need to be updated to use the contact picker when multiple contacts exist.

The pattern for each is the same:

**Before (broken):**
```python
contacts = extract_contacts(company)
primary_contact = contacts[0] if contacts else {"name": "Contact", "email": "contact@example.com"}
# ... draft email using primary_contact
```

**After (fixed):**
```python
contacts = get_contacts_for_deal_or_company(deal_name=deal_name, company_name=company)

if len(contacts) == 0:
    # No contacts found — tell the user
    say(text=f"⚠️ No contacts found for *{company}*. Use `/ask Who is our contact at {company}?` to search.", channel=channel_id)
    return

elif len(contacts) == 1:
    # Exactly 1 contact — draft email directly (no picker needed)
    primary_contact = contacts[0]
    # ... proceed with email drafting as before

else:
    # Multiple contacts — show picker
    from formatters.email import format_contact_picker
    blocks, fallback = format_contact_picker(
        company_name=company,
        contacts=contacts,
        email_context={
            "company_name": company,
            "deal_name": deal_name or "",
            "trigger": "draft_email",  # or "deal", "research", "followup" — identifies which flow triggered this
        },
    )
    say(text=fallback, blocks=blocks, channel=channel_id)
    return  # Stop here — the email will be drafted after user picks a contact
```

#### Update these specific functions:

1. **`handle_draft_email()`** (~line 546) — the `/draft-email [company]` command handler
2. **`handle_draft_email_from_research()`** (~line 735) — "Draft Follow-Up Email" button on research cards
3. **`handle_draft_email_from_deal()`** (~line 940) — "Draft Email" button on deal cards
4. **`handle_regenerate_email()`** (~line 1044) — "Regenerate" button on email drafts (this one can keep the same contact — no picker needed on regenerate)
5. **`handle_draft_followup_email()`** — "Draft Email" button from `/followup` list (if this exists from the expansion build)
6. **Any other `draft_email` action handler** — search for `extract_contacts` and `contacts[0]` to find them all

For functions triggered by action buttons (not slash commands), use `client.chat_update()` to replace the original message with the contact picker, then update again when the user selects a contact — same pattern as the deal picker.

---

### Part 4: Add the Contact Selection Action Handler

```python
@app.action("select_email_contact")
def handle_select_email_contact(ack, body, say, client):
    """User selected a contact for the email draft — now draft the email."""
    ack()

    action_data = json.loads(body["actions"][0]["value"])
    contact_name = action_data.get("contact_name", "Contact")
    contact_email = action_data.get("contact_email", "")
    company_name = action_data.get("company_name", "")
    deal_name = action_data.get("deal_name", "")
    trigger = action_data.get("trigger", "direct")

    channel = body["channel"]["id"]
    user_id = body["user"]["id"]
    message_ts = body["message"]["ts"]

    # Update the picker message to show "Drafting..."
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=f"✉️ Drafting email to {contact_name}...",
        blocks=[{
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"✉️ Drafting email to *{contact_name}* ({contact_email})..."}
        }],
    )

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

    llm_response = result["messages"][-1].content

    # Parse subject and body from LLM response
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

    # Format the email draft with the SELECTED contact
    from formatters import format_email_draft
    blocks, fallback = format_email_draft(
        company_name=company_name,
        to_name=contact_name,
        to_email=contact_email,
        subject=subject,
        body=body_text,
    )

    # Update the picker message with the email draft
    client.chat_update(
        channel=channel,
        ts=message_ts,
        text=fallback,
        blocks=blocks,
    )
```

---

## THE UX FLOW

### Single contact (no change to user experience):
```
/draft-email Horizon Education
→ Bot drafts email to David Okafor (the only contact) — no picker shown
```

### Multiple contacts (new contact picker):
```
/draft-email NovaTech Solutions
→ Bot shows:
┌─────────────────────────────────────────────────┐
│ ✉️ Who should this email go to?                 │
│ Drafting follow-up for NovaTech Solutions        │
│─────────────────────────────────────────────────│
│ *Wei Ahmed*                                      │
│ Head of Operations · wei.ahmed@novatech.io       │
│ · 📌 Deal contact                      [Select] │
│─────────────────────────────────────────────────│
│ *Alex Kowalski*                                  │
│ Head of Operations · alex.kowalski@novatech.io   │
│ · 🏢 Company contact                  [Select] │
│─────────────────────────────────────────────────│
│ *Marcus Patel*                                   │
│ Chief Data Officer · marcus.patel@novatech.io    │
│ · 🏢 Company contact                  [Select] │
│─────────────────────────────────────────────────│
│ SalesCoach AI • Mar 06, 2026                     │
└─────────────────────────────────────────────────┘

→ User clicks "Select" on Wei Ahmed
→ Message updates in place to the email draft addressed to Wei Ahmed
```

### From deal card (deal association used):
```
[User clicks "Draft Email" on a deal card for "NovaTech — Annual Platform License"]
→ Bot finds deal association: contact_907662 (Wei Ahmed) — marked as "📌 Deal contact"
→ Also finds company contacts: Alex Kowalski, Marcus Patel — marked as "🏢 Company contact"
→ Shows picker with Wei Ahmed first (deal contact), others below
→ User selects → email drafts
```

---

## GOTCHAS

1. **The deal-associated contact should appear FIRST** in the picker list with a "📌 Deal contact" tag. Company contacts appear below. This makes the default choice obvious.

2. **Button value size limit** — Slack limits button values to 2000 characters. The `json.dumps()` in `select_email_contact` must stay small. Only include: `contact_name`, `contact_email`, `company_name`, `deal_name`, `trigger`. Do NOT put the full email body in the button value.

3. **`chat_update` vs `say`** — When the contact picker is triggered by a button action (not a slash command), use `client.chat_update()` to replace the original message. When triggered by a slash command (`/draft-email`), use `say()` for the picker, then `client.chat_update()` won't work because you don't have the picker message's `ts` — so the email draft will be a new message (that's fine).

4. **The `trigger` field** in `email_context` helps the `select_email_contact` handler know which flow triggered the picker, so it can adapt its behavior if needed (e.g., different LLM prompts for deal emails vs general emails).

5. **`handle_regenerate_email()`** does NOT need the contact picker — it's regenerating an email that already has a contact. Keep the existing behavior there.

6. **"Emma Ahmed" hallucination** — The root cause was that `extract_contacts()` returned nothing for Horizon Education (RAG search missed), so `contacts[0]` hit the fallback `{"name": "Contact", "email": "contact@example.com"}`, and the LLM was given this placeholder in the prompt context. The LLM then invented "Emma Ahmed" as a realistic-sounding name. With `get_contacts_for_deal_or_company()`, this can't happen — it reads directly from the JSON data via mock_crm functions, not via fuzzy RAG search.

7. **Check `mock_crm.py` for needed helpers** — You may need to add `get_contact_by_id()` if it doesn't exist. Also check if `search_deal()` returns the full deal object with `associations` — if not, you'll need to enhance it.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `tools/mock_crm.py` | Add `get_contact_by_id()` helper if it doesn't exist |
| EDIT | `formatters/email.py` | Add `format_contact_picker()` function |
| EDIT | `formatters/__init__.py` | Add `format_contact_picker` to imports and `__all__` |
| EDIT | `app.py` | Add `get_contacts_for_deal_or_company()`. Update ALL 6 email drafting paths to use it + show picker when 2+ contacts. Add `handle_select_email_contact()` action handler. |

---

## SEARCH FOR ALL AFFECTED CODE

Run these searches to find every place that needs updating:

```
# Find all places that pick contacts[0] blindly
grep -n "contacts\[0\]" app.py

# Find all places that call extract_contacts
grep -n "extract_contacts" app.py

# Find all email draft formatting calls
grep -n "format_email_draft" app.py

# Find all action handlers that draft emails
grep -n "draft_email" app.py
```

Every match needs to be reviewed and updated with the new pattern.
