# SalesCoach AI Demo Script

**Version:** 2.0 (Hive Mind Architecture)  
**Duration:** 15-20 minutes  
**Presenter:** [Your Name]  
**Audience:** Sales leaders, sales reps, RevOps

---

## Pre-Demo Checklist

- [ ] Ollama running: `ollama serve`
- [ ] Model pulled: `ollama pull qwen3.5:397b-cloud`
- [ ] App running: `python app.py`
- [ ] Slack workspace accessible
- [ ] Demo data seeded: `python scripts/seed_demo_data.py`
- [ ] Test Slack commands work

---

## Demo Flow Overview

| Time | Section | Key Points |
|------|---------|------------|
| 0-2 min | Introduction | What is SalesCoach AI |
| 2-5 min | Architecture | Hive Mind overview |
| 5-8 min | DIRECT Demo | Instant responses |
| 8-12 min | WORKFLOW Demo | Roleplay scenario |
| 12-17 min | COMPLEX Demo | QBR preparation |
| 17-20 min | Q&A | Questions, next steps |

---

## Section 1: Introduction (2 minutes)

### Talking Points

"Today I'm showing you **SalesCoach AI** — a Slack-based intelligent sales assistant that combines:

1. **Real-time coaching** — Roleplay sales calls with AI buyers
2. **Instant research** — Company briefs, deal status, pipeline health
3. **Complex task execution** — QBR prep, win/loss analysis, coaching plans

**What makes this different:**

- **Hive Mind Architecture**: Unlike simple chatbots, SalesCoach uses multi-agent orchestration for complex tasks
- **Local LLM**: Runs on qwen3.5:397b-cloud via Ollama — no cloud API costs, full data privacy
- **Self-improving**: Learns from every interaction via our memory system

**Let me show you how it works.**"

### Screen Setup

- Slack workspace open
- Terminal visible (showing app.py running)
- Ollama status visible

---

## Section 2: Architecture Overview (3 minutes)

### Talking Points

"SalesCoach uses a **three-tier routing system** called Hive Mind Triage:

**Tier 1: DIRECT** — Simple lookups like 'Show pipeline'
- Single tool call
- Response in <2 seconds
- Uses DirectExecutor

**Tier 2: WORKFLOW** — Structured workflows like 'Roleplay discovery call'
- Coach or Assistant subgraph
- Response in ~4 seconds
- Uses typed contracts for reliability

**Tier 3: COMPLEX** — Multi-step tasks like 'Prepare for QBR'
- PM Agent decomposes into TaskGraph
- DAG Executor runs parallel batches
- Reviewer validates before responding
- Response in ~15-20 seconds

**All powered by local LLM** — qwen3.5:397b-cloud running on Ollama. No data leaves this machine."

### Visual Aid

Show the architecture diagram:

```
Slack → Triage → DIRECT → Executor → Respond
            → WORKFLOW → Coach/Assistant → Respond
            → COMPLEX → PM→DAG→Reviewer → Respond
```

---

## Section 3: DIRECT Path Demo (3 minutes)

### Scenario: Pipeline Health Check

**Presenter Action:** Type in Slack DM with bot:

```
Show pipeline
```

### Expected Response (within 2 seconds)

```
Pipeline Overview

Total: 24 deals ($1,245,000)

By Stage:
• Prospecting: 8 deals ($320,000)
• Qualification: 6 deals ($450,000)
• Proposal: 5 deals ($275,000)
• Negotiation: 3 deals ($150,000)

At Risk: 3 deals
Overdue: 2 deals
```

### Talking Points

"That was a **DIRECT** path request:

1. Triage classified it as DIRECT (single tool call)
2. DirectExecutor queried HubSpot via MCP
3. Returned typed PipelineDigest artifact
4. Formatted as Slack Block Kit

**Total latency: ~1.2 seconds** — faster than opening Salesforce.

Let me show you another DIRECT example:"

### Follow-up Demo

**Presenter Action:** Type:

```
Deal status for Acme Corp
```

### Expected Response

```
Deal: Acme Corp - Enterprise License

🟢 Stage: Verbal Commit | Value: $52,000 | Close: 2026-04-15

Key Contacts:
• Sarah Chen, VP Engineering (Champion)
• Mike Ross, CFO (Decision Maker)

Recent Activity:
• 2 days ago: Call scheduled with legal
• 5 days ago: Proposal sent

Next Steps:
• Send MSA by EOD tomorrow
• Schedule exec alignment call
```

---

## Section 4: WORKFLOW Path Demo (4 minutes)

### Scenario: Sales Roleplay

**Presenter Action:** Type:

```
/coach roleplay discovery call with VP Engineering at tech company
```

### Expected Response (within 5 seconds)

