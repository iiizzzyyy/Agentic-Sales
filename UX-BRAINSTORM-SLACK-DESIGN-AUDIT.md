# SalesCoach AI — UX Design Audit & Improvement Brainstorm

## Slack Official Design Principles vs. Our Implementation

This document maps Slack's official design guidelines against our current agent implementation, identifies gaps, and proposes prioritized improvements.

---

## 1. CRITICAL GAPS — High-Impact, Demo-Visible Issues

### 1A. No Message Cleanup After Interactions

**Slack Guideline:** "Visually rich messages are great in the moment, but they take up a lot of space. Think about whether buttons and menus need to stick around, or if you can condense the message down to a simple text record of what happened."

**Our Problem:** Zero cleanup across all 21 formatters. When a user clicks "Draft Follow-Up Email" on the /research card, the original research card stays fully expanded with all buttons still active. When a deal picker is used, the picker message stays visible. Over a 10-minute demo, the channel becomes a wall of dense cards.

**Proposed Fix:**
- After a button is clicked, UPDATE the original message to collapse it — remove the actions block and replace with a context line saying what happened (e.g., "✉️ Email drafted for Wei Ahmed • 2:34 PM")
- Use `client.chat_update()` with the original message `ts` to replace blocks
- For pickers (deal picker, contact picker, deal-for-email picker), replace the full picker with a single-line confirmation after selection
- Keep the header so users can still see what the card was about

**Impact:** Huge for demo — makes the conversation feel clean, professional, responsive

---

### 1B. No Ephemeral Messages for Loading States

**Slack Guideline:** "If the response only needs to be displayed to the user, use an ephemeral message rather than generate a DM." / "A chatty app is not necessarily a good thing."

**Our Problem:** Every command posts a permanent "Researching NovaTech... give me 15 seconds." loading message to the channel. This stays forever. After the real result arrives, you now have TWO messages — the loading message and the result. For /pipeline, /research, /coach, /forecast — every command doubles up.

**Proposed Fix:**
- Change ALL loading messages to ephemeral: `client.chat_postEphemeral()` — visible only to the invoking user, auto-disappears
- OR post the loading message, then DELETE it after the result arrives (using `chat_delete` with the loading message `ts`)
- OR post the loading message, then UPDATE it with the actual result (single message, no duplication)
- **Best approach for demo:** UPDATE pattern — post "Researching NovaTech..." then replace that same message with the full research card. Feels instant and clean.

**Impact:** Eliminates visual clutter, makes the agent feel polished

---

### 1C. Inconsistent Threading Strategy

**Slack Guideline:** "Just because the invocation happened in a channel doesn't mean other members need to see the rest of the process."

**Our Problem:** Roleplay uses threads (good). Everything else posts to channel. When someone does /research → clicks "Draft Email" → picks a contact → gets the email draft → clicks "Send" — that's 5 messages all in the main channel. Other team members see everything.

**Proposed Fix:**
- **Channel:** Initial command result (research card, pipeline digest, deal card) — these are valuable for the whole team
- **Thread:** All follow-up interactions (email drafts, contact pickers, deal pickers, coaching details) — threaded off the original card
- **Ephemeral:** Confirmations, loading states, errors — only the user sees them
- Specifically: when "Draft Follow-Up Email" is clicked on a /research card, the contact picker and subsequent email draft should appear as a thread reply to the research card, not as new channel messages

**Impact:** Makes the agent feel like a team tool, not a spam bot

---

### 1D. Information Overload on Key Cards

**Slack Guideline:** "Interactions should focus on what members are trying to do right then and there — focus on the simple, common tasks that make sense to complete inside Slack." / "It's easy to overload."

**Our Problem:** The /research card packs 10 blocks: company metrics, 5 contacts, 5 deals, 3 news items, talking points, 2 buttons, and a footer. The /handoff card is 14 blocks. The Home Tab is 18-25 blocks. On mobile, these become scrolling walls of text.

**Proposed Fix — Progressive Disclosure:**
- /research: Show SUMMARY card first (company name, industry, revenue, 1-line relationship status, talking points, buttons). Add a "Show Full Brief" button that expands to contacts, deals, news in a thread
- /pipeline: Show top-line metrics + flagged deals only. "See Stage Breakdown" and "See All Deals" as expansion buttons
- /handoff: Show deal snapshot + next steps. "Full Context" button for contacts, competitors, risks
- Use overflow menus (⋮) for secondary actions instead of showing all buttons upfront

