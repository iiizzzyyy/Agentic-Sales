"""
Synthetic Data Generator for Sales AI Agents POC
=================================================
Generates realistic fake data for testing all 5 slash commands without
needing a live HubSpot account, real playbooks, or BigQuery tables.

Creates:
  1. data/playbooks/  — Objection scripts, battle cards, ICPs, email templates (for RAG)
  2. data/mock_crm/   — Companies, contacts, deals, activities (JSON, mocks HubSpot responses)
  3. data/mock_bq/    — Pipeline analytics CSV (mocks BigQuery query results)
  4. data/mock_crm/call_transcripts/  — Realistic sales call transcripts (for Coach feedback)
  5. data/mock_crm/email_threads/     — Email conversation threads (for context + email drafting)
  6. data/mock_crm/meeting_notes/     — Meeting prep and recap notes (for Coach prep)

Usage:
  python scripts/generate_test_data.py

After running:
  - Index playbooks into ChromaDB:  python scripts/index_playbooks.py
  - Mock CRM data is used by the test harness (or swap in when HubSpot MCP isn't connected)
"""

import json
import os
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOK_DIR = os.path.join(BASE_DIR, "data", "playbooks")
MOCK_CRM_DIR = os.path.join(BASE_DIR, "data", "mock_crm")
MOCK_BQ_DIR = os.path.join(BASE_DIR, "data", "mock_bq")

CALL_TRANSCRIPTS_DIR = os.path.join(MOCK_CRM_DIR, "call_transcripts")
EMAIL_THREADS_DIR = os.path.join(MOCK_CRM_DIR, "email_threads")
MEETING_NOTES_DIR = os.path.join(MOCK_CRM_DIR, "meeting_notes")

