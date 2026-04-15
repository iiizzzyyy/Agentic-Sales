# Claude Code Instructions: `/ask` — Natural Language CRM Query

> **Read `CLAUDE-CODE-BRIEFING.md`, `app.py`, `graphs/router.py`, `tools/rag.py`, and `tools/mock_crm.py` first.**

---

## CONTEXT — WHAT AND WHY

Instead of memorizing specific commands, reps can just ask questions in plain English. `/ask` is the "catch-all" command — it takes any natural language query and routes it to the right data sources.

Examples:
- `/ask What deals are closing this month?`
- `/ask Who's our contact at Acme?`
- `/ask Show me stale deals over $100K`
- `/ask What did we discuss with NovaTech last week?`
- `/ask How many deals are in negotiation?`

This is the "wow, it just understands me" moment in the demo. It shows the AI is truly intelligent, not just a menu of slash commands.

---

## WHAT IT DOES

1. User types `/ask [any question about their CRM/pipeline/deals]`
2. Bot classifies the question type:
   - **Deal query** → search deals in RAG/mock
   - **Contact query** → search contacts
   - **Pipeline query** → aggregate deal data
   - **Activity query** → search notes/transcripts
   - **General** → use RAG + LLM to answer
3. LLM generates a natural language answer using the retrieved data
4. Bot posts the answer with relevant Block Kit formatting + action buttons

---

## STEP 1: Create `formatters/ask.py`

```python
"""Block Kit formatting for /ask command."""
import json
from formatters.helpers import timestamp, truncate


def format_ask_response(
    question: str,
    answer: str,
    data_sources: list,
    related_actions: list,
) -> tuple[list, str]:
    """Format a natural language CRM answer as Block Kit.

    Args:
        question: The original question
        answer: LLM-generated answer
        data_sources: List of source descriptions (e.g., "HubSpot CRM", "Sales Playbooks")
        related_actions: List of dicts with 'label', 'action_id', 'value'

    Returns:
        tuple: (blocks, fallback_text)
    """
    # Data sources tag
    sources_str = " • ".join(data_sources) if data_sources else "AI Knowledge"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🧠 Answer", "emoji": True}
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"_You asked: {truncate(question, 100)}_"}
            ]
        },

        {"type": "divider"},

        # The answer
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": answer}
        },
    ]

    # Add action buttons if any related actions are suggested
    if related_actions:
        action_elements = []
        for action in related_actions[:4]:  # Max 4 buttons
            action_elements.append({
                "type": "button",
                "text": {"type": "plain_text", "text": action.get("label", "View"), "emoji": True},
                "action_id": action.get("action_id", "noop"),
                "value": action.get("value", ""),
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": action_elements,
        })

    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Sources: {sources_str} • {timestamp()}"}
        ]
    })

    fallback = f"Answer: {truncate(answer, 200)}"
    return blocks, fallback
```

---

## STEP 2: Update `formatters/__init__.py`

Add:
```python
from formatters.ask import format_ask_response
```

And add `"format_ask_response"` to `__all__`.

---

## STEP 3: Add `/ask` Command Handler to `app.py`

