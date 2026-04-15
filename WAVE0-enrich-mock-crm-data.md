# Wave 0 — Enrich Mock CRM Data for Wave 1-5 Demo Coverage

The existing mock CRM data (10 companies, 20 contacts, 16 deals, 63 activity notes, 5 call transcripts, 3 email threads, 4 meeting notes) was built for the original 19 commands. The new 13 commands from Waves 1-5 need richer, more varied data to demo well. This instruction file adds new data without modifying any existing records.

**Files to modify:**
- `data/mock_crm/companies.json` — Add 2 new companies
- `data/mock_crm/contacts.json` — Add 6 new contacts
- `data/mock_crm/deals.json` — Add 4 new deals with rich activity notes
- New call transcripts, email threads, and meeting notes

**Files to create:**
- `data/mock_crm/call_transcripts/discovery_call_dataflow_2026-03-05.md`
- `data/mock_crm/call_transcripts/negotiation_call_cloudbridge_2026-03-08.md`
- `data/mock_crm/call_transcripts/demo_call_quantumleap_2026-03-03.md`
- `data/mock_crm/email_threads/thread_dataflow_pricing_negotiation.json`
- `data/mock_crm/email_threads/thread_cloudbridge_expansion.json`
- `data/mock_crm/email_threads/thread_quantumleap_intro.json`
- `data/mock_crm/meeting_notes/prep_dataflow_negotiation_2026-03-13.md`
- `data/mock_crm/meeting_notes/recap_cloudbridge_demo_2026-03-10.md`

---

## Why Each Wave Needs Richer Data

| Wave | Command | Data Gap |
|------|---------|----------|
| 1 | `/log`, auto-CRM-detect | Need deals with enough contacts to test note association. Need varied activity notes with company names the keyword detector can match. |
| 1 | `/training-history` | Handled by `seed_demo_data.py` (SQLite) — no CRM data needed. |
| 2 | `/skill-gaps` | Handled by `seed_demo_data.py` — no CRM data needed. |
| 3 | `/team-dashboard` | Handled by `seed_demo_data.py` — no CRM data needed. |
| 5 | `/my-day` → "Prep for Meeting" | Calendar references **DataFlow Inc** — but no company exists in mock CRM. `/coach prep` and `/research` will return empty results. |
| 5 | `/market-insights` | Analyzes CRM notes for objection patterns, competitor mentions, sentiment shifts. Current notes have only 11 competitor mentions (all "CompetitorAlpha") and limited objection diversity. Needs notes mentioning specific battle card competitors (Nexus Platform, CloudSync Pro, DataFlow Suite, AgileStack) and varied objections (price, timeline, security, integration, incumbent). |
| 5 | `/draft-email` → "Send Now" + "Attach Document" | Need contacts with realistic email addresses and deal context that warrants different attachment types (brochure vs. case study vs. pricing). |
| 1E | Auto-CRM-detect | Needs company names in CRM that match natural Slack messages. Current companies work, but adding DataFlow Inc ensures calendar-to-CRM continuity. |

---

## Step 1: Add 2 New Companies to `companies.json`

Append these to the existing array. These match the mock calendar companies that don't already exist in CRM.

```json
{
  "id": "dataflow_inc",
  "properties": {
    "name": "DataFlow Inc",
    "domain": "dataflow.com",
    "industry": "Data Infrastructure",
    "numberofemployees": "500-1000",
    "city": "San Jose",
    "state": "CA",
    "annualrevenue": "120000000",
    "description": "DataFlow Inc builds enterprise data pipeline and ETL infrastructure. Publicly traded, aggressive growth through acquisition. Currently using a competitor's coaching platform (Nexus Platform) for their 200-person sales team.",
    "createdate": "2025-11-15T10:00:00.000000",
    "lastmodifieddate": "2026-03-10T14:30:00.000000"
  }
},
{
  "id": "quantumleap_ai",
  "properties": {
    "name": "QuantumLeap AI",
    "domain": "quantumleap.ai",
    "industry": "Artificial Intelligence",
    "numberofemployees": "50-100",
    "city": "Palo Alto",
    "state": "CA",
    "annualrevenue": "8000000",
    "description": "QuantumLeap AI is a Series B startup building AI-powered productivity tools. Fast-growing sales team (tripled headcount in 6 months). Urgent need for standardized sales methodology and onboarding. Currently has no coaching solution.",
    "createdate": "2026-01-20T09:00:00.000000",
    "lastmodifieddate": "2026-03-08T11:00:00.000000"
  }
}
```

**Why these two:**
- **DataFlow Inc** — Already in the mock calendar (negotiation meeting on Mar 13). Adding it to CRM creates continuity: `/my-day` shows meeting → click "Prep" → `/research DataFlow` pulls real data. Also a competitive displacement story (they use Nexus Platform), which enriches `/market-insights`.
- **QuantumLeap AI** — New fast-growing startup deal. Provides a fresh onboarding-centric story for Wave 4 (`/onboard`, `/launch-training`). Also adds variety to the company mix (first AI company in the data).

---

## Step 2: Add 6 New Contacts to `contacts.json`

Append these to the existing array:

```json
{
  "id": "contact_df_001",
  "properties": {
    "firstname": "Tom",
    "lastname": "Baker",
    "email": "tom.baker@dataflow.com",
    "jobtitle": "VP of Procurement",
    "phone": "+1-408-555-3201",
    "company": "DataFlow Inc",
    "lifecyclestage": "opportunity",
    "lastmodifieddate": "2026-03-10T14:30:00.000000"
  },
  "associations": {
    "company_id": "dataflow_inc"
  }
},
{
  "id": "contact_df_002",
  "properties": {
    "firstname": "Lisa",
    "lastname": "Park",
    "email": "lisa.park@dataflow.com",
    "jobtitle": "VP of Sales Enablement",
    "phone": "+1-408-555-3202",
    "company": "DataFlow Inc",
    "lifecyclestage": "opportunity",
    "lastmodifieddate": "2026-03-05T10:00:00.000000"
  },
  "associations": {
    "company_id": "dataflow_inc"
  }
},
{
  "id": "contact_df_003",
  "properties": {
    "firstname": "Raj",
    "lastname": "Gupta",
    "email": "raj.gupta@dataflow.com",
    "jobtitle": "Chief Revenue Officer",
    "phone": "+1-408-555-3203",
    "company": "DataFlow Inc",
    "lifecyclestage": "opportunity",
    "lastmodifieddate": "2026-03-08T16:00:00.000000"
  },
  "associations": {
    "company_id": "dataflow_inc"
  }
},
{
  "id": "contact_ql_001",
  "properties": {
    "firstname": "Priya",
    "lastname": "Sharma",
    "email": "priya.sharma@quantumleap.ai",
    "jobtitle": "Head of Revenue",
    "phone": "+1-650-555-7701",
    "company": "QuantumLeap AI",
    "lifecyclestage": "salesqualifiedlead",
    "lastmodifieddate": "2026-03-08T11:00:00.000000"
  },
  "associations": {
    "company_id": "quantumleap_ai"
  }
},
{
  "id": "contact_ql_002",
  "properties": {
    "firstname": "Jake",
    "lastname": "Morrison",
    "email": "jake.morrison@quantumleap.ai",
    "jobtitle": "Sales Director",
    "phone": "+1-650-555-7702",
    "company": "QuantumLeap AI",
    "lifecyclestage": "salesqualifiedlead",
    "lastmodifieddate": "2026-03-06T15:00:00.000000"
  },
  "associations": {
    "company_id": "quantumleap_ai"
  }
},
{
  "id": "contact_ql_003",
  "properties": {
    "firstname": "Amy",
    "lastname": "Liu",
    "email": "amy.liu@quantumleap.ai",
    "jobtitle": "CEO",
    "phone": "+1-650-555-7700",
    "company": "QuantumLeap AI",
    "lifecyclestage": "subscriber",
    "lastmodifieddate": "2026-02-28T09:00:00.000000"
  },
  "associations": {
    "company_id": "quantumleap_ai"
  }
}
```

**Note:** Tom Baker's email (`tom.baker@dataflow.com`) matches the mock calendar contact, ensuring `/my-day` → "Prep" → `/draft-email` flows end-to-end.

