"""
Synthetic Coaching Data Generator for Sales AI Agents
======================================================
Generates rich coaching-specific data for roleplay scenarios, techniques,
anti-patterns, and debrief rubrics. This data gets indexed into the RAG
vector store to improve coaching quality.

Creates:
  1. data/playbooks/coaching_scenarios.md — 15+ roleplay scenarios with personas
  2. data/playbooks/coaching_techniques.md — Sales frameworks with coaching tips
  3. data/playbooks/coaching_anti_patterns.md — Common rep mistakes
  4. data/playbooks/coaching_debrief_rubrics.md — Scoring rubrics for debriefs

Usage:
  python scripts/generate_coaching_data.py

After running:
  - Re-index playbooks: python scripts/index_playbooks.py
"""

import os

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYBOOK_DIR = os.path.join(BASE_DIR, "data", "playbooks")

os.makedirs(PLAYBOOK_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# FILE 1: COACHING SCENARIOS
# ---------------------------------------------------------------------------
COACHING_SCENARIOS = """# Coaching Scenario Library

A library of roleplay scenarios for sales coaching practice sessions.
Each scenario includes buyer persona, ideal approach, common mistakes, and debrief criteria.

---

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
"Look, I'll be upfront — we've already looked at three tools in this space. I'm not sure yours is different. You've got 15 minutes to change my mind."

**Debrief Criteria:**
- Score 8-10: Asked 3+ discovery questions before any pitch, referenced specific tech stack details, proposed technical POC
- Score 5-7: Good rapport but pitched too early, or missed integration concern
- Score 1-4: Led with features, didn't adapt to skeptical personality

---

## Scenario: Discovery Call — Enthusiastic Champion
**Difficulty:** Easy
**Skills Tested:** Qualification, multi-threading, managing expectations

**Buyer Persona:**
- Name: Jordan Martinez, Director of Operations
- Company Type: Fast-growing startup (50-100 employees)
- Personality: Enthusiastic, fast-moving, wants to be a hero internally
- Hidden Objections: Limited budget authority, CEO makes final call
- Decision Style: Will champion internally but can't sign alone

**Ideal Approach:**
1. Match their energy but stay grounded in qualification
2. Ask about decision-making process early (who else is involved?)
3. Help them build the internal business case
4. Identify the economic buyer (CEO) and plan to involve them
5. Set realistic timeline expectations

**Common Mistakes:**
- Getting swept up in enthusiasm without qualifying budget/authority
- Treating them as the sole decision-maker
- Not helping them prepare for internal objections
- Moving too fast toward proposal without stakeholder alignment

**Sample Opening (Buyer):**
"I'm so glad we connected! I've been telling my team we need something like this for months. Let's figure out how to make this happen ASAP."

**Debrief Criteria:**
- Score 8-10: Qualified budget and authority, asked about other stakeholders, offered to help with internal pitch
- Score 5-7: Good conversation but missed qualification questions
- Score 1-4: Assumed the deal was done, didn't explore decision process

---

## Scenario: Pricing Negotiation — Budget-Constrained VP
**Difficulty:** Hard
**Skills Tested:** Value selling, negotiation, creative deal structuring

**Buyer Persona:**
- Name: Michelle Park, VP of Finance
- Company Type: Enterprise (1000+ employees)
- Personality: Numbers-focused, risk-averse, under budget pressure
- Hidden Objections: Has approval for 30% less than your list price
- Decision Style: Needs to justify ROI to the CFO

**Ideal Approach:**
1. Don't offer discounts first — explore their constraints
2. Ask what budget they have approved (anchor them)
3. Trade value for concessions (longer term, case study, reference)
4. Help them build the ROI story for their CFO
5. Be willing to walk away if deal doesn't make sense

**Common Mistakes:**
- Offering discount immediately when they mention budget
- Splitting the difference (shows weakness)
- Not asking what they CAN afford
- Failing to tie price to value delivered

**Sample Opening (Buyer):**
"Your product looks strong, but I'll be honest — your pricing is 40% higher than what we budgeted. We need to find a way to make the numbers work, or I can't move forward."

**Debrief Criteria:**
- Score 8-10: Explored constraints before discounting, traded value, held firm on core pricing
- Score 5-7: Good negotiation but gave discount too easily
- Score 1-4: Immediately offered maximum discount, didn't explore alternatives

---

## Scenario: Pricing Negotiation — Procurement-Led
**Difficulty:** Hard
**Skills Tested:** Patience, process navigation, maintaining champion relationship

**Buyer Persona:**
- Name: David Chen, Senior Procurement Manager
- Company Type: Enterprise (5000+ employees)
- Personality: Process-driven, impersonal, trained negotiator
- Hidden Objections: Has 3 competing quotes, must get 15% minimum discount
- Decision Style: Follows strict procurement process, multiple approval layers

**Ideal Approach:**
1. Understand their process and timeline upfront
2. Ask about evaluation criteria (not just price)
3. Maintain relationship with business champion separately
4. Provide value justification docs for their internal process
5. Don't negotiate against yourself — make them make proposals

**Common Mistakes:**
- Taking their "final offer" at face value
- Losing touch with the business champion
- Getting frustrated with process delays
- Revealing your discount authority too early

**Sample Opening (Buyer):**
"I've been assigned to handle vendor negotiations for this project. I have three qualified vendors and need to present final pricing to the committee next week. What's your best and final offer?"

**Debrief Criteria:**
- Score 8-10: Asked about evaluation criteria, maintained composure, didn't reveal walkaway
- Score 5-7: Handled professionally but showed cards too early
- Score 1-4: Got defensive or gave best price immediately

---

## Scenario: Competitive Displacement — Incumbent Vendor
**Difficulty:** Hard
**Skills Tested:** Differentiation, patience, finding pain with current solution

**Buyer Persona:**
- Name: Sarah Thompson, Head of Sales Operations
- Company Type: Mid-market (300 employees)
- Personality: Loyal to current vendor, skeptical of switching costs
- Hidden Objections: Switching would require her to admit her original choice was wrong
- Decision Style: Needs overwhelming evidence to justify change

**Ideal Approach:**
1. Don't attack the competitor — acknowledge what works
2. Find the "bleeding neck" problem the incumbent can't solve
3. Quantify the cost of the status quo
4. Offer a low-risk pilot or proof of concept
5. Make switching feel like evolution, not revolution

**Common Mistakes:**
- Badmouthing the competitor (makes her defensive)
- Focusing on features instead of outcomes
- Underestimating switching costs and change management
- Pushing too hard for immediate decision

**Sample Opening (Buyer):**
"We're happy with our current solution, but my CEO asked me to take this meeting. I'm not sure what you could offer that would justify the disruption of switching."

**Debrief Criteria:**
- Score 8-10: Found specific pain point, quantified cost of status quo, proposed low-risk trial
- Score 5-7: Good conversation but didn't find compelling reason to switch
- Score 1-4: Attacked competitor or failed to differentiate

---

## Scenario: Competitive Objection — "We're Evaluating Competitor X"
**Difficulty:** Medium
**Skills Tested:** Competitive intelligence, differentiation, FUD vs facts

**Buyer Persona:**
- Name: Kevin O'Brien, Director of IT
- Company Type: Mid-market tech company (200 employees)
- Personality: Technical, thorough evaluator, wants to make the right choice
- Hidden Objections: Competitor has slightly lower price, similar features
- Decision Style: Will create detailed comparison matrix

**Ideal Approach:**
1. Ask what they like about the competitor (understand their criteria)
2. Acknowledge competitor strengths honestly
3. Differentiate on 2-3 key areas that matter to THIS buyer
4. Offer customer references who evaluated both
5. Suggest evaluation criteria they might have missed

**Common Mistakes:**
- Dismissing the competitor entirely
- Focusing on features the buyer doesn't care about
- Getting defensive when they mention competitor advantages
- Failing to ask why they're evaluating alternatives

**Sample Opening (Buyer):**
"We're also talking to Competitor X. Their demo was impressive and they came in 20% cheaper. Why should we pay more for your solution?"

**Debrief Criteria:**
- Score 8-10: Asked about their criteria, differentiated on relevant points, offered references
- Score 5-7: Good response but didn't personalize differentiation
- Score 1-4: Got defensive or trash-talked competitor

---

## Scenario: Cold Call — Gatekeeper Bypass
**Difficulty:** Medium
**Skills Tested:** Rapport, persistence, creative approaches

**Buyer Persona:**
- Name: Reception / Executive Assistant
- Company Type: Enterprise (any size)
- Personality: Protective, busy, trained to screen calls
- Hidden Objections: Has been told to block all sales calls
- Decision Style: Will transfer if you seem legitimate

**Ideal Approach:**
1. Be confident and friendly — not salesy
2. Use the decision-maker's first name (familiarity)
3. Reference a specific trigger event or reason for calling
4. Offer to send info that the EA can review first
5. Ask for the best time to reach the decision-maker

**Common Mistakes:**
- Being overly aggressive or pushy
- Lying about the nature of the call
- Arguing with the gatekeeper
- Asking "Is [Name] available?" (easy to say no)

**Sample Opening (Gatekeeper):**
"Who's calling and what is this regarding?"

**Debrief Criteria:**
- Score 8-10: Built rapport, gave credible reason, got through or got callback
- Score 5-7: Professional but didn't differentiate from typical sales call
- Score 1-4: Got blocked immediately, was pushy or dishonest

---

## Scenario: Cold Call — Direct to Decision-Maker
**Difficulty:** Medium
**Skills Tested:** Pattern interrupt, value proposition, earning the meeting

**Buyer Persona:**
- Name: Rachel Foster, VP of Marketing
- Company Type: Growth-stage company (150 employees)
- Personality: Busy, skeptical of cold calls, but open if relevant
- Hidden Objections: Gets 10+ sales calls per day
- Decision Style: Will take meeting if you show you've done homework

**Ideal Approach:**
1. Open with a pattern interrupt (not "How are you today?")
2. Reference specific research about their company
3. Lead with an insight or challenge relevant to their role
4. Ask for 15 minutes, not 30 or 60
5. Offer flexibility on timing

**Common Mistakes:**
- Generic opening that sounds like every other sales call
- Pitching immediately without earning attention
- Asking for too much time
- Not having a clear value proposition

**Sample Opening (Decision-Maker):**
"Yeah, I have about 30 seconds. What's this about?"

**Debrief Criteria:**
- Score 8-10: Grabbed attention, showed relevance, earned the meeting
- Score 5-7: Good effort but didn't differentiate
- Score 1-4: Generic pitch, got hung up on quickly

---

## Scenario: Renewal Risk — Unhappy Customer
**Difficulty:** Hard
**Skills Tested:** Active listening, empathy, problem-solving, retention

**Buyer Persona:**
- Name: Tom Washington, Customer Success Lead (your point of contact)
- Company Type: Current customer, 2-year relationship
- Personality: Frustrated, feels ignored, considering alternatives
- Hidden Objections: Had a bad support experience, executive sponsor left
- Decision Style: Needs to see concrete changes before renewing

**Ideal Approach:**
1. Listen first — let them vent without defending
2. Acknowledge the problems and take ownership
3. Ask what would need to change for them to renew
4. Propose specific action plan with timeline
5. Escalate internally to get executive attention

**Common Mistakes:**
- Getting defensive about past issues
- Offering discounts before understanding the problem
- Making promises you can't keep
- Ignoring the emotional component of their frustration

**Sample Opening (Customer):**
"Honestly, I'm not sure we're going to renew. The last year has been really frustrating — support tickets take forever, our executive sponsor left and no one reached out, and the features you promised still aren't delivered."

**Debrief Criteria:**
- Score 8-10: Listened fully, acknowledged issues, proposed concrete action plan
- Score 5-7: Good empathy but solution was too vague
- Score 1-4: Got defensive or immediately offered discount

---

## Scenario: Upsell Conversation — Expand to New Department
**Difficulty:** Medium
**Skills Tested:** Discovery, internal navigation, building champions

**Buyer Persona:**
- Name: Lisa Patel, your current champion (Marketing bought your product)
- Company Type: Current customer, Marketing department only
- Personality: Happy customer, wants to help you expand
- Hidden Objections: Sales department has different needs, political tension
- Decision Style: Will make introduction if you make her look good

**Ideal Approach:**
1. Understand the Sales team's specific needs (different from Marketing)
2. Ask Lisa about the political landscape
3. Position the expansion as HER win internally
4. Get warm introduction rather than cold outreach
5. Tailor your pitch to Sales use cases

**Common Mistakes:**
- Assuming Sales has the same needs as Marketing
- Going around Lisa to reach Sales directly
- Not doing discovery on the new department
- Pushing too hard and damaging the existing relationship

**Sample Opening (Champion):**
"Our Sales team has been asking about what you do for us. I told them I'd connect you. But heads up — they're skeptical of Marketing-driven initiatives."

**Debrief Criteria:**
- Score 8-10: Asked about Sales needs, navigated politics, made Lisa the hero
- Score 5-7: Good approach but missed political nuances
- Score 1-4: Treated it like a cold call, didn't leverage relationship

---

## Scenario: Multi-Stakeholder Meeting — CFO + CTO Alignment
**Difficulty:** Hard
**Skills Tested:** Meeting facilitation, addressing different concerns, consensus building

**Buyer Persona:**
- Name: Two buyers — CFO (cost-focused) + CTO (technical concerns)
- Company Type: Enterprise (1000+ employees)
- Personality: CFO is skeptical of spend, CTO worries about implementation
- Hidden Objections: They don't fully agree with each other
- Decision Style: Need to align before any decision

**Ideal Approach:**
1. Address both sets of concerns — don't favor one
2. Find the common ground (usually business outcomes)
3. Let them talk to each other, not just to you
4. Prepare ROI data for CFO, technical deep-dive for CTO
5. Summarize agreements and action items for both

**Common Mistakes:**
- Focusing on one persona and losing the other
- Not preparing materials for both audiences
- Getting caught in the middle of their disagreement
- Leaving without clear alignment on next steps

**Sample Opening (Meeting Start):**
CFO: "I need to understand the ROI here. We're under budget pressure."
CTO: "And I need to know this won't be a six-month implementation nightmare."

**Debrief Criteria:**
- Score 8-10: Addressed both concerns, found common ground, got aligned next step
- Score 5-7: Handled one persona well but lost the other
- Score 1-4: Failed to manage the dual-audience dynamic

---

## Scenario: Demo Gone Wrong — Technical Failure Recovery
**Difficulty:** Medium
**Skills Tested:** Composure, improvisation, relationship management

**Buyer Persona:**
- Name: Demo audience of 5 stakeholders
- Company Type: Prospect in evaluation stage
- Personality: Watching closely, some skeptics in the room
- Hidden Objections: Wondering if this reflects product quality
- Decision Style: This demo is a key milestone in their process

**Ideal Approach:**
1. Stay calm — acknowledge the issue without over-apologizing
2. Have a backup plan (slides, video, or whiteboard)
3. Use the moment to demonstrate your support responsiveness
4. Offer to reschedule the live demo portion
5. Turn it into a conversation about their requirements

**Common Mistakes:**
- Panicking visibly
- Over-apologizing or making excuses
- Trying to force the broken demo to work
- Not having any backup content ready

**Sample Event (Mid-Demo):**
*The demo environment crashes. Error message on screen. Audience is watching.*

**Debrief Criteria:**
- Score 8-10: Stayed composed, pivoted smoothly, maintained credibility
- Score 5-7: Handled okay but showed visible stress
- Score 1-4: Panicked, blamed engineering, or lost the audience

---

## Scenario: Timeline Objection — "Not the Right Time"
**Difficulty:** Medium
**Skills Tested:** Objection handling, urgency creation, patience

**Buyer Persona:**
- Name: Robert Kim, VP of Operations
- Company Type: Mid-market manufacturing (400 employees)
- Personality: Conservative, prefers to wait and see
- Hidden Objections: Scared of change, comfortable with status quo
- Decision Style: Will delay indefinitely unless shown clear cost of waiting

**Ideal Approach:**
1. Acknowledge that timing is a valid consideration
2. Ask what would make it the right time
3. Quantify the cost of waiting (lost revenue, continued pain)
4. Offer a phased approach to reduce risk
5. Set a follow-up for when their timeline improves

**Common Mistakes:**
- Accepting "not now" at face value
- Creating false urgency that feels manipulative
- Pushing too hard and damaging the relationship
- Not understanding the real reason behind the timing concern

**Sample Opening (Buyer):**
"This looks great, but it's just not the right time. We're in the middle of a reorg and I don't want to add another project. Let's reconnect in Q3."

**Debrief Criteria:**
- Score 8-10: Explored the real concern, quantified cost of delay, set concrete follow-up
- Score 5-7: Good handling but accepted delay too easily
- Score 1-4: Pushed too hard or gave up immediately

---

## Scenario: Contract Negotiation — Legal Pushback on Terms
**Difficulty:** Hard
**Skills Tested:** Negotiation, patience, legal navigation

**Buyer Persona:**
- Name: Corporate Counsel representing the buyer
- Company Type: Enterprise (2000+ employees)
- Personality: Risk-averse, focused on liability and compliance
- Hidden Objections: Standard redlines that are negotiable
- Decision Style: Will delay close until legal is satisfied

**Ideal Approach:**
1. Understand which terms are deal-breakers vs. standard asks
2. Loop in your own legal early — don't negotiate alone
3. Trade non-essential terms for essential ones
4. Keep the business champion engaged (don't let legal own the deal)
5. Propose compromise language that addresses their concern

**Common Mistakes:**
- Agreeing to terms without understanding implications
- Getting frustrated with legal's pace
- Losing touch with the business champion
- Treating all redlines as non-negotiable

**Sample Opening (Legal):**
"We've completed our review. We have concerns about your limitation of liability clause, the indemnification language, and your data processing terms. These need to be addressed before we can proceed."

**Debrief Criteria:**
- Score 8-10: Understood concerns, involved your legal, found workable compromises
- Score 5-7: Handled professionally but got stuck on unnecessary issues
- Score 1-4: Got defensive, made unauthorized concessions, or lost the deal

---

## Scenario: Executive Sponsor Meeting — Board-Level Conversation
**Difficulty:** Very Hard
**Skills Tested:** Executive presence, business acumen, brevity

**Buyer Persona:**
- Name: CEO or Board Member
- Company Type: Public company or PE-backed
- Personality: Time-constrained, strategic thinker, wants bottom line
- Hidden Objections: Wondering if this deserves their attention
- Decision Style: Makes decisions quickly if convinced, delegates if not

**Ideal Approach:**
1. Get to the point immediately — no fluff
2. Lead with business outcomes, not product features
3. Use data and peer references (other CEOs, board members)
4. Be prepared to answer hard questions concisely
5. Have a clear ask ready

**Common Mistakes:**
- Wasting time on rapport-building small talk
- Going into too much detail
- Being intimidated by seniority
- Not having a clear ask at the end

**Sample Opening (Executive):**
"I have 10 minutes before my next meeting. My team says you can help with our expansion into Europe. What do you need from me?"

**Debrief Criteria:**
- Score 8-10: Led with outcomes, answered questions crisply, made clear ask
- Score 5-7: Good conversation but used too much time on details
- Score 1-4: Got lost in features, was intimidated, or wasted their time
"""

# ---------------------------------------------------------------------------
# FILE 2: COACHING TECHNIQUES
# ---------------------------------------------------------------------------
COACHING_TECHNIQUES = """# Sales Coaching Techniques Reference

A guide to sales methodologies and frameworks with specific coaching tips
for each. Use these to provide structured feedback during roleplay debriefs.

---

## SPIN Selling Framework

**When to Use:** Discovery calls, needs assessment, any conversation where you need to understand the buyer's situation before proposing solutions.

**Structure:**
- **S**ituation Questions: Understand current state ("What tools do you use today?", "How many reps are on your team?")
- **P**roblem Questions: Surface pain points ("What challenges do you face with...?", "Where does the current process break down?")
- **I**mplication Questions: Amplify pain ("What happens when that problem occurs?", "How does that impact your revenue?")
- **N**eed-Payoff Questions: Connect to value ("How would it help if you could...?", "What would solving this be worth?")

**Coaching Tips:**
- Reps often skip Implication questions — they hear a problem and jump to solution. Coach them to pause and explore the business impact first.
- Need-Payoff questions should ideally come from the BUYER, not the rep. A good Implication question naturally leads the buyer to ask "Can you help with that?"
- Limit Situation questions to 2-3 (too many feels like an interrogation). Do your research beforehand.
- The best reps spend 60% of discovery on Problem and Implication questions.

**Example Coaching Moment:**
Buyer says: "Our ramp time is 7 months."
- Bad rep response: "Our tool cuts that to 3 months!" (jumps to solution)
- Good rep response: "What does that 7-month ramp cost you in lost revenue?" (Implication)
- Coach tip: "Great moment to dig deeper. Ask about the business impact before offering solutions."

---

## Challenger Sale Methodology

**When to Use:** Complex B2B sales, sophisticated buyers, competitive situations where differentiation matters.

**Structure:**
1. **Teach**: Share insights the buyer doesn't know (industry trends, benchmark data)
2. **Tailor**: Connect insights to their specific situation
3. **Take Control**: Guide the conversation and push back when needed

**Coaching Tips:**
- Teaching requires preparation. Coach reps to research industry trends and come with 1-2 insights.
- "Challenger" doesn't mean aggressive. It means confident and willing to offer a different perspective.
- Tailoring requires listening. The insight must connect to THEIR specific challenges.
- Taking control includes pushing back on unrealistic timelines or unfair comparisons.

**Example Coaching Moment:**
Buyer says: "We're planning to build this internally."
- Bad rep response: "Our product is better than anything you could build." (defensive)
- Good rep response: "That's an option. Can I share what we've seen other companies learn when they tried that?" (teach)
- Coach tip: "Use data and stories from other customers to challenge their assumption without being confrontational."

---

## MEDDPICC Qualification

**When to Use:** Enterprise sales, complex deals, any situation where thorough qualification is critical.

**Structure:**
- **M**etrics: What business outcomes are they trying to achieve?
- **E**conomic Buyer: Who has budget authority?
- **D**ecision Criteria: How will they decide?
- **D**ecision Process: What steps will they follow?
- **P**aper Process: What's required to get a contract signed?
- **I**dentify Pain: What's the compelling event or pain point?
- **C**hampion: Who inside will sell on your behalf?
- **C**ompetition: Who else are they talking to?

**Coaching Tips:**
- Don't ask these as a checklist — weave them into natural conversation.
- Champion is the most overlooked element. No champion = low probability deal.
- Economic Buyer access is critical. If you haven't met them, the deal is at risk.
- Paper Process often kills deals at the end. Surface it early.

**Example Coaching Moment:**
Rep says: "The VP loves us. This deal is going to close."
- Coach challenge: "Have you met the Economic Buyer? Who is your Champion? What's the Paper Process?"
- Common issue: Reps confuse access with commitment.

---

## Sandler Pain Funnel

**When to Use:** Discovery calls, uncovering hidden objections, going deeper on surface-level problems.

**Structure:**
1. Start with surface-level problem ("Tell me more about that...")
2. Dig into specifics ("Can you give me an example?")
3. Explore impact ("What happens when...?")
4. Quantify ("How much does that cost you?")
5. Personal impact ("How does that affect you personally?")
6. Commitment ("Are you committed to solving this?")

**Coaching Tips:**
- Most reps stop after step 1 or 2. Coach them to go to step 5.
- Personal impact is powerful — "How does that affect YOUR goals?"
- Don't move to solution until you reach commitment. Otherwise, they're not bought in.
- Silence is your friend. Ask the question and wait.

**Example Coaching Moment:**
Buyer mentions: "Our data is scattered across five systems."
- Surface rep: "We can consolidate that!" (too fast)
- Good rep: "What happens when someone needs information that's in multiple systems?" → "How much time does that waste per week?" → "How does that affect your team's morale?"

---

## Feel-Felt-Found

**When to Use:** Handling objections, building empathy, overcoming resistance.

**Structure:**
1. "I understand how you **feel**..." (acknowledge emotion)
2. "Other customers have **felt** the same way..." (normalize)
3. "What they **found** was..." (provide evidence of resolution)

**Coaching Tips:**
- This technique defuses defensiveness. Use it when the buyer is emotional.
- "Felt" must reference real customers. Don't make up stories.
- "Found" should include specific outcomes, not vague promises.
- Don't overuse — it can feel formulaic if used in every objection.

**Example Coaching Moment:**
Buyer says: "I'm worried about implementation disruption."
- Feel: "That's a valid concern. Switching systems is disruptive."
- Felt: "CloudBridge had the same concern when they evaluated us."
- Found: "What they found was that our phased rollout actually caused less disruption than their legacy system was causing every day."

---

## LAER Objection Handling Framework

**When to Use:** Any objection situation. A general framework for thoughtful response.

**Structure:**
- **L**isten: Let them finish, don't interrupt. Really hear what they're saying.
- **A**cknowledge: Validate the concern ("That's a fair point...")
- **E**xplore: Ask follow-up ("Can you help me understand what's driving that concern?")
- **R**espond: Address with evidence or reframe

**Coaching Tips:**
- Most reps jump to "Respond" immediately. Coach them to spend more time on "Explore."
- Acknowledgment is not agreement. "I understand" is not "You're right."
- Exploration often reveals the REAL objection is different from the stated one.
- Respond with evidence — customer stories, data, demos — not opinions.

**Example Coaching Moment:**
Buyer says: "Your price is too high."
- Bad rep: "Well, here's why we're worth it..." (skips to Respond)
- Good rep: "I appreciate you being direct. Can you help me understand — compared to what? Is it over your budget, or does it seem high relative to the value?" (Explore)
- Often the real objection is "I don't understand the value yet" not "the price is too high."

---

## Command of the Sale

**When to Use:** Deal control, preventing stalls, maintaining momentum.

**Structure:**
1. Know the next step before ending any conversation
2. Get verbal commitment to that step
3. Send written confirmation (calendar invite, email)
4. Create mutual action plan for complex deals

**Coaching Tips:**
- Reps often end calls with "I'll send you some info" — too vague.
- Every meeting should end with a specific next step with a date.
- If the buyer won't commit to a next step, the deal isn't real.
- For complex deals, a Mutual Action Plan creates shared accountability.

**Example Coaching Moment:**
Rep says: "Great call! I'll follow up next week."
- Coach challenge: "What specifically are you following up about? Did they commit to a next step?"
- Better close: "Let's schedule a 30-minute technical deep-dive for Thursday. I'll send the invite now."

---

## Negative Reverse Selling (Sandler)

**When to Use:** When you sense resistance, when buyer is being polite but non-committal, when you need honesty.

**Structure:**
Give the buyer permission to say no by expecting it:
- "It sounds like this might not be a fit for you..."
- "Maybe we should just stop here..."
- "I'm getting the sense you're not convinced..."

**Coaching Tips:**
- This feels counterintuitive but works because it removes pressure.
- Buyers often become MORE engaged when given an out.
- Use sparingly — it's a pattern interrupt, not a constant technique.
- Requires confidence. Don't use if you'll panic at their response.

**Example Coaching Moment:**
Buyer is giving short answers, checking phone.
- Typical rep: Keeps pitching harder (makes it worse)
- Negative reverse: "I'm sensing this might not be the right time. Should we stop here?"
- Often the buyer opens up: "No, sorry, I'm just distracted. Let me focus..."

---

## Value Selling Framework

**When to Use:** Pricing conversations, ROI discussions, justifying premium pricing.

**Structure:**
1. Quantify the problem (cost of status quo)
2. Quantify the solution (value delivered)
3. Show the delta (ROI)
4. Compare to price (make price feel small)

**Coaching Tips:**
- Reps often sell features. Coach them to sell dollars.
- Get the buyer to help with the math — it's more believable.
- Use conservative assumptions. Inflated ROI kills credibility.
- Frame price as investment, not cost.

**Example Coaching Moment:**
Buyer says: "Your solution is $100K/year."
- Feature seller: "But you get all these features..."
- Value seller: "You mentioned your ramp time costs you $50K per rep. With 10 reps, that's $500K. If we cut that in half, the $100K investment pays back 2.5x in year one."
"""

# ---------------------------------------------------------------------------
# FILE 3: COACHING ANTI-PATTERNS
# ---------------------------------------------------------------------------
COACHING_ANTI_PATTERNS = """# Sales Coaching Anti-Patterns

Common mistakes reps make during sales calls, organized by call type.
Use these to identify issues during roleplay debriefs and live coaching.

---

## Discovery Call Anti-Patterns

### Anti-Pattern: "Feature Dumping"
**What It Looks Like:** Rep lists product features before understanding buyer needs. Starts pitching within the first 2 minutes.

**Why Reps Do It:** Nervous silence feels uncomfortable, they want to show value quickly, lack of discovery training, pressure to "sell."

**How to Coach:**
- Ask: "What did you learn about THEIR situation before talking about us?"
- Redirect: "Try asking 3 questions before mentioning any feature."
- Practice: Run a roleplay where the rep is NOT allowed to mention the product for 5 minutes.
- Reframe: "Discovery is selling. You're selling them on sharing their problems with you."

### Anti-Pattern: "Happy Ears"
**What It Looks Like:** Rep hears "sounds interesting" or "we should explore this" and marks the deal as likely to close. Confuses politeness with commitment.

**Why Reps Do It:** Confirmation bias, pressure to build pipeline, optimism over realism.

**How to Coach:**
- Challenge: "What specific next step did they commit to? With a date?"
- Teach: "Interest is not commitment. Look for actions, not words."
- Practice: Roleplay where the buyer is politely non-committal. Coach the rep to push for specifics.
- Metric: Track "Next Step Commitment Rate" — how often do prospects agree to specific next steps?

### Anti-Pattern: "Premature Close"
**What It Looks Like:** Rep asks for the business before establishing need, building value, or handling objections. Feels pushy.

**Why Reps Do It:** Eagerness, misunderstanding of "always be closing," end-of-month pressure.

**How to Coach:**
- Teach: "Closing isn't a moment, it's a process. You earn the close."
- Check: "Have you established need? Have you addressed their concerns? Have they seen enough value?"
- Practice: Roleplay the full sales process. Stop them if they close too early.

### Anti-Pattern: "Interrogation Mode"
**What It Looks Like:** Rep asks question after question without acknowledging answers. Feels like a checkbox exercise.

**Why Reps Do It:** Following a script too rigidly, not listening, trying to "qualify" rather than connect.

**How to Coach:**
- Teach: "After every answer, acknowledge what you heard before asking the next question."
- Practice: "Tell me more about that" and "That's interesting because..." as bridges.
- Watch for: Rep looking at their list instead of reacting to the buyer.

---

## Negotiation Anti-Patterns

### Anti-Pattern: "First to Blink"
**What It Looks Like:** Rep offers a discount before the buyer asks for one. Immediately caves on price at first hint of pushback.

**Why Reps Do It:** Fear of losing the deal, misreading buying signals, lack of confidence in value.

**How to Coach:**
- Rule: "Never negotiate against yourself. Wait for them to ask."
- Challenge: "What did you get in return for that discount?"
- Practice: Roleplay with a buyer who is silent after hearing the price. Coach the rep to wait.

### Anti-Pattern: "Splitting the Difference"
**What It Looks Like:** Buyer asks for 20% off, rep offers 10%. Both feel like they "won" but the rep gave away margin unnecessarily.

**Why Reps Do It:** Feels fair, ends the negotiation quickly, avoids conflict.

**How to Coach:**
- Teach: "Split the difference is for people who don't know how to negotiate. Trade value instead."
- Redirect: "What if you offer 5% off in exchange for a longer contract term?"
- Challenge: "Why did you offer ANY discount? Did they establish they couldn't afford full price?"

### Anti-Pattern: "Discounting Before Discovery"
**What It Looks Like:** Rep asks "What's your budget?" in discovery, then prices below it. Leaves money on the table.

**Why Reps Do It:** Trying to make the deal easy, fear of pricing objection, misunderstanding of value selling.

**How to Coach:**
- Teach: "Don't ask budget until you've established value. Otherwise, you anchor low."
- Reframe: "Budget is what they planned to spend. Value is what they're willing to spend for the right solution."
- Practice: Roleplay where the buyer mentions a budget. Coach the rep to explore whether that's a hard ceiling.

---

## Competitive Deal Anti-Patterns

### Anti-Pattern: "Trash Talking"
**What It Looks Like:** Rep badmouths the competitor instead of differentiating on value. "Their product is terrible." "They have no support."

**Why Reps Do It:** Frustration, lack of competitive intelligence, easier than explaining differentiation.

**How to Coach:**
- Rule: "Never speak negatively about competitors. It makes YOU look bad."
- Redirect: "Acknowledge what they do well, then differentiate on what matters to THIS buyer."
- Example: "They're a solid company. Where we're different is [specific area that matters to the buyer]."

### Anti-Pattern: "Feature Battle"
**What It Looks Like:** Rep gets into a point-by-point feature comparison instead of selling outcomes. Plays the competitor's game.

**Why Reps Do It:** Competitor set the agenda, buyer asked for comparison, lack of strategic response.

**How to Coach:**
- Reframe: "Don't compare features. Compare business outcomes."
- Challenge: "Are these the features that matter most to THIS buyer? Or are you just responding to what they asked?"
- Redirect: "Let's step back. What problem are you trying to solve? Let me share how other companies achieved that."

### Anti-Pattern: "Ignoring the Elephant"
**What It Looks Like:** Buyer mentions they're evaluating a competitor, and the rep changes the subject or ignores it entirely.

**Why Reps Do It:** Uncomfortable with competition, doesn't know what to say, hoping it goes away.

**How to Coach:**
- Rule: "Address competition directly. Ignoring it makes you seem evasive."
- Response: "That's a solid company. What attracted you to them?" (then listen and differentiate)
- Practice: Roleplay where the buyer brings up a competitor. Coach the rep to lean into it.

---

## Closing Anti-Patterns

### Anti-Pattern: "Endless Follow-Up"
**What It Looks Like:** Rep sends 5+ follow-up emails with no response. "Just checking in." "Wanted to see if you had any questions."

**Why Reps Do It:** Afraid to give up on the deal, don't know what else to do, hoping persistence wins.

**How to Coach:**
- Teach: "If they're not responding, your follow-ups aren't valuable. Change the approach."
- Better: Send new value (article, case study, insight) or try a different channel (phone, LinkedIn).
- Challenge: "After 3 unanswered emails, call and ask directly: 'Should I close this file?'"

### Anti-Pattern: "Assuming the Close"
**What It Looks Like:** Rep sends a contract without verbal commitment. "I'll send over the paperwork!" Buyer ghosts.

**Why Reps Do It:** Misread buying signals, wishful thinking, trying to accelerate the deal.

**How to Coach:**
- Rule: "Get verbal commitment before sending contracts. 'Are you ready to move forward?'"
- Check: "Did they explicitly agree to the terms, price, and timeline?"
- Practice: Roleplay where the rep needs to confirm before sending the contract.

### Anti-Pattern: "Leaving Without Next Steps"
**What It Looks Like:** Call ends with "Let's connect soon!" or "I'll send some info!" No specific next step, no calendar invite.

**Why Reps Do It:** Feels presumptuous to ask, ran out of time, forgot.

**How to Coach:**
- Rule: "Every call ends with a specific next step. 'Let's schedule the demo for Thursday at 2pm.'"
- Challenge: "If there's no next step, the deal isn't real. Why would they agree to meet again?"
- Metric: Track "Next Step Rate" — % of calls ending with confirmed next step.

---

## General Anti-Patterns

### Anti-Pattern: "Talking Too Much"
**What It Looks Like:** Rep talks 70%+ of the call. Buyer can't get a word in. Rep answers their own questions.

**Why Reps Do It:** Nervous energy, thinks talking = selling, uncomfortable with silence.

**How to Coach:**
- Target: Discovery calls should be 30% rep, 70% buyer. Demos should be 50/50.
- Practice: Set a timer. If the rep talks for more than 30 seconds straight, pause them.
- Reframe: "Your job is to get THEM talking. The more they talk, the more they sell themselves."

### Anti-Pattern: "Not Listening"
**What It Looks Like:** Buyer gives important information, rep doesn't follow up on it. Asks a question that was already answered.

**Why Reps Do It:** Thinking about what to say next instead of listening, following a script too rigidly.

**How to Coach:**
- Test: After a roleplay, ask: "What were the buyer's top 3 concerns?" Rep should know.
- Practice: Active listening exercises. Repeat back what you heard before responding.
- Challenge: "You asked about their tech stack, but they mentioned their budget is tight. Why didn't you explore that?"

### Anti-Pattern: "Winging It"
**What It Looks Like:** Rep goes into call without researching the company or preparing questions. Generic pitch, no personalization.

**Why Reps Do It:** Time pressure, thinks they can improvise, underestimates buyer expectations.

**How to Coach:**
- Rule: "Minimum 10 minutes of research before every call. LinkedIn, company website, news."
- Check: "What do you know about this company that isn't in our CRM?"
- Standard: Every call should have at least 1 personalized insight or question.
"""

# ---------------------------------------------------------------------------
# FILE 4: COACHING DEBRIEF RUBRICS
# ---------------------------------------------------------------------------
COACHING_DEBRIEF_RUBRICS = """# Coaching Debrief Scoring Rubrics

Structured scoring criteria for roleplay debriefs, organized by scenario type.
Use these to provide consistent, actionable feedback.

---

## Discovery Call Rubric

### Opening (1-10 points)
- **9-10:** Personalized opening referencing specific research about the company or person. Set clear agenda. Confirmed time availability. Built immediate rapport.
- **7-8:** Good rapport and set agenda, but opening was somewhat generic. Could have been more personalized.
- **5-6:** Polite but formulaic opening. "Thanks for taking the time..." No personalization or research evident.
- **3-4:** Jumped straight to pitch with minimal rapport building. No agenda set.
- **1-2:** Unprepared, stumbled, or inappropriate opening. Made buyer uncomfortable.

### Needs Assessment (1-10 points)
- **9-10:** Asked 5+ discovery questions. Uncovered 2+ pain points. Used SPIN or Challenger framework effectively. Let the buyer do most of the talking.
- **7-8:** Good questions but missed an obvious pain point, or asked too many Situation questions vs. Problem/Implication questions.
- **5-6:** Some discovery but shifted to pitch too early. Surface-level questions without going deep.
- **3-4:** Minimal discovery. Mostly talked about the product. Treated discovery as a checklist.
- **1-2:** No discovery questions. Pure product pitch from the start.

### Active Listening (1-10 points)
- **9-10:** Acknowledged every key point the buyer made. Asked relevant follow-up questions. Connected buyer's words to later points in conversation.
- **7-8:** Good listening but missed 1-2 opportunities to dig deeper.
- **5-6:** Heard the words but didn't explore. Moved on too quickly.
- **3-4:** Asked questions but didn't adjust based on answers. Felt like an interrogation.
- **1-2:** Clearly not listening. Repeated questions already answered. Talked over buyer.

### Objection Handling (1-10 points)
- **9-10:** Acknowledged concern genuinely. Explored root cause. Reframed effectively. Used evidence (case study, data). Buyer felt heard.
- **7-8:** Handled objection but didn't explore deeply enough. Response was generic.
- **5-6:** Gave a canned response. Didn't adapt to the specific concern.
- **3-4:** Got defensive or dismissive. Made buyer feel judged for raising concern.
- **1-2:** Ignored the objection or changed the subject.

### Next Steps (1-10 points)
- **9-10:** Proposed specific next step with date/time. Got verbal commitment. Identified other stakeholders to involve. Sent calendar invite or confirmation.
- **7-8:** Proposed next step but vague on timing or stakeholders.
- **5-6:** Asked "can we follow up?" without specifics. Left scheduling to later.
- **3-4:** Ended call without clear next step. Said "I'll send some info."
- **1-2:** Let the buyer end the call without any follow-up plan.

### Overall Discovery Score: Sum of above / 5 = Average (1-10)

---

## Negotiation Call Rubric

### Value Establishment (1-10 points)
- **9-10:** Clearly articulated business value before discussing price. Quantified ROI. Buyer understands what they're paying for.
- **7-8:** Good value discussion but could have been more specific or quantified.
- **5-6:** Mentioned value but didn't connect it to price. Price and value feel separate.
- **3-4:** Jumped to negotiation without establishing value. Defensive about price.
- **1-2:** No value discussion. Pure price haggling.

### Negotiation Discipline (1-10 points)
- **9-10:** Never negotiated against self. Asked questions before offering concessions. Traded value for discounts. Maintained confidence.
- **7-8:** Good discipline but gave a concession without getting something back.
- **5-6:** Offered discount too quickly. Split the difference.
- **3-4:** Offered maximum discount at first pushback. Seemed desperate to close.
- **1-2:** Gave away everything. No negotiation strategy evident.

### Creative Deal Structuring (1-10 points)
- **9-10:** Proposed alternatives to discount (longer term, payment terms, scope reduction, pilot). Found win-win solutions.
- **7-8:** Some creativity but limited to 1-2 options.
- **5-6:** Only discussed price, not terms. Missed opportunities for creative structure.
- **3-4:** Binary thinking — full price or full discount.
- **1-2:** No attempt at creative solutions.

### Composure Under Pressure (1-10 points)
- **9-10:** Remained calm when challenged. Used silence effectively. Didn't react emotionally to hardball tactics.
- **7-8:** Mostly composed but showed visible stress at key moments.
- **5-6:** Got slightly defensive or rushed when pressured.
- **3-4:** Lost composure. Became argumentative or anxious.
- **1-2:** Folded immediately under pressure.

### Closing Strength (1-10 points)
- **9-10:** Clear ask for commitment. Handled final objections. Got verbal yes or clear next step toward close.
- **7-8:** Good close but left some ambiguity.
- **5-6:** Vague close. "Let me know what you think."
- **3-4:** No close attempt. Let the negotiation end without resolution.
- **1-2:** Lost the deal by pushing too hard or giving up.

### Overall Negotiation Score: Sum of above / 5 = Average (1-10)

---

## Competitive Deal Rubric

### Competitive Positioning (1-10 points)
- **9-10:** Acknowledged competitor strengths. Differentiated on areas that matter to THIS buyer. Never trash-talked. Positioned as different, not better.
- **7-8:** Good differentiation but could have been more tailored to buyer priorities.
- **5-6:** Generic differentiation. Features vs. outcomes.
- **3-4:** Got defensive about competitor. Some negativity crept in.
- **1-2:** Trash-talked competitor. Made buyer defensive.

### Buyer Criteria Understanding (1-10 points)
- **9-10:** Asked what they like about competitor. Understood decision criteria. Tailored pitch to those criteria.
- **7-8:** Good understanding but missed 1-2 criteria.
- **5-6:** Some understanding but didn't fully tailor response.
- **3-4:** Assumed they knew what buyer cared about. Generic response.
- **1-2:** Completely missed buyer criteria. Pitched wrong value props.

### Evidence and Proof Points (1-10 points)
- **9-10:** Used customer references, case studies, data to support claims. Offered to connect buyer with references.
- **7-8:** Some evidence but could have been more specific.
- **5-6:** Made claims without evidence. "Trust me" approach.
- **3-4:** No evidence. All opinion.
- **1-2:** Made claims that weren't credible. Damaged trust.

### Strategic Questioning (1-10 points)
- **9-10:** Asked questions that highlighted competitor weaknesses without being negative. Planted seeds of doubt through curiosity.
- **7-8:** Good questions but some felt leading.
- **5-6:** Direct questions about competitor. Not strategic.
- **3-4:** Avoided competitive conversation entirely.
- **1-2:** Asked questions that made rep look defensive or scared.

### Overall Competitive Score: Sum of above / 4 = Average (1-10)

---

## Cold Call Rubric

### Pattern Interrupt (1-10 points)
- **9-10:** Opened with something unexpected that earned attention. Not a typical "How are you today?" opening.
- **7-8:** Decent opener but still felt somewhat like a sales call.
- **5-6:** Standard opening. Easy to brush off.
- **3-4:** Generic, forgettable opening.
- **1-2:** Immediately identified as a sales call and rejected.

### Relevance (1-10 points)
- **9-10:** Referenced specific research about the person or company. Made it clear why you called THEM, not just anyone.
- **7-8:** Some personalization but could have been more specific.
- **5-6:** Generic pitch that could apply to anyone in the industry.
- **3-4:** No personalization. Script reading.
- **1-2:** Clearly called the wrong person or company.

### Value in 30 Seconds (1-10 points)
- **9-10:** Communicated clear, compelling value in under 30 seconds. Buyer wanted to hear more.
- **7-8:** Good value prop but took too long to deliver.
- **5-6:** Value unclear. Buyer had to ask "What do you do?"
- **3-4:** No clear value. Just features.
- **1-2:** No value communicated. Lost buyer in first 30 seconds.

### Objection Handling (1-10 points)
- **9-10:** Handled "not interested" or "no time" smoothly. Earned another 30 seconds.
- **7-8:** Handled okay but gave up a bit too easily.
- **5-6:** Tried once, then accepted rejection.
- **3-4:** Got defensive or pushy.
- **1-2:** No attempt to handle objection. Gave up immediately.

### Next Step (1-10 points)
- **9-10:** Secured meeting or callback. Got specific date/time.
- **7-8:** Got vague interest. "Send me info."
- **5-6:** Got voicemail or no commitment.
- **3-4:** Rejected but left door open for future.
- **1-2:** Hard rejection or hung up on.

### Overall Cold Call Score: Sum of above / 5 = Average (1-10)

---

## General Debrief Questions

After scoring, discuss these questions with the rep:

1. **What did you do well?** (Let them self-assess first)
2. **What would you do differently?** (Let them identify growth areas)
3. **What was the hardest moment?** (Understand their challenges)
4. **What did you learn about the buyer?** (Test listening skills)
5. **If you could redo one exchange, which would it be?** (Focus on highest-impact learning)

---

## Scoring Interpretation

- **8-10:** Excellent. Ready for real calls. Minor coaching points only.
- **6-7:** Solid foundation. A few areas need practice before going live.
- **4-5:** Needs work. Specific skill gaps to address. More roleplay needed.
- **1-3:** Significant gaps. Back to basics. May need additional training.

After every debrief, identify:
1. **One thing to keep doing** (reinforce good behavior)
2. **One thing to improve** (focus on highest impact)
3. **Practice drill** (specific exercise to improve the weak area)
"""

# ---------------------------------------------------------------------------
# MAIN GENERATOR FUNCTION
# ---------------------------------------------------------------------------
def generate_coaching_data():
    """Generate all coaching data files."""

    files = [
        ("coaching_scenarios.md", COACHING_SCENARIOS),
        ("coaching_techniques.md", COACHING_TECHNIQUES),
        ("coaching_anti_patterns.md", COACHING_ANTI_PATTERNS),
        ("coaching_debrief_rubrics.md", COACHING_DEBRIEF_RUBRICS),
    ]

    for filename, content in files:
        filepath = os.path.join(PLAYBOOK_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"Generated: {filepath}")

    print(f"\n✅ Generated {len(files)} coaching data files in {PLAYBOOK_DIR}")
    print("\nNext steps:")
    print("  1. Re-index playbooks: python scripts/index_playbooks.py")
    print("  2. Test: /coach roleplay discovery call")


if __name__ == "__main__":
    generate_coaching_data()
