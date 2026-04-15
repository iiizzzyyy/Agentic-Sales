# Fix Prep Button Format Error — Claude Code Instructions

## Problem

After clicking **Prep** on a customer meeting in `/my-day`, the user sees:

> Something went wrong. Error: Unknown format code 'f' for object of type 'str'

## Root Cause

**File:** `formatters/calendar.py`, line 217
**Function:** `format_meeting_prep`

The line:

```python
"text": f"*Deal:* {deal_info.get('name', 'Unknown')}\n*Stage:* {deal_info.get('stage', 'Unknown')}\n*Value:* ${deal_info.get('amount', 0):,.0f}"
```

uses `:,.0f` (a float format spec) on the `amount` value. But `amount` comes from `data/mock_crm/deals.json` where it is stored as a **string** (e.g., `"48000"`), not a number. Python's f-string format spec `:,.0f` requires a float or int, so it throws `ValueError: Unknown format code 'f' for object of type 'str'`.

---

## Fix (Two Locations)

### Fix 1: `formatters/calendar.py` — Defensive formatting (primary fix)

In `formatters/calendar.py`, in the `format_meeting_prep` function (line ~217), change:

```python
# BEFORE (line ~217):
"text": f"*Deal:* {deal_info.get('name', 'Unknown')}\n*Stage:* {deal_info.get('stage', 'Unknown')}\n*Value:* ${deal_info.get('amount', 0):,.0f}"

# AFTER:
"text": f"*Deal:* {deal_info.get('name', 'Unknown')}\n*Stage:* {deal_info.get('stage', 'Unknown')}\n*Value:* ${float(deal_info.get('amount', 0)):,.0f}"
```

The only change is wrapping the amount value in `float()`: `${float(deal_info.get('amount', 0)):,.0f}`

### Fix 2: `app.py` — Cast at the source (defense-in-depth)

In `app.py`, in the `handle_prep_meeting_action` function (line ~7107-7112), where `deal_info` is built, change:

```python
# BEFORE:
deal_info = {
    "name": deal.get("properties", {}).get("dealname", "Unknown"),
    "stage": deal.get("properties", {}).get("dealstage", "Unknown"),
    "amount": deal.get("properties", {}).get("amount", 0)
}

# AFTER:
raw_amount = deal.get("properties", {}).get("amount", 0)
try:
    parsed_amount = float(raw_amount)
except (ValueError, TypeError):
    parsed_amount = 0.0

deal_info = {
    "name": deal.get("properties", {}).get("dealname", "Unknown"),
    "stage": deal.get("properties", {}).get("dealstage", "Unknown"),
    "amount": parsed_amount
}
```

This ensures `deal_info["amount"]` is always a float before it reaches any formatter.

---

## Why Both Fixes?

- **Fix 1** (formatter) is the minimum change that resolves the error immediately.
- **Fix 2** (handler) ensures any future code that consumes `deal_info["amount"]` also gets a proper float, preventing the same class of bug elsewhere.

Apply both fixes.

---

## Testing

1. Run `/my-day`
2. Click **Prep** on the DataFlow meeting
3. Should now show the meeting prep card with:
   - Deal name
   - Deal stage
   - Value formatted as currency (e.g., `$48,000`)
4. No error message should appear
