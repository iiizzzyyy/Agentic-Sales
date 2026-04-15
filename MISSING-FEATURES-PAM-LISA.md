# Missing Features: Pam & Lisa vs. Our Slack Bot

Comparison of Jam's two AI agents (Pam = Personal Assistant, Lisa = Personal Coach) against our current SalesCoach AI Slack bot implementation.

---

## Pam (Personal Assistant) — Missing Features

### 1. Voice-First Interaction
**Pam:** "You interact with Pam just by speaking. Call in, ask a question, or give a command." Hands-free voice interface designed for reps in the field.
**Our bot:** Text-only. All interaction via slash commands, typed messages, and button clicks. No voice input, no speech-to-text, no call-in capability.
**Gap:** Major — Pam's entire UX is built around voice. Field reps can use it while driving.

### 2. Automated CRM Updates from Conversations
**Pam:** "Captures every interaction and keeps your CRM accurate without extra effort." Automatically logs visit notes, call outcomes, and deal updates to CRM from voice conversations.
**Our bot:** CRM is read-only. We pull data from HubSpot but never write back automatically. The `/deal` and `/research` commands display CRM data; they don't update it. There is a "Log Note" button on deal cards but it doesn't auto-capture from conversations.
**Gap:** Major — Pam turns conversations into structured CRM entries automatically.

### 3. Post-Meeting Visit Logging by Voice
**Pam:** "Log a visit with Dr. Muller." Reps can dictate visit summaries that get structured and pushed to CRM.
**Our bot:** No visit logging concept. No way to say "I just met with X, here's what happened" and have it auto-logged.
**Gap:** Major — This is Pam's core time-savings feature (4h/week claim).

### 4. Follow-Up Automation (Email + Attachment Sending)
**Pam:** "Send a thank-you email with the brochure." Can compose and actually send emails with attachments.
**Our bot:** We draft emails and can create Gmail drafts, but we don't actually send them. No attachment support. No document/brochure attachment workflow.
**Gap:** Medium — We handle drafting well but lack the send + attach step.

### 5. Calendar & Day Plan Awareness
**Pam:** "Planning & navigation: reads your day plan, navigates to customers, reschedules if needed." / "What's my next meeting?"
**Our bot:** Zero calendar integration. No awareness of meetings, schedules, or appointments. The `/coach prep` command preps for a meeting but doesn't know when meetings actually are.
**Gap:** Major — Pam proactively briefs reps before each meeting based on calendar context.

### 6. Navigation / Routing to Customers
**Pam:** "Navigates to customers" — presumably driving directions or map integration for field reps.
**Our bot:** No geolocation, mapping, or navigation features.
**Gap:** Medium — Specific to field sales; less relevant for inside sales use cases.

### 7. Automatic Rescheduling
**Pam:** "Reschedules if needed" — can move meetings based on field conditions.
**Our bot:** No scheduling capabilities at all.
**Gap:** Medium — Requires calendar write access.

### 8. Order Capture & Entry
**Pam:** Designed for reps who take orders in the field. Implied by the CRM/ERP integration: "integrates seamlessly with your existing tools (CRM, ERP, calendar)."
**Our bot:** No order entry, quote generation, or ERP integration.
**Gap:** Medium — Relevant for field sales, less so for SaaS sales.

### 9. Performance Self-Service ("How's my month going?")
**Pam:** "Performance insights: answers 'How's my month going?' or 'What's my Q3 target?' in seconds."
**Our bot:** We have `/scorecard` and `/pipeline` which cover some of this, but it's not conversational. A rep can't ask natural-language performance questions and get instant answers. `/ask` could handle this but isn't specifically optimized for personal performance queries.
**Gap:** Small — We have the data, just need to make `/ask` smarter about personal performance context.

### 10. Multi-Language Support
**Pam:** "Built for global sales organizations with support for multiple languages, regional preferences, and cultural nuances."
**Our bot:** English only. All prompts, formatters, and UI text are hardcoded in English.
**Gap:** Large for international teams — Not relevant for English-only POC/demo.