---

## Step 3: Add 4 New Deals to `deals.json`

Append these to the existing array. Each has rich activity notes designed to feed `/market-insights` with varied objections, competitor mentions, and sentiment.

### Deal 1: DataFlow Inc — Competitive Displacement (Negotiation)

```json
{
  "id": "deal_df_001",
  "properties": {
    "dealname": "DataFlow Inc — Enterprise Platform Migration",
    "amount": "180000",
    "dealstage": "negotiation",
    "dealstage_label": "Negotiation",
    "pipeline": "default",
    "closedate": "2026-04-15",
    "createdate": "2025-12-10T10:00:00.000000",
    "hs_lastmodifieddate": "2026-03-10T14:30:00.000000",
    "hubspot_owner_id": "owner_101",
    "description": "Competitive displacement opportunity. DataFlow currently uses Nexus Platform for coaching their 200-person sales team. Contract expires April 30. They're unhappy with Nexus's lack of AI roleplay and poor reporting."
  },
  "associations": {
    "company": "dataflow_inc",
    "contact": "contact_df_001"
  },
  "activities": [
    {
      "type": "NOTE",
      "body": "Contract negotiation call with Tom Baker (VP Procurement). They want a 15% volume discount for 200 seats. I pushed back — offered 10% with a 2-year commitment. Tom said he needs to run it by the CRO (Raj Gupta). Raj is the economic buyer. Next step: pricing call with Raj on March 13.",
      "timestamp": "2026-03-10T14:30:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Lisa Park (VP Sales Enablement) confirmed they're dropping Nexus Platform. Main complaints: no AI-powered roleplay (Nexus only does static scenario scripts), reporting is too basic (can't track skill gaps per rep), and their implementation took 6 months. She wants our onboarding done in 4 weeks. Sent her our implementation timeline doc.",
      "timestamp": "2026-03-05T10:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Competitive intel: DataFlow also looked at AgileStack briefly but ruled them out — too focused on SMB, doesn't scale to 200 reps. CloudSync Pro is still in the conversation but Lisa said their demo was 'underwhelming' compared to ours. We're the front-runner.",
      "timestamp": "2026-02-28T11:00:00.000000"
    },
    {
      "type": "CALL",
      "body": "Discovery call with Lisa Park. They have 200 sales reps across 3 regions (US, EMEA, APAC). Biggest pain: inconsistent coaching across regions. US team performs well but EMEA is struggling with longer sales cycles and cultural nuances. They need multi-language support (English, German, French). Budget: $200K approved for coaching platform.",
      "timestamp": "2026-02-15T09:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Initial outreach via LinkedIn. Tom Baker responded to our case study post about Apex Manufacturing's 15% close rate improvement. He mentioned they're 'actively evaluating alternatives to our current coaching vendor.' Booked discovery call for Feb 15.",
      "timestamp": "2026-02-01T16:00:00.000000"
    }
  ]
}
```

### Deal 2: DataFlow Inc — APAC Training Sprint (Discovery)

```json
{
  "id": "deal_df_002",
  "properties": {
    "dealname": "DataFlow Inc — APAC Sales Training Sprint",
    "amount": "45000",
    "dealstage": "discovery",
    "dealstage_label": "Discovery",
    "pipeline": "default",
    "closedate": "2026-05-30",
    "createdate": "2026-03-06T14:00:00.000000",
    "hs_lastmodifieddate": "2026-03-08T16:00:00.000000",
    "hubspot_owner_id": "owner_103",
    "description": "Add-on deal from the main DataFlow engagement. APAC team needs a focused 6-week training sprint for their 35 reps who are underperforming."
  },
  "associations": {
    "company": "dataflow_inc",
    "contact": "contact_df_002"
  },
  "activities": [
    {
      "type": "NOTE",
      "body": "Raj Gupta brought up the APAC problem on our last call. Their APAC reps have 40% lower win rates than US team. Main issues: cultural differences in selling style, language barriers in English-first playbooks, and no localized coaching. He wants to start with a focused sprint before the full platform rollout. Lisa Park will own this internally.",
      "timestamp": "2026-03-08T16:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Objection from Lisa: 'We tried online training before and reps didn't engage. They said it felt like homework.' Addressed by showing our engagement analytics and cohort-based approach with manager visibility. She liked the accountability aspect — managers can see who's practicing and who isn't.",
      "timestamp": "2026-03-06T14:00:00.000000"
    }
  ]
}
```

### Deal 3: QuantumLeap AI — Full Platform (Demo Scheduled)

```json
{
  "id": "deal_ql_001",
  "properties": {
    "dealname": "QuantumLeap AI — Full Platform License",
    "amount": "96000",
    "dealstage": "demo_scheduled",
    "dealstage_label": "Demo Scheduled",
    "pipeline": "default",
    "closedate": "2026-04-30",
    "createdate": "2026-02-20T09:00:00.000000",
    "hs_lastmodifieddate": "2026-03-08T11:00:00.000000",
    "hubspot_owner_id": "owner_101",
    "description": "Fast-growing AI startup that tripled their sales team in 6 months. No coaching infrastructure. CEO Amy Liu wants to standardize on MEDDIC methodology across all reps. Urgent: they're losing deals they should be winning."
  },
  "associations": {
    "company": "quantumleap_ai",
    "contact": "contact_ql_001"
  },
  "activities": [
    {
      "type": "NOTE",
      "body": "Priya Sharma (Head of Revenue) is our champion. She joined from Salesforce 3 months ago and is frustrated that the team has no consistent sales process. Quote: 'Half our reps don't even know what MEDDIC stands for. We're leaving money on the table.' She wants the coaching platform live within 30 days.",
      "timestamp": "2026-03-08T11:00:00.000000"
    },
    {
      "type": "CALL",
      "body": "Discovery call with Priya and Jake Morrison (Sales Director). Key findings: 40 reps total (up from 12 six months ago), average ramp time is 5 months (industry avg 3), win rate dropped from 32% to 19% as they scaled, no sales playbook exists yet (building one now), budget approved — Amy Liu (CEO) fast-tracked it after Q4 miss. They're also considering DataFlow Suite as a lighter-weight alternative but Priya thinks it lacks the coaching depth they need.",
      "timestamp": "2026-03-03T14:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Sent Priya our ROI calculator and the Apex Manufacturing case study (similar scaling challenge — went from 15% to 30% win rate in 12 weeks). She forwarded it to Amy. Demo scheduled for March 15.",
      "timestamp": "2026-02-28T10:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Inbound from QuantumLeap AI website. Priya Sharma filled out the demo request form. Notes: 'We tripled our sales team and our win rate collapsed. Need coaching solution ASAP. Evaluated a few tools but nothing has real AI roleplay.' Looks like a strong fit — fast timeline, clear pain, budget owner engaged.",
      "timestamp": "2026-02-20T09:00:00.000000"
    }
  ]
}
```

### Deal 4: QuantumLeap AI — New Hire Onboarding Add-On (Qualification)

```json
{
  "id": "deal_ql_002",
  "properties": {
    "dealname": "QuantumLeap AI — New Hire Onboarding Program",
    "amount": "24000",
    "dealstage": "qualification",
    "dealstage_label": "Qualification",
    "pipeline": "default",
    "closedate": "2026-05-15",
    "createdate": "2026-03-05T10:00:00.000000",
    "hs_lastmodifieddate": "2026-03-06T15:00:00.000000",
    "hubspot_owner_id": "owner_103",
    "description": "Upsell from main QuantumLeap deal. They're hiring 15 more reps in Q2 and want a structured onboarding program using our cohort feature."
  },
  "associations": {
    "company": "quantumleap_ai",
    "contact": "contact_ql_002"
  },
  "activities": [
    {
      "type": "NOTE",
      "body": "Jake Morrison asked about onboarding specifically. Their current process: 2 weeks of shadowing, then 'sink or swim.' New reps take 5 months to hit quota. He wants a structured 4-week program with progressive difficulty. I mentioned our /onboard feature and he lit up — 'That's exactly what we need.' Biggest objection: timeline. They need onboarding live by May 1 when the new cohort starts.",
      "timestamp": "2026-03-06T15:00:00.000000"
    },
    {
      "type": "NOTE",
      "body": "Jake shared their current challenges with new hire ramp: reps practice on real leads and lose them, no consistent pitch delivery, managers can't coach 15 new reps individually. He wants the AI to handle the practice reps so managers can focus on deal strategy. Pricing concern: wants to bundle with the main platform deal.",
      "timestamp": "2026-03-05T10:00:00.000000"
    }
  ]
}
```

