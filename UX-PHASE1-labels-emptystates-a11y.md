# UX Phase 1.3 — Button Labels, Actionable Empty States, Screen Reader Accessibility

This instruction covers three quick-win improvements that span all formatters.

---

## Part A: Fix Vague Button Labels

Slack's official guidelines say:
- "Button labels should be clear and specific"
- "Make buttons active-voice and reflect the user's outcome"
- "Avoid vague, non-actionable text like 'Click here' or 'Settings'"
- "Don't replace words with emoji" (emoji decoration is fine, but emoji should not BE the label)

### Changes Required

Search all formatter files in `formatters/` for button `text` fields and update these vague labels:

| File | Current Label | New Label |
|------|--------------|-----------|
| `formatters/objection.py` | "More Detail" | "Get Full Objection Guide" |
| `formatters/deal.py` (format_deal_picker) | "View Details" | "Open Deal" |
| `formatters/alerts.py` | "Take Action" (if present) | "Update This Deal" |
| `formatters/win_loss.py` | "Full Analysis" (if present) | "See Win/Loss Breakdown" |
| `formatters/battlecard.py` | "Full Analysis" (if present) | "See Full Battlecard" |
| `formatters/forecast.py` | "At-Risk Deals" (if present) | "View At-Risk Deals" |

### Labels to KEEP (already good)
- "Draft Follow-Up Email" — active-voice, specific
- "Start Roleplay" — clear action
- "Practice Again" — clear action
- "Try Suggested Scenario" — clear action
- "Draft Email" — clear action
- "Full Research" — borderline but acceptable (refers to a specific flow)
- "Log Note" — clear action
- "Drill into Flagged Deal" — specific and active
- "Refresh Pipeline" — clear action
- "← Back to Results" — clear navigation

### How to Find All Button Labels
```bash
grep -n '"plain_text"' formatters/*.py | grep -i "text.*:"
```

Or search for all `"text": {"type": "plain_text", "text":` patterns across all formatter files.

---

## Part B: Actionable Empty States

When data is missing, we currently show passive italic text like "_No contacts found_". Users don't know what to do. Replace with helpful guidance.

### Changes Required in `formatters/research.py`

Line ~25 (contacts_str fallback):
```python
# BEFORE:
contacts_str = "_No contacts found_"

# AFTER:
contacts_str = "_No contacts in CRM yet — try `/research` to find contacts online_"
```

Line ~34 (deals_str fallback):
```python
# BEFORE:
deals_str = "_No active deals_"

# AFTER:
deals_str = "_No active deals — use `/draft-email` to start outreach_"
```

Line ~40 (news_str fallback):
```python
# BEFORE:
news_str = "_No recent news found_"

# AFTER:
news_str = "_No recent news available for this company_"
```

### Changes Required in `formatters/deal.py`

For the deal response (format_deal_response), find the empty state fallbacks:
```python
# Activities fallback — BEFORE:
"_No recent activity_"
# AFTER:
"_No activity in 14+ days — consider `/draft-email` to re-engage_"

# Contact fallback — BEFORE:
"_No contact associated_"
# AFTER:
"_No contact linked in CRM — check HubSpot to associate a contact_"
```

### Changes Required in `formatters/pipeline.py`

```python
# Deals fallback — BEFORE:
"_No deals in pipeline_"
# AFTER:
"_No deals in pipeline — use `/research` to identify prospects_"

# Flagged deals — KEEP AS-IS (already good):
"_No flagged deals — looking good!_"
```

### Changes Required in `formatters/followup.py`

```python
# No followups — BEFORE:
"_No follow-ups needed_"  # (or similar)
# AFTER:
"_All caught up! No overdue follow-ups right now._"
```

### Changes Required in `formatters/alerts.py`

The alerts formatter already has a good empty state ("✅ All clear!") — keep it.

### Pattern for All Formatters
When writing empty states, follow this formula:
`[What's missing] — [suggested next action with slash command]`

Examples:
- "_No competitors identified — try `/competitor [name]` to add one_"
- "_No coaching sessions yet — run `/coach roleplay` to start practicing_"
- "_No email threads found — use `/draft-email` to start a conversation_"

---

## Part C: Screen Reader Accessibility

Slack's docs state: "screen readers will default to the top-level `text` field of the post, and will not read the content of any interior `blocks`."