**Impact:** Dramatically better mobile experience, faster scanning, matches how sales reps actually use tools (glance → drill down)

---

## 2. SIGNIFICANT GAPS — Functional Issues

### 2A. No Truncation Indicators

**Slack Guideline:** Accessibility — "Use short, clear sentences and paragraphs."

**Our Problem:** 14 formatters silently truncate content (120-2800 chars). /ask truncates answers at 2800 chars with no "..." or "View More" button. /deal truncates activities at 120 chars. Users never know they're missing information.

**Proposed Fix:**
- When content is truncated, append "... [truncated]" or add a "View Full Response" button
- For /ask: if answer > 2800 chars, show first 2800 + "📄 Full answer available" button that posts the complete text in a thread
- For deal activities: show count "Showing 4 of 12 activities" with "View All" button

---

### 2B. Vague Button Labels

**Slack Guideline:** "Give buttons brief, repetitive labels to avoid truncation." / Keep interactions clear.

**Our Problem:** Several buttons use vague labels:
- "More Detail" (on /objection) — more detail about what?
- "View Details" (on deal picker) — every picker button says the same thing
- "Take Action" (on alerts) — which action?
- "Full Analysis" (on /win-loss) — analysis of what?

**Proposed Fix:**
- "More Detail" → "Deep Dive: Objection Handling"
- "View Details" → just "View" (with the deal name already visible in the section)
- "Take Action" → "Update Deal" or "Contact Rep"
- "Full Analysis" → "Win/Loss Breakdown"
- Add emoji prefixes for visual scanning: "📧 Draft Email", "🎯 Start Roleplay", "📊 Full Breakdown"

---

### 2C. No Smart Defaults

**Slack Guideline:** "Instead of presenting a full menu of choices every time, you could make the user's last order the default option."

**Our Problem:** Every /research always shows the same 2 buttons (Draft Email, Start Roleplay). Every /deal shows the same 3-4 buttons. No personalization based on deal stage, recent activity, or user behavior.

**Proposed Fix:**
- If deal is in "Negotiation" stage → show "Handle Objection" button prominently
- If deal has no recent activity → show "Draft Follow-Up" as primary CTA
- If deal close date is past → show "Update Close Date" or "Mark Lost?"
- If user has done 3+ roleplays on this deal → show "Try a Different Scenario" instead of "Start Roleplay"
- For /pipeline: if there are stale deals, make "Follow Up on Stale Deal" the primary CTA

---

### 2D. No Error State UX

**Slack Guideline:** Build with empathy — "Users are people of all ability levels who may have poor internet connections."

**Our Problem:** When data is missing, we show bland italic text: "_No contacts found_", "_No recent activity_", "_No active deals_". No guidance on what to do about it.

**Proposed Fix:**
- "_No contacts found_" → "No contacts in CRM — `Add in HubSpot` or `/research` for web results"
- "_No recent activity_" → "No activity in 14+ days ⚠️ — consider `/draft-email` to re-engage"
- "_No active deals_" → "No deals yet — `Create in HubSpot` or ask me to `/draft-email` for outreach"
- For API/LLM failures: "I couldn't complete the research right now. Retry with `/research NovaTech` or try `/ask` for a quick lookup."

---

## 3. POLISH GAPS — Nice-to-Have Refinements

### 3A. No Respond-in-Right-Place Strategy

**Slack Guideline:** "Your app will need to use contextual knowledge to figure out the best place to respond."

**Proposed Fix:**
- If user runs /research in a DM with the bot → respond in DM (private research)
- If user runs /research in #sales-team → respond in channel (team visibility)
- If user runs /coach in #sales-team → always start in thread (don't spam the channel with roleplay)
- If user runs /pipeline in DM → respond in DM. In channel → respond in channel

---

### 3B. No Overflow Menus for Secondary Actions

**Slack Guideline:** "Overflow menus offer the opportunity to clean up message complexity, allowing you to de-emphasize interactive actions that are less important."

**Our Problem:** Every card shows all buttons at the same visual weight. /deal shows 4 buttons in a row. Research shows 2. Pipeline shows 2. All equally prominent.

**Proposed Fix:**
- Primary action: One prominent button (e.g., "Draft Email" on research)
- Secondary actions: Overflow menu (⋮) containing "Start Roleplay", "View in HubSpot", "Share to Channel", "Add Note"
- This reduces visual noise from 2-4 buttons to 1 button + 1 overflow

---

