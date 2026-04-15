# EXPANSION-20: Synthetic Coaching Data Generator

## Goal
Generate rich coaching-specific synthetic data to improve the quality of roleplay sessions,
live coaching tips, and coaching debriefs. This data gets indexed into the RAG vector store
so that coaching commands pull from a library of scenarios, techniques, and annotated examples.

## Current State
- Existing coaching data comes from `data/playbooks/sales_methodology.md` and
  `data/playbooks/objection_handling_playbook.md` — these are general sales methodology docs
- Call transcripts exist in `data/mock_crm/call_transcripts/` (5 files) — realistic but
  NOT annotated with coaching insights
- The RAG system indexes everything in `data/playbooks/` via `scripts/index_playbooks.py`
- Coach queries use `rag_search(f"roleplay {scenario} objections sales")` and
  `search_playbooks(f"{call_type} call methodology techniques")`

## What to Build

### Step 1: Create the Generator Script

Create `scripts/generate_coaching_data.py` following the same pattern as `scripts/generate_test_data.py`.

The script should generate these files:

#### File 1: `data/playbooks/coaching_scenarios.md`

A library of 15-20 pre-built roleplay scenarios with structured metadata.

```markdown
# Coaching Scenario Library

## Scenario: Discovery Call — Skeptical CTO
**Difficulty:** Medium
**Skills Tested:** Rapport building, technical credibility, needs assessment
**Buyer Persona:**
- Name: Alex Rivera, CTO
- Company Type: Mid-market SaaS (200-500 employees)
- Personality: Analytical, data-driven, distrusts vendor claims
- Hidden Objections: Already evaluated a competitor, concerned about integration complexity
- Decision Style: Consensus-driven, will loop in VP Engineering

**Ideal Approach:**
1. Open with specific research about their tech stack (shows preparation)
2. Ask about current pain points before pitching
3. Use data and case studies, not anecdotes
4. Acknowledge integration concerns proactively
5. Propose a technical evaluation with their engineering team

**Common Mistakes:**
- Leading with product features instead of discovery questions
- Making ROI claims without backing data
- Ignoring the consensus decision-making style
- Pushing for next steps too aggressively

**Sample Opening (Buyer):**
"Look, I'll be upfront — we've already looked at three tools in this space.
I'm not sure yours is different. You've got 15 minutes to change my mind."

**Debrief Criteria:**
- Score 8-10: Asked 3+ discovery questions before any pitch, referenced specific
  tech stack details, proposed technical POC
- Score 5-7: Good rapport but pitched too early, or missed integration concern
- Score 1-4: Led with features, didn't adapt to skeptical personality

---

## Scenario: Pricing Negotiation — Budget-Constrained VP
...
```

Generate at least 15 scenarios covering:
1. Discovery call — skeptical CTO
2. Discovery call — enthusiastic champion
3. Pricing negotiation — budget-constrained VP
4. Pricing negotiation — procurement-led
5. Competitive displacement — incumbent vendor
6. Competitive objection — "We're evaluating [competitor]"
7. Cold call — gatekeeper bypass
8. Cold call — direct to decision-maker
9. Renewal risk — unhappy customer
10. Upsell conversation — expand into new department
11. Multi-stakeholder meeting — CFO + CTO alignment
12. Demo gone wrong — technical failure recovery
13. Timeline objection — "Not the right time"
14. Contract negotiation — legal pushback on terms
15. Executive sponsor meeting — board-level conversation

#### File 2: `data/playbooks/coaching_techniques.md`

A reference document of sales coaching techniques and frameworks.

```markdown
# Sales Coaching Techniques Reference

## SPIN Selling Framework
**When to Use:** Discovery calls, needs assessment
**Structure:**
- **S**ituation Questions: Understand current state ("What tools do you use today?")
- **P**roblem Questions: Surface pain points ("What challenges do you face with...?")
- **I**mplication Questions: Amplify pain ("What happens when that problem occurs?")
- **N**eed-Payoff Questions: Connect to value ("How would it help if you could...?")

**Coaching Tips:**
- Reps often skip Implication questions — coach them to pause and explore impact
- Need-Payoff questions should come from the BUYER, not the rep
- Limit Situation questions to 2-3 (too many feels like an interrogation)

**Example Coaching Moment:**
Buyer says: "Our ramp time is 7 months"
Bad rep response: "Our tool cuts that to 3 months!" (jumps to solution)
Good rep response: "What does that 7-month ramp cost you in lost revenue?" (Implication)
Coach tip: "Great moment to dig deeper. Ask about the business impact before offering solutions."

---

## Challenger Sale Methodology
...

## MEDDPICC Qualification
...

## Sandler Pain Funnel
...

## Feel-Felt-Found
...

## Objection Handling: LAER Framework
- **L**isten: Let them finish, don't interrupt
- **A**cknowledge: Validate the concern ("That's a fair point...")
- **E**xplore: Ask follow-up ("Can you help me understand what's driving that concern?")
- **R**espond: Address with evidence or reframe

...
```

Generate 8-10 technique entries with coaching tips and example moments.

#### File 3: `data/playbooks/coaching_anti_patterns.md`

Common mistakes reps make, organized by call type.

