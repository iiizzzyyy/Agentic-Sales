# Instructions: Using the Synthetic Test Data

> **For Claude Code.** This document tells you how to use the pre-generated synthetic test data and the generator script to develop and test the POC without needing live API connections.

---

## THE GENERATOR SCRIPT

`scripts/generate_test_data.py` creates all synthetic data. It has **already been run** — all data files exist in the project.

**When to re-run it:**
- Run `python scripts/generate_test_data.py` if you need fresh randomized CRM data (different deal amounts, dates, associations)
- After re-running, re-index into ChromaDB: `python scripts/index_playbooks.py`

**What's deterministic vs randomized:**
- **Same every run:** Playbooks, call transcripts, email threads, meeting notes, case studies, product catalog (these tell interconnected stories — see the STORYLINES section)
- **Randomized each run:** CRM contacts, companies, deals, and BQ analytics (different amounts, dates, stage assignments)

---

## WHAT EXISTS — COMPLETE FILE INVENTORY

### `data/playbooks/` — 8 markdown files (INDEX ALL INTO CHROMADB)
These are the knowledge base for RAG. They power the Coach's feedback, roleplay personas, and the Assistant's research/email drafts.

| File | What It Contains | Used By |
|------|-----------------|---------|
| `objection_handling_playbook.md` | 7 objection categories with Acknowledge→Question→Reframe→Advance scripts + quick-reference cheat sheet | Coach (roleplay + feedback), Assistant (email drafts) |
| `competitive_battle_cards.md` | Battle cards vs. CompetitorAlpha, CompetitorBeta, CompetitorGamma, and "Build In-House" — with strengths, weaknesses, how-to-win, and landmine questions | Coach (roleplay — competitor objections), Assistant (research briefs) |
| `ideal_customer_profiles.md` | 3 ICP tiers (Mid-Market SaaS, Enterprise, High-Growth Startup) with full personas (VP Sales, CTO, CFO, CRO, Head of Enablement, Founder), pain points, trigger events, disqualification criteria, vertical notes (Healthcare, FinServ, Manufacturing) | Coach (persona generation for roleplay), Assistant (research context) |
| `email_templates_playbook.md` | 8 email templates: post-discovery, post-demo, proposal follow-up (day 3/7/14), cold outreach pattern-interrupt, post-event + best practices (subject lines, body copy rules, timing) | Assistant (`/draft-email` command) |
| `sales_methodology.md` | Full SPIN discovery framework, MEDDPICC qualification scoring, demo structure, negotiation framework, closing techniques | Coach (feedback scoring, roleplay debrief criteria) |
| `product_pricing_catalog.md` | 3 pricing tiers (Starter $49, Professional $79, Enterprise $129/user/month), add-ons, discount guidelines with approval matrix, competitive pricing comparison, ROI benchmarks with source data | Coach (pricing objection roleplays), Assistant (proposal context, email drafts with specific pricing) |
| `case_study_cloudbridge.md` | Full case study: CloudBridge Systems — 60% ramp time reduction, 42% close rate improvement, 2,126% ROI. Includes timeline, metrics tables, quotes, expansion opportunity | Coach (reference in feedback — "companies like CloudBridge saw..."), Assistant (research briefs, email drafts) |
| `case_study_apex.md` | Full case study: Apex Manufacturing — 34% pipeline growth, standardized coaching across 3 regions, $152K deal. Includes regional performance tables, deal velocity data, feature usage stats, 691% ROI | Coach (reference in feedback), Assistant (research briefs, email drafts, proposal support) |

**Action:** Index ALL 8 files into ChromaDB using `scripts/index_playbooks.py`. Ensure the indexing script supports `.md` files (check the file extension filter).

### `data/mock_crm/` — CRM data (JSON) + conversations

#### Structured CRM Records
| File | Records | Format | Mirrors |
|------|---------|--------|---------|
| `contacts.json` | ~17-21 contacts | JSON array, HubSpot API response format | HubSpot MCP `search_contacts` response |
| `companies.json` | 10 companies | JSON array, HubSpot API response format | HubSpot MCP `get_company` response |
| `deals.json` | ~13-16 deals | JSON array with nested `activities` array | HubSpot MCP `get_deals` + `get_engagements` |

Each deal includes 3-5 realistic CRM activity notes (discovery calls, demo recaps, competitor alerts, negotiation updates). Some deals have a `"_test_flag"` field set to `"stale"` (no activity 14+ days) or `"overdue"` (past close date) — use these to verify `/pipeline` correctly identifies at-risk deals.