### 3C. No Pagination

**Our Problem:** Deal picker capped at 15 deals, followups at 10, contacts at 5. No "Load More" or "Next Page" pattern.

**Proposed Fix:**
- Add "Show More" button at bottom of truncated lists
- Track page state in button value (e.g., `{"page": 2, "company": "NovaTech"}`)
- Update original message with next page of results

---

### 3D. No Timestamp Context

**Our Problem:** /pipeline shows metrics but no date range. Is this current month? Quarter? All time? /forecast similarly lacks time context.

**Proposed Fix:**
- Add time context to all metrics: "Pipeline Health — Q1 2026 (as of Mar 11)"
- Forecast: "Forecast — March 2026"
- Research: "Last CRM update: Feb 28, 2026"

---

### 3E. Accessibility Gaps

**Slack Guideline:** "Include all necessary content in the top-level text field for screen readers." / "Limit redundant and purely decorative images."

**Our Problem:**
- Fallback text is minimal (e.g., "Research Brief: NovaTech - 3 contacts, 5 deals") — screen reader users miss all the detail
- No accessible PDF alternatives for any visual charts
- Emoji used for status indicators without text alternatives

**Proposed Fix:**
- Enrich fallback text to include key information, not just titles
- For score displays (roleplay debrief), add text like "Score: 8 out of 10, Excellent" not just "8/10"
- Always pair emoji indicators with text: "🟢 On Track" not just "🟢"

---

## 4. RECOMMENDED IMPLEMENTATION PRIORITY

### Phase 1 — Demo Essentials (before next executive demo)
1. **1B: Loading message → Update pattern** (eliminate duplicate messages)
2. **1A: Message cleanup after button clicks** (collapse cards after action)
3. **2B: Fix vague button labels** (quick wins)
4. **2D: Actionable empty states** (looks polished)

### Phase 2 — UX Upgrade
5. **1C: Threading strategy** (follow-ups in threads)
6. **1D: Progressive disclosure** (summary → expand pattern)
7. **3B: Overflow menus** (reduce button clutter)
8. **2A: Truncation indicators** (user trust)

### Phase 3 — Smart Agent
9. **2C: Smart defaults** (context-aware buttons based on deal stage)
10. **3A: Respond-in-right-place** (DM vs. channel awareness)
11. **3C: Pagination** (handle large datasets)
12. **3D: Timestamp context** (metrics clarity)
13. **3E: Accessibility** (screen reader support, fallback text)

---

## 5. BEFORE & AFTER: /research NovaTech

### BEFORE (Current)
```
[permanent] "Researching NovaTech... give me 15 seconds."

[permanent, 10 blocks] Research Brief: NovaTech
  Industry: Technology    Size: 120 employees
  HQ: Austin, TX          Revenue: $12M
  ───────────────
  Key Contacts:
  • Wei Ahmed — CTO (wei@novatech.com)
  • Sarah Chen — VP Sales (sarah@novatech.com)
  • Marcus Williams — Procurement (marcus@novatech.com)
  ───────────────
  Active Deals:
  • Enterprise Platform — Negotiation — $250,000
  • Security Add-on — Discovery — $48,000
  ───────────────
  Recent News:
  • NovaTech Expands Workforce...
  ───────────────
  Talking Points:
  • Focus on enterprise security needs...
  • Reference their recent expansion...
  ───────────────
  [Draft Follow-Up Email]  [Start Roleplay]
  ───────────────
  Generated by SalesCoach AI • Data from HubSpot • 2:34 PM
```

### AFTER (Proposed)
```
[single message, updated from loading state]
Research Brief: NovaTech
  🏢 Technology • 120 employees • Austin, TX • $12M revenue

  Your Relationship:
  3 contacts • 2 active deals ($298K) • Last activity: Feb 28

  💡 Top Talking Point:
  Their enterprise security evaluation is entering final stages —
  lead with ROI from the pilot program.

  [📧 Draft Email]  [⋮ More Actions]
  ───────────────
  SalesCoach AI • HubSpot + Web • 2:34 PM

  (clicking ⋮ shows: View All Contacts, View All Deals,
   Start Roleplay, Full Research Brief, View in HubSpot)
```

User clicks "📧 Draft Email" → original card collapses to:
```
Research Brief: NovaTech — ✉️ Drafting email...
  SalesCoach AI • 2:34 PM
```

Contact picker appears in thread, email draft appears in thread.
Channel stays clean. Context is preserved.

---

