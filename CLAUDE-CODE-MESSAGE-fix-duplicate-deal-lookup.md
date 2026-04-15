# Claude Code Task: Fix Deal Lookup Returning Wrong Deal When Duplicates Exist

> **Read `tools/mock_crm.py` (the `search_deal` function) and `app.py` (the `handle_view_deal_by_index` or `handle_view_deal_from_handoff` handler).**

---

## THE BUG

Two deals have the exact same name "Greenfield Analytics — New Department Rollout":
- One is stage `demoscheduled`, $120,000 (open)
- One is stage `closedlost`, $36,000 (lost)

When the user clicks "View Deal" on the $36K lost deal, `search_deal("Greenfield Analytics — New Department Rollout")` returns the FIRST match in `deals.json`, which is the $120K open deal. So the wrong deal card is shown.

`search_deal()` in `tools/mock_crm.py` does a fuzzy match and returns the first hit:

```python
def search_deal(name: str) -> dict | None:
    for deal in crm_data["deals"]:
        if name_lower in deal_name.lower():
            return deal  # <-- always returns the FIRST match
```

## THE FIX — Two Changes

### Fix 1: Add `get_deal_by_id()` to `tools/mock_crm.py`

The reliable way to find the right deal is by its unique ID, not by name. Add this function:

```python
def get_deal_by_id(deal_id: str) -> dict | None:
    """Get a deal by its unique ID."""
    crm_data = load_mock_crm()
    for deal in crm_data["deals"]:
        if deal.get("id") == deal_id:
            return deal
    return None
```

This may already exist — check first. If it does, just use it.

### Fix 2: Pass deal ID (not deal name) as the button value

The root cause is that the won/lost deal buttons pass `deal_name` as the button value. When two deals share the same name, there's no way to tell them apart. Pass the unique `deal["id"]` instead.

In `handle_win_loss_lost` and `handle_win_loss_won`, change the button value:

```python
# BEFORE:
for i, d in enumerate(lost):
    p = d.get("properties", {})
    deal_name = p.get("dealname", "Unknown")
    # ...
    "action_id": f"view_deal_{i}",
    "value": deal_name,  # <-- BUG: not unique when names duplicate

# AFTER:
for i, d in enumerate(lost):
    p = d.get("properties", {})
    deal_name = p.get("dealname", "Unknown")
    deal_id = d.get("id", "")
    # ...
    "action_id": f"view_deal_{i}",
    "value": deal_id,  # <-- Use unique deal ID
```

Do the same in `handle_win_loss_won`.

### Fix 3: Update the view deal handler to look up by ID first, fall back to name

Update the `handle_view_deal_by_index` (regex handler for `view_deal_\d+`) and `handle_view_deal_from_handoff`:

```python
@app.action(re.compile(r"view_deal_\d+"))
def handle_view_deal_by_index(ack, body, say):
    ack()
    value = body["actions"][0]["value"]
    channel = body["channel"]["id"]

    # Try to find by ID first (new approach), then fall back to name search (backward compat)
    deal = mock_crm.get_deal_by_id(value)
    if not deal:
        deal = mock_crm.search_deal(value)

    if not deal:
        say(text=f"Could not find deal matching '{value}'.", channel=channel)
        return

    # ... rest of the deal card rendering stays the same
```

Do the same for `handle_view_deal_from_handoff` if it still exists.

### Fix 4: Apply the same pattern everywhere

Search `app.py` for any other place where a deal name is passed as a button `value` for later lookup. These should all be changed to pass `deal["id"]` instead:

```bash
# Search for patterns like:
"value": deal_name
"value": props.get("dealname"
```

Common places this appears:
- `/handoff` action buttons
- `/alerts` action buttons
- `/forecast` action buttons
- Home tab "View Deal" buttons
- Any formatter that creates deal-related action buttons

For each one: pass `d.get("id", deal_name)` as the value, so it falls back to the name if ID isn't available.

---

## TESTING

1. Restart bot
2. Run `/win-loss`
3. Click "View Lost Deals"
4. Find "Greenfield Analytics — New Department Rollout" in the lost deals list (should show $36,000)
5. Click "View Deal" on it → should show stage: Closed Lost, value: $36,000 (NOT $120,000)
6. Click "View Won Deals" and verify those deals also show correct data when clicked

---

## FILES TO CHANGE

| Action | File | What To Change |
|--------|------|----------------|
| EDIT | `tools/mock_crm.py` | Add `get_deal_by_id()` if it doesn't exist |
| EDIT | `app.py` | Update `handle_win_loss_lost` — pass `d.get("id")` as button value |
| EDIT | `app.py` | Update `handle_win_loss_won` — same fix |
| EDIT | `app.py` | Update `handle_view_deal_by_index` — try ID lookup first, then name |
| EDIT | `app.py` | Update `handle_view_deal_from_handoff` — same fix |
| AUDIT | `app.py` | Check all other deal-related buttons for same issue |