---

## Step 4: Add Enrichment Notes to 4 Existing Deals

Add 2-3 new activity notes to existing deals to increase objection diversity and competitor mentions for `/market-insights`. These go into the `activities` array of existing deals.

### Add to `deal_992410` (NovaTech — Annual Platform License)

Append to existing activities:

```json
{
  "type": "NOTE",
  "body": "Pricing objection: Wei said their CFO is comparing our per-seat pricing to CloudSync Pro's flat-rate model. CloudSync Pro quoted them $35K/year flat for unlimited users. I explained our model includes AI roleplay tokens and personalized coaching, which CloudSync Pro doesn't offer. Need to build a value comparison one-pager. Also: security review is a concern — they need SOC 2 Type II, not just Type I.",
  "timestamp": "2026-03-04T10:00:00.000000"
},
{
  "type": "NOTE",
  "body": "Integration concern from their CTO (Marcus): they run a custom Salesforce instance with heavy automation. Asked if our platform can sync coaching data back to their Salesforce dashboards. I confirmed yes via API but flagged this as a post-implementation phase. Marcus seemed satisfied but wants it in the contract as a committed roadmap item.",
  "timestamp": "2026-02-26T15:00:00.000000"
}
```

### Add to `deal_269957` (NovaTech — Enterprise Expansion)

Append to existing activities:

```json
{
  "type": "NOTE",
  "body": "Timeline objection: Wei wants to push the expansion start to Q3 instead of Q2. Reason: their EMEA team isn't ready for rollout and they don't want to 'half-launch.' I proposed a phased approach — US team in Q2, EMEA in Q3 — with a single contract. She's taking it to the CFO. If we lose the Q2 start, we risk losing momentum to AgileStack who just opened a European office.",
  "timestamp": "2026-03-06T11:00:00.000000"
}
```

### Add to CloudBridge deal (`deal` in negotiation at $72K)

Find the CloudBridge Systems — Enterprise Expansion deal and append:

```json
{
  "type": "NOTE",
  "body": "Security deep-dive with David Patel (VP Eng). He grilled us on data residency — they need EU data to stay in EU (GDPR). Our current hosting is US-only. This is a real blocker. Options: (1) add EU hosting by Q3, (2) offer on-prem deployment, (3) partner with a EU cloud provider. Escalating internally. If we can't solve this, DataFlow Suite becomes a real threat — they already have EU hosting.",
  "timestamp": "2026-03-07T14:00:00.000000"
},
{
  "type": "NOTE",
  "body": "Budget expansion: Yuki Williams secured additional budget from their CTO. Original deal was $72K, now they want to include their 25-person SDR team in addition to the 15 AEs. New deal value could be $120K. But the GDPR blocker needs to be solved first. Yuki said: 'We love the product but our legal team won't sign off without EU data residency.'",
  "timestamp": "2026-03-09T10:00:00.000000"
}
```

### Add to Velocity Retail deal (`deal` in negotiation at $24K)

Find the Velocity Retail deal and append:

```json
{
  "type": "NOTE",
  "body": "Pricing pushback from Wei Kim (Director IT). They think $24K is too much for a team of 8 reps. Compared us to 'free YouTube training videos.' I repositioned the value around measurable ROI: showed the Apex Manufacturing case study (15% close rate improvement). She acknowledged the difference but wants a 3-month pilot at reduced cost before committing to annual. Nexus Platform offered them a free pilot — competitive pressure.",
  "timestamp": "2026-03-08T09:00:00.000000"
}
```

---

## Step 5: Add New Call Transcripts

### `call_transcripts/discovery_call_dataflow_2026-03-05.md`

```markdown
# Discovery Call — DataFlow Inc
**Date:** March 5, 2026
**Attendees:** Lisa Park (VP Sales Enablement, DataFlow), Our Rep
**Duration:** 45 minutes

## Key Points

**Current State:**
- 200 sales reps across US (120), EMEA (50), APAC (30)
- Currently using Nexus Platform for coaching — contract expires April 30
- Unhappy with Nexus: static scripts only, no AI roleplay, basic reporting
- EMEA team underperforming significantly (40% lower win rates than US)

**Pain Points:**
- "Our EMEA managers say Nexus scenarios feel like reading from a script. Reps check the box but don't actually improve."
- "We have no way to track who's actually getting better vs. just completing assignments."
- "Localization is a nightmare — everything is in English. Our German and French reps struggle."
- "Implementation with Nexus took 6 months. We can't afford that again."

**Requirements:**
1. AI-powered roleplay (not scripted)
2. Multi-language support (English, German, French minimum)
3. Skill gap tracking per rep with trend data
4. Manager dashboards by region
5. Implementation in 4 weeks max

**Budget:** $200K approved by CRO (Raj Gupta)
**Timeline:** Decision by March 30, go-live by May 1
**Competitors:** Nexus Platform (incumbent, leaving), CloudSync Pro (demoed, "underwhelming"), AgileStack (ruled out, too SMB)

## Objections Raised
1. "How fast can you implement for 200 users?" — Addressed with phased rollout plan
2. "Our Nexus data — can you migrate scenario history?" — Committed to data migration support
3. "What if reps don't engage? We've had adoption problems before." — Showed engagement analytics and manager accountability features

## Next Steps
- Send implementation timeline document
- Schedule demo with full feature walkthrough
- Connect Lisa with Apex Manufacturing reference customer
```

### `call_transcripts/negotiation_call_cloudbridge_2026-03-08.md`

```markdown
# Negotiation Call — CloudBridge Systems
**Date:** March 8, 2026
**Attendees:** Yuki Williams (CDO), David Patel (VP Eng), Our Rep
**Duration:** 30 minutes

## Key Points

**Deal Update:**
- Original deal: $72K for 15 AEs
- Expansion: Want to include 25-person SDR team → new value ~$120K
- Budget approved, but GDPR blocker is critical

**GDPR Discussion:**
- David: "Our legal team requires all EU employee data to be processed within the EU. This is non-negotiable."
- Explored options: EU hosting (our roadmap), on-prem, third-party EU cloud
- David prefers EU hosting (least operational overhead for their team)
- DataFlow Suite already has EU hosting — making them a competitive threat

**Pricing:**
- Yuki pushing for volume discount on expanded deal
- Proposed 12% discount for 40 seats + 2-year commitment
- They want 18% — still negotiating

## Objections
1. "EU data residency is a hard requirement" — Escalating to our infrastructure team
2. "DataFlow Suite quoted us 18% cheaper" — Differentiated on AI coaching quality and ROI
3. "Can we get a 90-day out clause?" — Offered 60-day out with 30-day notice

## Next Steps
- Internal escalation on EU hosting timeline
- Send revised proposal with expanded seat count
- Follow up with legal team on data processing agreement
```

### `call_transcripts/demo_call_quantumleap_2026-03-03.md`