### 11. Deep CRM/ERP Integration (Write-Back)
**Pam:** Integrates with Salesforce, Dynamics 365, HubSpot, SAP — and writes back to them.
**Our bot:** Read-only HubSpot integration via MCP. No Salesforce, Dynamics, or SAP. No write-back.
**Gap:** Medium — We have HubSpot read; missing write-back and multi-CRM.

### 12. Manager Visibility / Field Insights
**Pam:** "Gives managers real visibility into the field: understand customers & market shifts better."
**Our bot:** We have `/pipeline`, `/win-loss`, `/forecast`, `/alerts`, and `/scorecard` which give managers good visibility. But no "market shifts" intelligence or customer sentiment aggregation across all reps.
**Gap:** Small — We cover pipeline visibility well. Missing aggregate market/customer trend analysis.

### 13. Best Practice Sharing / Faster Onboarding
**Pam:** "Faster onboarding and training through best practice sharing."
**Our bot:** Our RAG playbook supports this conceptually, but there's no structured onboarding flow. No way for managers to curate "best practices" that get surfaced to new reps.
**Gap:** Medium — We have the infrastructure (RAG + playbooks) but not the onboarding workflow.

---

## Lisa (Personal Coach) — Missing Features

### 14. Simulation Builder / Effortless Setup
**Lisa:** "Rapidly create tailored sales simulations using your playbooks, buyer personas, and real sales data in no time."
**Our bot:** Roleplay scenarios are generated on-the-fly by the LLM. There's no manager-facing UI to create, save, name, and assign specific roleplay scenarios. No scenario library.
**Gap:** Major — Lisa lets managers build a library of reusable training scenarios.

### 15. Performance Management Dashboard
**Lisa:** "Track real-time progress with intuitive dashboards, easily spotting skill gaps and coaching opportunities."
**Our bot:** We have `/scorecard` for individual reps, but no manager-facing dashboard that shows all reps' coaching progress, skill scores over time, completion rates, or skill gap heatmaps.
**Gap:** Major — Lisa has a full analytics dashboard; we have a single-rep scorecard.

### 16. Skill Gap Detection
**Lisa:** "Lisa identifies skill gaps and individual coaching opportunities."
**Our bot:** Our roleplay debrief gives per-session feedback and scores, but there's no aggregation over time. If a rep consistently scores low on "discovery questions," we don't surface that pattern.
**Gap:** Major — We score individual sessions but don't track longitudinal skill trends.

### 17. Cohort-Based Learning Cycles
**Lisa:** "Launch cohort-based learning cycles that target specific skills and drive ongoing improvements."
**Our bot:** No concept of cohorts, learning paths, multi-week training programs, or skill-targeted drill sequences.
**Gap:** Major — This is a structured training management feature we don't have at all.

### 18. Custom Scorecards Aligned to Playbooks
**Lisa:** "Creates 100% customized simulations and scorecards aligned with your playbooks, buyer personas, and training gaps."
**Our bot:** Our coaching debrief has a fixed scoring rubric. There's no way for managers to define custom scoring criteria that map to their specific playbook or methodology (MEDDIC, SPIN, Challenger, etc.).
**Gap:** Large — We score generically; Lisa scores against the team's actual methodology.

### 19. Safe Practice Environment (Emphasis)
**Lisa:** "Equip every rep with their private, real-time and unbiased AI coach to confidently grow their sales skills." / "Allowing new reps to practice in a safe environment without risking actual leads."
**Our bot:** We have roleplay, but it runs in Slack channels where others can see. Our Phase 3 `/settings` coaching_privacy feature addresses this but isn't built yet.
**Gap:** Medium — Planned in Phase 3 (DM privacy) but not yet implemented.

### 20. Manager Assignment of Scenarios to Reps
**Lisa:** Implied by "track training progress" and "cohort-based learning" — managers can assign specific scenarios to reps.
**Our bot:** No assignment system. Reps self-serve with `/coach roleplay`. Managers can't push training to reps.
**Gap:** Large — No manager → rep assignment workflow exists.

