# Bug Report: Reaction Duplication in Google Sheets

## Overview
When users add reactions to a Slack message, the same emoji is appended multiple times to the "Reactions" column in Google Sheets (e.g., `👀 , 👀` instead of just `👀`).

## Date
2026-01-26

## Impact
- **Severity**: Low/Medium
- **Scope**: `arxiv-slack-listener` (Google Sheets Sync)
- **Visuals**: The spreadsheet cell becomes cluttered with duplicate emojis (e.g., `👀 , 👀 , 👀` for 3 identical reactions).

## Current Behavior
The current implementation in `lambda_function.py` indiscriminately appends every incoming `reaction_added` event to the cell value.

```python
# lambda_function.py (Line 83)
new_text = f"{current_text}, {reaction}" if current_text else reaction
```

Is simply concatenating strings without checking for existence.

## Expected Behavior
- **Option A (Unique)**: Only append the emoji if it doesn't already exist in the cell.
- **Option B (Counted)**: (Optional) Show counts, e.g., `👀 (2)`. (Might be too complex for a simple CSV string)
- **Recommended**: Prioritize uniqueness. If `👀` is already there, do not append it again.

## Steps to Reproduce
1. Post a message to Slack.
2. User A reacts with `👀`.
3. System updates Sheet: `Reactions` = `👀`.
4. User B reacts with `👀`.
5. System updates Sheet: `Reactions` = `👀 , 👀` (Current Bug).

## Proposed Fix
Modify `arxiv-slack-listener/lambda_function.py` to checking if `reaction` is already present in `current_strings` split by comma.

```python
existing_reactions = [r.strip() for r in current_text.split(',')] if current_text else []
if reaction not in existing_reactions:
    # Append
```