```markdown
# Discovery Call — QuantumLeap AI
**Date:** March 3, 2026
**Attendees:** Priya Sharma (Head of Revenue), Jake Morrison (Sales Director), Our Rep
**Duration:** 50 minutes

## Key Points

**Company Context:**
- Series B AI startup, $8M ARR, growing fast
- Sales team tripled from 12 to 40 reps in 6 months
- Win rate dropped from 32% to 19% during scaling
- No formal sales methodology or playbook

**Pain Points:**
- Priya: "Half our reps don't even know what MEDDIC stands for. We're leaving money on the table."
- Jake: "New reps practice on real leads and burn them. We literally lost a $200K deal because a junior rep mishandled the discovery call."
- No coaching infrastructure — managers overwhelmed coaching 40 reps
- Average ramp time: 5 months (industry avg: 3 months)

**Requirements:**
1. MEDDIC methodology training and scoring
2. AI roleplay for safe practice
3. New hire onboarding program (4-week structured ramp)
4. Product launch training (they ship quarterly and reps can't keep up)
5. Live within 30 days

**Budget:** CEO fast-tracked after Q4 revenue miss. Priya has approval for $120K/year.
**Timeline:** Decision in 2 weeks, need live by April 15
**Competitors:** DataFlow Suite (lighter weight, lacks coaching depth per Priya)

## Objections
1. "Can your AI actually simulate our specific buyer personas?" — Live demo'd a custom persona, impressed them
2. "We don't have a playbook yet — can you help us build one?" — Mentioned playbook RAG and methodology templates
3. "Thirty days is aggressive for implementation" — Showed 2-week quick-start plan
4. "What about our product launch cadence? We ship quarterly." — Showed /launch-training feature concept

## Next Steps
- Full product demo on March 15 (Amy Liu CEO joining)
- Send ROI calculator and Apex Manufacturing case study
- Prepare MEDDIC onboarding demo scenario
```

---

## Step 6: Add New Email Threads

### `email_threads/thread_dataflow_pricing_negotiation.json`

```json
[
  {
    "id": "email_df_001",
    "from": "our.rep@ourcompany.com",
    "to": "tom.baker@dataflow.com",
    "cc": "lisa.park@dataflow.com",
    "subject": "DataFlow Inc — Pricing Proposal for 200-Seat Deployment",
    "date": "2026-03-07T09:00:00.000000",
    "body": "Hi Tom,\n\nFollowing our conversation, I've attached the pricing proposal for 200 seats with the 10% volume discount for a 2-year commitment. Key highlights:\n\n- Year 1: $162,000 (10% off standard $180,000)\n- Year 2: $162,000 (locked rate)\n- Includes: AI roleplay, skill analytics, team dashboards, multi-language (EN/DE/FR)\n- Implementation: 4-week phased rollout with dedicated CSM\n- Data migration from Nexus Platform: included at no cost\n\nI'd love to schedule a call with Raj to walk through the ROI model. Would Thursday at 2pm PT work?\n\nBest,\nOur Rep"
  },
  {
    "id": "email_df_002",
    "from": "tom.baker@dataflow.com",
    "to": "our.rep@ourcompany.com",
    "cc": "lisa.park@dataflow.com, raj.gupta@dataflow.com",
    "subject": "Re: DataFlow Inc — Pricing Proposal for 200-Seat Deployment",
    "date": "2026-03-08T14:00:00.000000",
    "body": "Thanks for the proposal. Raj is looping in.\n\nTwo items we need to discuss:\n1. We're targeting 15% discount, not 10%. Our Nexus contract was significantly cheaper on a per-seat basis.\n2. Can you add a 90-day performance guarantee? If adoption doesn't hit 70% by Day 90, we want the option to exit.\n\nThursday 2pm works for Raj. Please send a calendar invite.\n\n— Tom"
  },
  {
    "id": "email_df_003",
    "from": "lisa.park@dataflow.com",
    "to": "our.rep@ourcompany.com",
    "subject": "Quick question on multi-language",
    "date": "2026-03-09T08:30:00.000000",
    "body": "Hey,\n\nSeparate from the pricing discussion — can the AI coach actually roleplay in German and French? Not just translate the UI, but actually simulate a German buyer with German business culture? Our EMEA reps specifically asked about this.\n\nAlso, can managers run the team dashboard filtered by region? I need to see EMEA vs US vs APAC performance separately.\n\nThanks,\nLisa"
  }
]
```

### `email_threads/thread_cloudbridge_expansion.json`

```json
[
  {
    "id": "email_cb_001",
    "from": "yuki.williams@cloudbridge.dev",
    "to": "our.rep@ourcompany.com",
    "subject": "Expanding our deal + GDPR question",
    "date": "2026-03-09T10:15:00.000000",
    "body": "Hi,\n\nGood news: I got approval to include our SDR team. That brings us from 15 to 40 seats. Can you send an updated proposal?\n\nBad news: Our legal team flagged GDPR as a hard blocker. David Patel (cc'd on our last call) confirmed we need EU data residency for any tool processing employee data. Where does your platform host data?\n\nThis is urgent — our legal review window closes March 20. If we can't resolve by then, we'll need to look at alternatives.\n\n— Yuki"
  },
  {
    "id": "email_cb_002",
    "from": "our.rep@ourcompany.com",
    "to": "yuki.williams@cloudbridge.dev",
    "cc": "david.patel@cloudbridge.dev",
    "subject": "Re: Expanding our deal + GDPR question",
    "date": "2026-03-09T15:00:00.000000",
    "body": "Yuki,\n\nGreat news on the expansion! I'll have the updated proposal over by tomorrow.\n\nOn GDPR: I've escalated this to our infrastructure team. Current hosting is US (AWS us-east-1). We have EU hosting on our roadmap for Q3, but I'm exploring whether we can accelerate this for your timeline. I'll have a concrete answer by March 14.\n\nWould a Data Processing Agreement (DPA) with contractual EU hosting commitment by a specific date satisfy your legal team in the interim?\n\nBest,\nOur Rep"
  }
]
```

### `email_threads/thread_quantumleap_intro.json`

```json
[
  {
    "id": "email_ql_001",
    "from": "priya.sharma@quantumleap.ai",
    "to": "our.rep@ourcompany.com",
    "subject": "Demo request — QuantumLeap AI",
    "date": "2026-02-20T09:15:00.000000",
    "body": "Hi,\n\nI'm Priya Sharma, Head of Revenue at QuantumLeap AI. We're a Series B startup that's tripled our sales team to 40 reps. Our win rate has dropped significantly and we need a coaching solution urgently.\n\nWe've looked at a few tools but nothing has the AI-powered roleplay capability we need. Your platform came up in a conversation with a friend at Apex Industries who's a customer.\n\nCan we schedule a discovery call this week? Our CEO is pressing for a solution by end of Q1.\n\n— Priya"
  },
  {
    "id": "email_ql_002",
    "from": "our.rep@ourcompany.com",
    "to": "priya.sharma@quantumleap.ai",
    "subject": "Re: Demo request — QuantumLeap AI",
    "date": "2026-02-20T11:00:00.000000",
    "body": "Hi Priya,\n\nThanks for reaching out! The scaling challenge you describe is exactly what our platform was built for.\n\nI'd love to learn more about your team's needs. How about Thursday at 2pm PT for a discovery call? I'll send a calendar invite.\n\nIn the meantime, here's a quick case study from Apex Manufacturing — similar situation (rapid team scaling, win rate decline) and they saw 15% improvement in close rates within 12 weeks.\n\nLooking forward to the conversation!\n\nBest,\nOur Rep"
  }
]
```

---

## Step 7: Add New Meeting Notes

### `meeting_notes/prep_dataflow_negotiation_2026-03-13.md`

```markdown
# Meeting Prep — DataFlow Inc Pricing Call
**Date:** March 13, 2026 at 2:00 PM PT
**Attendees:** Tom Baker (VP Procurement), Raj Gupta (CRO), Our Rep
**Type:** Pricing Negotiation

## Objectives
1. Close on pricing (they want 15%, we offered 10%, floor is 12%)
2. Address the 90-day performance guarantee ask
3. Get Raj's verbal commitment to move forward

## Key Context
- Tom is the negotiator; Raj is the economic buyer and decision maker
- They're leaving Nexus Platform (contract expires April 30)
- Time pressure works in our favor — they need to be live before Nexus expires
- CloudSync Pro is a weak competitor here (Lisa said their demo was "underwhelming")
- AgileStack already eliminated

## Negotiation Strategy
- Offer 12% discount with 2-year + quarterly business review commitment
- Counter the 90-day guarantee with a 60-day adoption checkpoint (not exit clause)
- Emphasize the Nexus data migration we're including for free ($15K value)
- If Raj pushes hard on 15%, offer it contingent on 3-year deal

## Risks
- Tom may use CloudSync Pro pricing as leverage (they quoted lower)
- Raj hasn't been in our previous calls — may ask questions we've already covered
- If we can't close by March 30, they might extend Nexus month-to-month
```