## 6. BEFORE & AFTER: Roleplay Debrief

### BEFORE
```
Roleplay Debrief
  Score: *8/10* — Excellent

  Strengths:
  • Good discovery questions...
  • Strong value proposition...

  Areas for Improvement:
  • Could probe deeper on budget...
  • Missed competitive positioning...

  Recommended Practice:
  Try the "Budget Objection" scenario next.

  [Practice Again]  [Try Suggested Scenario]
```

### AFTER
```
Roleplay Debrief 🎯

  ████████░░ 8/10 — Excellent

  ✅ Strong: Discovery questions, value proposition framing
  🔧 Improve: Budget probing, competitive positioning

  💡 Next: Try "Budget Objection" — targets your growth areas

  [🔄 Practice Again]  [🎯 Try Budget Objection]  [📊 Full Debrief]
```

"📊 Full Debrief" expands to show detailed strengths,
improvements, specific quotes from the roleplay, and
a comparison to previous attempts.

---

## 7. REVALIDATION AGAINST slack-ux.md (Official Slack Docs)

After reading the full `slack-ux.md` reference file (Block Kit docs, Block Elements, Composition Objects, Modal Views, and the complete App Design guide from docs.slack.dev), here's what's confirmed, strengthened, and new:

### CONFIRMED — Our findings match the official docs exactly

**1A (Message Cleanup):** STRONGLY CONFIRMED. No new nuance — Slack's guidance is direct about condensing messages after interaction.

**1B (Ephemeral Messages):** STRONGLY CONFIRMED. The official docs are explicit: "If the response only needs to be displayed to the user, it's a better idea to use an ephemeral message than it is to generate a DM." This is in the "Responding to users in channel" section. Our loading messages ("Researching NovaTech... give me 15 seconds.") are a textbook case for ephemeral. They only matter to the invoking user and add noise for everyone else.

**1C (Threading):** CONFIRMED. The "Responding to users in channel" section says: "Whatever you post in channel is going to be long-lived and add to the group conversation... only pick responses that are important to the entire team when posting in-channel." Our follow-up flows (contact pickers, email drafts) are NOT important to the team — they should thread.

**2B (Button Labels):** STRONGLY CONFIRMED and now we have MORE specific guidance. The official docs say:
- "Button labels should be clear and specific"
- "Make buttons active-voice and reflect the user's outcome (Save, Book Flight, Place Order)"
- "Avoid vague, non-actionable text like 'Click here' or 'Settings'"
- "Don't replace words with emoji"

That last point is interesting — my earlier proposal to add emoji prefixes to buttons ("📧 Draft Email") actually VIOLATES Slack's guideline. Emoji in buttons is fine for decoration (`"emoji": true` in the text object) but should NOT replace clarity. So the fix is simpler: just use clear active-voice labels WITHOUT emoji prefix. Keep emoji for decorative purposes only, not as the primary indicator.

**UPDATED button label recommendations:**
- "More Detail" → "Get Full Objection Guide"
- "View Details" → "Open Deal"
- "Take Action" → "Update This Deal"
- "Full Analysis" → "See Win/Loss Breakdown"
- "Draft Follow-Up Email" → keep as-is (already active-voice and specific)
- "Start Roleplay" → keep as-is (already clear)

### STRENGTHENED — Deeper detail from the official docs

**1D (Information Overload):** The official docs add important nuance. The block limit is 50 blocks per message, 100 for modals and Home tabs. We're well within limits, but the DESIGN principle is what matters. Slack explicitly says "it's easy to overload." Combined with mobile testing advice ("Some people only use Slack on their phones"), our /research card's 10 blocks are a real concern on mobile.

**3E (Accessibility):** SIGNIFICANTLY STRENGTHENED. The official docs have a critical accessibility rule we weren't fully addressing: "screen readers will default to the top-level `text` field of the post, and will not read the content of any interior `blocks`." This means our fallback text isn't just a nice-to-have — it's the ENTIRE experience for screen reader users. Our current fallback like "Research Brief: NovaTech - 3 contacts, 5 deals" is woefully incomplete. Screen reader users get almost nothing.

**UPDATED accessibility recommendation:**
- Every message MUST have a rich top-level `text` field OR omit it to let Slack auto-build from blocks
- Since we use Block Kit, the best approach is to provide a comprehensive `text` field that includes all key information: company overview, top contacts, deal summary, and talking points — basically a plain-text version of the card
- OR: omit the `text` field entirely and let Slack concatenate from blocks (simpler but less controlled)