#### Call Transcripts — `data/mock_crm/call_transcripts/` (5 files)
Full sales call transcripts with timestamps, dialogue, and rep post-call notes. These test the Coach's feedback feature.

| File | Call Type | Rep | Quality | What Coach Should Say |
|------|-----------|-----|---------|----------------------|
| `discovery_call_novatech_2026-02-18.md` | Discovery (28 min) | Jordan | **Good** | Praise: strong SPIN technique, let prospect quantify pain ($720K/quarter), identified 3 stakeholders, secured next step |
| `discovery_call_greenfield_2026-02-12.md` | Discovery (18 min) | Alex | **Weak** | Flag: feature-dumped immediately, zero discovery questions, no pain uncovered, jumped to pricing, no urgency created, vague next step |
| `negotiation_call_apex_2026-02-25.md` | Negotiation (35 min) | Jordan | **Good** | Praise: never discounted without trading (2yr + case study for 15% off), handled build-vs-buy, included 90-day exit clause, clear close |
| `cold_call_stratos_2026-03-01.md` | Cold Call (6 min) | Nina | **Good** | Praise: concise pattern interrupt, relevant personalization (LinkedIn post), earned meeting in 2 minutes, got champion + enablement lead added |
| `demo_call_velocity_retail_2026-02-20.md` | Demo (42 min) | Alex | **Bad** | Flag: ignored CTO's request for technical architecture, did generic feature tour instead, couldn't answer data flow questions, lost credibility with technical buyer |

**How to use:** When testing `/coach feedback`, pass the transcript text as the call notes. The Coach should pull relevant context from RAG (sales methodology for SPIN/MEDDPICC scoring, objection playbook for handling analysis) and give specific, actionable feedback referencing actual moments from the transcript.

#### Email Threads — `data/mock_crm/email_threads/` (3 files)
Email conversation threads in JSON format matching Gmail MCP response structure.

| File | Thread | Emails | Status | What to Test |
|------|--------|--------|--------|-------------|
| `thread_novatech_proposal_followup.json` | Proposal → questions about scaling/pilot → answers → Marcus security concerns → Jordan's response | 5 | Active, progressing | `/draft-email NovaTech` should continue this thread, reference security whitepaper and upcoming demo |
| `thread_apex_contract.json` | Contract sent → Michael's legal questions (liability cap, GDPR) → Jordan's response | 3 | Near close | `/draft-email Apex` should know contract is in legal review, GDPR addressed |
| `thread_greenfield_gone_cold.json` | Case studies sent → follow-up (no reply) → follow-up with report (no reply) → Tom says they went with CompetitorAlpha | 4 | Lost | `/draft-email Greenfield` should generate a win-back email, not a standard follow-up |

**JSON structure:** `thread_id`, `subject`, `participants` (with name, email, role), `messages` array with `from`, `to`, `cc`, `date`, `body`.

#### Meeting Notes — `data/mock_crm/meeting_notes/` (4 files)
Meeting prep and recap documents for testing Coach prep and `/research` output.

| File | Type | What to Test |
|------|------|-------------|
| `prep_novatech_demo_2026-02-22.md` | Pre-demo prep | Full prep doc with attendees, pain points per persona, demo agenda, risk factors, pre-meeting checklist. Test `/research NovaTech` output quality against this as a benchmark. |
| `recap_cloudbridge_qbr_2026-02-15.md` | QBR recap (existing customer) | Key metrics (9-week ramp, 92% adoption, NPS 9/10), issues raised (reporting, custom personas, Slack integration), expansion opportunity (30→45 users). Tests `/deal CloudBridge`. |
| `recap_terralogistics_lost_deal_2026-01-30.md` | Lost deal postmortem | Root cause analysis (no champion, poor price handling, generic demo, no urgency), coaching plan for Alex. Tests Coach feedback patterns. |
| `prep_pinnacle_discovery_2026-03-04.md` | Discovery prep (FinServ) | Research notes, questions for VP Sales + CDO, FinServ-specific objections, risk factors (compliance review timeline). Tests `/research Pinnacle` with ICP Tier 2 context. |

### `data/mock_bq/` — Analytics CSVs
| File | What It Contains |
|------|-----------------|
| `pipeline_analytics.csv` | 6 months × 5 stages: deal_count, total_value, avg_deal_size, win_rate, avg_days_in_stage |
| `win_loss_analysis.csv` | 5 quarters: total_won, total_lost, win_rate, avg_won_deal_size, avg_sales_cycle_days, top_loss_reason |

---

## HOW TO USE THIS DATA