### `meeting_notes/recap_cloudbridge_demo_2026-03-10.md`

```markdown
# Meeting Recap — CloudBridge Systems Expanded Demo
**Date:** March 10, 2026
**Attendees:** Yuki Williams (CDO), David Patel (VP Eng), James Ahmed (VP Sales), Our Rep
**Type:** Product Demo (Expanded Scope)

## What Happened
- Showed full platform demo for 40 seats (original 15 AEs + 25 SDRs)
- James Ahmed (VP Sales) joined for the first time — very engaged
- David Patel pressed hard on GDPR/EU hosting — this is the single blocker
- Yuki confirmed budget expansion approved

## Key Moments
- James loved the team dashboard: "This is exactly what I need to see which reps need coaching vs. which ones I should promote"
- David asked about data encryption at rest (AES-256 — we have this) and in transit (TLS 1.3 — we have this)
- The GDPR discussion took 20 minutes — David won't budge without EU hosting
- Yuki asked about ROI metrics — showed engagement analytics and the Apex case study

## Competitor Mention
- David mentioned DataFlow Suite has EU hosting already
- James said their sales team evaluated DataFlow Suite last year but found the coaching "too basic — more like a quiz platform than real practice"

## Action Items
1. [ ] Escalate EU hosting timeline internally (blocker)
2. [ ] Send updated proposal for 40 seats with volume discount
3. [ ] Prepare DPA (Data Processing Agreement) as interim solution
4. [ ] Schedule follow-up with David once we have EU hosting answer
```

---

## Step 8: Update Mock Calendar for Continuity

Update `data/mock_calendar/events.json` to ensure the DataFlow Inc meeting references match CRM data. The existing calendar entry already has:

```json
{
  "company": "DataFlow Inc",
  "contact_name": "Tom Baker",
  "contact_title": "VP Procurement"
}
```

This now matches `contact_df_001` in CRM. No calendar changes needed.

---

## Step 9: Sync New Data to HubSpot

After adding all new data to the local JSON files (Steps 1-7), run the existing sync script to push everything into the live HubSpot instance. The script reads from `data/mock_crm/*.json` and creates matching records in HubSpot via the Python SDK.

### Prerequisites

1. `HUBSPOT_ACCESS_TOKEN` must be set in `.env`
2. `hubspot-api-client` Python package must be installed (`pip install hubspot-api-client`)

### Dry run first

Preview what will be created without actually writing to HubSpot:

```bash
python scripts/sync_data_to_hubspot.py --dry-run
```

Verify the output shows the 2 new companies, 6 new contacts, 4 new deals, and their activity notes. The script is idempotent for existing records (it checks by name/email before creating), so re-running it won't duplicate the original 10 companies.

### Push to HubSpot

```bash
python scripts/sync_data_to_hubspot.py
```

This will:
1. Create **DataFlow Inc** and **QuantumLeap AI** as companies in HubSpot
2. Create the 6 new contacts and associate them with their companies
3. Create the 4 new deals and associate them with companies + contacts
4. Create all activity notes and associate them with their deals

### Update the industry mapping

The sync script has an `INDUSTRY_MAP` dict that maps JSON industry labels to HubSpot enum values. Add mappings for the two new industries:

```python
# Add to INDUSTRY_MAP in scripts/sync_data_to_hubspot.py:
"data infrastructure": "INFORMATION_TECHNOLOGY_AND_SERVICES",
"artificial intelligence": "INFORMATION_TECHNOLOGY_AND_SERVICES",
```

### Sync the enrichment notes (Step 4)

The enrichment notes added to existing deals (NovaTech, CloudBridge, Velocity Retail) will be picked up automatically by the sync script since it reads all activities from `deals.json`. However, if the existing deals were already synced previously, the script may skip them. In that case, run with the `--force-notes` flag (if available) or manually add notes via the HubSpot UI for those 4 existing deals.

Alternatively, add a targeted note-push helper:

```bash
# If the sync script doesn't re-push notes for existing deals,
# use this one-liner to push just the new notes:
python -c "
from scripts.sync_data_to_hubspot import push_notes_for_deal
push_notes_for_deal('deal_992410')   # NovaTech Annual - 2 new notes
push_notes_for_deal('deal_269957')   # NovaTech Enterprise - 1 new note
# CloudBridge and Velocity Retail deal IDs - check deals.json for exact IDs
"
```

### Verify in HubSpot

After syncing, spot-check in the HubSpot UI:
- Search for "DataFlow Inc" → should have 3 contacts, 2 deals, and 7+ notes
- Search for "QuantumLeap AI" → should have 3 contacts, 2 deals, and 6+ notes
- Check NovaTech's deal notes → should see the new pricing objection and integration concern notes

### If you need to clean up

The sync script supports cleanup:

```bash
python scripts/sync_data_to_hubspot.py --clean
```

This deletes all synced records from HubSpot (tracked by a local `.sync_manifest.json` file). Useful if you need to re-sync from scratch.

---

## Step 10: Create `data/mock_crm/meetings.json` Structured File

The existing meeting notes are markdown files (great for RAG) but unusable by the sync script. Create a structured JSON file alongside them that the sync script can read. Each meeting maps to a HubSpot meeting engagement object.

**File:** `data/mock_crm/meetings.json`

