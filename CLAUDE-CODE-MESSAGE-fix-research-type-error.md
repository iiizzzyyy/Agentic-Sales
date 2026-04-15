# FIX: TypeError in /research — `int + str` in `_generate_mock_news()`

## Bug Description
Running `/research NovaTech` crashes with:
```
TypeError: unsupported operand type(s) for +: 'int' and 'str'
```

## Root Cause
In `graphs/assistant.py`, the `_generate_mock_news()` function (line 498-502) calculates total deal value using `sum()` without converting string amounts to numbers:

```python
# BROKEN — amounts are strings like "48000" in deals.json
total_value = sum(
    d.get("properties", {}).get("amount", 0)
    for d in deals
    if d.get("properties", {}).get("amount")
)
```

Python's `sum()` starts with `0` (int) and tries `0 + "48000"` (string) → TypeError.

The correct pattern already exists 80 lines below in `_get_mock_pipeline_context()` (line 577-578):
```python
# CORRECT — wraps in float()
total_value = sum(
    float(d.get("properties", {}).get("amount", 0) or 0)
    for d in open_deals
)
```

## Fix — One Line Change

In `graphs/assistant.py`, find the `_generate_mock_news()` function and replace lines 498-502:

```python
# BEFORE (line 498-502):
        total_value = sum(
            d.get("properties", {}).get("amount", 0)
            for d in deals
            if d.get("properties", {}).get("amount")
        )

# AFTER:
        total_value = sum(
            float(d.get("properties", {}).get("amount", 0) or 0)
            for d in deals
            if d.get("properties", {}).get("amount")
        )
```

## Secondary Check — `app.py` line 408

While investigating, I also found a potential issue in `app.py` line 408 (inside `handle_pipeline` or similar):

```python
total_value = sum(d.get("amount", 0) for d in open_deals)
```

This one works currently because `open_deals` comes from `extract_deals()` which already converts amounts to `float` at line 257. But for safety, add the `float()` conversion here too:

```python
total_value = sum(float(d.get("amount", 0) or 0) for d in open_deals)
```

## Testing

1. `/research NovaTech` → should complete without errors
2. The "Recent News" section should show mock news (workforce, HQ presence, active evaluation)
3. `/research Apex` → should also work
4. `/pipeline` → should still calculate totals correctly

## DO NOT
- Do not change the `_get_mock_pipeline_context()` function — it already uses `float()` correctly
- Do not change the mock CRM data files — amounts should stay as strings (that's how HubSpot returns them)
- Do not remove the `if d.get("properties", {}).get("amount")` filter — it correctly skips deals with no amount