### 21. Training Progress Tracking Per Rep
**Lisa:** "Track training progress in real-time." / "Monitor training effectiveness, engagement, and progress against individual targets."
**Our bot:** No persistent training history. Each roleplay session is independent. There's no record of how many sessions a rep has completed, their score trajectory, or which scenarios they've practiced.
**Gap:** Major — We have no training history or progress tracking whatsoever.

### 22. Engagement Analytics
**Lisa:** Tracks engagement (how often reps practice, session frequency, completion rates).
**Our bot:** No usage analytics. We don't know which reps use the bot, how often, or which features they use.
**Gap:** Large — No usage/engagement tracking at all.

### 23. Product Launch Training Mode
**Lisa:** "Launch new products and train your team on best practices with Lisa in record time."
**Our bot:** No concept of "product launch" training. We could potentially use playbook RAG for new product info, but there's no structured rollout workflow.
**Gap:** Medium — We have the RAG infrastructure; missing the workflow wrapper.

---

## Summary: Feature Gap Severity

| # | Feature | Source | Severity | Notes |
|---|---------|--------|----------|-------|
| 1 | Voice-first interaction | Pam | Critical | Pam's core differentiator |
| 2 | Auto CRM updates from conversations | Pam | Critical | Write-back to CRM from natural language |
| 3 | Voice visit logging | Pam | Critical | Core time-savings feature |
| 4 | Email send + attachments | Pam | Medium | We draft; they send |
| 5 | Calendar awareness | Pam | High | Proactive meeting prep |
| 6 | Navigation/routing | Pam | Low | Field sales specific |
| 7 | Auto rescheduling | Pam | Medium | Calendar write access |
| 8 | Order capture/ERP | Pam | Low | Field/distribution sales specific |
| 9 | "How's my month?" self-service | Pam | Low | `/ask` mostly covers this |
| 10 | Multi-language | Both | Low (for POC) | English-only is fine for demo |
| 11 | CRM write-back (multi-CRM) | Pam | Medium | We read HubSpot; no write |
| 12 | Market shift insights | Pam | Low | Pipeline visibility is solid |
| 13 | Structured onboarding flow | Pam | Medium | Infrastructure exists, workflow doesn't |
| 14 | Simulation builder UI | Lisa | High | Manager scenario library |
| 15 | Team performance dashboard | Lisa | High | Multi-rep coaching analytics |
| 16 | Skill gap detection | Lisa | High | Longitudinal skill tracking |
| 17 | Cohort-based learning | Lisa | High | Structured training programs |
| 18 | Custom methodology scorecards | Lisa | High | Score against MEDDIC/SPIN/etc |
| 19 | Private practice space | Lisa | Medium | Phase 3 planned (DM privacy) |
| 20 | Manager scenario assignment | Lisa | High | Push training to reps |
| 21 | Training progress tracking | Lisa | Critical | No coaching history at all |
| 22 | Engagement analytics | Lisa | High | No usage tracking |
| 23 | Product launch training mode | Lisa | Medium | RAG infra exists, workflow doesn't |

### By Priority for Our POC

**Should build for demo differentiation:**
- #14 Simulation builder (even a simple `/create-scenario` command)
- #15 Team dashboard (even a basic `/team-dashboard` view)
- #16 + #21 Skill tracking + training history (store session scores, show trend)
- #18 Custom scorecards (let managers pick MEDDIC vs SPIN scoring)
- #2 + #11 CRM write-back (even just "Log this note to HubSpot")

**Nice to have but not critical for demo:**
- #5 Calendar awareness (would make `/coach prep` much more impressive)
- #17 Cohort learning (complex to build, huge to demo)
- #20 Manager assignment (powerful but heavy)

**Out of scope for Slack POC:**
- #1 Voice interaction (requires native mobile app or Twilio integration)
- #3 Voice visit logging (same — needs audio pipeline)
- #6 Navigation (mobile app feature)
- #8 Order capture (different product vertical)