### 1. Index playbooks + transcripts + meeting notes into ChromaDB

Update `scripts/index_playbooks.py` to index from multiple directories with metadata tagging:

```python
# Directories to index into ChromaDB — each with a document type tag
INDEX_DIRS = [
    ("data/playbooks/", "playbook"),                         # Sales knowledge base (8 files)
    ("data/mock_crm/call_transcripts/", "call_transcript"),  # Past calls for Coach reference
    ("data/mock_crm/meeting_notes/", "meeting_note"),        # Meeting context for prep
]
```

The `type` metadata lets the RAG system filter by document type. For example, when generating a roleplay persona, search only `type=playbook` docs. When giving call feedback, include `type=call_transcript` to reference past calls.

Then run: `python scripts/index_playbooks.py`

### 2. Use mock CRM data as fallback when MCP isn't connected

When developing without a live HubSpot connection, load the mock data as a fallback:

```python
import json

def load_mock_crm():
    """Load synthetic CRM data for local testing."""
    with open("data/mock_crm/companies.json") as f:
        companies = json.load(f)
    with open("data/mock_crm/contacts.json") as f:
        contacts = json.load(f)
    with open("data/mock_crm/deals.json") as f:
        deals = json.load(f)
    return {"companies": companies, "contacts": contacts, "deals": deals}

def search_mock_company(name: str, crm_data: dict) -> dict | None:
    """Search mock CRM by company name (fuzzy match)."""
    name_lower = name.lower()
    for company in crm_data["companies"]:
        if name_lower in company["properties"]["name"].lower():
            return company
    return None

def get_mock_deals_for_company(company_id: str, crm_data: dict) -> list:
    """Get all deals associated with a company."""
    return [d for d in crm_data["deals"] if d["associations"]["company"] == company_id]

def get_stale_deals(crm_data: dict, stale_days: int = 14) -> list:
    """Find deals with no activity in N days (for /pipeline)."""
    return [d for d in crm_data["deals"] if d.get("_test_flag") == "stale"]
```

### 3. Use mock email threads for `/draft-email` testing

When Gmail MCP isn't connected, load email thread context:

```python
def load_email_thread(company_name: str) -> dict | None:
    """Load mock email thread for a company."""
    import glob
    for filepath in glob.glob("data/mock_crm/email_threads/*.json"):
        with open(filepath) as f:
            thread = json.load(f)
        for participant in thread["participants"]:
            if company_name.lower().replace(" ", "") in participant["email"].lower():
                return thread
    return None
```

### 4. Use mock BQ data for `/pipeline` analytics

```python
import csv

def load_pipeline_analytics() -> list[dict]:
    """Load mock BigQuery pipeline data."""
    with open("data/mock_bq/pipeline_analytics.csv") as f:
        return list(csv.DictReader(f))
```

### 5. Test each command with this data

| Command | Test Input | Expected Data Sources | What to Verify |
|---------|-----------|----------------------|----------------|
| `/research NovaTech` | Company name | `companies.json` (NovaTech), `contacts.json` (Sarah Chen), `deals.json`, RAG (ICP for Enterprise Software, case study CloudBridge for reference) | Brief includes deal status, contacts, talking points from playbook, competitive context |
| `/research Pinnacle` | Company name | `companies.json` (Pinnacle), RAG (ICP Tier 2 FinServ, meeting prep notes) | Brief should flag compliance/HIPAA considerations, reference FinServ vertical notes |
| `/deal Apex` | Deal name substring | `deals.json` (Apex deals), deal activities | Deal card shows stage, amount, recent activity notes, recommended next actions |
| `/coach roleplay discovery call with CFO` | Scenario text | RAG (sales methodology SPIN framework, ICP CFO persona, product pricing for objections) | Buyer persona matches CFO profile, uses MEDDPICC language, raises realistic pricing objections |
| `/coach feedback` + NovaTech transcript | Call transcript content | RAG (sales methodology, objection handling) | Praises SPIN technique, pain quantification, multi-stakeholder identification. References specific moments. |
| `/coach feedback` + Greenfield transcript | Call transcript content | RAG (sales methodology, objection handling) | Flags lack of discovery questions, feature-dumping, no pain uncovered. Recommends specific practice areas. |
| `/draft-email NovaTech` | Company name | `deals.json`, `email_threads/thread_novatech_*.json`, RAG (email templates, case study CloudBridge as reference) | Draft continues the existing thread, references demo/security concerns, includes relevant case study data |
| `/draft-email Greenfield` | Company name | `email_threads/thread_greenfield_*.json` (lost deal) | Draft is a win-back email, not a standard follow-up. Acknowledges they chose CompetitorAlpha. |
| `/draft-email Apex` | Company name | `email_threads/thread_apex_*.json`, RAG (email templates) | Draft acknowledges contract is in legal review, offers to help with GDPR questions |
| `/pipeline` | No input | `deals.json` (all open deals), `mock_bq/pipeline_analytics.csv` | Flags stale deals (14+ days), overdue deals, includes total pipeline value, stage breakdown, recommended actions |