```json
[
  {
    "id": "meeting_novatech_demo",
    "title": "NovaTech Solutions — Platform Demo",
    "start_time": "2026-02-22T14:00:00.000000",
    "end_time": "2026-02-22T15:00:00.000000",
    "outcome": "SCHEDULED",
    "body": "Full platform demo for NovaTech's evaluation committee. Showing AI roleplay, team dashboards, and skill gap tracking. Key attendee: Wei Chen (VP Sales).\n\nPrep notes: Focus on MEDDIC scoring, show Apex Manufacturing case study, address Salesforce integration question from CTO Marcus.",
    "attendees": [
      {"name": "Wei Chen", "email": "wei.chen@novatech.io"},
      {"name": "Marcus Reed", "email": "marcus.reed@novatech.io"}
    ],
    "associations": {
      "company": "novatech",
      "contact": "contact_001",
      "deal": "deal_992410"
    },
    "source_file": "prep_novatech_demo_2026-02-22.md"
  },
  {
    "id": "meeting_cloudbridge_qbr",
    "title": "CloudBridge Systems — Quarterly Business Review",
    "start_time": "2026-02-15T10:00:00.000000",
    "end_time": "2026-02-15T11:00:00.000000",
    "outcome": "COMPLETED",
    "body": "QBR with CloudBridge. Reviewed platform usage metrics, training completion rates, and expansion opportunity for SDR team. Key discussion: GDPR/EU hosting blocker surfaced by VP Eng David Patel.\n\nOutcome: Budget approved for expansion from 15 to 40 seats, but EU data residency must be resolved before legal sign-off.",
    "attendees": [
      {"name": "Yuki Williams", "email": "yuki.williams@cloudbridge.dev"},
      {"name": "David Patel", "email": "david.patel@cloudbridge.dev"}
    ],
    "associations": {
      "company": "cloudbridge",
      "contact": "contact_007",
      "deal": "deal_663921"
    },
    "source_file": "recap_cloudbridge_qbr_2026-02-15.md"
  },
  {
    "id": "meeting_pinnacle_discovery",
    "title": "Pinnacle Financial Group — Discovery Call",
    "start_time": "2026-03-04T15:00:00.000000",
    "end_time": "2026-03-04T15:30:00.000000",
    "outcome": "COMPLETED",
    "body": "First meeting with Pinnacle Financial Group from conference lead (Revenue Summit 2026). Rachel O'Brien (VP Sales) and Daniel Singh (CDO) joined. 45 reps across 3 regions. Salesforce shop. Key concern: regulatory compliance and AI governance for financial services.",
    "attendees": [
      {"name": "Rachel O'Brien", "email": "rachel.obrien@pinnaclefg.com"},
      {"name": "Daniel Singh", "email": "daniel.singh@pinnaclefg.com"}
    ],
    "associations": {
      "company": "pinnacle_financial",
      "contact": "contact_013"
    },
    "source_file": "prep_pinnacle_discovery_2026-03-04.md"
  },
  {
    "id": "meeting_terralogistics_postmortem",
    "title": "TerraLogistics — Lost Deal Recap (Internal)",
    "start_time": "2026-01-30T11:00:00.000000",
    "end_time": "2026-01-30T11:30:00.000000",
    "outcome": "COMPLETED",
    "body": "Internal post-mortem on lost TerraLogistics deal. They went with a cheaper competitor. Key lessons: we didn't engage the economic buyer early enough, pricing wasn't competitive for their team size (8 reps), and our enterprise features were overkill for their needs.",
    "attendees": [],
    "associations": {
      "company": "terralogistics",
      "deal": "deal_884320"
    },
    "source_file": "recap_terralogistics_lost_deal_2026-01-30.md"
  },
  {
    "id": "meeting_dataflow_negotiation",
    "title": "DataFlow Inc — Pricing Negotiation with CRO",
    "start_time": "2026-03-13T14:00:00.000000",
    "end_time": "2026-03-13T15:00:00.000000",
    "outcome": "SCHEDULED",
    "body": "Pricing negotiation with Tom Baker (VP Procurement) and Raj Gupta (CRO). They want 15% discount; we offered 10%, floor is 12%. Must address 90-day performance guarantee ask. Goal: get Raj's verbal commitment.\n\nKey context: leaving Nexus Platform (contract expires April 30), CloudSync Pro is weak competitor, AgileStack eliminated.",
    "attendees": [
      {"name": "Tom Baker", "email": "tom.baker@dataflow.com"},
      {"name": "Raj Gupta", "email": "raj.gupta@dataflow.com"}
    ],
    "associations": {
      "company": "dataflow_inc",
      "contact": "contact_df_001",
      "deal": "deal_df_001"
    },
    "source_file": "prep_dataflow_negotiation_2026-03-13.md"
  },
  {
    "id": "meeting_cloudbridge_expanded_demo",
    "title": "CloudBridge Systems — Expanded Demo (40 Seats)",
    "start_time": "2026-03-10T13:00:00.000000",
    "end_time": "2026-03-10T14:00:00.000000",
    "outcome": "COMPLETED",
    "body": "Full platform demo for expanded scope (15 AEs + 25 SDRs = 40 seats). James Ahmed (VP Sales) joined for the first time — very engaged, loved team dashboard. David Patel pressed hard on GDPR/EU hosting. Budget expansion confirmed by Yuki.\n\nBlocker: EU data residency. DataFlow Suite has EU hosting already — competitive threat.",
    "attendees": [
      {"name": "Yuki Williams", "email": "yuki.williams@cloudbridge.dev"},
      {"name": "David Patel", "email": "david.patel@cloudbridge.dev"},
      {"name": "James Ahmed", "email": "james.ahmed@cloudbridge.dev"}
    ],
    "associations": {
      "company": "cloudbridge",
      "contact": "contact_007",
      "deal": "deal_663921"
    },
    "source_file": "recap_cloudbridge_demo_2026-03-10.md"
  }
]
```

**Why structured JSON alongside markdown:** The markdown files remain the source-of-truth for RAG queries (richer context, better for LLM consumption). The JSON file provides the structured metadata HubSpot needs (timestamps, attendee emails, associations). The `source_file` field links them.

**Note on associations:** Some `contact` and `deal` IDs reference records from the original data set (e.g., `contact_001`, `deal_992410`). Ensure the sync script resolves these via the ID mapping — if the original records were synced first, their HubSpot IDs will be in the mapping file.

---

## Step 11: Update Sync Script for Emails and Meetings

Add two new functions to `scripts/sync_data_to_hubspot.py` and update `main()` to call them.

### 11a. Add imports

Add to the import block at the top of the script:

```python
from hubspot.crm.objects.emails import SimplePublicObjectInputForCreate as EmailInput
from hubspot.crm.objects.meetings import SimplePublicObjectInputForCreate as MeetingInput
import glob
```

### 11b. Add association type constants

Add to the constants block (after `ASSOC_NOTE_TO_DEAL`):

```python
ASSOC_EMAIL_TO_CONTACT = 198    # email -> contact
ASSOC_EMAIL_TO_DEAL = 214       # email -> deal
ASSOC_EMAIL_TO_COMPANY = 186    # email -> company  (optional, for extra context)
ASSOC_MEETING_TO_CONTACT = 200  # meeting -> contact
ASSOC_MEETING_TO_DEAL = 206     # meeting -> deal
ASSOC_MEETING_TO_COMPANY = 188  # meeting -> company (optional)
```

**Important:** These are the default HubSpot-defined association type IDs. If your portal uses custom association types, check via the HubSpot Associations API: `GET /crm/v4/associations/{fromObjectType}/{toObjectType}/labels`.

### 11c. Add `load_email_threads()` helper

Add after `load_json_data()`:

```python
def load_email_threads():
    """Load all email thread JSON files from the email_threads directory."""
    threads_dir = os.path.join(MOCK_CRM_DIR, "email_threads")
    threads = []

    if not os.path.exists(threads_dir):
        print("  No email_threads directory found")
        return threads

    for filepath in sorted(glob.glob(os.path.join(threads_dir, "*.json"))):
        with open(filepath) as f:
            data = json.load(f)

        filename = os.path.basename(filepath)

        # Handle both formats:
        # Format A (old): {thread_id, subject, participants, messages: [...]}
        # Format B (new from Step 6): [{id, from, to, subject, date, body}, ...]
        if isinstance(data, list):
            # Format B: array of individual email objects
            threads.append({
                "filename": filename,
                "messages": data,
                "format": "flat"
            })
        elif isinstance(data, dict) and "messages" in data:
            # Format A: thread wrapper with nested messages
            threads.append({
                "filename": filename,
                "thread_id": data.get("thread_id", ""),
                "subject": data.get("subject", ""),
                "participants": data.get("participants", []),
                "messages": data.get("messages", []),
                "format": "threaded"
            })

    return threads


def load_meetings():
    """Load structured meetings from meetings.json."""
    meetings_file = os.path.join(MOCK_CRM_DIR, "meetings.json")
    if not os.path.exists(meetings_file):
        print("  No meetings.json found")
        return []
    with open(meetings_file) as f:
        return json.load(f)
```

### 11d. Add `create_emails()` function

Add after `create_notes()`:

```python
def create_emails(
    client: HubSpot,
    threads: list,
    contact_mapping: dict,
    deal_mapping: dict,
    company_mapping: dict,
    dry_run: bool = False
) -> int:
    """Create email engagement objects from email thread files.
    Returns total emails created."""

    total_messages = sum(len(t.get("messages", [])) for t in threads)
    print(f"\n--- Creating Emails ({total_messages} messages from {len(threads)} threads) ---")

    if total_messages == 0:
        print("  No email messages to create")
        return 0

    emails_created = 0

    for thread in threads:
        filename = thread["filename"]
        messages = thread.get("messages", [])
        fmt = thread.get("format", "threaded")

        # Determine subject for the thread
        if fmt == "threaded":
            thread_subject = thread.get("subject", filename)
        else:
            # Flat format: use first message's subject
            thread_subject = messages[0].get("subject", filename) if messages else filename

        thread_created = 0
        for msg in messages:
            # Extract fields based on format
            if fmt == "threaded":
                sender = msg.get("from", "")
                recipients = msg.get("to", [])
                if isinstance(recipients, str):
                    recipients = [recipients]
                cc = msg.get("cc", [])
                if isinstance(cc, str):
                    cc = [cc]
                date_str = msg.get("date", "")
                body = msg.get("body", "")
                subject = thread_subject
            else:
                # Flat format (Step 6 email threads)
                sender = msg.get("from", "")
                recipients_raw = msg.get("to", "")
                if isinstance(recipients_raw, str):
                    recipients = [recipients_raw]
                else:
                    recipients = recipients_raw
                cc_raw = msg.get("cc", "")
                if isinstance(cc_raw, str):
                    cc = [c.strip() for c in cc_raw.split(",") if c.strip()] if cc_raw else []
                else:
                    cc = cc_raw or []
                date_str = msg.get("date", "")
                body = msg.get("body", "")
                subject = msg.get("subject", thread_subject)

            # Determine email direction
            is_outbound = "ourcompany.com" in sender or "our.rep" in sender
            direction = "EMAIL" if is_outbound else "INCOMING_EMAIL"

            # Convert timestamp
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                timestamp_ms = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                timestamp_ms = int(datetime.now().timestamp() * 1000)

            # Build properties
            props = {
                "hs_timestamp": str(timestamp_ms),
                "hs_email_direction": direction,
                "hs_email_subject": subject,
                "hs_email_text": body,
                "hs_email_status": "SENT",
                "hs_email_sender_email": sender,
                "hs_email_to_email": ";".join(recipients),
            }
            if cc:
                props["hs_email_cc_email"] = ";".join(cc)

            if dry_run:
                print(f"  [DRY-RUN] Would create: {direction} \"{subject[:50]}\" from {sender}")
                emails_created += 1
                continue

            try:
                result = client.crm.objects.emails.basic_api.create(
                    simple_public_object_input_for_create=EmailInput(properties=props)
                )
                email_id = result.id
                thread_created += 1
                emails_created += 1

                # Associate to contacts (match sender or recipients against contact mapping)
                all_emails_in_msg = [sender] + recipients + cc
                for contact_local_id, contact_hs_id in contact_mapping.items():
                    if contact_hs_id.startswith("dry_run_"):
                        continue
                    # We need to look up the contact's email from the original data
                    # For simplicity, try associating by matching known email patterns
                    # The association will be done by matching against known contact emails
                    pass  # See note below

                # Associate to deal — use thread-level mapping (see 11e)
                # Associate to company — use thread-level mapping (see 11e)

                time.sleep(0.1)
            except Exception as e:
                print(f"    x Failed to create email: {e}")

        if thread_created > 0:
            print(f"  + {thread_created} emails from \"{thread_subject[:50]}\"")

    print(f"  -> {emails_created} emails created")
    return emails_created
```

### 11e. Add email-to-record association mapping

The tricky part: email threads don't have explicit `associations` fields like deals do. Add a lookup table that maps thread filenames to their deal/company/contact associations:

```python
# Add as a constant near the top of the file, after STAGE_MAP:

EMAIL_THREAD_ASSOCIATIONS = {
    "thread_novatech_proposal_followup.json": {
        "company": "novatech",
        "deal": "deal_992410",
        "contacts": ["contact_001"]
    },
    "thread_greenfield_gone_cold.json": {
        "company": "greenfield",
        "deal": "deal_334216",
        "contacts": ["contact_005"]
    },
    "thread_apex_contract.json": {
        "company": "apex_manufacturing",
        "deal": "deal_778543",
        "contacts": ["contact_009", "contact_010"]
    },
    "thread_dataflow_pricing_negotiation.json": {
        "company": "dataflow_inc",
        "deal": "deal_df_001",
        "contacts": ["contact_df_001", "contact_df_002"]
    },
    "thread_cloudbridge_expansion.json": {
        "company": "cloudbridge",
        "deal": "deal_663921",
        "contacts": ["contact_007"]
    },
    "thread_quantumleap_intro.json": {
        "company": "quantumleap_ai",
        "deal": "deal_ql_001",
        "contacts": ["contact_ql_001"]
    }
}
```

Then update `create_emails()` to use this mapping for associations. After creating each email, add:

```python
                # Associate using thread-level mapping
                assocs = EMAIL_THREAD_ASSOCIATIONS.get(filename, {})

                # Associate to deal
                deal_local_id = assocs.get("deal")
                if deal_local_id and deal_local_id in deal_mapping:
                    deal_hs_id = deal_mapping[deal_local_id]
                    try:
                        client.crm.associations.v4.basic_api.create(
                            object_type="emails",
                            object_id=email_id,
                            to_object_type="deals",
                            to_object_id=deal_hs_id,
                            association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_EMAIL_TO_DEAL}]
                        )
                    except Exception as e:
                        print(f"    ! Email→deal association failed: {e}")

                # Associate to contacts
                for contact_local_id in assocs.get("contacts", []):
                    if contact_local_id in contact_mapping:
                        contact_hs_id = contact_mapping[contact_local_id]
                        try:
                            client.crm.associations.v4.basic_api.create(
                                object_type="emails",
                                object_id=email_id,
                                to_object_type="contacts",
                                to_object_id=contact_hs_id,
                                association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_EMAIL_TO_CONTACT}]
                            )
                        except Exception as e:
                            print(f"    ! Email→contact association failed: {e}")

                # Associate to company
                company_local_id = assocs.get("company")
                if company_local_id and company_local_id in company_mapping:
                    company_hs_id = company_mapping[company_local_id]
                    try:
                        client.crm.associations.v4.basic_api.create(
                            object_type="emails",
                            object_id=email_id,
                            to_object_type="companies",
                            to_object_id=company_hs_id,
                            association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_EMAIL_TO_COMPANY}]
                        )
                    except Exception as e:
                        print(f"    ! Email→company association failed: {e}")
```

### 11f. Add `create_meetings()` function

```python
def create_meetings(
    client: HubSpot,
    meetings: list,
    contact_mapping: dict,
    deal_mapping: dict,
    company_mapping: dict,
    dry_run: bool = False
) -> int:
    """Create meeting engagement objects from meetings.json.
    Returns total meetings created."""

    print(f"\n--- Creating Meetings ({len(meetings)} records) ---")

    if not meetings:
        print("  No meetings to create")
        return 0

    meetings_created = 0

    for meeting in meetings:
        local_id = meeting.get("id", "unknown")
        title = meeting.get("title", "Untitled Meeting")
        body = meeting.get("body", "")
        outcome = meeting.get("outcome", "COMPLETED")
        start_time = meeting.get("start_time", "")
        end_time = meeting.get("end_time", "")
        attendees = meeting.get("attendees", [])
        assocs = meeting.get("associations", {})

        # Convert timestamps to Unix milliseconds
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            start_ms = int(start_dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            start_ms = int(datetime.now().timestamp() * 1000)

        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            end_ms = int(end_dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            end_ms = start_ms + 3600000  # Default 1-hour meeting

        # Build properties
        props = {
            "hs_timestamp": str(start_ms),
            "hs_meeting_title": title,
            "hs_meeting_body": body,
            "hs_meeting_start_time": str(start_ms),
            "hs_meeting_end_time": str(end_ms),
            "hs_meeting_outcome": outcome,
        }

        # Add attendee emails as semicolon-separated list
        if attendees:
            external_emails = [a["email"] for a in attendees if a.get("email")]
            if external_emails:
                props["hs_meeting_external_url"] = ""  # Required field, can be empty
                # HubSpot stores attendees via associations, but we can add
                # a text note with attendee info
                props["hs_meeting_body"] = f"Attendees: {', '.join(external_emails)}\n\n{body}"

        if dry_run:
            print(f"  [DRY-RUN] Would create: \"{title}\" ({outcome})")
            meetings_created += 1
            continue

        try:
            result = client.crm.objects.meetings.basic_api.create(
                simple_public_object_input_for_create=MeetingInput(properties=props)
            )
            meeting_id = result.id
            meetings_created += 1
            print(f"  + \"{title}\" ({outcome}) -> HubSpot ID: {meeting_id}")

            # Associate to deal
            deal_local_id = assocs.get("deal")
            if deal_local_id and deal_local_id in deal_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="meetings",
                        object_id=meeting_id,
                        to_object_type="deals",
                        to_object_id=deal_mapping[deal_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_DEAL}]
                    )
                except Exception as e:
                    print(f"    ! Meeting→deal association failed: {e}")

            # Associate to contacts
            contact_local_id = assocs.get("contact")
            if contact_local_id and contact_local_id in contact_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="meetings",
                        object_id=meeting_id,
                        to_object_type="contacts",
                        to_object_id=contact_mapping[contact_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_CONTACT}]
                    )
                except Exception as e:
                    print(f"    ! Meeting→contact association failed: {e}")

            # Also associate attendees by email lookup
            for attendee in attendees:
                attendee_email = attendee.get("email", "")
                # Find contact by email in our mapping
                for c_local_id, c_hs_id in contact_mapping.items():
                    if c_hs_id.startswith("dry_run_"):
                        continue
                    # We'll associate the primary contact above;
                    # additional attendees need a reverse email lookup
                    # For now, skip — the primary association covers the key relationship
                    pass

            # Associate to company
            company_local_id = assocs.get("company")
            if company_local_id and company_local_id in company_mapping:
                try:
                    client.crm.associations.v4.basic_api.create(
                        object_type="meetings",
                        object_id=meeting_id,
                        to_object_type="companies",
                        to_object_id=company_mapping[company_local_id],
                        association_spec=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": ASSOC_MEETING_TO_COMPANY}]
                    )
                except Exception as e:
                    print(f"    ! Meeting→company association failed: {e}")

            time.sleep(0.1)
        except Exception as e:
            print(f"    x Failed to create meeting \"{title}\": {e}")

    print(f"  -> {meetings_created} meetings created")
    return meetings_created
```

