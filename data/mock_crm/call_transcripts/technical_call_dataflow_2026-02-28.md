# Call Transcript: Technical Deep-Dive — DataFlow Inc
**Date:** February 28, 2026 | **Duration:** 55 minutes
**Rep:** Jordan Mitchell | **Prospect:** Marcus Chen, CTO & Priya Sharma, VP of Engineering
**Deal:** DataFlow Inc — Enterprise Platform License ($156,000)
**Call Type:** Technical Evaluation | **Recording ID:** REC-2026-0228-001

---

**[0:00] Jordan:** Marcus, Priya, thanks for setting this up. I know your time is valuable, so I want to make this as useful as possible. Marcus, Priya mentioned you had questions about integrations and security. Do you want to start there?

**[0:18] Marcus:** Yes, let's dive right in. We're a data infrastructure company, so our security bar is high. Our customers trust us with their data, and any vendor we work with reflects on that trust. First question: where does our data live, and who can access it?

**[0:40] Jordan:** Fair question. All data is stored in AWS, encrypted at rest with AES-256 and in transit with TLS 1.3. For DataFlow, given your customer base, I'd recommend our US-West region, but we also have EU-Frankfurt if you have EU data residency requirements. On access: your data is logically isolated. Our employees cannot access customer data without your explicit written permission and an audited access request.

**[1:12] Marcus:** Do you have SOC 2 Type II?

**[1:15] Jordan:** Yes, here's our latest report — it covers the past 12 months. We also have penetration test results from NCC Group if you want to share those with your security team.

**[1:28] Marcus:** *reviews briefly* This looks solid. What about Salesforce integration? We sync about 50,000 records a month. I've seen "Salesforce integrations" that break at scale.

**[1:45] Jordan:** Good concern. We use Salesforce's Bulk API 2.0 for syncs, so we handle volume well. Our largest customer syncs 2 million records monthly without issues. We can configure sync frequency — real-time for new deals, hourly batch for historical. And we respect your Salesforce rate limits, so we won't impact your other integrations.

**[2:15] Marcus:** What data do you pull from Salesforce?

**[2:20] Jordan:** By default: deals, contacts, accounts, and activity history. We can customize the field mappings. We don't pull sensitive data like social security numbers or credit card info — our schema explicitly excludes PII fields unless you whitelist them.

**[2:42] Marcus:** What about data we generate in your platform? Call recordings, roleplay sessions — where does that go?

**[2:52] Jordan:** That stays in our platform by default. If you want to push coaching scores or activity summaries back to Salesforce, we can enable that bidirectionally. Some customers create a custom "Coaching Score" field on the Contact object and we populate it weekly.

**[3:15] Marcus:** That's interesting — we might want that for manager visibility. Priya, thoughts?

**[3:22] Priya:** Yes, I'd want our managers to see coaching activity in Salesforce alongside deal data. Let's include that in scope.

**[3:32] Jordan:** Easy to configure. We can set that up during implementation. Marcus, anything else on security?

**[3:40] Marcus:** One more. We're rolling out Zero Trust architecture. Do you support SSO with Okta?

**[3:48] Jordan:** Yes, SAML 2.0 and SCIM provisioning. Most of our enterprise customers use Okta or Azure AD. We can also enforce MFA and restrict access by IP range if needed.

**[4:02] Marcus:** Good. Let's switch to customization. Priya mentioned you can customize sales methodologies. We use MEDDIC but we've added a "Technical Validation" stage. Deals can't move to negotiation without it.

**[4:20] Jordan:** We support that completely. Our methodology engine is configurable per customer. We'd add "Technical Validation" as a qualification dimension with its own rubric. Roleplay scenarios would include prompts like "The prospect says they need to validate with their IT team — how do you handle that?" and score reps on how well they set up technical validation steps.

**[4:55] Marcus:** Can I see an example of a custom methodology in action?

**[5:00] Jordan:** *shares screen* Here's a customer in the cybersecurity space. They added "Security Review" as a qualification step. Watch this roleplay — the AI prospect raises a security concern, and the rep needs to both handle the objection and proactively schedule a security review call. See the scoring here? Technical Validation: 7/10, with feedback that the rep should have confirmed stakeholders for the review.

**[5:35] Marcus:** That's exactly what we need. Our reps skip technical validation, then deals stall in procurement because we didn't get the right sign-offs.

**[5:48] Priya:** Marcus, this would address the gap we've been talking about. How long does implementation take, Jordan?

**[5:55] Jordan:** Standard implementation is 3 weeks. For DataFlow, given the custom MEDDIC work, I'd estimate 4 weeks — but we'd front-load the methodology configuration so your team can start practicing while we finish the Salesforce integration.

**[6:20] Marcus:** So we'd be live by late March?

**[6:25] Jordan:** If we start implementation by March 10th, yes. You'd have 3 weeks before your April 20th SKO for reps to practice. We'd also do a live training session at the SKO if helpful.

**[6:42] Marcus:** That would be valuable. I'm satisfied on the technical side. Priya, what else do you need?

**[6:50] Priya:** I think we're good. Jordan, can you send over the integration architecture diagram and the custom methodology documentation? I want to share with our IT team so they can start preparing on their side.

**[7:05] Jordan:** Absolutely. I'll send that today. One thing we should discuss before we wrap: pricing. Have you had a chance to review the proposal?

**[7:18] Priya:** We have. Jennifer wants to discuss the payment terms. Can we do quarterly instead of annual upfront?

**[7:28] Jordan:** Quarterly is possible. We typically do net-30 on quarterly invoices. I'll include that option in the updated proposal.

**[7:40] Marcus:** Jordan, one last question. You mentioned other data infrastructure customers. Can you share references?

**[7:50] Jordan:** Definitely. I'll set up calls with two customers — one is similar size to DataFlow, the other is larger. You can ask them anything.

---

**REP'S POST-CALL NOTES:**
- Marcus is now a champion — key quote: "This is the first sales tool our reps might actually use"
- Technical validation complete. No blockers.
- **Action Items:**
  1. Send integration architecture diagram — TODAY
  2. Send custom methodology documentation — TODAY
  3. Update proposal with quarterly payment option
  4. Schedule reference calls — target 2 customers in data/infrastructure space
  5. Prep for Jennifer (CFO) call — she's focused on payment terms
- **Implementation Timeline:**
  - Start: March 10
  - Live: Late March
  - SKO Training: April 20
- **Next Hurdle:** Jennifer sign-off on budget. Need to align on ROI numbers before meeting.