### 6. Regenerate data if needed

```bash
python scripts/generate_test_data.py    # Generate fresh data
python scripts/index_playbooks.py       # Re-index into ChromaDB
```

---

## INTERCONNECTED STORYLINES

The test data tells 7 coherent stories across all data types. Each storyline crosses multiple file types so you can test that the agents connect the dots:

**NovaTech Solutions — Active Deal, Good Process:**
CRM record (Demo Scheduled, $72K) → Discovery call transcript (strong, Jordan) → Email thread (proposal + security questions, 5 emails) → Meeting prep (demo with Sarah + Marcus) → Case study reference (CloudBridge, similar profile)
Tests: `/research NovaTech`, `/deal NovaTech`, `/coach feedback` with good transcript, `/draft-email NovaTech`

**Apex Manufacturing — Near Close, Negotiation:**
CRM record (Negotiation, $180K) → Negotiation call transcript (strong, Jordan, traded discount for 2yr + case study) → Email thread (contract + GDPR legal, 3 emails) → Case study (Apex is itself a case study — 691% ROI, 34% pipeline growth)
Tests: `/deal Apex`, `/coach feedback` with negotiation transcript, `/draft-email Apex`

**Greenfield Analytics — Lost Deal, Coaching Opportunity:**
CRM record (likely Closed Lost) → Weak discovery call transcript (Alex, feature-dumped) → Email thread (ghosted, lost to CompetitorAlpha, 4 emails)
Tests: `/coach feedback` with weak transcript (should give tough but constructive feedback), `/draft-email Greenfield` (win-back email)

**Velocity Retail — Troubled Demo:**
CRM record (at risk) → Bad demo call transcript (Alex, ignored CTO's technical questions)
Tests: `/coach feedback` with bad demo transcript (should flag feature touring, ignoring prospect needs, loss of CTO credibility)

**TerraLogistics — Lost Deal Postmortem:**
Meeting notes (lost deal review with root cause analysis and coaching plan for Alex) → CRM record (Closed Lost)
Tests: `/coach feedback` reference material, `/pipeline` should NOT show this in active pipeline

**Stratos Energy — New Prospect:**
Cold call transcript (successful, Nina, earned meeting + got enablement lead added) → No deal yet → CRM company record exists
Tests: `/research Stratos` (new prospect, limited CRM history), `/coach feedback` with cold call (should praise)

**Pinnacle Financial Group — Upcoming Discovery (FinServ):**
Meeting prep notes (discovery call with VP Sales + CDO, FinServ compliance concerns) → No deal yet → CRM company record exists
Tests: `/research Pinnacle` (should pull FinServ ICP context, flag compliance review timeline)

**CloudBridge Systems — Existing Customer, Expansion:**
Meeting notes (QBR recap: 9-week ramp, 92% adoption, NPS 9/10, expanding from 30→45 users) → Case study (full success story) → CRM record exists
Tests: `/deal CloudBridge` (should show expansion opportunity), case study content should appear in RAG for reference in other deals

---

## DATA RELATIONSHIPS MAP

```
COMPANY          CALL TRANSCRIPT       EMAIL THREAD          MEETING NOTES         CASE STUDY
─────────────    ─────────────────     ──────────────        ────────────          ──────────
NovaTech    ←──→ discovery (good)  ←──→ proposal+security ←──→ demo prep              —
Apex        ←──→ negotiation (good)←──→ contract+GDPR         —              ←──→ case_study_apex
Greenfield  ←──→ discovery (weak) ←──→ gone cold              —                       —
Velocity    ←──→ demo (bad)            —                      —                       —
TerraLog         —                     —                 ←──→ lost deal postmortem     —
Stratos     ←──→ cold call (good)      —                      —                       —
Pinnacle         —                     —                 ←──→ discovery prep           —
CloudBridge      —                     —                 ←──→ QBR recap         ←──→ case_study_cloudbridge
```

All companies exist in `companies.json`, `contacts.json`, and `deals.json`. The arrows show which companies have additional data types available for richer testing.