os.makedirs(PLAYBOOK_DIR, exist_ok=True)
os.makedirs(MOCK_CRM_DIR, exist_ok=True)
os.makedirs(MOCK_BQ_DIR, exist_ok=True)
os.makedirs(CALL_TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(EMAIL_THREADS_DIR, exist_ok=True)
os.makedirs(MEETING_NOTES_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# SEED DATA — names, companies, industries
# ---------------------------------------------------------------------------
COMPANIES = [
    {"name": "NovaTech Solutions", "domain": "novatech.io", "industry": "Enterprise Software", "size": "250-500", "hq": "Austin, TX"},
    {"name": "Greenfield Analytics", "domain": "greenfieldanalytics.com", "industry": "Data Analytics", "size": "50-100", "hq": "Denver, CO"},
    {"name": "Meridian Healthcare", "domain": "meridianhc.com", "industry": "Healthcare Tech", "size": "1000-5000", "hq": "Boston, MA"},
    {"name": "Apex Manufacturing", "domain": "apexmfg.com", "industry": "Manufacturing", "size": "500-1000", "hq": "Detroit, MI"},
    {"name": "CloudBridge Systems", "domain": "cloudbridge.dev", "industry": "Cloud Infrastructure", "size": "100-250", "hq": "San Francisco, CA"},
    {"name": "TerraLogistics", "domain": "terralogistics.com", "industry": "Supply Chain", "size": "250-500", "hq": "Chicago, IL"},
    {"name": "Pinnacle Financial Group", "domain": "pinnaclefg.com", "industry": "Financial Services", "size": "500-1000", "hq": "New York, NY"},
    {"name": "Velocity Retail", "domain": "velocityretail.co", "industry": "Retail Tech", "size": "100-250", "hq": "Seattle, WA"},
    {"name": "Stratos Energy", "domain": "stratosenergy.com", "industry": "Clean Energy", "size": "50-100", "hq": "Houston, TX"},
    {"name": "Horizon Education", "domain": "horizonedu.org", "industry": "EdTech", "size": "50-100", "hq": "Portland, OR"},
]

FIRST_NAMES = ["Sarah", "James", "Maria", "David", "Lisa", "Michael", "Priya", "Carlos", "Emma", "Wei",
               "Rachel", "Tom", "Fatima", "Alex", "Nina", "Robert", "Aisha", "Daniel", "Yuki", "Marcus"]

LAST_NAMES = ["Chen", "Williams", "Patel", "Rodriguez", "Thompson", "Kim", "O'Brien", "Nakamura",
              "Fischer", "Okafor", "Santos", "Johansson", "Ahmed", "Kowalski", "Dubois", "Singh"]

TITLES = ["VP of Engineering", "CTO", "Head of Operations", "CFO", "Director of IT",
          "VP of Sales", "Chief Data Officer", "Head of Procurement", "CEO", "Director of Digital Transformation"]

DEAL_STAGES = ["Discovery", "Qualification", "Demo Scheduled", "Proposal Sent", "Negotiation", "Closed Won", "Closed Lost"]
DEAL_STAGE_WEIGHTS = [0.15, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05]

OBJECTION_CATEGORIES = ["Price", "Timing", "Competition", "Authority", "Need", "Trust", "Integration"]

# ---------------------------------------------------------------------------
# 1. GENERATE PLAYBOOK FILES (for RAG)
# ---------------------------------------------------------------------------

def generate_objection_scripts():
    """Generate a comprehensive objection handling playbook."""
    content = """# Sales Objection Handling Playbook
## Version 2.1 — Updated Q1 2026

### How to Use This Document
When a prospect raises an objection, identify the category below and follow the framework:
**Acknowledge → Question → Reframe → Advance**

---

## PRICE OBJECTIONS

### "Your solution is too expensive"
**Acknowledge:** "I completely understand budget is a key consideration."
**Question:** "When you say too expensive, are you comparing to a specific alternative, or is it about the total investment?"
**Reframe:** "Let me walk you through the ROI our customers typically see. On average, teams recover the investment within 4.2 months through [time savings / error reduction / revenue increase]."
**Advance:** "Would it help if I put together a custom ROI model based on your team's numbers?"

### "We don't have the budget right now"
**Acknowledge:** "Budget cycles are real — I appreciate you being upfront about that."
**Question:** "When does your next budget cycle open? And is this something that would be prioritized if budget were available?"
**Reframe:** "Many of our customers started with our starter tier at $X/month to prove value before the next budget cycle. That way you're not waiting 6 months to start seeing results."
**Advance:** "Could we set up a pilot that fits within discretionary spending limits?"

### "Competitor X is 30% cheaper"
**Acknowledge:** "That's a fair point — price matters."
**Question:** "Beyond price, what are the top 3 things that matter most for this decision?"
**Reframe:** "When our customers compared us to [Competitor X], they found that the implementation time was 3x longer and the total cost of ownership over 3 years was actually higher because of [hidden costs / add-on fees / professional services]. Let me share a comparison one of our customers put together."
**Advance:** "Would a side-by-side TCO comparison be helpful for your evaluation?"

---

## TIMING OBJECTIONS

### "We're not ready to make a decision yet"
**Acknowledge:** "No pressure at all — timing is important."
**Question:** "What would need to happen internally before you'd be ready to move forward?"
**Reframe:** "Totally fair. What I've seen work well is getting the technical evaluation done now, so when the timing is right, you're not starting from scratch. That usually saves 4-6 weeks."
**Advance:** "Would it make sense to start a technical proof-of-concept while you sort out the internal timeline?"

### "We just signed a contract with another vendor"
**Acknowledge:** "Got it — you've already made a commitment."
**Question:** "How long is the contract? And how's it going so far?"
**Reframe:** "I hear you. A lot of our best customers came to us after their current contract ended because they had already done a thorough evaluation. Let me stay in touch so we're ready when that time comes."
**Advance:** "Can I check in with you [3 months before renewal]? In the meantime, I'll send you our quarterly product updates so you can see how we're evolving."

---

## AUTHORITY OBJECTIONS

### "I need to get buy-in from my team / leadership"
**Acknowledge:** "Makes total sense — these decisions are rarely made alone."
**Question:** "Who else is involved in the decision? What are their main concerns likely to be?"
**Reframe:** "I can help with that. I've put together a one-pager specifically for [CFOs / CTOs / procurement] that addresses their typical questions. I can also join a call with them if that would help."
**Advance:** "Would it be useful if I prepared a brief for your leadership team? I just need to know their top 3 priorities."

### "Our CTO wants to build this in-house"
**Acknowledge:** "Your CTO's instinct makes sense — having full control is appealing."
**Question:** "Has the team scoped out the build? Do you know the estimated timeline and resources needed?"
**Reframe:** "We've seen this play out at a few companies. The build usually takes 2-3x longer than estimated, and the opportunity cost of pulling your engineering team off product work is significant. One of our customers, [Company X], estimated a 6-month build — it turned into 14 months. They switched to us and were live in 3 weeks."
**Advance:** "What if we ran a 2-week pilot alongside the scoping exercise? That way you have real data to compare build vs. buy."

---

## COMPETITION OBJECTIONS

### "We're also evaluating [Competitor Name]"
**Acknowledge:** "Smart — you should absolutely evaluate your options."
**Question:** "What criteria are most important to your evaluation? And where does [Competitor] look strong to you so far?"
**Reframe:** "Great that you're being thorough. The areas where we consistently win are [differentiation 1], [differentiation 2], and [differentiation 3]. I'd love for you to test both on those specific dimensions."
**Advance:** "Can I share a few evaluation questions that our happiest customers wish they'd asked during their process? They're vendor-neutral — just designed to help you make the best decision."

---

## NEED / FIT OBJECTIONS

### "We don't really have that problem"
**Acknowledge:** "Appreciate you being direct."
**Question:** "How is your team currently handling [the pain point]? What does that process look like day to day?"
**Reframe:** "Interesting — a lot of our customers didn't realize the scope of the issue until they measured it. For example, [Customer X] thought their process was fine, but when they tracked it, they were losing 12 hours per rep per week on manual data entry."
**Advance:** "Would a quick diagnostic be useful? It takes 15 minutes and shows you exactly where time is going."

### "We tried something similar before and it didn't work"
**Acknowledge:** "That's frustrating — bad past experiences are hard to shake."
**Question:** "What went wrong? Was it the technology, the implementation, or the adoption?"
**Reframe:** "That feedback is super valuable. The #1 reason these projects fail is [poor onboarding / lack of integration / wrong use case]. We've built our entire implementation process around avoiding those exact pitfalls — dedicated CSM, 30-day onboarding, weekly check-ins."
**Advance:** "Would it help to talk to a customer who had a similar bad experience before switching to us?"

---

## QUICK REFERENCE: OBJECTION RESPONSE CHEAT SHEET

| Objection Type | First Response | Key Move |
|---|---|---|
| Price | Acknowledge, ask what they're comparing to | Shift to ROI / TCO |
| Timing | Acknowledge, ask what needs to happen | Suggest pilot or technical eval now |
| Authority | Acknowledge, ask who's involved | Offer to help build the internal case |
| Competition | Acknowledge, ask their evaluation criteria | Differentiate on specific dimensions |
| Need | Acknowledge, ask about current process | Quantify the hidden cost |
| Past failure | Acknowledge, ask what went wrong | Show how you prevent the same failure |
| Trust | Acknowledge, ask what would build confidence | Offer references, pilot, or guarantee |

---

*Last updated: January 2026. Contact Sales Enablement for questions.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "objection_handling_playbook.md"), "w") as f:
        f.write(content)
    print("  ✓ objection_handling_playbook.md")


def generate_battle_cards():
    """Generate competitive battle cards."""
    content = """# Competitive Battle Cards
## Q1 2026 — Confidential: Internal Use Only

---

## BATTLE CARD: vs. CompetitorAlpha

**Their Positioning:** "All-in-one platform for revenue teams"
**Their Strengths:**
- Lower entry price ($49/user/month vs. our $79/user/month)
- Good brand recognition in SMB market
- Native dialer built in

**Their Weaknesses:**
- No AI coaching — only call recording and transcription
- Analytics are surface-level (no pipeline health scoring)
- Integration ecosystem is limited (12 integrations vs. our 45+)
- Customer support rated 3.2/5 on G2 (ours: 4.7/5)
- No BigQuery/data warehouse connector

**How to Win:**
1. Lead with AI coaching differentiation — live roleplay, personalized feedback
2. Show the integration depth (especially HubSpot, Salesforce, BigQuery)
3. Use the TCO calculator — their add-ons for analytics and integrations push the real cost above ours
4. Reference win story: "TerraLogistics switched from CompetitorAlpha after 8 months. They saw 34% improvement in close rates within the first quarter with us."

**Landmine Questions to Plant:**
- "How does their AI coaching handle personalized feedback based on your specific playbook?"
- "Can you connect it to your data warehouse for custom pipeline analytics?"
- "What's the implementation timeline and who manages it?"

---

## BATTLE CARD: vs. CompetitorBeta

**Their Positioning:** "Enterprise conversation intelligence"
**Their Strengths:**
- Strong in enterprise (Fortune 500 logos)
- Advanced call analytics and sentiment analysis
- SOC 2 Type II certified
- Good product marketing and analyst coverage

**Their Weaknesses:**
- Pricing is opaque and very high ($150-300/user/month)
- Requires 6-month implementation with professional services ($50K+)
- Limited to call analysis — no proactive coaching or role-play
- Locked into annual contracts with auto-renewal
- Their AI is retrospective only — no real-time guidance

**How to Win:**
1. Speed to value — we're live in 2 weeks, they take 6 months
2. Proactive vs. reactive — we coach before the call, not just analyze after
3. Pricing transparency — show our simple per-user pricing vs. their enterprise quotes
4. Flexibility — monthly contracts, no lock-in

**Landmine Questions to Plant:**
- "How long from signature to your first rep actually using the product?"
- "Does it help reps prepare before calls, or only analyze after?"
- "What's the total cost including implementation and professional services?"

---

## BATTLE CARD: vs. "Do Nothing" / Build In-House

**Their Positioning:** "We can build this ourselves" or "We don't need a tool for this"
**Why They Think This:**
- Engineering team is confident they can build it
- Budget concerns — tools are a recurring cost
- Desire for full customization and control
- Privacy/security concerns about third-party tools

**Reality Check:**
- Average build time: 12-18 months (they'll estimate 3-6)
- Requires ML/AI expertise most sales teams don't have
- Maintenance burden: 1-2 FTEs ongoing just to keep it running
- Opportunity cost: every engineer on this is NOT building product features
- They'll rebuild what we've spent 4 years and $20M perfecting

**How to Win:**
1. Ask: "What's the fully-loaded cost of an ML engineer for 12 months?" (answer: $250-400K)
2. Show time-to-value: "Your reps could be using AI coaching next week, or in 18 months"
3. Offer a pilot: "Let's prove the value in 2 weeks. If the ROI isn't there, no harm done."
4. Reference: "CloudBridge Systems started building in-house, spent $380K over 14 months, then switched to us and were live in 11 days."

**Landmine Questions:**
- "What's the opportunity cost of pulling engineers off your product roadmap?"
- "Who on the team has experience building and maintaining ML models in production?"
- "What happens when the engineer who built it leaves?"

---

## BATTLE CARD: vs. CompetitorGamma

**Their Positioning:** "AI-powered sales engagement platform"
**Their Strengths:**
- Excellent email sequencing and cadence management
- Good Salesforce integration
- Established market presence (IPO'd 2023)

**Their Weaknesses:**
- AI features are bolt-on acquisitions, not natively built
- No coaching or roleplay — focused on outbound automation
- Customer churn rate estimated at 18% annually
- Recent layoffs and product team restructuring (Q4 2025)
- Email deliverability issues reported by multiple customers on G2

**How to Win:**
1. Position as complementary first, then replacement — "we handle the coaching and intelligence layer"
2. Highlight our native AI vs. their acquired/bolted-on approach
3. Use their instability as a risk factor — "are you confident they'll still be investing in this product in 2 years?"
4. Show breadth — we do coaching + research + pipeline health, not just email sequences

---

*Updated monthly by Product Marketing. Slack #competitive-intel for real-time updates.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "competitive_battle_cards.md"), "w") as f:
        f.write(content)
    print("  ✓ competitive_battle_cards.md")


def generate_icps():
    """Generate Ideal Customer Profile documents."""
    content = """# Ideal Customer Profiles (ICPs)
## Target Market Segmentation — 2026

---

## ICP TIER 1: Mid-Market SaaS Companies

**Company Profile:**
- Revenue: $10M - $100M ARR
- Employees: 100-500
- Sales team size: 10-50 reps
- Industry: B2B SaaS, Technology
- Tech stack: HubSpot or Salesforce CRM, Slack, modern tooling
- Growth stage: Series B through Series D

**Key Personas:**

### VP of Sales / Head of Sales
- **Pain points:** Inconsistent rep performance, long ramp time for new hires (avg 7 months), no visibility into what top reps do differently, coaching is ad-hoc and unscalable
- **Goals:** Reduce ramp time to 3 months, improve team close rate by 20%, create a scalable coaching program
- **Objections likely:** Budget, need to prove ROI first, already using call recording tools
- **Trigger events:** New VP hired, missed quota 2 quarters in a row, preparing for Series C/D fundraise
- **How we win:** Show the coaching ROI calculator, offer a pilot with 5 reps, reference similar-stage SaaS wins

### CTO / VP of Engineering
- **Pain points:** Sales wants to buy another tool, concerned about data security, integration burden on eng team
- **Goals:** Minimize integration work, ensure data stays secure, avoid shadow IT
- **Objections likely:** Security concerns, "we can build this," integration complexity
- **Trigger events:** Board pushing for AI adoption, sales team requesting better tooling
- **How we win:** SOC 2 compliance, API-first architecture, MCP integration (zero custom code), 2-week implementation with no eng resources needed

### CFO / Finance Lead
- **Pain points:** Sales tool sprawl and cost, unclear ROI on existing tools, quota attainment declining
- **Goals:** Consolidate tools, prove ROI on every dollar spent, improve sales efficiency metrics
- **Objections likely:** Price, want to see ROI before committing, prefer annual billing for discount
- **Trigger events:** Budget planning season, board pressure on unit economics, preparing for fundraise
- **How we win:** TCO analysis showing consolidation savings, ROI guarantee, flexible monthly billing

---

## ICP TIER 2: Enterprise Companies (New Market Expansion)

**Company Profile:**
- Revenue: $100M - $1B
- Employees: 500-5000
- Sales team size: 50-200 reps
- Industry: Financial Services, Healthcare, Manufacturing
- Tech stack: Salesforce Enterprise, Microsoft ecosystem
- Buying process: Long (6-12 months), involves procurement

**Key Personas:**

### Chief Revenue Officer (CRO)
- **Pain points:** Forecast accuracy below 70%, inconsistent methodology across regions, no way to measure coaching impact
- **Goals:** Improve forecast accuracy to 85%+, standardize sales methodology globally, prove coaching drives revenue
- **Objections likely:** Security review required, integration with existing tech stack, change management concerns
- **Trigger events:** New CRO hired (first 90 days), missed annual target, post-acquisition team integration
- **How we win:** Enterprise security package, methodology-agnostic coaching, global deployment references

### Head of Sales Enablement
- **Pain points:** Content goes unused, training doesn't stick, can't measure what works, reps ignore the LMS
- **Goals:** Create a coaching culture, measure training impact on pipeline, reduce content creation burden
- **Objections likely:** Already invested in LMS, reps won't adopt another tool, customization requirements
- **Trigger events:** New enablement hire, annual SKO planning, low adoption scores on existing tools
- **How we win:** Show how AI coaching replaces boring LMS modules, integration with existing content, adoption metrics dashboard

---

## ICP TIER 3: High-Growth Startups

**Company Profile:**
- Revenue: $1M - $10M ARR
- Employees: 20-100
- Sales team size: 3-15 reps
- Industry: Any B2B
- Tech stack: HubSpot CRM, Slack, scrappy tooling
- Growth stage: Seed through Series A

**Key Personas:**

### Founder / CEO (acting as sales leader)
- **Pain points:** Doing everything themselves, can't clone their sales knowledge, first sales hires are underperforming
- **Goals:** Codify the founder's sales playbook, ramp first hires faster, build a repeatable process
- **Objections likely:** Budget-constrained, "I can just coach them myself," not sure they need AI
- **Trigger events:** First 3 sales hires, product-market fit achieved, first $1M ARR milestone
- **How we win:** Show how the AI captures their playbook and scales it, starter tier pricing, time savings argument (founder's time is the most expensive resource)

---

## DISQUALIFICATION CRITERIA

Do NOT pursue if:
- Company has fewer than 3 sales reps (not enough scale for ROI)
- No CRM in place (they need basic infrastructure first)
- Exclusively inbound/PLG motion with no outbound sales team
- Active RFP with competitor where we weren't invited (usually means it's wired)
- IT security review would take >6 months (deal will die)

---

## VERTICAL-SPECIFIC NOTES

### Healthcare
- HIPAA compliance is table stakes — lead with our BAA
- Longer sales cycles (avg 9 months) — budget for it
- Procurement involvement from day 1 — get MSA process started early

### Financial Services
- Data residency requirements — confirm regional hosting
- Compliance team will review AI outputs — have examples of guardrails
- Reference other FinServ logos heavily — they buy in herds

### Manufacturing
- Digital transformation is the entry point — they're modernizing everything
- Less tech-savvy buyers — demo must be simple and visual
- Long decision chains — identify the economic buyer early

---

*Maintained by Revenue Operations. Updated quarterly. Slack #icp-updates for changes.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "ideal_customer_profiles.md"), "w") as f:
        f.write(content)
    print("  ✓ ideal_customer_profiles.md")


def generate_email_templates():
    """Generate email follow-up templates playbook."""
    content = """# Email Templates & Follow-Up Playbook
## Sales Outreach Best Practices — 2026

---

## POST-DISCOVERY CALL FOLLOW-UP

**When to send:** Within 2 hours of the discovery call
**Subject line formula:** [Their Pain Point] + next step

### Template 1: Standard Follow-Up

Subject: Reducing your rep ramp time — next steps

Hi {first_name},

Great speaking with you today. I really appreciated your honesty about {specific_pain_point_discussed}.

Here's what I took away from our conversation:
- {key_challenge_1}
- {key_challenge_2}
- You're looking to {their_goal} by {their_timeline}

As promised, I'm attaching {resource_mentioned}. I think you'll find the section on {specific_section} especially relevant given what you shared about {their_situation}.

For next steps, I'd suggest {proposed_next_step}. I have availability on {date_1} and {date_2} — do either of those work?

Best,
{sender_name}

### Template 2: After a Strong Discovery

Subject: {Company} + [Our Company] — the path to {their_goal}

Hi {first_name},

I left our call genuinely excited about what we could do together. The way your team is approaching {initiative} is exactly where we see the biggest impact.

Three things stood out to me:
1. {insight_from_call}
2. {second_insight}
3. {third_insight}

I've already started putting together a {custom deliverable — ROI model / integration plan / pilot proposal} based on what you shared. I should have it ready by {date}.

In the meantime, I thought this case study from {similar_company} might resonate — they had a very similar situation and saw {specific_result}.

Talk soon,
{sender_name}

---

## POST-DEMO FOLLOW-UP

**When to send:** Within 1 hour of the demo
**Subject line formula:** [Action item from demo] + timeline

### Template 3: Demo Recap

Subject: Your custom {product} walkthrough — recording + next steps

Hi {first_name},

Thanks for making time for the demo today. Great questions from {other_attendee_names} — especially about {specific_question_asked}.

Here's what we covered:
- {feature_1} → addresses your {pain_point_1}
- {feature_2} → solves {pain_point_2}
- {integration} → connects with your existing {tool}

Recording link: {link}

You mentioned wanting to {their_requested_next_step}. I can set that up — just need:
1. {requirement_1}
2. {requirement_2}

Can we book 15 minutes on {date} to kick that off?

Best,
{sender_name}

---

## PROPOSAL FOLLOW-UP (NO RESPONSE)

**Cadence:** Day 3, Day 7, Day 14, Day 21 (then re-evaluate)

### Template 4: Day 3 — Soft Nudge

Subject: Re: {original_proposal_subject}

Hi {first_name},

Just floating this back to the top of your inbox. I know things get busy.

Any questions on the proposal? Happy to jump on a quick call to walk through anything.

{sender_name}

### Template 5: Day 7 — Add Value

Subject: Thought of you — {relevant_insight}

Hi {first_name},

Came across this {article/report/data point} about {their_industry} and immediately thought of our conversation about {their_challenge}.

{One sentence summary of the insight and why it's relevant.}

Also — still here whenever you're ready to discuss the proposal. No rush, just want to make sure I'm being helpful.

{sender_name}

### Template 6: Day 14 — Direct

Subject: {first_name} — should I close this out?

Hi {first_name},

I want to be respectful of your time. We sent over the proposal on {date} and I haven't heard back.

Totally understand if the timing isn't right. Could you let me know:
(a) You're still interested but need more time
(b) You've gone in a different direction
(c) Something else came up — let's reconnect in {timeframe}

Any answer is a good answer. Just don't want to keep pinging you if it's not helpful.

{sender_name}

---

## COLD OUTREACH

### Template 7: Pattern Interrupt — VP Level

Subject: {Their company} and the {specific_metric} problem

{first_name},

{Competitor/peer company} just cut their rep ramp time from 7 months to 11 weeks. Their VP of Sales told me the biggest unlock was {specific insight}.

You're probably dealing with the same challenge at {company} — especially with {observation about their situation, e.g., "your 15 open sales roles on LinkedIn"}.

Worth a 15-minute conversation? I've got some data from {their_industry} that might change how you think about this.

{sender_name}

### Template 8: Post-Event / Post-Content Engagement

Subject: Saw you at {event} / liked your post about {topic}

Hi {first_name},

{Personal connection — "Enjoyed your panel at SaaStr" or "Your LinkedIn post about AI in sales really resonated"}.

It got me thinking — you mentioned {specific point from their content}. That's exactly the problem we're solving for teams like {reference_customer}.

Curious if you've explored using AI coaching to {connect to their stated interest}? I have a few ideas that might be relevant.

Open to a quick chat?

{sender_name}

---

## EMAIL BEST PRACTICES

### Subject Lines That Work
- Specific > Generic: "Reducing ramp time from 7 months to 11 weeks" beats "Quick question"
- Questions perform well: "How is {company} handling rep onboarding?"
- Name-drop when relevant: "{Peer company} just did this..."
- Keep under 50 characters for mobile

### Body Copy Rules
- First sentence must earn the second sentence
- Max 150 words for cold outreach, 250 for follow-ups
- One CTA per email — don't give them choices
- No attachments on first touch — links are fine
- Personalization must be genuine, not just {first_name} merge tags
- Mobile-first: short paragraphs, no walls of text

### Timing
- Best days: Tuesday, Wednesday, Thursday
- Best times: 8:00-9:00 AM or 5:00-6:00 PM (their timezone)
- Avoid: Monday morning, Friday afternoon
- Follow-up cadence: 3-3-7-7-14 (days between touches)

---

*Maintained by Sales Enablement. Submit new templates in #email-templates.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "email_templates_playbook.md"), "w") as f:
        f.write(content)
    print("  ✓ email_templates_playbook.md")


def generate_sales_methodology():
    """Generate a sales methodology playbook."""
    content = """# Sales Methodology Playbook
## The Discovery-to-Close Framework — 2026

---

## STAGE 1: DISCOVERY

**Goal:** Understand the prospect's world — pain, goals, timeline, stakeholders.

### The SPIN Framework (adapted)

**Situation Questions** (2-3 max — do your homework first):
- "Walk me through how your team currently handles [process]."
- "How many reps do you have, and how are they structured?"
- "What tools are you using today for [relevant function]?"

**Problem Questions** (the meat of discovery):
- "What's the biggest challenge your team faces with [area]?"
- "When that happens, what's the impact on [revenue / timeline / team]?"
- "How long has this been an issue?"

**Implication Questions** (make the pain real):
- "If nothing changes, what does that mean for your [quota / goals / team] this year?"
- "How does that affect your ability to [strategic initiative]?"
- "What's the cost of that in terms of [time / money / opportunity]?"

**Need-Payoff Questions** (let them sell themselves):
- "If you could fix [pain point], what would that mean for your team?"
- "How would solving this impact your [metric]?"
- "What would it be worth to get [desired outcome]?"

### Discovery Call Structure (30 minutes)
1. **Rapport & Agenda** (3 min): Confirm time, set expectations
2. **Their World** (10 min): Situation + Problem questions
3. **Impact** (7 min): Implication questions — quantify the pain
4. **Vision** (5 min): Need-payoff — what does good look like?
5. **Next Steps** (5 min): Who else is involved? What's the timeline? Schedule demo.

### What Good Discovery Looks Like
- You talk less than 40% of the time
- You uncover at least 2 specific pain points with quantified impact
- You identify the decision-maker AND the process
- The prospect mentions their timeline unprompted
- You have a clear next step booked before hanging up

---

## STAGE 2: QUALIFICATION (MEDDPICC)

Use MEDDPICC to qualify every deal:

| Letter | Element | Key Question |
|--------|---------|-------------|
| M | Metrics | "What specific metrics would define success?" |
| E | Economic Buyer | "Who ultimately signs off on this?" |
| D | Decision Criteria | "What are the top 3 things you'll evaluate?" |
| D | Decision Process | "Walk me through your buying process — what happens after the demo?" |
| P | Paper Process | "Does this need legal/procurement review? How long does that take?" |
| I | Identify Pain | "What's the #1 problem you need to solve?" |
| C | Champion | "Who internally is pushing for this solution?" |
| C | Competition | "Who else are you evaluating?" |

### Qualification Scoring
- **Strong (8-10):** All MEDDPICC elements identified, champion engaged, timeline < 90 days
- **Medium (5-7):** Most elements identified, some gaps in process or authority
- **Weak (1-4):** Missing economic buyer, no clear pain, no timeline — deprioritize

---

## STAGE 3: DEMO / PRESENTATION

### Demo Structure (45 minutes)
1. **Recap Discovery** (5 min): "Last time we discussed [pain 1] and [pain 2]. Still accurate?"
2. **Tailored Demo** (25 min): Show ONLY features that address THEIR pain points
3. **Social Proof** (5 min): "Here's how [similar company] achieved [result]"
4. **Open Discussion** (5 min): Questions, concerns, reactions
5. **Next Steps** (5 min): Propose specific next step with date

### Demo Rules
- NEVER do a feature tour. Map every feature to a pain point from discovery.
- If you haven't done discovery, don't demo. Reschedule.
- Pause after showing key features: "How would this work for your team?"
- Record every demo (with permission) — use for coaching.
- If the prospect goes quiet, they're confused or disengaged. Stop and ask.

---

## STAGE 4: PROPOSAL & NEGOTIATION

### Proposal Best Practices
- Send within 24 hours of the demo
- Include: Executive summary, proposed solution, pricing, timeline, ROI estimate
- Keep it under 5 pages — they won't read more
- Always include 3 pricing options (Good / Better / Best)

### Negotiation Framework
- Never discount without getting something in return
- Trade, don't cave: "I can do X if you can commit to Y"
- Common trades: Multi-year for lower price, faster timeline for standard pricing, case study agreement for extra features
- Walk-away point: Know it before the conversation starts

---

## STAGE 5: CLOSE

### Closing Techniques
- **Assumptive Close:** "I'll send over the contract. Any preference on start date?"
- **Timeline Close:** "You mentioned wanting to be live by Q2. Working backward, we'd need to start implementation by [date]. Should we lock that in?"
- **Summary Close:** "So we've agreed on [scope], [price], and [timeline]. The next step is getting the contract signed. I'll send it over today."

### Common Close Killers (and how to prevent them)
- **No urgency:** Create it early by tying to their goals/timeline
- **Ghost after proposal:** Set clear follow-up expectations during the demo
- **Procurement delays:** Ask about the paper process in discovery (MEDDPICC)
- **New stakeholder appears:** Map all stakeholders early, ask "who else should be involved?"
- **Budget freeze:** Propose smaller pilot or phased rollout

---

*This methodology is the foundation of our sales motion. Every rep should internalize these stages. Coaching sessions should reference specific methodology elements.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "sales_methodology.md"), "w") as f:
        f.write(content)
    print("  ✓ sales_methodology.md")


# ---------------------------------------------------------------------------
# 2. GENERATE MOCK CRM DATA (mimics HubSpot API responses)
# ---------------------------------------------------------------------------

def generate_contacts():
    """Generate realistic contacts linked to companies."""
    contacts = []
    for company in COMPANIES:
        num_contacts = random.randint(1, 3)
        for _ in range(num_contacts):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            title = random.choice(TITLES)
            contacts.append({
                "id": f"contact_{random.randint(100000, 999999)}",
                "properties": {
                    "firstname": first,
                    "lastname": last,
                    "email": f"{first.lower()}.{last.lower()}@{company['domain']}",
                    "jobtitle": title,
                    "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
                    "company": company["name"],
                    "lifecyclestage": random.choice(["lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer"]),
                    "lastmodifieddate": (datetime.now() - timedelta(days=random.randint(0, 60))).isoformat(),
                },
                "associations": {
                    "company_id": company["name"].lower().replace(" ", "_"),
                }
            })
    return contacts


def generate_companies():
    """Generate company records matching the seed data."""
    records = []
    for company in COMPANIES:
        records.append({
            "id": company["name"].lower().replace(" ", "_"),
            "properties": {
                "name": company["name"],
                "domain": company["domain"],
                "industry": company["industry"],
                "numberofemployees": company["size"],
                "city": company["hq"].split(", ")[0],
                "state": company["hq"].split(", ")[1] if ", " in company["hq"] else "",
                "annualrevenue": str(random.choice([5, 10, 15, 25, 50, 75, 100, 150]) * 1_000_000),
                "description": f"{company['name']} is a {company['industry'].lower()} company headquartered in {company['hq']} with {company['size']} employees.",
                "createdate": (datetime.now() - timedelta(days=random.randint(90, 365))).isoformat(),
                "lastmodifieddate": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
            }
        })
    return records


def generate_deals(contacts):
    """Generate deals associated with companies and contacts."""
    deals = []
    deal_names = [
        "{company} — Annual Platform License",
        "{company} — Enterprise Expansion",
        "{company} — Pilot Program",
        "{company} — Q1 Renewal",
        "{company} — New Department Rollout",
        "{company} — Professional Services Add-On",
        "{company} — Multi-Year Agreement",
    ]

    for company in COMPANIES:
        num_deals = random.randint(1, 2)
        company_contacts = [c for c in contacts if c["properties"]["company"] == company["name"]]

        for _ in range(num_deals):
            stage = random.choices(DEAL_STAGES, weights=DEAL_STAGE_WEIGHTS, k=1)[0]
            amount = random.choice([15000, 24000, 36000, 48000, 72000, 96000, 120000, 180000, 250000])
            close_date = datetime.now() + timedelta(days=random.randint(-30, 90))
            create_date = close_date - timedelta(days=random.randint(30, 120))
            last_activity = datetime.now() - timedelta(days=random.randint(0, 45))

            deal_name = random.choice(deal_names).format(company=company["name"])
            associated_contact = random.choice(company_contacts) if company_contacts else None

            deal = {
                "id": f"deal_{random.randint(100000, 999999)}",
                "properties": {
                    "dealname": deal_name,
                    "amount": str(amount),
                    "dealstage": stage.lower().replace(" ", ""),
                    "dealstage_label": stage,
                    "pipeline": "default",
                    "closedate": close_date.strftime("%Y-%m-%d"),
                    "createdate": create_date.isoformat(),
                    "hs_lastmodifieddate": last_activity.isoformat(),
                    "hubspot_owner_id": f"owner_{random.randint(100, 105)}",
                    "description": f"{'Active' if stage not in ['Closed Won', 'Closed Lost'] else stage} deal with {company['name']} for platform access.",
                },
                "associations": {
                    "company": company["name"].lower().replace(" ", "_"),
                    "contact": associated_contact["id"] if associated_contact else None,
                },
            }

            # Add notes/activities
            deal["activities"] = generate_activities(company["name"], associated_contact, stage)

            # Flag deals that are "at risk" for pipeline testing
            days_since_activity = (datetime.now() - last_activity).days
            if days_since_activity > 14 and stage not in ["Closed Won", "Closed Lost"]:
                deal["_test_flag"] = "stale"
            elif close_date < datetime.now() and stage not in ["Closed Won", "Closed Lost"]:
                deal["_test_flag"] = "overdue"

            deals.append(deal)

    return deals


def generate_activities(company_name, contact, stage):
    """Generate realistic CRM activity/note entries for a deal."""
    templates = [
        {
            "type": "NOTE",
            "body": f"Discovery call with {contact['properties']['firstname'] if contact else 'prospect'}. They're currently using a manual process for sales coaching — spending ~2 hours/week per manager. Main pain: inconsistent messaging across the team. Budget: approved for Q1. Decision timeline: 6 weeks.",
            "days_ago": 28,
        },
        {
            "type": "NOTE",
            "body": f"Demo completed. {contact['properties']['firstname'] if contact else 'Prospect'} was impressed with the AI roleplay feature. Their CTO asked about data security and integration with HubSpot. Sent follow-up with SOC 2 report and integration docs. Next step: technical review with their IT team.",
            "days_ago": 21,
        },
        {
            "type": "EMAIL",
            "body": f"Sent proposal to {contact['properties']['email'] if contact else 'prospect'}. Three-tier pricing. Recommended the Professional plan ($79/user/month, 25 users). Included custom ROI model showing 340% return over 12 months.",
            "days_ago": 14,
        },
        {
            "type": "NOTE",
            "body": f"Negotiation call. {company_name} wants a 15% discount. Offered 10% for annual commitment + case study agreement. They're checking with procurement. Decision expected next week.",
            "days_ago": 7,
        },
        {
            "type": "CALL",
            "body": f"Quick check-in call. {contact['properties']['firstname'] if contact else 'Prospect'} says procurement approved the budget. Legal is reviewing the MSA — should be back by Friday. They want to start implementation on the 1st.",
            "days_ago": 3,
        },
        {
            "type": "NOTE",
            "body": f"Competitor alert: {company_name} is also evaluating CompetitorAlpha. Their demo is next Tuesday. Need to send battle card info to champion and reinforce our AI coaching differentiator.",
            "days_ago": 10,
        },
        {
            "type": "NOTE",
            "body": f"Champion call with {contact['properties']['firstname'] if contact else 'internal sponsor'}. They confirmed the CFO is the economic buyer. CFO cares about: ROI timeline, implementation disruption, and integration with existing stack. Prepping a CFO-specific one-pager.",
            "days_ago": 18,
        },
    ]

    # Pick 3-5 activities based on deal stage
    num_activities = min(len(templates), random.randint(3, 5))
    selected = random.sample(templates, num_activities)

    activities = []
    for t in selected:
        activities.append({
            "type": t["type"],
            "body": t["body"],
            "timestamp": (datetime.now() - timedelta(days=t["days_ago"])).isoformat(),
        })

    return sorted(activities, key=lambda x: x["timestamp"], reverse=True)


# ---------------------------------------------------------------------------
# 3. GENERATE MOCK BIGQUERY DATA
# ---------------------------------------------------------------------------

def generate_bq_analytics():
    """Generate pipeline analytics CSV mimicking BigQuery query results."""
    rows = ["date,stage,deal_count,total_value,avg_deal_size,win_rate,avg_days_in_stage"]

    stages = ["Discovery", "Qualification", "Demo Scheduled", "Proposal Sent", "Negotiation"]

    for month_offset in range(6):
        date = (datetime.now() - timedelta(days=30 * month_offset)).strftime("%Y-%m-01")
        for stage in stages:
            deal_count = random.randint(3, 25)
            avg_size = random.randint(20000, 120000)
            total = deal_count * avg_size
            win_rate = round(random.uniform(0.10, 0.45), 2)
            avg_days = random.randint(7, 45)
            rows.append(f"{date},{stage},{deal_count},{total},{avg_size},{win_rate},{avg_days}")

    csv_content = "\n".join(rows)
    with open(os.path.join(MOCK_BQ_DIR, "pipeline_analytics.csv"), "w") as f:
        f.write(csv_content)
    print("  ✓ pipeline_analytics.csv")

    # Also generate a win/loss analysis
    wl_rows = ["quarter,total_won,total_lost,win_rate,avg_won_deal_size,avg_sales_cycle_days,top_loss_reason"]
    loss_reasons = ["Price", "Competitor", "No Decision", "Timing", "Lost Champion"]

    for q in ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1"]:
        won = random.randint(8, 25)
        lost = random.randint(5, 18)
        rate = round(won / (won + lost), 2)
        avg_size = random.randint(30000, 90000)
        cycle = random.randint(35, 85)
        reason = random.choice(loss_reasons)
        wl_rows.append(f"{q},{won},{lost},{rate},{avg_size},{cycle},{reason}")

    csv2 = "\n".join(wl_rows)
    with open(os.path.join(MOCK_BQ_DIR, "win_loss_analysis.csv"), "w") as f:
        f.write(csv2)
    print("  ✓ win_loss_analysis.csv")


# ---------------------------------------------------------------------------
# 4. GENERATE CALL TRANSCRIPTS (for Coach feedback)
# ---------------------------------------------------------------------------

def generate_call_transcripts():
    """Generate realistic sales call transcripts that the Coach can analyze."""
    transcripts = []

    # TRANSCRIPT 1: Good discovery call
    transcripts.append({
        "filename": "discovery_call_novatech_2026-02-18.md",
        "content": """# Call Transcript: Discovery Call — NovaTech Solutions
**Date:** February 18, 2026 | **Duration:** 28 minutes
**Rep:** Jordan Mitchell | **Prospect:** Sarah Chen, VP of Engineering, NovaTech Solutions
**Deal:** NovaTech Solutions — Annual Platform License ($72,000)
**Call Type:** Discovery | **Recording ID:** REC-2026-0218-001

---

**[0:00] Jordan:** Sarah, thanks for making time today. I know you've got a packed schedule. I want to make sure we use these 30 minutes well — my goal is to understand your team's situation and see if there's a genuine fit. Sound good?

**[0:18] Sarah:** Yeah, that works. I've got a hard stop at 2:30 though.

**[0:22] Jordan:** Absolutely, I'll keep us on track. So I did some research ahead of this call — I saw NovaTech just closed a Series C, congrats on that. And you've got about 15 open sales roles on LinkedIn. It seems like you're in a major growth phase. Can you tell me a bit about what's driving that expansion?

**[0:45] Sarah:** Thanks, yeah. We closed the round in December. The board wants us to 3x revenue by end of next year, so we're basically doubling the sales team from 20 to 40 reps over the next two quarters.

**[1:05] Jordan:** That's aggressive growth. When you think about scaling from 20 to 40, what keeps you up at night?

**[1:15] Sarah:** Honestly? Ramp time. Our current reps took about 7 months to hit full quota. If our new hires take that long, we're going to miss our targets for Q3 and Q4. We can't afford that with the board breathing down our necks.

**[1:35] Jordan:** Seven months is actually pretty common for the industry, but I hear you — at your growth rate, it's a real problem. What does your current onboarding look like?

**[1:48] Sarah:** It's... not great. We have a 2-week bootcamp, then they shadow senior reps for a month, and then they're kind of on their own. Our VP of Sales, Marcus, tries to do coaching sessions, but he's stretched thin. He's managing 20 reps and selling himself. The coaching is inconsistent — some reps get weekly 1:1s, others get nothing for weeks.

**[2:18] Jordan:** So if I'm hearing you right, the coaching is ad-hoc and depends entirely on Marcus having time, which is getting scarcer as the team grows?

**[2:28] Sarah:** Exactly. And it's not just the new hires. We've got a big performance gap between our top 3 reps and the rest. The top reps close at 35-40%, the bottom half is at 12-15%. We know the top reps are doing something differently, but we can't figure out how to transfer that knowledge.

**[2:50] Jordan:** That's a 20+ point gap. Have you tried to capture what the top reps do differently?

**[3:00] Sarah:** We tried. We recorded some calls, Marcus wrote up a best practices doc, but honestly nobody reads it. And the recordings just sit in a folder. There's no structured way to learn from them.

**[3:18] Jordan:** What would it mean for the business if you could close that gap? Like if you got the bottom half from 15% to even 25%?

**[3:28] Sarah:** *pauses* That would be massive. Let me think... we've got about 10 reps in that bottom half, average deal size is $48K, they each work about 15 opportunities per quarter. Going from 15% to 25% — that's an extra 1.5 deals per rep per quarter. So roughly $720K in additional quarterly revenue. Yeah, that would more than justify whatever we'd spend.

**[4:02] Jordan:** I appreciate you doing that math live. That's really helpful context. Let me ask about timeline — when are the first batch of new hires starting?

**[4:12] Sarah:** We've got 8 starting March 15th and another 10 in May.

**[4:18] Jordan:** So March 15th is your clock starting. What have you looked at so far to solve this?

**[4:25] Sarah:** We've been looking at call recording tools — Gong, Chorus — but honestly they feel like they're solving the wrong problem. We don't just need to record calls, we need something that actively coaches reps. Our reps don't have time to go back and watch 45-minute recordings.

**[4:48] Jordan:** That's a really important distinction — passive recording versus active coaching. Would it be helpful if I showed you how our AI coaching works? Specifically how it takes your existing playbooks, watches what top reps do, and then actively coaches new hires through roleplays and real-time feedback?

**[5:08] Sarah:** Yeah, that's exactly what we need. But I want to be clear — I'm not the final decision maker on this. Marcus, our VP of Sales, would need to sign off. And anything over $50K needs our CFO, David Thompson.

**[5:25] Jordan:** Good to know. What matters most to Marcus? And what about David?

**[5:32] Sarah:** Marcus cares about results — show him the ramp time data and he's in. David is all about ROI. He'll want to see the numbers, payback period, and how this compares to hiring another sales manager instead.

**[5:48] Jordan:** Perfect. So here's what I'd suggest as a next step — let me put together a quick demo tailored to your specific situation. I'll show the roleplay coaching and the performance analytics. If Marcus is available, I'd love to include him. Then for David, I can prepare a custom ROI model using the numbers you just shared. Does a 45-minute demo work, maybe next Tuesday or Wednesday?

**[6:15] Sarah:** Tuesday at 10am works. I'll get Marcus on the call. Let's leave David for after the demo — I want to make sure Marcus is bought in first.

**[6:28] Jordan:** Smart approach. I'll send over a calendar invite with a brief agenda. And Sarah — I really appreciate you being so open with the numbers today. That helps me make sure the demo is relevant, not generic.

**[6:42] Sarah:** Yeah, no problem. Looking forward to it.

**[6:45] Jordan:** Great, talk to you Tuesday. Have a good rest of your day.

---

**REP'S POST-CALL NOTES:**
- Strong discovery. Sarah quantified the pain herself ($720K/quarter opportunity).
- Decision process: Sarah (champion) → Marcus VP Sales (sign-off) → David CFO (budget >$50K).
- Demo scheduled for Tuesday 10am with Sarah + Marcus.
- Key pain: 7-month ramp time, inconsistent coaching, big gap between top/bottom reps.
- Competition: Looking at Gong/Chorus but doesn't feel they solve the real problem.
- Need to prep: ROI model, ramp time benchmarks, and a roleplay demo.
"""
    })

    # TRANSCRIPT 2: Weak discovery call (for coaching feedback)
    transcripts.append({
        "filename": "discovery_call_greenfield_2026-02-12.md",
        "content": """# Call Transcript: Discovery Call — Greenfield Analytics
**Date:** February 12, 2026 | **Duration:** 18 minutes
**Rep:** Alex Rivera | **Prospect:** Tom Fischer, Director of IT, Greenfield Analytics
**Deal:** Greenfield Analytics — Pilot Program ($24,000)
**Call Type:** Discovery | **Recording ID:** REC-2026-0212-003

---

**[0:00] Alex:** Hey Tom, thanks for hopping on. So I wanted to tell you about our platform and how it can help your sales team.

**[0:08] Tom:** Sure, go ahead.

**[0:10] Alex:** Great. So we're an AI-powered sales coaching platform. We use artificial intelligence to help sales reps improve their performance. We've got roleplay features, call analytics, pipeline management, and integrations with all the major CRMs. We work with companies like NovaTech and Apex Manufacturing. Do you use HubSpot or Salesforce?

**[0:35] Tom:** We're on HubSpot.

**[0:37] Alex:** Perfect, we integrate with HubSpot. So basically what we do is we analyze your sales calls and give reps feedback on how to improve. We also have AI roleplays where reps can practice different scenarios. It's really powerful stuff.

**[0:55] Tom:** Okay, how much does it cost?

**[0:58] Alex:** We have different tiers. Our Professional plan is $79 per user per month, and for your team size — how many reps do you have?

**[1:05] Tom:** About 12.

**[1:07] Alex:** So that would be about $950 a month. But we also have a Starter tier at $49 per user which gives you the core features. And our Enterprise tier has advanced analytics and custom integrations.

**[1:22] Tom:** That's a bit more than we expected. We were looking at CompetitorAlpha and they're about $49 per user.

**[1:30] Alex:** Yeah, CompetitorAlpha is cheaper, but we offer a lot more value. Our AI coaching is way more advanced than theirs. They basically just record calls and transcribe them. We actually coach reps with roleplays and personalized feedback. Plus our integration with HubSpot is deeper.

**[1:48] Tom:** How is it deeper?

**[1:50] Alex:** Well, we pull in all your deal data and use it to contextualize the coaching. So if a rep is working a deal in the negotiation stage, our AI knows that and tailors the coaching accordingly.

**[2:02] Tom:** Interesting. What kind of results do your customers see?

**[2:06] Alex:** Our customers typically see a 20-30% improvement in close rates and they cut ramp time in half. One customer went from 7 months to 11 weeks for new hire ramp time.

**[2:18] Tom:** That sounds good. Can you send me some case studies?

**[2:22] Alex:** Absolutely. I'll send those over. Would it make sense to schedule a demo? I can show you the platform and all the features.

**[2:30] Tom:** Yeah, maybe. Let me look at the case studies first and I'll get back to you.

**[2:35] Alex:** Sounds good. When do you think you'll have time to review them? I don't want to let this slip through the cracks.

**[2:42] Tom:** Probably by next week. I'm pretty busy this week.

**[2:45] Alex:** Okay, how about I follow up next Wednesday?

**[2:48] Tom:** Sure, that works.

**[2:50] Alex:** Great, I'll send the case studies today and follow up Wednesday. Thanks for your time, Tom.

**[2:55] Tom:** Thanks, bye.

---

**REP'S POST-CALL NOTES:**
- Tom seemed interested but not super engaged.
- They're comparing us to CompetitorAlpha.
- Sending case studies, following up next Wednesday.
- 12 reps on HubSpot.
"""
    })

    # TRANSCRIPT 3: Negotiation call
    transcripts.append({
        "filename": "negotiation_call_apex_2026-02-25.md",
        "content": """# Call Transcript: Negotiation Call — Apex Manufacturing
**Date:** February 25, 2026 | **Duration:** 35 minutes
**Rep:** Jordan Mitchell | **Prospect:** David Rodriguez, CFO & Michael Kim, Head of Procurement
**Deal:** Apex Manufacturing — Enterprise Expansion ($180,000)
**Call Type:** Negotiation | **Recording ID:** REC-2026-0225-002

---

**[0:00] Jordan:** David, Michael, thanks for making time. I know you've been reviewing the proposal we sent over last week. Before we dive in, can I confirm — are we aligned on the scope? 50 users on the Enterprise plan with the custom BigQuery integration?

**[0:18] David:** Yes, the scope looks right. Michael has some questions on pricing and terms.

**[0:25] Michael:** Thanks David. Jordan, we like the platform — the demo was impressive and our VP of Sales is very enthusiastic. But I need to be direct: $180,000 annually is above our budget. We had allocated $140,000 for this initiative. Is there room to work on the price?

**[0:48] Jordan:** Appreciate the transparency, Michael. Can I ask — when you set the $140K budget, was that based on a specific benchmark or another vendor's pricing?

**[0:58] Michael:** We benchmarked against CompetitorBeta. Their initial proposal came in around $130K for similar user count.

**[1:08] Jordan:** Got it. I know CompetitorBeta well — did their quote include implementation and professional services? Because those are usually separate and can add $40-60K.

**[1:20] Michael:** *pauses* Actually, I'd need to check on that. Their initial quote was just the license.

**[1:28] Jordan:** It's worth confirming. When our customers compare total cost of ownership, we're typically within 5-10% of CompetitorBeta all-in, but our implementation is included — no surprise costs 6 months in.

**[1:42] David:** That's a fair point. But we still need to get closer to our budget. Can you do $150K?

**[1:50] Jordan:** I can't go to $150K on a one-year deal — but I want to find a way to make this work. Here's what I can do: if Apex commits to a two-year agreement, I can bring it down to $156K per year. That's a 13% discount. And I'd include priority onboarding — which is normally a $15K add-on — for free. So you're getting about $39K in total value back.

**[2:18] David:** Two years is a big commitment. What if it doesn't work out?

**[2:23] Jordan:** Totally fair concern. We can include a 90-day performance clause. If you're not seeing measurable improvement in rep performance metrics within 90 days of full deployment, you can exit the contract. We've never had a customer invoke that clause, but it protects you.

**[2:42] Michael:** I like the 90-day clause. David, what do you think about the two-year term?

**[2:48] David:** If we have the exit clause, I'm comfortable with it. Jordan, would you also be open to a case study? Our marketing team has been wanting to do more thought leadership around AI adoption in manufacturing.

**[3:05] Jordan:** Absolutely — we'd love that. In fact, if you're open to a case study, I can take another $4K off annually. So $152K per year, two-year term, 90-day performance guarantee, priority onboarding included, and a joint case study.

**[3:22] David:** That works for me. Michael?

**[3:25] Michael:** I can work with $152K. I'll need to run the two-year commitment through our legal team for the MSA review. How long does your contract process usually take?

**[3:35] Jordan:** We can have a redline back to you within 48 hours. Most customers close legal review in 1-2 weeks. If you can send us your standard terms or any must-have clauses upfront, we can accelerate that.

**[3:50] Michael:** I'll have our legal team send over our standard addendum by end of week.

**[3:55] Jordan:** Perfect. And David — I'll send over that custom ROI model we discussed, updated with the $152K pricing. You'll see the payback period comes in around 3.5 months based on Apex's pipeline data.

**[4:10] David:** That would be helpful for my board presentation next month.

**[4:15] Jordan:** I'll make it board-ready — clean slides, clear numbers. You shouldn't have to reformat anything. Is there anything else you need from me to move this forward?

**[4:28] David:** I think we're good. Let's get the contract process started.

**[4:32] Jordan:** Excellent. Thanks David, thanks Michael. I'll send the updated proposal and contract within 48 hours, and the ROI deck by Friday. Looking forward to getting Apex's team up and running.

---

**REP'S POST-CALL NOTES:**
- Closed at $152K/year (2-year commitment) — down from $180K ask. 15.5% discount.
- Traded: 2-year commitment + case study for discount + priority onboarding + 90-day exit clause.
- Next: Send contract (48hrs), ROI deck for board (by Friday), legal addendum expected EOW.
- CompetitorBeta was benchmarked at $130K but likely doesn't include implementation.
- David (CFO) is supportive. Michael (procurement) is driving terms but aligned.
"""
    })

    # TRANSCRIPT 4: Cold call
    transcripts.append({
        "filename": "cold_call_stratos_2026-03-01.md",
        "content": """# Call Transcript: Cold Call — Stratos Energy
**Date:** March 1, 2026 | **Duration:** 6 minutes
**Rep:** Nina Okafor | **Prospect:** Wei Nakamura, VP of Sales, Stratos Energy
**Deal:** None (prospecting)
**Call Type:** Cold Call | **Recording ID:** REC-2026-0301-007

---

**[0:00] Nina:** Hi Wei, this is Nina Okafor from [Company]. I know I'm calling out of the blue — do you have 2 minutes? I promise I'll be respectful of your time.

**[0:08] Wei:** Uh, sure. Two minutes.

**[0:10] Nina:** Thanks. I'll be quick. I noticed Stratos just posted 6 new sales roles on LinkedIn, and I saw your recent post about building a "world-class sales culture." I'm reaching out because we help scaling sales teams like yours cut new-hire ramp time in half using AI coaching. Would it be worth a conversation, or am I totally off base?

**[0:30] Wei:** You're not off base. We are scaling fast. But I get 10 of these calls a week. What makes you different from Gong or Chorus?

**[0:40] Nina:** Fair question. Gong and Chorus are great at telling you what happened on a call after the fact. We're different because we actively coach your reps before and during their deals — AI roleplays where they practice with realistic buyer personas built from your ICP, real-time deal coaching based on your CRM data, and personalized feedback tied to your specific playbook. Think of it as every rep getting a dedicated coach, not just a call recorder.

**[1:10] Wei:** The roleplay piece is interesting. We've been doing manual roleplays in team meetings but it's time-consuming and awkward. Some reps hate it.

**[1:20] Nina:** Totally. The AI removes the awkwardness factor — reps can practice privately, as many times as they want, and get instant scored feedback. One of our customers in the energy space — I can share their name on a call — saw their new hires hit quota 60% faster after rolling this out.

**[1:38] Wei:** What does something like this cost?

**[1:42] Nina:** Depends on team size and tier, but for a team of 15-20 reps, most customers land between $1,200-$1,600 per month. But honestly, the ROI conversation is better done with context about your specific goals. Could I grab 20 minutes with you this week to dig into what you're building at Stratos and see if there's a real fit?

**[2:02] Wei:** I can do Thursday afternoon. 2pm?

**[2:05] Nina:** Thursday at 2pm works perfectly. I'll send a calendar invite with a short agenda. And Wei — would it be helpful if your sales enablement lead or anyone else joined?

**[2:15] Wei:** Actually yeah, let me add Fatima Ahmed — she's our new Head of Sales Enablement. She just started last month and this is right in her wheelhouse.

**[2:25] Nina:** Perfect. I'll include Fatima on the invite. Thanks for the time, Wei. Talk Thursday.

**[2:30] Wei:** Sounds good. Bye.

---

**REP'S POST-CALL NOTES:**
- Cold call converted to discovery meeting. Thursday 2pm.
- Wei is VP Sales, scaling team from ~12 to 20+.
- Fatima Ahmed = new Head of Sales Enablement (1 month in — perfect timing, she's building programs).
- Interest trigger: AI roleplays replacing awkward live roleplays.
- Mention energy sector reference customer on the discovery call.
"""
    })

    # TRANSCRIPT 5: Demo gone wrong (for coaching)
    transcripts.append({
        "filename": "demo_call_velocity_retail_2026-02-20.md",
        "content": """# Call Transcript: Product Demo — Velocity Retail
**Date:** February 20, 2026 | **Duration:** 42 minutes
**Rep:** Alex Rivera | **Prospect:** Lisa Santos, Head of Operations & Robert Dubois, CTO
**Deal:** Velocity Retail — New Department Rollout ($96,000)
**Call Type:** Demo | **Recording ID:** REC-2026-0220-004

---

**[0:00] Alex:** Hey Lisa, Robert, good to see you again. So today I'm going to walk you through our platform. I've got a lot to show you so let's jump right in.

**[0:12] Lisa:** Before we start, can I just mention — we had an internal meeting yesterday and our priorities have shifted a bit. We're now really focused on the integration with our existing tech stack. Robert has some specific questions about that.

**[0:28] Alex:** Sure, no problem. Let me just start with the overview and we'll get to integrations in a bit. So here's our dashboard...

**[0:38] Robert:** Actually, I'd prefer to start with the technical architecture. We need to understand how your platform connects to our systems before we evaluate features.

**[0:48] Alex:** Okay, well, let me show you the features first because it'll make more sense in context. So this is our main dashboard. You can see the rep performance scores, pipeline overview, and coaching recommendations. Let me click into the coaching section...

**[1:05] Alex:** So here's where the AI coaching lives. You can see each rep has a performance profile. Let me show you the roleplay feature — this is really cool. I'll start a demo roleplay...

**[3:20] Alex:** ...and then the AI gives you this scorecard. See, it rates the rep on discovery skills, objection handling, closing techniques, and overall effectiveness. Pretty powerful, right?

**[3:35] Robert:** That's nice, but you didn't answer my question about technical architecture. How does this connect to our HubSpot? Do you have a REST API? What about webhooks? And we use BigQuery for all our analytics — can you push data there?

**[3:55] Alex:** Yeah, we integrate with HubSpot. It's a standard integration — you just connect it in the settings. And for BigQuery, we have a data export feature. Let me show you the integrations page...

**[4:10] Alex:** Here's the integrations tab. You can see HubSpot, Salesforce, and a bunch of other CRMs. Just click connect and authorize.

**[4:22] Robert:** But HOW does it connect? REST API? GraphQL? What data flows in each direction? What's the sync frequency? We have strict data governance requirements. I need to understand the data flow before I can approve this.

**[4:40] Alex:** Um, it's through their API. I'd have to get our technical team to give you the specifics on the data flow. I'm not sure about the sync frequency off the top of my head.

**[4:52] Robert:** *to Lisa* This is what I was concerned about.

**[4:55] Lisa:** Alex, it seems like we might be misaligned on what we needed from today. We were hoping for a technical deep-dive, not a feature tour. Is there someone more technical who could join a follow-up call?

**[5:08] Alex:** Yes, absolutely. I can get our solutions engineer on a call with you. Sorry about that — I should have tailored this more to your needs.

**[5:18] Lisa:** No worries. Let's do that. In the meantime, can you send us technical documentation? API specs, data flow diagrams, security whitepaper?

**[5:28] Alex:** Yes, I'll send all of that over today.

**[5:32] Robert:** And one more thing — we need to know about data residency. Where are your servers? We have data sovereignty requirements for our EU customers.

**[5:42] Alex:** We're hosted on AWS. I believe we have options for different regions but I'd need to confirm.

**[5:50] Robert:** Please do. That's a dealbreaker for us if we can't keep EU customer data in the EU.

**[5:58] Alex:** Understood. I'll get all those answers to you by end of day tomorrow. And I'll set up the technical deep-dive with our SE. Would next week work?

**[6:08] Lisa:** Let's aim for next Thursday. Robert, does that work?

**[6:12] Robert:** If they come prepared this time, yes.

**[6:15] Alex:** We'll be prepared. Thanks Lisa, Robert. I appreciate your patience.

---

**REP'S POST-CALL NOTES:**
- Demo didn't go well. Robert wanted technical deep-dive, I did a feature tour.
- Need to bring SE on follow-up call next Thursday.
- Action items: Send API docs, data flow diagrams, security whitepaper, data residency info.
- Robert is the blocker — technical requirements are his domain.
- Lisa is still interested but Robert's skepticism could kill the deal.
- Need to confirm EU data residency options ASAP.
"""
    })

    for t in transcripts:
        filepath = os.path.join(CALL_TRANSCRIPTS_DIR, t["filename"])
        with open(filepath, "w") as f:
            f.write(t["content"])
    print(f"  ✓ {len(transcripts)} call transcripts")
    return transcripts


# ---------------------------------------------------------------------------
# 5. GENERATE EMAIL THREADS (for context + email drafting)
# ---------------------------------------------------------------------------

def generate_email_threads():
    """Generate realistic email conversation threads."""
    threads = []

    threads.append({
        "filename": "thread_novatech_proposal_followup.json",
        "content": {
            "thread_id": "thread_novatech_001",
            "subject": "Re: NovaTech Solutions — Professional Plan Proposal",
            "participants": [
                {"name": "Jordan Mitchell", "email": "jordan.mitchell@ourcompany.com", "role": "rep"},
                {"name": "Sarah Chen", "email": "sarah.chen@novatech.io", "role": "prospect"},
                {"name": "Marcus Williams", "email": "marcus.williams@novatech.io", "role": "prospect"},
            ],
            "messages": [
                {
                    "from": "jordan.mitchell@ourcompany.com",
                    "to": ["sarah.chen@novatech.io"],
                    "cc": [],
                    "date": "2026-02-19T10:15:00Z",
                    "body": "Hi Sarah,\n\nGreat speaking with you yesterday. As promised, here's the proposal for NovaTech.\n\nI've put together three options based on our conversation:\n\n- Starter (20 users): $49/user/month = $11,760/year\n- Professional (20 users): $79/user/month = $18,960/year — RECOMMENDED\n- Enterprise (20 users): $129/user/month = $30,960/year\n\nThe Professional plan includes everything you mentioned needing: AI roleplay coaching, performance analytics, HubSpot integration, and the custom playbook ingestion.\n\nI've also attached the custom ROI model we discussed — based on your numbers, the payback period is about 3.8 months.\n\nDemo is confirmed for Tuesday at 10am with you and Marcus. Looking forward to it.\n\nBest,\nJordan"
                },
                {
                    "from": "sarah.chen@novatech.io",
                    "to": ["jordan.mitchell@ourcompany.com"],
                    "cc": ["marcus.williams@novatech.io"],
                    "date": "2026-02-19T14:32:00Z",
                    "body": "Thanks Jordan, this looks thorough.\n\nI've forwarded to Marcus (cc'd) and we'll review before Tuesday. A couple of quick questions:\n\n1. The Professional plan — is that per-seat, or can we add users later if we scale to 40?\n2. Do you offer a pilot / trial period before committing annually?\n\nAlso, Marcus asked if you could include a section on data security in the demo — specifically around where call recordings are stored and who has access.\n\nSee you Tuesday.\n\nSarah"
                },
                {
                    "from": "jordan.mitchell@ourcompany.com",
                    "to": ["sarah.chen@novatech.io"],
                    "cc": ["marcus.williams@novatech.io"],
                    "date": "2026-02-19T16:05:00Z",
                    "body": "Great questions, Sarah:\n\n1. Per-seat pricing, and you can add users anytime. We typically see customers start with a core group and expand. If you commit to 40+ users from the start, I can lock in a better per-user rate — happy to discuss.\n\n2. We do a 30-day pilot with 5 reps. Full access to all features, dedicated onboarding support. No charge, no commitment.\n\nAnd absolutely on the security section for Marcus — I'll dedicate 10 minutes to our security architecture, data handling, and SOC 2 compliance. I'll also send our security whitepaper ahead of the call so he can review.\n\nJordan"
                },
                {
                    "from": "marcus.williams@novatech.io",
                    "to": ["jordan.mitchell@ourcompany.com"],
                    "cc": ["sarah.chen@novatech.io"],
                    "date": "2026-02-20T09:10:00Z",
                    "body": "Jordan,\n\nThanks for the security whitepaper — I skimmed it last night and it looks solid. I do have one concern: we're a HubSpot shop and our CRM data is sensitive. Can you walk me through exactly what data your platform reads from HubSpot and whether it stores any of it? Our legal team will want to know.\n\nAlso, is the AI coaching model trained on our data or is it a general model? I don't want our sales conversations being used to train models for your other customers.\n\nSee you at 10am.\n\nMarcus"
                },
                {
                    "from": "jordan.mitchell@ourcompany.com",
                    "to": ["marcus.williams@novatech.io"],
                    "cc": ["sarah.chen@novatech.io"],
                    "date": "2026-02-20T09:28:00Z",
                    "body": "Marcus, great questions — I'll address both in detail during the demo, but quick answers now:\n\n1. HubSpot data: We read deal records, contact info, and activity history to contextualize coaching. We do NOT store raw CRM data permanently — it's fetched in real-time via API and used in-session only. I'll show the data flow diagram today.\n\n2. AI model: Our coaching uses general models (not trained on your data). Your conversations, playbooks, and call recordings are NEVER used to train models. This is in our DPA — I'll send that over for your legal team.\n\nSee you in 30 minutes!\n\nJordan"
                },
            ]
        }
    })

    threads.append({
        "filename": "thread_apex_contract.json",
        "content": {
            "thread_id": "thread_apex_002",
            "subject": "Re: Apex Manufacturing — Contract & Next Steps",
            "participants": [
                {"name": "Jordan Mitchell", "email": "jordan.mitchell@ourcompany.com", "role": "rep"},
                {"name": "Michael Kim", "email": "michael.kim@apexmfg.com", "role": "prospect"},
                {"name": "David Rodriguez", "email": "david.rodriguez@apexmfg.com", "role": "prospect"},
            ],
            "messages": [
                {
                    "from": "jordan.mitchell@ourcompany.com",
                    "to": ["michael.kim@apexmfg.com", "david.rodriguez@apexmfg.com"],
                    "cc": [],
                    "date": "2026-02-26T08:30:00Z",
                    "body": "David, Michael,\n\nThank you for a productive conversation yesterday. As agreed, here's the updated proposal:\n\n- 50 users, Enterprise Plan\n- $152,000/year (2-year commitment)\n- Priority onboarding included (normally $15K)\n- 90-day performance guarantee with exit clause\n- Joint case study agreement\n\nI've attached:\n1. Updated proposal PDF\n2. Master Service Agreement (MSA)\n3. Custom ROI model for Apex (board-ready format)\n\nMichael — please send your legal team's standard addendum when ready. We'll turn around a redline within 48 hours.\n\nDavid — the ROI deck projects a 3.5-month payback. Happy to walk through it before your board presentation if helpful.\n\nLooking forward to getting this across the finish line.\n\nBest,\nJordan"
                },
                {
                    "from": "michael.kim@apexmfg.com",
                    "to": ["jordan.mitchell@ourcompany.com"],
                    "cc": ["david.rodriguez@apexmfg.com"],
                    "date": "2026-02-27T11:45:00Z",
                    "body": "Jordan,\n\nI've sent the MSA to our legal team. They'll have our standard addendum back by Monday.\n\nTwo things from legal's initial review:\n1. They want to adjust the liability cap from 1x to 2x annual contract value\n2. They're asking about GDPR compliance for our EU operations (we have a manufacturing plant in Germany)\n\nCan you address the GDPR point? Our DPO will likely want to speak with your privacy team directly.\n\nMichael"
                },
                {
                    "from": "jordan.mitchell@ourcompany.com",
                    "to": ["michael.kim@apexmfg.com"],
                    "cc": ["david.rodriguez@apexmfg.com"],
                    "date": "2026-02-27T14:20:00Z",
                    "body": "Michael,\n\nGood news on both:\n\n1. Liability cap: We can accommodate 2x — I've already flagged it with our legal team and they've approved.\n\n2. GDPR: We are fully GDPR-compliant. We have EU data processing agreements, we support data residency in EU (Frankfurt region), and we can provide our Article 30 records. I'll have our privacy team reach out to your DPO directly — can you share their contact info?\n\nWe're also preparing the Data Processing Agreement (DPA) which covers all GDPR requirements. I'll send that with the redline.\n\nOn track for signatures by end of next week?\n\nJordan"
                },
            ]
        }
    })

    threads.append({
        "filename": "thread_greenfield_gone_cold.json",
        "content": {
            "thread_id": "thread_greenfield_003",
            "subject": "Re: Greenfield Analytics — Case Studies & Next Steps",
            "participants": [
                {"name": "Alex Rivera", "email": "alex.rivera@ourcompany.com", "role": "rep"},
                {"name": "Tom Fischer", "email": "tom.fischer@greenfieldanalytics.com", "role": "prospect"},
            ],
            "messages": [
                {
                    "from": "alex.rivera@ourcompany.com",
                    "to": ["tom.fischer@greenfieldanalytics.com"],
                    "cc": [],
                    "date": "2026-02-12T16:00:00Z",
                    "body": "Hi Tom,\n\nGreat chatting today. As promised, here are the case studies:\n\n1. CloudBridge Systems — 60% faster ramp time\n2. TerraLogistics — 34% improvement in close rates\n3. Energy sector reference — 28% pipeline growth\n\nLet me know what you think and we can set up that demo.\n\nBest,\nAlex"
                },
                {
                    "from": "alex.rivera@ourcompany.com",
                    "to": ["tom.fischer@greenfieldanalytics.com"],
                    "cc": [],
                    "date": "2026-02-19T10:30:00Z",
                    "body": "Hi Tom,\n\nJust following up on the case studies I sent last week. Had a chance to review them?\n\nHappy to schedule a quick demo whenever works for you.\n\nBest,\nAlex"
                },
                {
                    "from": "alex.rivera@ourcompany.com",
                    "to": ["tom.fischer@greenfieldanalytics.com"],
                    "cc": [],
                    "date": "2026-02-26T09:15:00Z",
                    "body": "Tom,\n\nCircling back one more time. I also wanted to share something relevant — we just published a report on AI adoption in the analytics industry. Given Greenfield's focus on data analytics, I thought you might find the section on sales team productivity interesting.\n\n[link to report]\n\nStill happy to chat whenever the timing is right.\n\nAlex"
                },
                {
                    "from": "tom.fischer@greenfieldanalytics.com",
                    "to": ["alex.rivera@ourcompany.com"],
                    "cc": [],
                    "date": "2026-03-01T15:40:00Z",
                    "body": "Alex,\n\nSorry for the radio silence — things have been crazy here. We ended up going with CompetitorAlpha for now. The price point was a big factor since we're a smaller team.\n\nAppreciate you sending all those materials though. If things change, I'll reach out.\n\nTom"
                },
            ]
        }
    })

    for t in threads:
        filepath = os.path.join(EMAIL_THREADS_DIR, t["filename"])
        with open(filepath, "w") as f:
            json.dump(t["content"], f, indent=2)
    print(f"  ✓ {len(threads)} email threads")
    return threads


# ---------------------------------------------------------------------------
# 6. GENERATE MEETING NOTES (for Coach prep)
# ---------------------------------------------------------------------------

def generate_meeting_notes():
    """Generate meeting prep docs and post-meeting recap notes."""
    notes = []

    notes.append({
        "filename": "prep_novatech_demo_2026-02-22.md",
        "content": """# Meeting Prep: NovaTech Solutions — Demo
**Date:** February 22, 2026 at 10:00 AM
**Duration:** 45 minutes
**Type:** Product Demo
**Rep:** Jordan Mitchell

## Attendees
- **Sarah Chen** — VP of Engineering (Champion, initiated contact)
- **Marcus Williams** — VP of Sales (Decision-influencer, needs to see results)

## Account Context
- **Company:** NovaTech Solutions | Enterprise Software | Austin, TX | 250-500 employees
- **Deal:** Annual Platform License | Stage: Demo Scheduled | Value: $72,000
- **Series C just closed** (December 2025) — 3x revenue goal by end of 2027
- **Doubling sales team** from 20 to 40 reps (8 starting March 15, 10 more in May)

## Key Pain Points (from Discovery)
1. **7-month ramp time** for new hires (industry avg, but they can't afford it at 2x growth)
2. **Inconsistent coaching** — VP Sales (Marcus) coaching 20 reps but stretched thin
3. **Performance gap** — top 3 reps close at 35-40%, bottom half at 12-15%
4. **Dead content** — playbook docs and recorded calls sit unused

## What Matters to Each Person
- **Sarah:** Speed — she needs ramp time cut before March 15 hires start
- **Marcus:** Results data — show him metrics proving coaching works; he'll also want security details

## Competitive Landscape
- Looking at Gong/Chorus but Sarah said they feel like "the wrong solution" (passive recording vs active coaching)
- We are differentiated on: active AI coaching, roleplay, personalized feedback

## Demo Agenda
1. **[5 min]** Recap discovery — confirm pain points still accurate
2. **[15 min]** AI Roleplay demo — live roleplay with buyer persona, show scorecard
3. **[10 min]** Performance analytics — rep comparison dashboard, identify coaching gaps
4. **[5 min]** HubSpot integration — show data flow, address Marcus's security concerns
5. **[5 min]** ROI review — walk through custom model (3.8-month payback)
6. **[5 min]** Next steps — propose 30-day pilot with 5 reps

## Risk Factors
- Marcus is security-conscious — be prepared for deep technical questions
- CFO (David Thompson) is not on this call — anything >$50K needs his approval later
- New hires start March 15 — if we don't close by then, urgency drops

## Pre-Meeting Checklist
- [x] Sent security whitepaper to Marcus
- [x] Prepared custom ROI model
- [x] Set up demo environment with NovaTech-like scenario
- [x] Practiced roleplay demo with realistic buyer persona
- [ ] Prepare CFO one-pager for Sarah to share with David after the demo
"""
    })

    notes.append({
        "filename": "recap_cloudbridge_qbr_2026-02-15.md",
        "content": """# Meeting Recap: CloudBridge Systems — Quarterly Business Review
**Date:** February 15, 2026 | **Duration:** 60 minutes
**Type:** QBR (Existing Customer)
**Rep:** Jordan Mitchell
**Attendees:** Priya Patel (Head of Sales Ops, CloudBridge), Emma Johansson (CS Manager, our side)

## Summary
Quarterly check-in with CloudBridge. They've been a customer for 8 months (since June 2025). Overall satisfied, expanding usage.

## Key Metrics Shared
- **Ramp time:** Down from 6.5 months to 9 weeks (goal was 12 weeks — exceeded)
- **Close rate improvement:** Team average up 18% since deployment
- **Adoption:** 92% weekly active usage across 30 users
- **NPS:** Priya gave us a 9/10

## What's Working
- AI roleplay is the most popular feature — reps are using it 3-4x/week voluntarily
- The playbook ingestion saved Priya's team ~15 hours/month on content creation
- HubSpot integration "just works" — Priya's words

## Issues Raised
1. **Reporting granularity:** Priya wants per-manager views (not just per-rep). Currently rolling up to team level only.
2. **Custom personas:** They want to create their own buyer personas for roleplays specific to their ICPs. Currently using our default library.
3. **Slack integration:** They use Slack heavily and want coaching recommendations delivered in Slack, not just the dashboard.

## Action Items
| Action | Owner | Due |
|--------|-------|-----|
| Investigate per-manager reporting | Emma (CS) | March 1 |
| Share custom persona roadmap (it's on Q2 roadmap) | Jordan | Feb 20 |
| Connect product team re: Slack integration request | Jordan | Feb 22 |
| Schedule case study interview with Priya | Jordan | March 5 |

## Expansion Opportunity
- CloudBridge is hiring 15 more reps in Q2. Priya said she'd "definitely expand seats."
- Current contract: 30 users at $79/user = $28,440/year
- Potential: 45 users = $42,660/year (50% expansion)
- Priya mentioned interest in Enterprise tier for advanced analytics — could be $58K+ if upgraded

## Next Steps
- Send follow-up email with action items by EOD
- Prep expansion proposal for Q2 renewal conversation (renewal in June)
- Schedule case study recording
"""
    })

    notes.append({
        "filename": "recap_terralogistics_lost_deal_2026-01-30.md",
        "content": """# Meeting Recap: TerraLogistics — Deal Lost Postmortem
**Date:** January 30, 2026 | **Duration:** 30 minutes (internal)
**Type:** Lost Deal Review
**Rep:** Alex Rivera
**Manager:** Jordan Mitchell

## Deal Summary
- **Company:** TerraLogistics | Supply Chain | Chicago, IL | 250-500 employees
- **Deal:** TerraLogistics — Annual Platform License
- **Stage:** Closed Lost (was at Negotiation stage)
- **Value:** $48,000/year
- **Time in pipeline:** 4.5 months
- **Lost to:** CompetitorAlpha

## What Happened
Alex ran a standard sales process — discovery, demo, proposal. The deal progressed to negotiation and then went dark for 3 weeks. When TerraLogistics responded, they had already signed with CompetitorAlpha.

## Root Cause Analysis
1. **No champion built:** Alex's primary contact was a Director of IT who was evaluating on behalf of the VP of Sales. The VP was never engaged directly. The Director was comparing on features and price, not on strategic value.
2. **Price objection not handled:** When CompetitorAlpha came in at $49/user vs our $79/user, Alex offered a straight 10% discount without getting anything in return and without reframing to TCO/ROI.
3. **Demo was generic:** Alex did a standard feature tour instead of tailoring to TerraLogistics' specific pain points (supply chain visibility, long sales cycles with enterprise shippers).
4. **No urgency created:** There was no clear event or deadline driving the purchase. The deal drifted.
5. **Competition underestimated:** Alex didn't use the CompetitorAlpha battle card or plant landmine questions about their limited AI capabilities.

## Lessons Learned
- Always get the economic buyer on a call, even briefly, before proposal stage
- Never discount without trading something (commitment, timeline, case study)
- Always tailor the demo — this is the #1 controllable factor
- Use battle cards proactively, don't wait for the prospect to mention competition
- Create urgency by tying to a business event, not an arbitrary deadline

## Coaching Plan for Alex
1. [x] Review the objection handling playbook — specifically the "Competitor is cheaper" section
2. [ ] Practice 3 roleplay sessions focused on: price objection, multi-stakeholder navigation, urgency creation
3. [ ] Shadow Jordan on next 2 discovery calls to observe questioning technique
4. [ ] Re-read MEDDPICC section on Champion identification

## Can We Win This Back?
- Possibly in 6-12 months. CompetitorAlpha contracts are typically 1 year.
- Set a reminder for August 2026 to check in.
- In the meantime, monitor TerraLogistics on LinkedIn for signs of dissatisfaction.
"""
    })

    notes.append({
        "filename": "prep_pinnacle_discovery_2026-03-04.md",
        "content": """# Meeting Prep: Pinnacle Financial Group — Discovery Call
**Date:** March 4, 2026 at 3:00 PM
**Duration:** 30 minutes
**Type:** Discovery Call
**Rep:** Nina Okafor

## Attendees
- **Rachel O'Brien** — VP of Sales, Pinnacle Financial Group
- **Daniel Singh** — Chief Data Officer (joining for first 10 minutes, data governance questions)

## Account Context
- **Company:** Pinnacle Financial Group | Financial Services | New York, NY | 500-1000 employees
- **No existing deal** — this is a first meeting from a conference lead (met at Revenue Summit 2026)
- **Sales team:** ~45 reps across 3 regions (East, Central, West)
- **CRM:** Salesforce Enterprise
- **Known challenge:** Regulatory compliance makes them conservative about new tools

## Pre-Call Research
- Pinnacle had a strong Q4 2025 — press release mentioned 22% YoY revenue growth
- Rachel O'Brien was promoted to VP of Sales 4 months ago (from Director) — likely building her vision
- Daniel Singh published a LinkedIn article about "responsible AI in financial services" — he cares about AI governance
- They're a Salesforce shop, not HubSpot — confirm our Salesforce integration is relevant for them

## Discovery Goals
1. Understand their current coaching process and pain points
2. Learn about their tech stack and data governance requirements
3. Identify decision-making process and timeline
4. Qualify: does this fit our ICP Tier 2 (Enterprise Financial Services)?

## Questions to Ask
**For Rachel:**
- "You were recently promoted to VP — congratulations. What's your vision for the sales team over the next 12 months?"
- "How are your managers currently coaching reps? What's working and what isn't?"
- "With 45 reps across 3 regions, how do you ensure consistency in methodology and messaging?"
- "What does your current onboarding/ramp process look like for new hires?"

**For Daniel:**
- "I saw your article on responsible AI — that clearly matters to you. What would you need to see from an AI vendor to feel comfortable?"
- "What's your data governance framework for evaluating new SaaS tools?"
- "How long does a typical security and compliance review take at Pinnacle?"

## Potential Objections
- "We're in financial services — we can't use AI for customer-facing interactions" → We're used for internal coaching, not customer-facing. No customer data is processed.
- "Our compliance team will take 6 months to approve" → Ask about expedited review for low-risk tools. We don't handle PII or financial data.
- "We use Salesforce, not HubSpot" → We integrate with both. Same depth of integration.

## Risk Factors
- Compliance review could be a dealbreaker if it takes >4 months
- Daniel (CDO) could be a blocker if AI governance concerns aren't addressed upfront
- Financial services = longer sales cycle, need to budget for 6-9 month close

## Talking Points
- Reference other FinServ customers (if we have any — check with marketing)
- Lead with "internal coaching tool" positioning, not "AI sales platform"
- Mention SOC 2 Type II and GDPR compliance early
"""
    })

    for n in notes:
        filepath = os.path.join(MEETING_NOTES_DIR, n["filename"])
        with open(filepath, "w") as f:
            f.write(n["content"])
    print(f"  ✓ {len(notes)} meeting notes")
    return notes


# ---------------------------------------------------------------------------
# 7. GENERATE PRODUCT CATALOG (for pricing + feature grounding)
# ---------------------------------------------------------------------------

def generate_product_catalog():
    """Generate a product and pricing catalog so the AI has real numbers to reference."""
    content = """# Product & Pricing Catalog
## Internal Reference — Q1 2026

> **For internal use only.** Do not share pricing pages directly with prospects.
> Reps should use the interactive pricing calculator at [internal link] for custom quotes.

---

## PRODUCT OVERVIEW

**SalesCoach AI** — The AI-powered sales performance platform that actively coaches your reps, not just records them.

Core capabilities:
- AI Roleplay Coaching — practice with realistic buyer personas built from your ICP
- Real-Time Deal Intelligence — contextual coaching tied to your CRM data
- Performance Analytics — identify skill gaps and track improvement over time
- Playbook Ingestion — upload your playbooks, the AI coaches against them
- Meeting Prep — auto-generated briefs using CRM + web intel
- Pipeline Health — AI-flagged at-risk deals with recommended actions

---

## PRICING TIERS

### Starter — $49/user/month
**Best for:** Teams of 5-15 reps just getting started with AI coaching

**Included:**
- AI roleplay (10 sessions/user/month)
- Basic call analytics (post-call summaries)
- 1 CRM integration (HubSpot OR Salesforce)
- Email template suggestions
- Standard onboarding (self-serve + docs)
- Community support

**Not included:**
- Custom playbook ingestion
- Advanced analytics & reporting
- BigQuery / data warehouse connector
- Dedicated CSM
- API access

**Billing:** Monthly or annual (15% discount on annual)
**Minimum commitment:** None (month-to-month available)

---

### Professional — $79/user/month ⭐ MOST POPULAR
**Best for:** Teams of 10-50 reps scaling their coaching

**Everything in Starter, plus:**
- Unlimited AI roleplay sessions
- Custom playbook ingestion (up to 50 documents)
- Advanced performance analytics (per-rep, per-team, per-manager)
- AI meeting prep briefs
- Pipeline health monitoring with deal risk scoring
- 3 CRM integrations
- HubSpot + Salesforce bi-directional sync
- Custom buyer persona builder
- Email draft generation (context-aware)
- Slack integration
- Priority onboarding (dedicated 2-week setup)
- Email support (4-hour SLA)

**Not included:**
- BigQuery / data warehouse connector
- Custom API access
- Dedicated CSM
- SSO / SAML
- Custom reporting

**Billing:** Monthly or annual (15% discount on annual)
**Minimum commitment:** 10 users

---

### Enterprise — $129/user/month
**Best for:** Teams of 25-200+ reps with advanced requirements

**Everything in Professional, plus:**
- BigQuery & data warehouse connector (read/write)
- Custom API access (REST + webhooks)
- Dedicated Customer Success Manager
- SSO / SAML authentication
- Custom reporting & dashboards
- Unlimited CRM integrations
- Advanced security features (audit logs, IP allowlisting, data residency options)
- Custom AI model tuning (train on your historical win/loss data)
- Multi-region deployment (US, EU, APAC)
- Quarterly business reviews
- Phone support (1-hour SLA)
- Custom onboarding program (4-week white-glove)

**Billing:** Annual only
**Minimum commitment:** 25 users, 1-year contract

---

## ADD-ONS (Available on any tier)

| Add-On | Price | Description |
|--------|-------|-------------|
| Priority Onboarding | $15,000 one-time | Dedicated implementation specialist, 2-week guided setup |
| White-Glove Onboarding | $30,000 one-time | 4-week program with custom playbook migration, training workshops, go-live support |
| Additional CRM Integration | $500/month per integration | Connect additional CRM instances |
| API Overage | $0.02/call | Beyond Enterprise included volume (100K calls/month) |
| Data Residency (EU) | $10/user/month | Host all data in EU (Frankfurt) |
| Data Residency (APAC) | $15/user/month | Host all data in APAC (Sydney) |
| Advanced Analytics Pack | $20/user/month | Custom dashboards, cohort analysis, forecasting models |
| Content Studio | $2,000/month | AI-generated playbook content, quarterly refresh |

---

## DISCOUNT GUIDELINES

| Scenario | Max Discount | Approval Required |
|----------|-------------|-------------------|
| Annual pre-pay (vs monthly) | 15% | Auto-applied |
| 2-year commitment | 10-15% | Sales Manager |
| 3-year commitment | 15-20% | VP Sales |
| 50+ users | 10% additional | Sales Manager |
| 100+ users | 15% additional | VP Sales |
| Non-profit / Education | 25% | VP Sales |
| Case study agreement | $2,000-5,000/year credit | Sales Manager |
| Competitive displacement | Up to 20% | VP Sales (with competitive intel) |

**Rules:**
- Never stack more than 2 discounts
- Never discount below 30% off list price without VP approval
- Always trade — get something in return (commitment, timeline, case study, reference)
- Document all discounts in HubSpot deal properties

---

## COMPETITIVE PRICING COMPARISON

| Feature | Us (Professional) | CompetitorAlpha | CompetitorBeta | CompetitorGamma |
|---------|-------------------|-----------------|----------------|-----------------|
| Per-user/month | $79 | $49 | $150-300 | $89 |
| AI Roleplay | ✅ Unlimited | ❌ None | ❌ None | ❌ None |
| Real-time coaching | ✅ | ❌ | ⚠️ Post-call only | ❌ |
| Playbook ingestion | ✅ 50 docs | ❌ | ✅ Unlimited | ⚠️ 10 docs |
| Pipeline health AI | ✅ | ⚠️ Basic | ✅ | ❌ |
| Implementation time | 2 weeks | 1 week | 6 months | 3 weeks |
| Implementation cost | $0 (included) | $0 | $50-80K | $10K |
| Contract flexibility | Monthly available | Annual only | Annual only | Annual only |

**Total Cost of Ownership (20 users, 1 year):**
- Us: $18,960
- CompetitorAlpha: $11,760 (but no coaching → lower ROI)
- CompetitorBeta: $36,000-72,000 + $60K implementation = $96K-132K
- CompetitorGamma: $21,360 + $10K implementation = $31,360

---

## ROI BENCHMARKS (use in proposals)

| Metric | Average Improvement | Source |
|--------|-------------------|--------|
| New hire ramp time | 45% reduction (7mo → 3.8mo avg) | Internal data, 42 customers |
| Team close rate | 23% improvement | Internal data, 38 customers |
| Pipeline velocity | 31% faster stage progression | Internal data, 28 customers |
| Quota attainment | 18% increase in reps hitting quota | Customer survey, Q4 2025 |
| Manager time saved | 8 hours/week per manager | Customer survey, Q4 2025 |
| Payback period | 3.2 months average | Internal data, all customers |
| 12-month ROI | 340% average | Internal data, 35 customers |

---

*Pricing effective January 1, 2026. Subject to change. Contact Revenue Operations for exceptions.*
"""
    with open(os.path.join(PLAYBOOK_DIR, "product_pricing_catalog.md"), "w") as f:
        f.write(content)
    print("  ✓ product_pricing_catalog.md")


# ---------------------------------------------------------------------------
# 8. GENERATE CASE STUDIES (for references + RAG)
# ---------------------------------------------------------------------------

def generate_case_studies():
    """Generate detailed customer case study documents."""

    case_study_1 = """# Customer Case Study: CloudBridge Systems
## "From 6.5 Months to 9 Weeks: How CloudBridge Cut New Hire Ramp Time by 60%"

---

## Company Overview

| | |
|---|---|
| **Company** | CloudBridge Systems |
| **Industry** | Cloud Infrastructure |
| **Size** | 100-250 employees |
| **HQ** | San Francisco, CA |
| **Sales Team** | 30 reps across 2 regions (West Coast, East Coast) |
| **CRM** | HubSpot |
| **Became Customer** | June 2025 |
| **Plan** | Professional (30 users) |
| **Annual Value** | $28,440 |

---

## The Challenge

CloudBridge Systems was growing fast. After closing a $22M Series B in early 2025, they needed to double their sales team from 15 to 30 reps within 6 months. Head of Sales Ops Priya Patel faced three interconnected problems:

**1. Ramp time was killing growth.**
New reps took 6.5 months to reach full quota. At the pace they were hiring, that meant half the team would be underperforming for the rest of the year. "We were essentially paying full salaries for reps who couldn't close for two quarters," Priya explained.

**2. Coaching was bottlenecked on one person.**
Their VP of Sales was the only person doing meaningful coaching, spending 12+ hours per week on 1:1s, call reviews, and ride-alongs. With the team doubling, that model would break. "He was already burning out. We couldn't ask him to coach 30 reps."

**3. Top performers' knowledge wasn't transferable.**
CloudBridge had 4 top reps closing at 38% while the rest averaged 16%. They knew the top reps were doing something different, but couldn't articulate or codify it. "We tried recording calls and sharing them, but nobody watched hour-long recordings. The knowledge was stuck in people's heads."

---

## Why CloudBridge Chose SalesCoach AI

CloudBridge evaluated three solutions: Gong, CompetitorAlpha, and SalesCoach AI.

**Gong** was strong on call analytics but passive — it analyzed what happened after the fact but didn't actively coach reps.

**CompetitorAlpha** was cheaper ($49/user/month) but lacked AI coaching entirely — just call recording and basic transcription.

**SalesCoach AI** won because of three differentiators:

1. **Active coaching, not passive analysis.** "Other tools tell you what went wrong after the call. SalesCoach AI coaches you before and during. That's a completely different value proposition," said Priya.

2. **AI roleplays replaced awkward team sessions.** "Our reps hated practicing in front of peers. With AI roleplay, they practice privately, get instant feedback, and actually enjoy it. Usage went through the roof."

3. **Playbook ingestion made coaching consistent.** "We uploaded our 40-page sales playbook, our objection scripts, and our battle cards. The AI coaches against OUR methodology, not generic sales advice. That's huge."

---

## Implementation

CloudBridge went live in 11 business days:

| Timeline | Milestone |
|----------|-----------|
| Day 1-2 | HubSpot integration configured, playbooks uploaded |
| Day 3-5 | 5-rep pilot group onboarded, first roleplays completed |
| Day 6-8 | Feedback from pilot incorporated, full team onboarded |
| Day 9-11 | Analytics dashboards configured, manager training completed |

"We braced for a 3-month rollout. It took less than 2 weeks. Our engineering team didn't have to lift a finger," said Priya.

---

## Results (After 8 Months)

### Headline Numbers

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| New hire ramp time | 6.5 months | 9 weeks | **60% reduction** |
| Team close rate | 19% avg | 27% avg | **42% improvement** |
| Top-bottom performance gap | 22 percentage points | 11 percentage points | **50% reduction** |
| Manager coaching time | 12 hrs/week | 4 hrs/week | **67% reduction** |
| Weekly active usage | N/A | 92% | — |
| Rep satisfaction (NPS) | — | 9/10 | — |

### Ramp Time Breakdown

The biggest impact was on new hire ramp. CloudBridge hired 15 new reps between June and October 2025. Here's how they compared to the previous cohort:

| Milestone | Previous Cohort | With SalesCoach AI |
|-----------|----------------|-------------------|
| First qualified meeting | Week 6 | Week 2 |
| First proposal sent | Week 12 | Week 5 |
| First closed deal | Week 18 | Week 8 |
| Full quota attainment | Month 6.5 | Week 9 |

"The AI roleplay was the single biggest factor. New reps were practicing 4-5 scenarios a day in their first week. By week 2, they sounded like they'd been here 6 months," Priya explained.

### Close Rate by Cohort

The performance gap between top and bottom reps shrank dramatically:

| Cohort | Close Rate Before | Close Rate After |
|--------|------------------|-----------------|
| Top performers (4 reps) | 38% | 41% |
| Mid performers (11 reps) | 22% | 29% |
| New hires (15 reps) | N/A (ramping) | 24% by month 3 |

### ROI Calculation

| Item | Amount |
|------|--------|
| Annual cost (30 users, Professional) | $28,440 |
| Revenue from faster ramp (15 new reps × 3.5 months earlier × est. pipeline) | ~$420,000 |
| Revenue from close rate improvement (existing reps) | ~$180,000 |
| Manager time saved (8 hrs/week × $80/hr × 52 weeks) | ~$33,280 |
| **Total estimated value** | **~$633,280** |
| **ROI** | **~2,126%** |
| **Payback period** | **~2.3 weeks** |

---

## What's Next

CloudBridge is expanding from 30 to 45 users in Q2 2026 and evaluating an upgrade to the Enterprise tier for BigQuery integration and custom reporting. They're also planning a joint webinar with SalesCoach AI on "Scaling Sales Teams Without Scaling Coaching Headcount."

---

## Key Quotes

> "SalesCoach AI is the single best investment we've made in our sales team. It's like giving every rep a personal coach who knows our playbook inside and out."
> — **Priya Patel, Head of Sales Ops, CloudBridge Systems**

> "I used to spend Sunday nights prepping for Monday coaching sessions. Now the AI handles 80% of it and I focus on the strategic stuff. I actually have my weekends back."
> — **VP of Sales, CloudBridge Systems**

> "The roleplays are addictive. I did 3 before my first real call and I felt like I'd done this a hundred times. My first demo with a real prospect went better than most of my demos at my last company."
> — **New Sales Rep, CloudBridge Systems (hired August 2025)**

---

*Case study approved by CloudBridge Systems, January 2026. Contact Marketing for presentation-ready version.*
"""

    case_study_2 = """# Customer Case Study: Apex Manufacturing
## "How Apex Manufacturing Standardized Sales Coaching Across 3 Regions and Grew Pipeline 34%"

---

## Company Overview

| | |
|---|---|
| **Company** | Apex Manufacturing |
| **Industry** | Industrial Manufacturing |
| **Size** | 500-1000 employees |
| **HQ** | Detroit, MI |
| **Sales Team** | 50 reps across 3 regions (Midwest, Southeast, Northeast) |
| **CRM** | HubSpot |
| **Became Customer** | September 2025 |
| **Plan** | Enterprise (50 users) |
| **Annual Value** | $152,000 (2-year contract) |

---

## The Challenge

Apex Manufacturing sells industrial automation equipment to factories and distribution centers. Their sales cycle averages 4-6 months, deal sizes range from $50K to $500K, and every deal involves 3-5 stakeholders (plant manager, VP operations, CFO, procurement, sometimes the CEO).

When David Rodriguez joined as CFO in mid-2025, he identified a critical problem: **sales performance varied wildly across their 3 regions, and nobody knew why.**

**1. Regional inconsistency.**
The Midwest team (home territory, 20 reps) closed at 28%. The Southeast team (15 reps, newer market) closed at 14%. The Northeast team (15 reps, competitive market) closed at 19%. "Same product, same pricing, completely different results. It was clear we had a coaching problem, not a market problem," said David.

**2. No standardized sales methodology.**
Each regional manager coached differently. The Midwest manager did weekly roleplay sessions. The Southeast manager reviewed call recordings once a month. The Northeast manager mostly left reps to figure it out. "We had three different sales cultures in one company."

**3. Long sales cycles getting longer.**
Average deal cycle had crept from 4.2 months to 5.8 months over the past year. Deals were stalling in the Proposal and Negotiation stages. "Reps were great at discovery but couldn't close. They'd get to the proposal stage and then the deal would just... sit there."

**4. Enterprise prospects required more sophisticated selling.**
Apex was moving upmarket — targeting larger factories with $200K-500K deals instead of their traditional $50K-100K sweet spot. "Our reps knew how to sell to plant managers. They didn't know how to sell to C-suite executives at Fortune 500 manufacturers. We needed to upskill the entire team."

---

## Why Apex Chose SalesCoach AI

Apex ran a formal evaluation over 6 weeks, comparing SalesCoach AI against CompetitorBeta and an internal "build it ourselves" option.

**CompetitorBeta** had strong enterprise credentials but came with a $60K implementation cost on top of $150-300/user/month pricing. Implementation timeline: 6 months. "By the time we'd be live, we'd have missed two quarters," said David.

**Build in-house** was championed by the CTO. Engineering estimated 6 months and $250K. "I asked our CTO one question: 'What else could your engineering team build in 6 months that would generate revenue?' That ended the conversation."

**SalesCoach AI** won on three factors:
1. **Speed to value** — live in 3 weeks vs. 6 months
2. **Standardization** — the same AI coach enforcing the same methodology across all 3 regions
3. **Total cost** — $152K/year vs. CompetitorBeta's $250K+ all-in or internal build's $250K+ with ongoing maintenance

The negotiation resulted in a 2-year deal at $152K/year with a 90-day performance guarantee, priority onboarding, and a joint case study.

---

## Implementation

Apex rolled out in 3 phases over 4 weeks:

| Phase | Timeline | Scope |
|-------|----------|-------|
| Phase 1: Midwest (pilot) | Week 1-2 | 20 reps, 3 managers |
| Phase 2: Northeast + Southeast | Week 3 | 30 reps, 4 managers |
| Phase 3: Analytics + optimization | Week 4 | Dashboards, baseline metrics, manager training |

Key implementation steps:
- Uploaded Apex's 65-page sales playbook, 12 product spec sheets, and 8 competitive battle cards
- Created 6 custom buyer personas matching Apex's ICP (Plant Manager, VP Operations, CFO of manufacturing companies, Procurement Director, CEO of mid-size manufacturer, Director of Digital Transformation)
- Configured HubSpot integration for real-time deal context
- Trained 7 managers on using coaching analytics

---

## Results (After 5 Months)

### Headline Numbers

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Team close rate (overall) | 21% avg | 28% avg | **34% improvement** |
| Southeast close rate | 14% | 25% | **79% improvement** |
| Average sales cycle | 5.8 months | 4.1 months | **29% reduction** |
| Pipeline value | $4.2M | $6.8M | **62% increase** |
| Deals stuck in Proposal 30+ days | 38% of pipeline | 12% of pipeline | **68% reduction** |
| Reps hitting quota | 42% | 68% | **62% improvement** |

### Regional Standardization

The biggest win was closing the gap between regions:

| Region | Close Rate Before | Close Rate After | Gap to Best Region |
|--------|------------------|------------------|--------------------|
| Midwest | 28% | 31% | — (best) |
| Northeast | 19% | 27% | 4 pts (was 9 pts) |
| Southeast | 14% | 25% | 6 pts (was 14 pts) |

"The Southeast team went from our worst-performing region to nearly matching the Midwest in 5 months. That's not a market change — that's a coaching change," said David.

### Deal Velocity Improvement

Deals were moving faster, especially through the stages where they previously stalled:

| Stage | Avg Days Before | Avg Days After | Change |
|-------|----------------|----------------|--------|
| Discovery → Qualification | 12 days | 8 days | -33% |
| Qualification → Demo | 18 days | 11 days | -39% |
| Demo → Proposal | 22 days | 14 days | -36% |
| Proposal → Negotiation | 35 days | 15 days | **-57%** |
| Negotiation → Close | 28 days | 18 days | -36% |

"The Proposal-to-Negotiation stage was our black hole. Deals would go in and never come out. The AI coaching on negotiation prep and follow-up cadences cut that by more than half," said the VP of Sales.

### Feature Usage

| Feature | Weekly Active Users | Avg Sessions/User/Week |
|---------|-------------------|----------------------|
| AI Roleplay | 88% | 3.2 |
| Deal Intelligence | 76% | Daily (passive) |
| Meeting Prep | 92% | 2.1 |
| Pipeline Health Alerts | 100% (managers) | Daily |
| Email Draft Suggestions | 64% | 1.8 |

The most popular roleplay scenarios:
1. "CFO pricing objection" (248 sessions in 5 months)
2. "Competitive displacement — CompetitorX installed base" (189 sessions)
3. "Discovery call with VP Operations" (176 sessions)
4. "Cold call to plant manager" (165 sessions)
5. "Negotiation — procurement pushing for 30% discount" (142 sessions)

### ROI Calculation

| Item | Amount |
|------|--------|
| Annual cost (50 users, Enterprise + case study discount) | $152,000 |
| Revenue from pipeline growth ($6.8M - $4.2M × 28% close rate) | ~$728,000 |
| Revenue from faster cycles (deals closing 1.7 months earlier) | ~$310,000 |
| Manager coaching efficiency (7 managers × 6 hrs saved/week × $90/hr) | ~$163,800 |
| **Total estimated value** | **~$1,201,800** |
| **ROI** | **~691%** |
| **Payback period** | **~2.3 months** |

---

## What's Next

Apex is planning to:
1. Add BigQuery integration to correlate deal outcomes with manufacturing industry trends
2. Expand to their APAC sales team (12 reps in Singapore and Tokyo) in H2 2026
3. Build custom roleplay scenarios for their new product line launching Q3 2026
4. Present results at the annual Manufacturing Sales Summit (Apex's VP of Sales speaking)

---

## Key Quotes

> "I came in as CFO expecting to cut costs. Instead, I approved a $152K spend that generated over $1M in pipeline value in 5 months. The 90-day guarantee made the decision easy, but honestly, we saw results in 30 days."
> — **David Rodriguez, CFO, Apex Manufacturing**

> "For the first time, all three regions are running the same playbook, getting the same quality coaching, and producing consistent results. That's what I've been trying to achieve for 3 years."
> — **VP of Sales, Apex Manufacturing**

> "I was skeptical about AI coaching — I've been selling industrial equipment for 15 years. But the roleplay for my first C-suite pitch was genuinely helpful. It caught things I didn't even realize I was doing wrong."
> — **Senior Account Executive, Apex Manufacturing (18 years experience)**

---

*Case study approved by Apex Manufacturing, February 2026. Contact Marketing for presentation-ready version.*
"""

    with open(os.path.join(PLAYBOOK_DIR, "case_study_cloudbridge.md"), "w") as f:
        f.write(case_study_1)
    print("  ✓ case_study_cloudbridge.md")

    with open(os.path.join(PLAYBOOK_DIR, "case_study_apex.md"), "w") as f:
        f.write(case_study_2)
    print("  ✓ case_study_apex.md")


# ---------------------------------------------------------------------------
# MAIN — Generate everything
# ---------------------------------------------------------------------------

def main():
    print("\n🔧 Generating synthetic test data for Sales AI Agents POC...\n")

    print("📚 Playbooks (for RAG indexing):")
    generate_objection_scripts()
    generate_battle_cards()
    generate_icps()
    generate_email_templates()
    generate_sales_methodology()
    generate_product_catalog()
    generate_case_studies()

    print(f"\n💼 Mock CRM Data (mimics HubSpot API):")
    contacts = generate_contacts()
    companies = generate_companies()
    deals = generate_deals(contacts)

    with open(os.path.join(MOCK_CRM_DIR, "contacts.json"), "w") as f:
        json.dump(contacts, f, indent=2)
    print(f"  ✓ contacts.json ({len(contacts)} contacts)")

    with open(os.path.join(MOCK_CRM_DIR, "companies.json"), "w") as f:
        json.dump(companies, f, indent=2)
    print(f"  ✓ companies.json ({len(companies)} companies)")

    with open(os.path.join(MOCK_CRM_DIR, "deals.json"), "w") as f:
        json.dump(deals, f, indent=2)
    print(f"  ✓ deals.json ({len(deals)} deals)")

    print(f"\n📊 Mock BigQuery Analytics:")
    generate_bq_analytics()

    print(f"\n📞 Call Transcripts (for Coach feedback):")
    generate_call_transcripts()

    print(f"\n📧 Email Threads (for context + email drafting):")
    generate_email_threads()

    print(f"\n📝 Meeting Notes (for Coach prep):")
    generate_meeting_notes()

    print(f"\n✅ All test data generated!")
    print(f"\n📁 Files created:")
    print(f"   {PLAYBOOK_DIR}/")
    print(f"     ├── objection_handling_playbook.md")
    print(f"     ├── competitive_battle_cards.md")
    print(f"     ├── ideal_customer_profiles.md")
    print(f"     ├── email_templates_playbook.md")
    print(f"     ├── sales_methodology.md")
    print(f"     ├── product_pricing_catalog.md")
    print(f"     ├── case_study_cloudbridge.md")
    print(f"     └── case_study_apex.md")
    print(f"   {MOCK_CRM_DIR}/")
    print(f"     ├── contacts.json")
    print(f"     ├── companies.json")
    print(f"     ├── deals.json")
    print(f"     ├── call_transcripts/  (5 transcripts)")
    print(f"     ├── email_threads/     (3 threads)")
    print(f"     └── meeting_notes/     (4 notes)")
    print(f"   {MOCK_BQ_DIR}/")
    print(f"     ├── pipeline_analytics.csv")
    print(f"     └── win_loss_analysis.csv")
    print(f"\n📌 Next steps:")
    print(f"   1. Index playbooks into ChromaDB:  python scripts/index_playbooks.py")
    print(f"   2. Index call transcripts + meeting notes into ChromaDB for RAG")
    print(f"   3. Use mock CRM data for testing when HubSpot MCP isn't connected")
    print(f"   4. Use mock BQ data for testing when BigQuery MCP isn't connected")


if __name__ == "__main__":
    main()