```python
@app.command("/ask")
def handle_ask(ack, say, command):
    """Answer any natural language question about CRM/pipeline/deals."""
    ack()
    question = command["text"].strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not question:
        say(
            "Ask me anything about your CRM:\n"
            "• `/ask What deals are closing this month?`\n"
            "• `/ask Who's our contact at NovaTech?`\n"
            "• `/ask Show me stale deals over $50K`\n"
            "• `/ask What happened in our last call with Apex?`",
            channel=channel_id,
        )
        return

    say(f"🧠 Thinking...", channel=channel_id)

    # 1. Classify the question to determine data sources
    question_lower = question.lower()
    data_sources = []
    context_parts = []
    related_actions = []

    # Determine what data to pull based on the question
    from tools.rag import search_crm, search_crm_deals, search_crm_contacts, search_crm_companies, search_playbooks

    # Always search CRM broadly
    crm_results = search_crm(question, n_results=8)
    if crm_results and crm_results.strip() != "No results found.":
        context_parts.append(f"CRM DATA:\n{crm_results}")
        data_sources.append("HubSpot CRM")

    # If question mentions contacts or people
    if any(w in question_lower for w in ["contact", "who", "person", "email", "phone", "name"]):
        # Extract potential company name from question
        contact_results = search_crm_contacts(question, n_results=5)
        if contact_results and contact_results.strip() != "No results found.":
            context_parts.append(f"CONTACTS:\n{contact_results}")

    # If question is about deals, pipeline, revenue, stage
    if any(w in question_lower for w in ["deal", "pipeline", "revenue", "stage", "closing", "stale", "overdue", "amount", "forecast"]):
        deal_results = search_crm_deals(question, n_results=8)
        if deal_results and deal_results.strip() != "No results found.":
            context_parts.append(f"DEALS:\n{deal_results}")

        # Also pull mock CRM aggregates for pipeline questions
        all_deals = mock_crm.get_all_open_deals()
        stale = mock_crm.get_stale_deals(days=14)
        overdue = mock_crm.get_overdue_deals()

        pipeline_summary = f"Total open deals: {len(all_deals)}\n"
        pipeline_summary += f"Stale deals (14+ days): {len(stale)}\n"
        pipeline_summary += f"Overdue deals: {len(overdue)}\n"

        # Stage breakdown
        stage_counts = {}
        total_value = 0
        for d in all_deals:
            props = d.get("properties", {})
            stage = props.get("dealstage", "unknown")
            amount = float(props.get("amount", 0) or 0)
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            total_value += amount

        pipeline_summary += f"Total pipeline value: ${total_value:,.0f}\n"
        for stage, count in stage_counts.items():
            pipeline_summary += f"  {stage}: {count} deals\n"

        context_parts.append(f"PIPELINE SUMMARY:\n{pipeline_summary}")
        data_sources.append("Pipeline Analytics")

        # Add related action
        related_actions.append({
            "label": "View Full Pipeline",
            "action_id": "refresh_pipeline",
            "value": "refresh",
        })

    # If question is about activities, calls, meetings, notes
    if any(w in question_lower for w in ["call", "meeting", "note", "activity", "last", "discuss", "talked"]):
        from tools.rag import search_call_transcripts, search_meeting_notes
        transcript_results = search_call_transcripts(question, n_results=3)
        meeting_results = search_meeting_notes(question, n_results=3)
        if transcript_results and "No results" not in transcript_results:
            context_parts.append(f"CALL TRANSCRIPTS:\n{transcript_results}")
            data_sources.append("Call Transcripts")
        if meeting_results and "No results" not in meeting_results:
            context_parts.append(f"MEETING NOTES:\n{meeting_results}")
            data_sources.append("Meeting Notes")

    # If question is about best practices, methodology, playbook
    if any(w in question_lower for w in ["how to", "best practice", "playbook", "template", "approach", "strategy"]):
        playbook_results = search_playbooks(question, n_results=5)
        if playbook_results:
            context_parts.append(f"SALES PLAYBOOKS:\n{playbook_results}")
            data_sources.append("Sales Playbooks")

    if not data_sources:
        data_sources.append("AI Knowledge")

    # 2. Run LLM to generate answer
    combined_context = "\n\n---\n\n".join(context_parts) if context_parts else "No specific data found."

    result = app_graph.invoke({
        "messages": [HumanMessage(content=f"""A sales rep asked: "{question}"

Here is the data available to answer their question:

{combined_context}

Answer the question directly and concisely. Use specific data from the context above.
If the answer involves specific deals, contacts, or numbers — include them.
If you can't find the answer in the data, say so honestly and suggest what command they could use.

Format your answer using Slack mrkdwn:
- Bold with *text*
- Bullet points with •
- Keep it scannable — reps are busy

Do NOT wrap your response in any code blocks or extra formatting. Just answer naturally.""")],
        "route": "assistant",
        "workflow": "research",
        "user_id": user_id,
        "channel_id": channel_id,
        "thread_ts": None,
    })

    answer = result["messages"][-1].content

    # 3. Add contextual action buttons based on what was found
    # Extract company names mentioned in the answer for action buttons
    for company in ["NovaTech", "Greenfield", "Meridian", "Apex", "CloudBridge",
                     "TerraLogistics", "Pinnacle", "Velocity", "Stratos", "Horizon"]:
        if company.lower() in answer.lower() and len(related_actions) < 3:
            related_actions.append({
                "label": f"Research {company}",
                "action_id": "research_from_deal",
                "value": company,
            })
            break  # Only add one company action

    # 4. Format and send
    from formatters import format_ask_response
    blocks, fallback = format_ask_response(
        question=question,
        answer=answer,
        data_sources=data_sources,
        related_actions=related_actions,
    )

    say(text=fallback, blocks=blocks, channel=channel_id)
```

---

## STEP 4: Add No-Op Handler for Safety

Add a catch-all for action IDs that might not exist yet:

```python
@app.action("noop")
def handle_noop(ack):
    """No-op handler for placeholder buttons."""
    ack()
```

---

## REGISTER IN SLACK

Add `/ask` slash command in api.slack.com:
- **Command:** `/ask`
- **Description:** `Ask anything about your CRM, deals, or pipeline`
- **Usage Hint:** `[your question in plain English]`

---

## HOW IT DECIDES WHAT DATA TO PULL

The handler uses keyword detection (not an LLM classifier) for speed:

| Keywords in Question | Data Sources Searched |
|---------------------|----------------------|
| contact, who, person, email | CRM contacts |
| deal, pipeline, revenue, stage, closing, stale | CRM deals + pipeline aggregates |
| call, meeting, note, discussed, talked | Call transcripts + meeting notes |
| how to, best practice, playbook, template | Sales playbooks |
| (always) | Broad CRM search |

This is intentionally simple. A more sophisticated approach would use the LLM to classify the question first, but that adds latency. Keyword detection is instant and covers 90% of cases.

---

## GOTCHAS

1. **Block Kit text limit** — Slack sections have a 3000 character limit for `mrkdwn` text. If the LLM generates a long answer, truncate it. Add `truncate(answer, 2800)` as a safety measure.

2. **Data might not exist** — If the rep asks about a company not in the CRM, the answer should gracefully say "I don't have data on X. Try `/research X` to look them up."

3. **The company name detection for action buttons** is hardcoded to your synthetic data companies. In production, you'd extract company names dynamically from the LLM response.

4. **This reuses the `research` workflow** in the graph. It's fine for the POC — the research node already handles open-ended questions with context injection. In production, you might want a dedicated `ask` workflow.

---

## FILES CHANGED SUMMARY

| Action | File | What To Change |
|--------|------|----------------|
| CREATE | `formatters/ask.py` | New formatter for Q&A response Block Kit |
| EDIT | `formatters/__init__.py` | Add `format_ask_response` export |
| EDIT | `app.py` | Add `handle_ask()`, `handle_noop()` |