### 11g. Update `load_json_data()` to include emails and meetings

Replace `load_json_data()`:

```python
def load_json_data():
    """Load all JSON data files."""
    with open(os.path.join(MOCK_CRM_DIR, "companies.json")) as f:
        companies = json.load(f)

    with open(os.path.join(MOCK_CRM_DIR, "contacts.json")) as f:
        contacts = json.load(f)

    with open(os.path.join(MOCK_CRM_DIR, "deals.json")) as f:
        deals = json.load(f)

    email_threads = load_email_threads()
    meetings = load_meetings()

    return companies, contacts, deals, email_threads, meetings
```

### 11h. Update `main()` to call the new functions

Update the data loading and creation calls in `main()`:

```python
    # Load data
    companies, contacts, deals, email_threads, meetings = load_json_data()
    total_emails = sum(len(t.get("messages", [])) for t in email_threads)
    print(f"\nLoaded: {len(companies)} companies, {len(contacts)} contacts, "
          f"{len(deals)} deals, {total_emails} emails, {len(meetings)} meetings")

    # Create records (order matters — companies first, then contacts, then deals,
    # then engagement objects that reference all three)
    company_mapping = create_companies(client, companies, dry_run=args.dry_run)
    contact_mapping = create_contacts(client, contacts, company_mapping, dry_run=args.dry_run)
    deal_mapping = create_deals(client, deals, company_mapping, contact_mapping, dry_run=args.dry_run)
    notes_count = create_notes(client, deals, deal_mapping, dry_run=args.dry_run)
    emails_count = create_emails(client, email_threads, contact_mapping, deal_mapping, company_mapping, dry_run=args.dry_run)
    meetings_count = create_meetings(client, meetings, contact_mapping, deal_mapping, company_mapping, dry_run=args.dry_run)

    # Save mapping
    full_mapping = {
        "companies": company_mapping,
        "contacts": contact_mapping,
        "deals": deal_mapping,
        "synced_at": datetime.now().isoformat(),
    }

    if not args.dry_run:
        save_mapping(full_mapping)

    # Summary
    print("\n" + "=" * 60)
    print("Sync complete!" if not args.dry_run else "Dry run complete!")
    print(f"  Companies: {len(company_mapping)} | Contacts: {len(contact_mapping)} | "
          f"Deals: {len(deal_mapping)} | Notes: {notes_count} | "
          f"Emails: {emails_count} | Meetings: {meetings_count}")
    if not args.dry_run:
        print(f"  ID mapping saved to: {ID_MAPPING_FILE}")
    print("=" * 60)
```

### 11i. Update `clean_synced_records()` for email and meeting cleanup

Add "emails" and "meetings" to the cleanup loop. Update the deletion order:

```python
    # Delete in reverse order: engagement objects first, then core objects
    for object_type in ["emails", "meetings", "notes", "deals", "contacts", "companies"]:
        ids = mapping.get(object_type, {})
        if not ids:
            continue

        # ... existing deletion logic ...

        # Add handlers for new types:
        elif object_type == "emails":
            client.crm.objects.emails.basic_api.archive(email_id=hubspot_id)
        elif object_type == "meetings":
            client.crm.objects.meetings.basic_api.archive(meeting_id=hubspot_id)
```

Also update the mapping save to include email and meeting IDs (track them in the mapping dict inside `create_emails()` and `create_meetings()` — return dicts instead of ints, or save a separate counter).

---

## Step 12: Verify Emails and Meetings in HubSpot

After running the updated sync script:

### Dry run first

```bash
python scripts/sync_data_to_hubspot.py --dry-run
```

Expected output should show:
- 6 email threads → ~15 individual email messages
- 6 meetings

### Push to HubSpot

```bash
python scripts/sync_data_to_hubspot.py
```

### Verify in HubSpot UI

1. **Emails:** Go to a contact record (e.g., Tom Baker at DataFlow Inc) → Activity tab → should show the pricing negotiation email thread
2. **Meetings:** Go to a deal record (e.g., DataFlow Enterprise Platform Migration) → Activity tab → should show the March 13 pricing negotiation meeting
3. **Cross-referencing:** The CloudBridge deal should show both the expansion email thread AND the QBR/demo meeting records

### What this enables for demos

| Feature | Email Sync Benefit | Meeting Sync Benefit |
|---|---|---|
| `/research [company]` | HubSpot MCP can pull email history for a company | Meeting history shows engagement timeline |
| `/deal [deal]` | Deal activity timeline includes email exchanges | Shows upcoming/past meetings on the deal |
| `/coach prep` | Can reference recent email context for meeting prep | Knows what was discussed in prior meetings |
| `/draft-email` | References prior email thread for context continuity | Can draft follow-up emails based on meeting outcomes |
| `/market-insights` | Email threads capture competitor mentions organically | Meeting recaps feed into objection analysis |
| Auto-CRM-detect | Validates that email context matches CRM records | Meeting follow-ups can be auto-suggested |

---

## Summary of New Data

| Type | Added | New Total | Synced to HubSpot? |
|------|-------|-----------|--------------------|
| Companies | +2 (DataFlow Inc, QuantumLeap AI) | 12 | Yes — via `create_companies()` |
| Contacts | +6 (3 DataFlow, 3 QuantumLeap) | 26 | Yes — via `create_contacts()` |
| Deals | +4 (2 DataFlow, 2 QuantumLeap) | 20 | Yes — via `create_deals()` |
| Activity Notes | +4 new deals (13 notes) + enrichment to 4 existing deals (6 notes) | 82 | Yes — via `create_notes()` |
| Call Transcripts | +3 | 8 | No — local only (RAG) |
| Email Threads | +3 (6 total, ~15 messages) | 6 | Yes — via `create_emails()` |
| Meeting Notes | +2 (6 total structured) | 6 | Yes — via `create_meetings()` |

## What This Enables for Demos

| Demo Scenario | Data Support |
|---|---|
| `/my-day` → "Prep for Meeting" → DataFlow negotiation | DataFlow Inc company + contacts + deal + notes all in CRM |
| `/market-insights` competitor analysis | Notes now mention Nexus Platform (3x), CloudSync Pro (3x), AgileStack (2x), DataFlow Suite (3x) instead of just "CompetitorAlpha" |
| `/market-insights` objection patterns | Notes include price (3x), timeline (2x), security/GDPR (3x), integration (2x), adoption concern (2x) |
| `/draft-email DataFlow` with attachment | Contact `tom.baker@dataflow.com` with active negotiation context → attach pricing guide |
| `/launch-training` with QuantumLeap story | QuantumLeap deal notes describe exactly the problem product launch training solves |
| `/onboard` narrative | QuantumLeap's "sink or swim" onboarding problem is documented in deal notes |
| Auto-CRM-detect testing | Channel messages mentioning "DataFlow", "QuantumLeap", "CloudBridge" will match CRM company names |
| `/log DataFlow` | Multiple contacts and deals to associate notes with |
| `/coach roleplay` pricing negotiation | DataFlow deal provides rich context for a negotiation scenario |
| `/skill-gaps` + `/team-dashboard` | More varied notes feed richer SQLite seed data for training analytics |