```
Buyer Persona:
• Name: Sarah Chen
• Title: VP of Engineering
• Company: Mid-market SaaS, 200 employees
• Traits: Technical, data-driven, skeptical of sales fluff
• Hidden Objections: "We've tried similar tools before"
• Cares About: Implementation time, team adoption

---

Sarah Chen: "Thanks for reaching out. Look, we're currently 
using [Competitor X] and it's working okay. We've got a lot 
on our plate right now, so I'd need to see a really compelling 
reason to switch. What's your pitch?"
```

### Talking Points

"This is a **WORKFLOW** path request:

1. Triage classified as WORKFLOW, route=coach
2. Coach subgraph executed roleplay_node
3. RAG pulled objection handling playbooks
4. Generated realistic buyer persona
5. Started interactive roleplay

**The roleplay continues** — each rep reply is scored, and after 3-4 turns, you get a full debrief with:
- Overall score (1-10)
- Dimension scores (MEDDIC/SPIN/Challenger)
- Strengths and improvements
- Recommended practice

Let me show you what the debrief looks like:"

### Continue Roleplay (Optional)

**Presenter Action:** Reply as rep:

```
Thanks Sarah. I appreciate the honesty. Can you tell me more 
about what's working well with Competitor X and where you 
see gaps?
```

### Expected Response

```
Sarah Chen: "Honestly, the biggest issue is adoption. We 
bought it 6 months ago, maybe 30% of the team uses it 
regularly. It's also pretty rigid — takes weeks to customize 
for our workflow. And don't get me started on the reporting... 
it's basically useless for our QBRs."
```

### End Roleplay (After 3-4 turns)

**Expected Debrief:**

```
Roleplay Debrief

Overall Score: 7.2/10

What You Did Well:
• Opened with empathy ("I appreciate the honesty")
• Asked exploratory questions about current solution
• Didn't pitch features immediately

Areas to Improve:
• Could have quantified the impact ("What's the cost of 30% adoption?")
• Missed opportunity to ask about decision criteria
• Need stronger transition to value prop

Dimension Scores:
• Discovery: 8/10
• Qualification: 6/10
• Value Prop: 7/10
• Closing: 6/10

Recommended Practice:
• Discovery call with price-sensitive buyer
• Handling "we're happy with current solution" objection
```

---

## Section 5: COMPLEX Path Demo (5 minutes)

### Scenario: QBR Preparation

**Presenter Action:** Type:

```
Prepare for my QBR meeting next week with Acme Corp
```

### Expected Flow (Show Terminal Logs)

```
[TRIAGE] Classifying: "Prepare for QBR..." → COMPLEX
[PM AGENT] Decomposing into TaskGraph...
[PM AGENT] Created 6 tasks:
  - fetch_pipeline (parallel)
  - fetch_wins (parallel)
  - fetch_losses (parallel)
  - analyze_patterns (depends: losses)
  - generate_qbr_slides (depends: all above)
  - executive_summary (depends: slides)
[DAG EXECUTOR] Batch 1: Running 3 parallel tasks...
[DAG EXECUTOR] Batch 2: Running analyze_patterns...
[DAG EXECUTOR] Batch 3: Running generate_qbr_slides...
[REVIEWER] Validating output...
[REVIEWER] Approved (quality score: 8.5/10)
[MEMORY] Extracting lessons...
[MEMORY] Recorded: "QBR prep requires win/loss + pipeline"
```

### Expected Response (within 20 seconds)

```
QBR Deck: Acme Corp

Executive Summary:
Acme Corp is a strategic account with 67% win rate 
(vs. 54% company avg) and $45K avg deal size 
(vs. $32K avg). Three open deals totaling $185K 
are in various stages. Key risk: Competitor X 
undercutting on price in last two losses.

---

Wins Last Quarter (2 deals, $90K):
• Deal A: $52K - Won via champion coaching
• Deal B: $38K - Won on implementation speed

Losses Last Quarter (2 deals, $103K):
• Deal C: $75K - Lost to Competitor X (price)
• Deal D: $28K - Lost to status quo (no decision)

Win/Loss Analysis:
• Win Rate: 67% (vs. 54% benchmark)
• Avg Sales Cycle: 42 days (vs. 58 days benchmark)
• Top Loss Reason: Price (Competitor X 30% below)

---

Current Pipeline (3 deals, $185K):
[Visual pipeline by stage]

Strategic Recommendations:
1. Executive alignment meeting with CEO (schedule by 4/12)
2. ROI analysis for price-sensitive deals (use Deal A as reference)
3. Reference call with Deal A customer (Sarah Chen intro)
4. Competitive battlecard update (Competitor X pricing)
```

### Talking Points

"This is a **COMPLEX** path request — the full Hive Mind orchestration:

1. **Triage** classified as COMPLEX (multi-step, requires synthesis)
2. **PM Agent** decomposed into 6 tasks with dependencies
3. **DAG Executor** ran 3 parallel batches:
   - Batch 1: Fetch pipeline, wins, losses (parallel)
   - Batch 2: Analyze win/loss patterns (sequential)
   - Batch 3: Generate QBR slides + summary (sequential)
4. **Reviewer** validated output (quality score: 8.5/10)
5. **Memory** extracted lessons for future QBR preps

**Key benefits:**
- Parallel execution = faster than sequential
- Typed contracts = reliable artifact passing
- Reviewer = no hallucinations sent to user
- Memory = gets smarter every time

This would take a sales rep **2-3 hours** manually. SalesCoach does it in **~20 seconds**."

---

## Section 6: Memory System Demo (2 minutes)

### Show Memory in Action

**Presenter Action:** Type:

```
Research Acme Corp
```

### Expected Response

```
Research Brief: Acme Corp

Company Overview:
Acme Corp is a mid-market SaaS provider specializing in 
workflow automation. 200 employees, $50M ARR, headquartered 
in Austin, TX.

Your Relationship:
• 3 open deals totaling $185K
• 12 contacts in CRM (Sarah Chen = champion)
• Last interaction: 2 days ago (legal call scheduled)

Recent News:
• Raised $25M Series C (2 weeks ago)
• Hired new CTO from Competitor Y (1 month ago)
• Announced enterprise tier launch (3 weeks ago)

Talking Points:
• Congratulate on Series C — expansion budget available
• New CTO may be evaluating stack — timing is ideal
• Enterprise tier aligns with their growth trajectory
```

### Talking Points

"Notice the response included **'Your Relationship'** section — that's the Memory System at work:

1. **User Preferences**: Retrieved from SQLite (e.g., prefers detailed briefs)
2. **Project Lessons**: 'Acme Corp is strategic — prioritize' from previous QBR
3. **Execution History**: Previous interactions with Acme retrieved

**Memory makes SalesCoach self-improving** — it remembers:
- Your preferences
- Past interactions
- What worked (and what didn't)
- Patterns from successful executions"

---

## Section 7: Closing & Q&A (3 minutes)

### Summary Talking Points

"Let me recap what we've seen:

1. **DIRECT Path** — Instant pipeline/deal lookups (<2s)
2. **WORKFLOW Path** — Interactive roleplays with debriefs (~4s)
3. **COMPLEX Path** — Multi-agent QBR preparation (~20s)
4. **Memory System** — Self-improving through experience

**All running locally** on qwen3.5:397b-cloud via Ollama. No cloud API costs. No data leaving your infrastructure.

**Next Steps:**
1. Install SalesCoach in your Slack workspace
2. Seed with your playbooks and CRM data
3. Train your team with roleplay sessions
4. Monitor adoption via engagement dashboard

**Questions?**"

### Common Q&A

**Q: How accurate is qwen3.5:397b-cloud vs. Claude Sonnet?**  
A: Benchmarks show qwen3.5 is comparable to Claude Sonnet 4.5 for most sales tasks. The key advantage is **local inference** — no API costs, full privacy.

**Q: Can I use OpenRouter instead of Ollama?**  
A: Yes — Ollama is primary, but OpenRouter is configured as fallback. Just set `OPENROUTER_API_KEY` and remove `OLLAMA_BASE_URL`.

**Q: How do I customize the sales methodology?**  
A: Add your methodology to `data/playbooks/methodologies/` (MEDDIC, SPIN, Challenger, BANT supported out of box).

**Q: Can SalesCoach write back to CRM?**  
A: Yes — via HubSpot MCP. All writes are logged in `crm_writes` table for audit. Requires manager approval for first-time writes.

**Q: What's the deployment model?**  
A: Runs on Cloud Run, GKE, or any Docker host. SQLite for state, ChromaDB for RAG, MCP servers as sidecars.

---

## Appendix: Demo Troubleshooting

### If Ollama is slow:

```bash
# Check GPU acceleration
ollama run qwen3.5:397b-cloud "Hello"

# If CPU-only, expect ~5 tokens/sec
# With GPU (RTX 3090+), expect ~30 tokens/sec
```

### If MCP tools fail:

```bash
# Test HubSpot connection
curl -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  https://api.hubapi.com/crm/v3/objects/companies?limit=1
```

### If Triage misclassifies:

```bash
# Check triage logs
tail -f logs/triage.log | grep "Classifying"

# Update prompt in prompts/triage_prompt.py
```

---

## Post-Demo Follow-Up

1. **Send recording** of demo
2. **Share docs**: `docs/SALESCOACH-DEMO-GUIDE-UPDATED.md`
3. **Schedule onboarding** call
4. **Provide sandbox** environment for testing