### NEW FINDINGS — From the official docs that we missed

**NEW: Notification frequency awareness.** The docs warn: "Consider how frequently your messages are generating notifications for a user... offer the user an option to get a digest of these messages." We haven't thought about this at all. When someone runs /pipeline, /research, /deal, and /forecast in a session, that's 4+ notifications to everyone in the channel. Plus each button click creates more. For a demo this is fine, but in production, a /settings command to control notification preferences would be important.

**NEW: DM privacy expectations.** "Users will assume that information shared back and forth with your app in DM is private. Be aware of any sensitive information that's being shared, and don't surprise users by announcing results of DM conversations in channel." This matters for our coaching flows — if a rep does a roleplay in DM with the coach bot, the debrief score shouldn't automatically post to a public channel. We should respect the DM boundary.

**NEW: Don't post to #general by default.** "Don't post to a workspace's #general channel by default. You'll likely be unnecessarily disrupting many users." We should add a check in our handlers — if channel is #general, warn or redirect.

**NEW: Modals for complex flows.** The official docs describe Modal views extensively. We're not using modals AT ALL. For multi-step flows like deal picker → contact picker → email draft, a modal could be much cleaner than threading. The user fills out a form (pick deal, pick contact, customize email), clicks "Send", and the result posts to channel as a single clean message. This is a Phase 2/3 consideration but worth noting.

**NEW: Preferences link in messages.** The docs show an example of an app that "builds a preferences link into the actual messages." We could add a small context block with a link to /settings in our footer blocks. This gives users an easy path to customize their experience.

**NEW: Voice and tone guidance.** The docs say to "foreground the information necessary to the task at hand, then add voice and tone elements." Our LLM-generated talking points and coaching feedback sometimes get chatty. We should add prompt engineering guidance to keep responses brief and action-oriented, matching Slack's "be brief" principle.

**NEW: Table block.** The Block Kit reference includes a `Table` block type for "structured information." We're not using this — we're building tables manually with section fields and bullet points. For /pipeline stage breakdowns and /win-loss metrics, a proper Table block could improve readability significantly.

**NEW: Context Actions block.** A newer Block Kit feature: `context_actions` block with feedback buttons and icon buttons. This could replace our heavy action blocks with lighter-weight inline actions for things like "Was this helpful?" or quick reactions to coaching advice.

### UPDATED PRIORITY LIST

The revalidation confirms our Phase 1 priorities and adds two new items:

**Phase 1 — Demo Essentials (before next executive demo)**
1. 1B: Loading message → Update pattern (eliminate duplicate messages)
2. 1A: Message cleanup after button clicks (collapse cards after action)
3. 2B: Fix vague button labels (active-voice, NO emoji-as-words)
4. 2D: Actionable empty states (looks polished)
5. **NEW: Screen reader accessibility** — rich `text` field on all messages

**Phase 2 — UX Upgrade**
6. 1C: Threading strategy (follow-ups in threads)
7. 1D: Progressive disclosure (summary → expand pattern)
8. 3B: Overflow menus (reduce button clutter)
9. 2A: Truncation indicators (user trust)
10. **NEW: Table blocks** for pipeline/win-loss structured data

**Phase 3 — Smart Agent & Production**
11. 2C: Smart defaults (context-aware buttons based on deal stage)
12. 3A: Respond-in-right-place (DM vs. channel awareness)
13. **NEW: Modal flows** for multi-step interactions
14. **NEW: Notification preferences** via /settings command
15. **NEW: DM privacy respect** — don't leak coaching scores to public channels
16. 3C: Pagination (handle large datasets)
17. 3D: Timestamp context (metrics clarity)
18. **NEW: Context Actions blocks** for lightweight inline feedback

---

## Sources
- `slack-ux.md` — local project reference file compiled from docs.slack.dev
- Slack General Design Guidelines: https://api.slack.com/start/designing/guidelines
- Slack App Design: https://docs.slack.dev/surfaces/app-design/
- Designing with Block Kit: https://api.slack.com/block-kit/designing
- Block Kit Reference: https://docs.slack.dev/reference/block-kit/blocks/
- Block Elements Reference: https://docs.slack.dev/reference/block-kit/block-elements/
- Modal Views: https://docs.slack.dev/reference/views/modal-views
- Slack Interaction Guidelines: https://api.slack.com/start/planning/guidelines
- Slack Messaging Docs: https://docs.slack.dev/messaging/