```markdown
# Sales Coaching Anti-Patterns

## Discovery Call Anti-Patterns

### Anti-Pattern: "Feature Dumping"
**What It Looks Like:** Rep lists product features before understanding buyer needs
**Why Reps Do It:** Nervous silence, want to show value quickly, lack of discovery training
**How to Coach:**
- Ask: "What did you learn about THEIR situation before talking about us?"
- Redirect: "Try asking 3 questions before mentioning any feature"
- Practice: Run a roleplay where the rep is NOT allowed to mention the product for 5 minutes

### Anti-Pattern: "Happy Ears"
**What It Looks Like:** Rep hears "sounds interesting" and assumes the deal is progressing
**Why Reps Do It:** Confirmation bias, pressure to build pipeline
**How to Coach:**
- Challenge: "What specific next step did they commit to?"
- Teach: "Interest is not commitment. Look for actions, not words."
- Practice: Roleplay where the buyer is politely non-committal

### Anti-Pattern: "Premature Close"
...

## Negotiation Anti-Patterns

### Anti-Pattern: "First to Blink"
**What It Looks Like:** Rep offers discounts before the buyer asks
...

### Anti-Pattern: "Splitting the Difference"
...

## Competitive Deal Anti-Patterns

### Anti-Pattern: "Trash Talking"
**What It Looks Like:** Rep badmouths competitor instead of differentiating
...
```

Generate 12-15 anti-patterns across discovery, negotiation, competitive, and closing categories.

#### File 4: `data/playbooks/coaching_debrief_rubrics.md`

Scoring rubrics for roleplay debriefs, organized by scenario type.

```markdown
# Coaching Debrief Scoring Rubrics

## Discovery Call Rubric

### Opening (1-10)
- 9-10: Personalized opening referencing specific research, set clear agenda, confirmed time
- 7-8: Good rapport, set agenda, but opening was somewhat generic
- 5-6: Polite but formulaic opening, no personalization
- 3-4: Jumped straight to pitch, no rapport building
- 1-2: Unprepared, stumbled, or inappropriate opening

### Needs Assessment (1-10)
- 9-10: Asked 5+ discovery questions, uncovered 2+ pain points, used SPIN/Challenger framework
- 7-8: Good questions but missed an obvious pain point, or asked too many Situation questions
- 5-6: Some discovery but shifted to pitch too early
- 3-4: Minimal discovery, mostly talked about the product
- 1-2: No discovery questions, pure product pitch

### Objection Handling (1-10)
- 9-10: Acknowledged concern, explored root cause, reframed effectively, used evidence
- 7-8: Handled objection but didn't explore deeply enough
- 5-6: Gave a canned response, didn't adapt to the specific concern
- 3-4: Got defensive or dismissive
- 1-2: Ignored the objection or changed the subject

### Next Steps (1-10)
- 9-10: Proposed specific next step with date, got verbal commitment, identified stakeholders
- 7-8: Proposed next step but vague on timing or stakeholders
- 5-6: Asked "can we follow up?" without specifics
- 3-4: Ended call without clear next step
- 1-2: Let the buyer end the call without any follow-up plan

## Negotiation Call Rubric
...

## Competitive Deal Rubric
...
```

### Step 2: Run the Generator

```bash
python scripts/generate_coaching_data.py
```

This should create/overwrite the 4 files listed above.

### Step 3: Re-index the RAG Store

After generating, re-index:

```bash
python scripts/index_playbooks.py
```

The existing indexer should pick up the new files in `data/playbooks/` automatically.

### Step 4: Update RAG Queries for Coaching

In `graphs/coach.py`, update the RAG queries to target the new data more effectively.

In `roleplay_node()` (line 46):
```python
# BEFORE:
rag_context = rag_search(f"roleplay {scenario} objections sales")

# AFTER:
rag_context = rag_search(f"coaching scenario {scenario} buyer persona approach mistakes")
```

In `continue_roleplay()`, add RAG context for the debrief:
```python
if turn_count >= max_turns:
    # Get debrief rubric from RAG
    debrief_context = rag_search(f"debrief rubric scoring criteria {scenario_type}")

    system_prompt = f"""You are an AI sales coach. The roleplay is complete.

SCORING RUBRIC FROM PLAYBOOK:
{debrief_context}

COACHING CONTEXT:
{rag_context}

Based on the conversation so far, provide a detailed debrief...
"""
```

In `app.py` for live coaching (the message handler section around line 800), update the methodology query:
```python
# Currently the methodology_context is loaded once at session start.
# No change needed — it already queries:
# search_playbooks(f"{call_type} call methodology techniques")
# The new coaching_techniques.md will be found by this query automatically.
```

## Testing

1. Run `python scripts/generate_coaching_data.py` — verify 4 new files created in `data/playbooks/`
2. Run `python scripts/index_playbooks.py` — verify new documents indexed without errors
3. `/coach roleplay discovery call` — the AI should reference specific techniques and
   scenario details from the new data. The debrief should be more structured.
4. `/coach roleplay pricing negotiation` — should match the pricing negotiation scenario
5. `/coach-live NovaTech discovery` — coaching tips should reference SPIN/Challenger techniques
6. Check that existing commands (/research, /deal, /ask, etc.) still work — new playbook
   files should not interfere

## DO NOT
- Do not modify the existing `generate_test_data.py` — this is a SEPARATE generator
- Do not delete existing playbook files — add new ones alongside them
- Do not change the RAG indexing logic — just add new source files
- Do not make LLM calls in the generator script — all content should be hardcoded strings
  (same pattern as `generate_test_data.py`)