This means our `fallback` text parameter is the ENTIRE experience for screen reader users. Currently it's minimal.

### The Problem

Every formatter returns `(blocks, fallback)` where fallback is something like:
```python
fallback = f"Research Brief: {company_name} - {len(contacts)} contacts, {len(deals)} deals"
```
Screen reader users get: "Research Brief: NovaTech - 3 contacts, 5 deals" and nothing else.

### The Fix

Update the `fallback` variable in every formatter to include a plain-text version of the key information. The `text` parameter in `say()` / `chat_update()` supports mrkdwn but screen readers read it as plain text. Keep it under 3000 characters.

#### `formatters/research.py` — format_research_response

```python
# BEFORE:
fallback = f"Research Brief: {company_name} - {len(contacts)} contacts, {len(deals)} deals"

# AFTER:
contact_names = ", ".join([c.get("name", "Unknown") for c in contacts[:3]])
deal_names = ", ".join([f"{d.get('name', 'Unknown')} ({d.get('stage', 'N/A')})" for d in deals[:3]])
fallback = (
    f"Research Brief: {company_name}. "
    f"Industry: {company_data.get('industry', 'N/A')}. "
    f"Size: {company_data.get('size', 'N/A')} employees. "
    f"Revenue: {company_data.get('revenue', 'N/A')}. "
    f"Key contacts: {contact_names or 'none found'}. "
    f"Active deals: {deal_names or 'none'}. "
    f"Talking points: {talking_points[:500]}"
)
```

#### `formatters/deal.py` — format_deal_response

```python
# BEFORE:
fallback = f"Deal: {deal_name}"  # (or similar)

# AFTER:
fallback = (
    f"Deal: {deal_name}. "
    f"Stage: {stage}. Amount: {amount}. Close date: {close_date}. "
    f"Primary contact: {primary_contact}. "
    f"Recent activity: {activities_summary}. "
    f"Recommendations: {recommendations[:300]}"
)
```

#### `formatters/pipeline.py` — format_pipeline_response

```python
# AFTER:
fallback = (
    f"Pipeline Health: {total_deals} deals worth {total_value}. "
    f"Weighted forecast: {forecast}. "
    f"Flagged deals: {len(flagged_deals)}. "
    f"Stage breakdown: {stage_summary}"
)
```

#### Pattern for ALL Formatters

Every `format_*` function that returns `(blocks, fallback)` should have a rich fallback:
```python
fallback = (
    f"{CARD_TITLE}. "
    f"{KEY_METRIC_1}. {KEY_METRIC_2}. "
    f"{MOST_IMPORTANT_CONTENT[:500]}"
)
```

Keep fallbacks under 3000 characters. Include the most actionable information first.

### Which formatters to update (all 22):
1. research.py — format_research_response
2. deal.py — format_deal_response, format_deal_picker
3. pipeline.py — format_pipeline_response
4. coach.py — format_roleplay_start, format_roleplay_debrief
5. objection.py — format_objection_response
6. ask.py — format_ask_response
7. followup.py — format_followup_response
8. competitor.py — format_competitor_response
9. battlecard.py — format_battlecard_response, format_battlecard_picker
10. alerts.py — format_alerts_digest
11. forecast.py — format_forecast_response
12. persona.py — format_persona_response
13. email.py — format_email_draft, format_contact_picker, format_email_deal_picker
14. email_sequence.py — format_email_sequence_response
15. win_loss.py — format_win_loss_response
16. handoff.py — format_handoff_response
17. coach_live.py — format_coach_live_start, format_coach_live_tip, format_coach_live_summary
18. home_tab.py — format_home_tab (Home tab uses views.publish, not messages — accessibility handled differently)
19. demo_flow.py — format_demo_welcome, format_demo_step_intro, etc.

## DO NOT
- Do not change button action_ids — only change the display text
- Do not add emoji as button label prefixes (Slack says don't replace words with emoji)
- Do not make fallback text longer than 3000 characters
- Do not remove the Block Kit blocks — only improve the `text` fallback alongside them
- Do not change the Home tab formatter's accessibility approach — it uses views.publish, not chat messages

## Testing
1. Use Slack's accessibility inspector or a screen reader to verify the `text` field is read
2. Check that all buttons have clear, active-voice labels
3. Check that empty states show helpful guidance (not just "No data found")
4. Run each command with missing data to verify empty states render correctly
