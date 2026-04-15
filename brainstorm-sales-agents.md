# Sales AI Agents — Brainstorming & Planning Document

> **Owner:** Izzy (tuiizzyy@gmail.com)
> **Started:** March 4, 2026
> **Status:** Active brainstorming
> **Purpose:** Plan and design AI sales agents inspired by WeJam's Lisa & Pam, customized for Izzy's sales team on Slack.

---

## 1. Inspiration: WeJam's Lisa & Pam

### Lisa — AI Sales Coach
- Delivers real-time feedback, personalized training, and data-driven insights
- Runs hyper-realistic roleplays grounded in the company's playbook & customer insights
- Accelerates onboarding — new reps practice in a safe environment without risking actual leads
- Managers can track team progress, assign scenarios, and review conversation analytics
- Identifies each rep's skill profile, uncovers winning behaviors, captures market signals

### Pam — Personal AI Assistant for Field Sales
- Logs meetings, drafts follow-ups, and updates CRM automatically
- Captures every interaction and keeps CRM accurate without extra effort
- Gives managers real visibility into the field: customer & market shifts, coaching with best practices
- Voice-first design — reps update deals by speaking naturally
- Claims to free up ~4 hours/week of admin work per rep
- Open API for custom integrations with industry-specific CRMs or ERP systems

### What Makes Them Effective
- Voice-based interaction (low friction for field reps)
- Deep CRM integration (auto-updates, not manual entry)
- Coaching loop (not just automation — active skill development)
- Manager dashboards (visibility without micromanagement)
- GDPR-compliant, encrypted, enterprise-grade security

---

## 2. Izzy's Vision: What We're Building

### Platform & Channel
- **Primary interface: Slack** (where the sales team already works)
- Agents will live as Slack bots that team members interact with via messages, slash commands, and threads

### Data Sources
- **HubSpot CRM** — contacts, deals, companies, activities, pipeline data
- **The Internet** — prospect research, company news, market intelligence, competitive analysis
- **BigQuery** — internal analytics, historical sales data, custom metrics, reporting data

### Action Channels (where agents take action)
- **Gmail** — drafting/sending follow-ups, scheduling, email sequences
- **HubSpot CRM** — creating/updating contacts, deals, notes, tasks, logging activities

### Two Agents Envisioned

#### Agent 1: "Coach" (inspired by Lisa)
- Sales coaching & training via Slack
- Roleplay scenarios using real deal context from HubSpot + BigQuery
- Post-call feedback and skill tracking
- Surfaces best practices and winning patterns from team data
- Onboarding accelerator for new reps

#### Agent 2: "Assistant" (inspired by Pam)
- Admin automation: meeting notes → CRM updates → follow-up drafts
- Pre-meeting research briefs (pulls from HubSpot + internet + BigQuery)
- Pipeline hygiene alerts (stale deals, missing data, overdue tasks)
- Automated activity logging
- Manager digest: daily/weekly summaries of team activity and deal movement

---

## 3. Technical Architecture (Initial Thinking)

### Core Stack (To Be Decided)
```
┌─────────────────────────────────────────────────┐
│                   SLACK (UI Layer)               │
│         Slash commands, DMs, Channels            │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              AGENT ORCHESTRATOR                  │
│   (Routes messages, manages context, memory)     │
│   Options: LangGraph, CrewAI, Custom, Claude SDK │
└──┬───────────┬───────────┬───────────┬──────────┘
   │           │           │           │
┌──▼──┐  ┌────▼────┐  ┌───▼───┐  ┌───▼────┐
│HubSpot│ │BigQuery │  │ Gmail │  │Web/Search│
│ API  │  │  API    │  │  API  │  │  APIs   │
└──────┘  └─────────┘  └───────┘  └────────┘
```

### Key Technical Decisions Needed
1. **LLM Provider** — Claude API (Anthropic), OpenAI, or multi-model?
2. **Agent Framework** — LangGraph, CrewAI, Anthropic Agent SDK, or custom?
3. **Hosting** — Cloud Run, AWS Lambda, dedicated server?
4. **Memory & State** — How to persist conversation context across Slack threads?
5. **Authentication** — OAuth flows for HubSpot, Gmail, BigQuery
6. **Data Pipeline** — Real-time vs. batch sync from BigQuery/HubSpot?
7. **Security** — How to handle sensitive CRM/email data in agent context?

### Integration Details

#### Slack Integration
- Slack Bolt SDK (Python or Node.js)
- Socket Mode or HTTP endpoints
- Slash commands: `/coach`, `/assistant`, `/research`, `/pipeline`
- Event subscriptions: message events, app mentions, reactions
- Interactive components: buttons, modals, block kit messages

#### HubSpot Integration
- HubSpot API v3 (REST)
- OAuth 2.0 authentication
- Read: contacts, companies, deals, engagements, notes, tasks
- Write: create/update contacts, deals, notes, tasks, log activities
- Webhooks for real-time CRM event triggers

#### BigQuery Integration
- Google Cloud BigQuery API
- Service account authentication
- Read-only queries for analytics and historical data
- Potential: scheduled queries for pre-computed summaries

#### Gmail Integration
- Gmail API via Google Cloud
- OAuth 2.0 (user-level consent)
- Draft creation, send on behalf (with permission), read recent emails
- Thread context for follow-up drafts

#### Web/Internet Research
- Web search API (Tavily, Serper, or Google Custom Search)
- Web scraping for company pages, LinkedIn (within ToS)
- News APIs for real-time market/company intelligence

---

## 4. Deep Dive: How to Make the Coach Agent "Know" Your Business

### The Core Question
For the Coach agent to deliver real-time feedback, personalized training, and data-driven insights, it needs to deeply understand your sales methodology, product, customer personas, deal patterns, and what "good" looks like for your team. There are four approaches to achieve this, and the answer is almost certainly a layered combination — not a single technique.

### Option A: Prompt Engineering Only (Start Here — Always)

**What it is:** Carefully crafted system prompts that tell the base LLM how to behave as a sales coach, what your methodology is, how to give feedback, etc.

**What it's good for:**
- Defining the coach's personality, tone, and feedback style
- Setting the structure of roleplay sessions (opener → objection → close)
- Enforcing output formats (scorecards, action items, skill ratings)
- Basic sales methodology rules ("always ask about budget before demo")

**What it can't do:**
- Can't hold your entire product catalog, deal history, or playbook (context window limits)
- Can't "remember" what it learned about rep #4's weak spots last Tuesday
- Gets brittle when you need it to reference very specific internal data

**Cost & effort:** Minimal. Hours to days. This is your baseline — you'll use it regardless.

**Verdict for Coach:** Necessary but not sufficient. This is layer 1 of every approach.

---

### Option B: RAG (Retrieval-Augmented Generation) — The Core Architecture

**What it is:** At query time, the agent searches a knowledge base of your documents and data, retrieves the most relevant chunks, and injects them into the LLM context alongside the user's message.

**What you'd put in the RAG knowledge base:**
- Your sales playbook and methodology docs
- Product information, pricing, competitive battle cards
- Call transcripts and meeting notes (from HubSpot)
- Historical deal data and win/loss analyses (from BigQuery)
- Best practice examples ("here's how Sarah handled the pricing objection on the Acme deal")
- Onboarding materials and training content
- ICP (Ideal Customer Profile) definitions
- Common objection handling scripts

**What it enables for the Coach:**
- "Run a roleplay where I'm selling to a CFO in manufacturing" → RAG pulls your manufacturing ICP, relevant case studies, and common CFO objections
- "Give me feedback on my call with Acme Corp" → RAG pulls Acme's deal history, previous interactions, and the relevant playbook section
- "What do top performers do differently in discovery calls?" → RAG pulls patterns from BigQuery analytics on won vs. lost deals
- "Help me prep for my QBR with BigCo" → RAG pulls the account history, open deals, recent activity

**Architecture sketch:**
```
Rep asks Coach a question in Slack
        │
        ▼
┌─────────────────────────┐
│   Query Understanding    │ ← Prompt engineering (layer 1)
│   (What does rep need?)  │
└───────────┬─────────────┘
            │
    ┌───────▼────────┐
    │  RAG Retrieval  │
    │                 │
    │  Searches:      │
    │  • Vector DB    │ ← Playbooks, battle cards, training docs
    │  • HubSpot API  │ ← Live CRM data (deals, contacts, notes)
    │  • BigQuery     │ ← Analytics (win rates, patterns, benchmarks)
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │  LLM generates  │
    │  response with   │
    │  retrieved       │
    │  context         │
    └────────────────┘
```

**Cost & effort:** Moderate. Days to weeks to set up. ~$70–1,000/month for vector DB + embeddings depending on scale.

**Verdict for Coach:** This is the backbone. RAG is how the Coach knows YOUR business, YOUR deals, YOUR methodology — without retraining the model.

---

### Option C: Fine-Tuning — For Deep Behavioral Specialization

**What it is:** Training the base LLM on your own dataset so it internalizes patterns, tone, and domain-specific behavior.

**When it makes sense for a sales coach:**
- You want the coach to consistently mimic a specific coaching methodology (e.g., MEDDIC, Challenger, SPIN) at a deep level — not just follow prompts about it
- You have hundreds or thousands of annotated call transcripts with "good" and "bad" labels, and you want the model to internalize what good sounds like
- You need very specific output formats or scoring rubrics that the model struggles with via prompting alone
- You want to reduce latency and token costs by baking knowledge into the model rather than retrieving it every time

**When it does NOT make sense:**
- Your sales data changes frequently (fine-tuned knowledge becomes stale)
- You don't have a large, high-quality labeled dataset (garbage in = garbage out)
- You're still figuring out what the coach should even do (fine-tuning locks in behavior)
- Budget is limited (fine-tuning = 3-6x inference cost, plus training costs)

**The HubSpot lesson:** HubSpot built their SalesBot and explicitly chose RAG over fine-tuning. They said the foundation (clean data, good retrieval) matters more than model customization. They doubled response speed, improved accuracy, and lifted qualified lead conversion from 3% to 5% — all with RAG + GPT-4, no fine-tuning.

**Cost & effort:** High. Weeks to months. Requires curated datasets, training infrastructure, ongoing retraining as data changes. 3-6x inference cost.

**Verdict for Coach:** Not needed at launch. Revisit after 3-6 months when you have real usage data and can identify specific behavioral gaps that RAG + prompting can't solve.

---

### Option D: Agentic Tool Use (The Multiplier)

**What it is:** Instead of baking all knowledge into the model or retrieval, you give the agent tools it can call in real-time — HubSpot API, BigQuery SQL, web search, Gmail.

**Why this matters for the Coach:**
- "How did our Q4 deals compare to Q3?" → Agent writes and runs a BigQuery query
- "What's the latest on the Acme deal?" → Agent calls HubSpot API for real-time data
- "What's Acme Corp's latest news?" → Agent searches the web
- "Draft a follow-up based on my call notes" → Agent drafts in Gmail

**This is not a replacement for RAG** — it's complementary. RAG handles static/semi-static knowledge (playbooks, historical patterns). Tool use handles live, real-time data (current deal status, fresh analytics).

---

### RECOMMENDED APPROACH: The Layered Stack

```
┌─────────────────────────────────────────┐
│     Layer 4: FINE-TUNING (Future)       │
│     Only if specific gaps identified     │
│     after months of real usage data      │
├─────────────────────────────────────────┤
│     Layer 3: AGENTIC TOOL USE           │
│     HubSpot API, BigQuery SQL,          │
│     Web Search, Gmail — for live data   │
├─────────────────────────────────────────┤
│     Layer 2: RAG                        │
│     Playbooks, battle cards, call       │
│     transcripts, training docs,         │
│     historical deal patterns            │
├─────────────────────────────────────────┤
│     Layer 1: PROMPT ENGINEERING         │
│     Coach persona, methodology rules,   │
│     output formats, feedback style      │
└─────────────────────────────────────────┘
```

**Expected accuracy:** ~93-97% (industry benchmarks for this layered approach vs. ~75-85% for prompting alone).

### Decision: RAG is the answer, NOT fine-tuning (for now)

**Rationale:**
1. Your data is dynamic — deals change daily, CRM updates constantly. RAG retrieves fresh data; fine-tuned models go stale.
2. You're still defining what "good coaching" looks like for your team. Prompting + RAG lets you iterate fast. Fine-tuning locks you in.
3. HubSpot themselves chose RAG for their sales AI — and they have millions of data points. If RAG works at their scale, it works at yours.
4. Fine-tuning is a future optimization, not a starting requirement. Revisit when you have 6+ months of coaching interactions and clear evidence of behavioral gaps.

### RAG Implementation Choices — Deep Dive

---

#### Component 1: Vector Database

The vector DB stores your embedded documents and handles similarity search at query time. This is the foundation of your RAG system.

**Option 1A: Pinecone (Fully Managed)**
- Pros: Zero ops — Pinecone handles scaling, indexing, backups, and infrastructure. SOC 2 / HIPAA compliance on enterprise tier. Consistent sub-50ms latency. Multi-region. Best documentation and ecosystem support.
- Cons: Vendor lock-in (proprietary, closed-source). Cost can escalate — startups report jumps from $50 to $3,000/month as data grows. Opaque per-unit pricing.
- Pricing: Free starter (1 index). Standard ~$0.096/hr. ~$675/month at 10M vectors & 1M queries.
- Best use case: You want to ship fast, don't want to manage infrastructure, and budget isn't the primary constraint. Good for a team that wants to focus on the agent logic, not the DB ops.

**Option 1B: Weaviate (Open Source, Feature-Rich)**
- Pros: Combines vector search with knowledge graph capabilities and GraphQL interface. Built-in hybrid search (vector + BM25 keyword). Multi-modal support (text, images). Strong multi-tenancy for isolating data per sales rep or team. Can self-host (free) or use managed cloud.
- Cons: Higher resource usage — needs larger instances and tuning for scale. More complex pricing than competitors. Steeper learning curve than Pinecone.
- Pricing: Serverless from ~$25/month. Self-hosted is free.
- Best use case: You want hybrid search out of the box (important for sales — reps search by company name AND by semantic meaning). Good if you might need multi-modal later (e.g., embedding slide decks, images).

**Option 1C: Qdrant (Open Source, Rust Performance)**
- Pros: Written in Rust — fast and memory-efficient. Best-in-class metadata filtering (critical for filtering by rep, deal stage, date range). ACID-compliant transactions. Can run in-memory, on disk, or hybrid. Apache 2.0 license — no vendor lock-in.
- Cons: Smaller ecosystem — fewer tutorials, Stack Overflow answers, community examples. At very large scale (50M+ vectors), benchmarks show lower QPS than pgvectorscale.
- Pricing: Small free cloud tier. ~$27–102/month on AWS depending on quantization. Self-hosted is free.
- Best use case: You need powerful filtering (e.g., "find coaching examples where deal stage = negotiation AND industry = SaaS AND rep = Sarah") and want open-source flexibility with low cost.

**Option 1D: ChromaDB (Prototyping / Lightweight)**
- Pros: Simplest to set up — pip install, runs locally, in-memory or persistent. Built-in metadata and full-text search. Apache 2.0, Python-native. Perfect for validating your RAG pipeline before committing to infrastructure.
- Cons: Not built for production scale. Full Python — slower than Rust/Go competitors. Max practical scale ~1M vectors. Will need migration when you outgrow it.
- Pricing: Free (open source).
- Best use case: Week 1 prototyping. Build your pipeline with Chroma, validate it works, then migrate to Qdrant/Pinecone/Weaviate for production.

**Option 1E: pgvector (PostgreSQL Extension)**
- Pros: If you already run Postgres, add vector search with zero new infrastructure. SQL-based queries — your team already knows the language. 75% lower cost than Pinecone (Timescale benchmark). Combines structured + vector data in one DB.
- Cons: Maxes out at ~10–100M vectors before performance degrades. Vector indexes compete for memory with your main database. ORM support (Prisma, etc.) still incomplete. Not as feature-rich for pure vector operations.
- Pricing: Free. ~$250/month on Supabase for 10M vectors.
- Best use case: You're already on Postgres, your dataset is under 10M vectors, and you want to minimize infrastructure complexity. Good for the Assistant agent's CRM data cache.

**Summary Matrix:**

| Factor | Pinecone | Weaviate | Qdrant | ChromaDB | pgvector |
|--------|----------|----------|--------|----------|----------|
| Setup effort | Lowest | Medium | Medium | Lowest | Low (if Postgres exists) |
| Production readiness | Excellent | Excellent | Excellent | Poor | Good (under 10M) |
| Metadata filtering | Good | Good | Best | Basic | SQL-native |
| Hybrid search built-in | No (separate) | Yes | Yes | Basic | No |
| Self-host option | No | Yes | Yes | Yes | Yes |
| Cost at scale | High | Medium | Low-Medium | Free (limited) | Low |
| Vendor lock-in | High | Low | Low | Low | None |

---

#### Component 2: Embedding Model

The embedding model converts your text (playbooks, deal notes, queries) into vectors. This choice directly impacts retrieval quality — a bad embedding model means the right document won't be found even if it exists in your DB.

**Option 2A: OpenAI text-embedding-3 (Small & Large)**
- Pros: Most widely used — largest ecosystem, most tutorials, easiest to integrate. text-embedding-3-small is extremely cheap ($0.02/M tokens). text-embedding-3-large scores 64.6 on MTEB benchmark. Configurable dimensions (reduce storage costs). Reliable API with high uptime.
- Cons: 8K token context window (limiting for long documents). Outperformed by Voyage AI on retrieval benchmarks by ~9.7%. Closed-source, API-only — dependency on OpenAI. No free tier.
- Pricing: Small = $0.02/M tokens. Large = $0.13/M tokens.
- Best use case: You want the safe, well-documented default. You're already using OpenAI for your LLM. Your documents are under 8K tokens each.

**Option 2B: Cohere Embed v4**
- Pros: Highest MTEB benchmark score among commercial options (65.2). 128K token context window — can embed entire documents without chunking. Native int8 compression reduces storage costs. Best multilingual support — 15-20% better than OpenAI on non-Latin scripts. Matryoshka embeddings (configurable dimensions).
- Cons: Slightly more expensive than OpenAI small. Smaller ecosystem than OpenAI. Some independent benchmarks show lower real-world accuracy than Voyage despite higher MTEB scores.
- Pricing: $0.12/M tokens (text). Trial API key available (rate-limited).
- Best use case: Your sales team operates in multiple languages. You have long documents (128K context). You want top-tier benchmark performance with managed API simplicity.

**Option 2C: Voyage AI (voyage-3.5 / voyage-3-large)**
- Pros: Best retrieval quality — outperforms OpenAI by 9.74% and Cohere v3 by 20.71% across 100 datasets. 32K token context window (4x OpenAI). 200M tokens free per account. Best storage efficiency — int8 at 1024 dims beats OpenAI float at 3072 dims (12x less storage, still 9.44% better). Voyage-3.5-lite at $0.02/M offers exceptional price-performance.
- Cons: Newer company (acquired by MongoDB) — smaller ecosystem and community. Fewer integrations out of the box. Some independent benchmarks (Amazon reviews) show mid-range accuracy (68.6%).
- Pricing: voyage-3.5 = $0.06/M tokens. voyage-3.5-lite = $0.02/M tokens. 200M tokens free.
- Best use case: Retrieval quality is your top priority (critical for a coaching agent that must find the RIGHT playbook section). You want the best quality per dollar spent.

**Option 2D: Open-Source (BGE-M3, Nomic, etc.)**
- Pros: Free — no API costs. BGE-M3 scores 63.0 on MTEB, supports 100+ languages. Full control, no vendor dependency. Can fine-tune on your sales domain. Run locally for zero-latency embedding.
- Cons: Need GPU infrastructure to run (or CPU with higher latency). More operational burden. Typically lower quality than top commercial options. Self-managed updates and scaling.
- Pricing: Free (compute costs only — ~$0.50-2/hour for GPU).
- Best use case: Budget is extremely tight, you have GPU infrastructure, or you need to fine-tune embeddings on your specific sales vocabulary.

**Summary Matrix:**

| Factor | OpenAI embed-3 | Cohere embed-v4 | Voyage AI | Open-Source (BGE-M3) |
|--------|-----------------|------------------|-----------|----------------------|
| Retrieval quality | Good (64.6 MTEB) | Very Good (65.2 MTEB) | Best (outperforms by 9.7%) | Good (63.0 MTEB) |
| Context window | 8K tokens | 128K tokens | 32K tokens | Varies (512–8K) |
| Price per 1M tokens | $0.02 (sm) / $0.13 (lg) | $0.12 | $0.02 (lite) / $0.06 (3.5) | Free (GPU costs) |
| Free tier | None | Trial (rate-limited) | 200M tokens | Unlimited |
| Multilingual | Good | Best | Very Good | Good (BGE-M3) |
| Storage efficiency | 3,072 dims (large) | 1,536 dims (v4) | 1,024–2,048 dims (int8) | Varies |
| Ecosystem maturity | Best | Good | Growing | Large (HuggingFace) |

**Key insight:** Benchmark on YOUR data. Generic MTEB scores don't always predict real-world performance on sales playbooks and CRM notes. The recommended approach: test 2-3 models on a sample of your actual documents before committing.

---

#### Component 3: Chunking Strategy

Chunking is how you break your documents into pieces before embedding them. This is arguably the most underrated component — bad chunking ruins retrieval even with the best embedding model and vector DB.

**Option 3A: Fixed-Size Chunking**
- What it does: Splits text by character/token count (e.g., every 500 tokens). No awareness of content boundaries.
- Pros: Simplest to implement — one line of code. Fastest processing. Predictable chunk sizes for token budgeting.
- Cons: Cuts sentences mid-thought. Destroys paragraph/section coherence. Only 13% accuracy in clinical study vs. 87% for adaptive chunking. Useless for production RAG.
- Best use case: Quick prototyping only. Never use in production.

**Option 3B: Recursive Chunking (Recommended Default)**
- What it does: Splits hierarchically — first by sections (##), then paragraphs, then sentences — until chunks fit the target size. Respects document structure.
- Pros: Best balance of quality and efficiency. 69% accuracy in Vecta benchmark (first place across 7 strategies). LangChain default — massive ecosystem support. Easy to tune (adjust chunk size and overlap). Works well on most document types.
- Cons: Can still break mid-context on unstructured text. Doesn't understand meaning — only structure. Requires decent document formatting (headers, paragraphs).
- Recommended settings: 400-512 tokens with 10-20% overlap.
- Best use case: Your sales playbooks, battle cards, and methodology docs that have clear headings and structure. This should be your starting point.

**Option 3C: Semantic Chunking**
- What it does: Uses embeddings to measure similarity between sentences. Creates chunk boundaries where the topic shifts — groups sentences by meaning, not by position.
- Pros: Up to 70% accuracy lift over naive baselines. Respects topic boundaries. Produces coherent, self-contained chunks. LLMSemanticChunker achieves 0.919 recall.
- Cons: Expensive — every sentence needs an embedding call. A 10K-word doc may require 200-300 embedding calls just for chunking. Slower processing pipeline. NAACL 2025 paper found that fixed 200-word chunks sometimes match or beat semantic chunking — gains aren't guaranteed.
- Best use case: High-value, unstructured documents where meaning boundaries matter — call transcripts, meeting notes, long-form competitive intelligence. Worth the cost for your most important coaching knowledge.

**Option 3D: Agentic / LLM-Based Chunking**
- What it does: An LLM reads the full document and decides how to split it — understanding structure, density, and content importance.
- Pros: Highest quality chunks. Understands context, importance, and relationships. Can add metadata/summaries to each chunk.
- Cons: Most expensive — LLM call per document. Slowest processing. Overkill for most use cases. Not well-supported in standard frameworks yet.
- Best use case: Legal contracts, compliance documents, or complex research papers. Likely overkill for your initial sales coaching use case, but worth revisiting for analyzing complex deal documents.

**Summary Matrix:**

| Factor | Fixed-Size | Recursive | Semantic | Agentic/LLM |
|--------|-----------|-----------|----------|-------------|
| Accuracy | Poor (13%) | Good (69%) | Very Good (0.919 recall) | Best |
| Processing speed | Fastest | Fast | Slow | Slowest |
| Cost per document | Free | Free | $0.01-0.10 | $0.10-1.00 |
| Implementation effort | Trivial | Low | Medium | High |
| Best for | Prototyping | Structured docs (playbooks, battle cards) | Unstructured docs (call notes, transcripts) | Complex/high-value docs |

**Practical recommendation for your use case:**
- Sales playbooks, battle cards, ICPs → Recursive chunking (400-512 tokens, 15% overlap)
- Call transcripts, meeting notes → Semantic chunking (worth the cost for coaching accuracy)
- Product docs, pricing sheets → Recursive chunking
- Short docs (FAQs, quick tips) → No chunking (embed whole document)

---

#### Component 4: Retrieval Method & Reranking

Retrieval is the actual search that happens when a rep asks the Coach something. The quality of retrieval determines whether the LLM gets the right context — and therefore whether the coaching is accurate or hallucinated.

**Stage 1: Initial Retrieval**

**Option 4A-i: Pure Vector Search (Dense Retrieval)**
- What it does: Converts the query to a vector, finds nearest neighbors in the vector DB.
- Pros: Understands semantic meaning ("How do I handle price pushback?" matches "objection handling for pricing concerns"). Works across paraphrases and synonyms.
- Cons: Misses exact keyword matches. If a rep asks about "Acme Corp deal #4521", pure vector search might return semantically similar but wrong deals.

**Option 4A-ii: Keyword Search (BM25 / Sparse Retrieval)**
- What it does: Traditional keyword matching with TF-IDF scoring.
- Pros: Perfect for exact matches — company names, deal IDs, specific terms. Fast. Well-understood.
- Cons: No semantic understanding. "pricing objection" won't match "cost concern" or "budget pushback."

**Option 4A-iii: Hybrid Search (Recommended)**
- What it does: Runs both vector search AND keyword search in parallel, then merges and scores results using Reciprocal Rank Fusion (RRF) or similar.
- Pros: Best of both worlds — semantic understanding + exact keyword matching. Weaviate and Qdrant have this built in. Critical for sales: reps search by company name (keyword) AND by situation (semantic).
- Cons: Slightly more complex to set up. Need to tune the balance between vector and keyword scores.
- Best use case: This is the right choice for your sales agents. Reps will ask both "what's the latest on Acme?" (keyword) and "how do I handle a prospect who goes silent?" (semantic).

**Stage 2: Reranking (The Precision Booster)**

After initial retrieval returns ~50-100 candidates, a reranker re-scores them for precision. This typically improves accuracy by 10-48%.

**Option 4B-i: Cohere Rerank (Managed API)**
- Pros: Easiest to integrate — API call with query + documents, returns reranked list. Rerank v4 Pro scores 1627 ELO (among top worldwide). 100+ language support. 32K context window.
- Cons: API dependency. ~200ms added latency (including network). ~$1 per 1,000 queries.
- Best use case: You want production-grade reranking without managing GPU infrastructure. The cost is trivial for a sales coaching agent (your reps won't send 1,000 queries per day).

**Option 4B-ii: ColBERT (Late Interaction, Open Source)**
- Pros: Precomputes document embeddings → tens of milliseconds at query time. Quality close to Cohere on top-5 results. Free (open-source). Great for large-scale, low-latency scenarios.
- Cons: Indexing is computationally intensive. Requires GPU for reasonable performance. More complex to set up and maintain than an API call.
- Best use case: You have millions of documents and need sub-50ms reranking. Likely overkill for your initial use case but good to know for scale.

**Option 4B-iii: Cross-Encoder (Self-Hosted)**
- Pros: Deepest semantic understanding — examines full query-document pairs. +33-40% accuracy improvement for ~50-120ms latency. Free (open-source). Models like ms-marco-MiniLM-L6-v2 are excellent out of the box. FlashRank maintains 95% accuracy with 80% less latency.
- Cons: Needs GPU for production speed. Can't be precomputed — runs at query time. More operational burden than a managed API.
- Best use case: Budget-conscious, want full control, have GPU infrastructure or can use a small CPU model (FlashRank).

**Option 4B-iv: No Reranker (Start Simple)**
- Pros: Zero added latency or cost. Simpler pipeline. Often "good enough" for initial versions.
- Cons: Lower precision. The LLM receives more noise in its context, which can cause hallucinated coaching advice.
- Best use case: Phase 1 prototyping. Add a reranker when you see retrieval quality issues.

**Summary Matrix:**

| Factor | Cohere Rerank | ColBERT | Cross-Encoder | No Reranker |
|--------|--------------|---------|---------------|-------------|
| Accuracy boost | +25-48% | +20-35% | +33-40% | None |
| Latency added | ~200ms | ~10-50ms | ~50-120ms | 0ms |
| Cost | ~$1/1K queries | Free (GPU needed) | Free (GPU needed) | Free |
| Setup complexity | Trivial (API) | High | Medium | None |
| Best for | Production, managed | Large scale, low latency | Budget + quality | Prototyping |

---

#### Component 5: Knowledge Sources & Sync Strategy

| Source | What Goes In | Sync Method | Refresh Cadence |
|--------|-------------|-------------|-----------------|
| Sales Playbooks | Methodology, scripts, frameworks | Manual upload + watch folder | On change (monthly?) |
| Battle Cards | Competitive positioning, objections | Manual upload | On change (quarterly?) |
| HubSpot Deals/Notes | Deal context, call notes, activities | API webhook or scheduled pull | Real-time or hourly |
| BigQuery Analytics | Win/loss patterns, rep benchmarks | Scheduled export → embed | Daily or weekly |
| Call Transcripts | Full conversation records | HubSpot/Gong API → process → embed | After each call |
| Product Docs | Features, pricing, roadmap | Manual upload | On release |
| ICP Definitions | Ideal customer profiles | Manual upload | Quarterly |
| Onboarding Materials | Training content, exercises | Manual upload | On change |

---

## 5. Deep Dive: Agent Framework

The agent framework is the "brain plumbing" — it decides how your agents reason, use tools, manage state, and coordinate with each other. This choice impacts development speed, production reliability, and how easy it is to evolve the system over time.

### Option A: LangGraph (Graph-Based State Machines)

**What it is:** An open-source library from the LangChain ecosystem that models agents as directed graphs — nodes are reasoning/tool-use steps, edges define flow, and state persists across the entire graph.

**Pros:**
- Most production-hardened framework available. Reached v1.0 in October 2025. Used by Klarna, Replit, and Elastic in production.
- Models agents as finite state machines — exceptionally powerful for multi-turn, conditional, and retry-prone workflows. Your Coach roleplay (multi-turn with branching) maps naturally to a graph.
- Durable execution — agents persist through failures and resume automatically. Critical for Slack where a user might send a message, wait 10 minutes, then continue.
- Human-in-the-loop built in — inspect and modify agent state at any point. Useful for manager oversight of coaching sessions.
- LangGraph Platform offers 1-click deployment, memory APIs, and pre-built patterns.
- Model-agnostic — works with Claude, GPT, Gemini, or any LLM.

**Cons:**
- Steepest learning curve of all frameworks. You must understand graph theory, state reducers, and node composition.
- Documentation is technical and not beginner-friendly. Abstraction layering can be confusing.
- Frequent updates and breaking changes in the LangChain ecosystem add maintenance burden.
- Has not natively adopted MCP or A2A protocol standards yet.

**Pricing:** Open-source (free). LangGraph Platform (managed) has tiered pricing for deployment.

**Best use case for your project:** The Coach agent's roleplay system (multi-turn conversations with branching logic, state tracking per session, conditional tool calls). Also strong for the Assistant's multi-step workflows (research → draft email → update CRM → notify manager).

**Effort estimate:** 2-3 weeks to learn + build first agent. Ongoing maintenance moderate.

---

### Option B: CrewAI (Role-Based Agent Teams)

**What it is:** A framework focused on collaborative autonomy — agents with defined roles that delegate tasks, share updates, and coordinate like a real team.

**Pros:**
- Second easiest framework to learn. Well-structured, beginner-friendly docs. Over 100,000 developers certified through community courses.
- Two modes: Crews (autonomous agents with true agency — they decide when to delegate) and Flows (event-driven pipelines for predictable production workloads).
- Natural mapping to your two-agent architecture: Coach agent and Assistant agent as crew members with distinct roles.
- A2A protocol support added — future-proofed for agent-to-agent communication.
- Model-agnostic.

**Cons:**
- Works best when your problem decomposes into distinct, pre-defined roles. Struggles when agent interactions are dynamic and unpredictable.
- Multi-agent systems amplify complexity — watch for loops, tool misuse, and cost blowups. (Your "Agentic Loop of Death" research is directly relevant here.)
- YAML-driven configuration can feel limiting as business needs grow beyond standard patterns.
- Less granular control over state transitions compared to LangGraph.

**Pricing:** Open-source (free). CrewAI Enterprise has managed hosting.

**Best use case for your project:** Fast initial prototype. If you want the Coach and Assistant to naturally collaborate (e.g., Coach asks Assistant to pull deal data mid-roleplay), CrewAI's crew metaphor is intuitive.

**Effort estimate:** 1-2 weeks to learn + build first agent. Lower ceiling for complex workflows.

---

### Option C: OpenAI Agents SDK (Lightweight Handoffs)

**What it is:** A minimalist Python framework from OpenAI for multi-agent workflows, built around four primitives: agents, handoffs, guardrails, and tracing.

**Pros:**
- Easiest to start — just a few lines of code. Lightest abstraction overhead.
- Handoff-based orchestration: one agent passes control to another via a specialized tool call. Clean for routing (e.g., triage agent → Coach or Assistant).
- Built-in tracing and guardrails. Good debugging tools.
- Despite being from OpenAI, supports 100+ LLMs (provider-agnostic).

**Cons:**
- Lacks built-in parallel execution. State management is simpler than LangGraph.
- No native durable execution — if a process fails mid-way, recovery is manual.
- Smaller community and ecosystem than LangGraph or CrewAI.
- Tighter coupling to OpenAI's patterns, even if technically model-agnostic.

**Pricing:** Open-source (free).

**Best use case for your project:** If you want the absolute simplest starting point and plan to add complexity incrementally. Good for a triage/router agent that hands off to specialized sub-agents.

**Effort estimate:** Days to first agent. May need migration as complexity grows.

---

### Option D: Anthropic Claude Agent SDK (Claude-Native)

**What it is:** Anthropic's SDK for building AI agents with Claude's capabilities, available in Python and TypeScript. Gives Claude the ability to use a computer, read/write files, run commands, and execute workflows.

**Pros:**
- First-class Claude integration. If you choose Claude as your LLM, this gives you the tightest integration with Claude's tool-use capabilities (0.920 tool selection score — best in class).
- Anthropic originated MCP (Model Context Protocol) — the emerging standard for connecting agents to tools. The SDK has native MCP support.
- Claude's instruction-following requires 60% fewer guardrails than alternatives for multi-step conditional workflows.
- Python and TypeScript versions available.

**Cons:**
- Newer and less mature than LangGraph and CrewAI. Smaller community and fewer production references.
- Primarily Claude-focused — if you ever want to swap LLMs, you'd need to refactor.
- More of a building-block SDK than a full framework — you'll need to build more orchestration logic yourself.
- Significant engineering effort to build production-grade agents. Not plug-and-play.

**Pricing:** Open-source (free). Claude API costs apply.

**Best use case for your project:** If you commit to Claude as your LLM and want the deepest integration with Claude's capabilities. Good foundation if you value MCP compatibility for connecting to HubSpot, BigQuery, Gmail tools.

**Effort estimate:** 2-4 weeks. More custom code required than LangGraph or CrewAI.

---

### Option E: Custom / No Framework (Direct API)

**What it is:** Build your own agent loop directly on top of an LLM API — no framework, just your code managing the prompt → LLM → tool call → LLM cycle.

**Pros:**
- Total control. No abstractions to fight with. No dependency risk from framework breaking changes.
- Simplest possible architecture — you understand every line of code.
- No learning curve for a framework. Python + LLM API + Slack Bolt is all you need.
- Can adopt MCP for tool integration without committing to a framework.

**Cons:**
- You'll rebuild what frameworks give you for free: state management, error recovery, parallel tool execution, memory, tracing, human-in-the-loop.
- Harder to maintain as complexity grows. No community patterns to lean on.
- Production hardening (retries, timeouts, graceful degradation) is all on you.

**Pricing:** Free (your development time is the cost).

**Best use case for your project:** If you want to deeply understand agent internals, or if your use case is simple enough that a framework is overkill. Some production teams start custom and adopt a framework later when complexity demands it.

**Effort estimate:** 1 week for basic agent. Ongoing effort scales with complexity.

---

### Framework Summary Matrix

| Factor | LangGraph | CrewAI | OpenAI SDK | Claude Agent SDK | Custom |
|--------|-----------|--------|------------|------------------|--------|
| Learning curve | Steep | Moderate | Easy | Moderate | None (but DIY) |
| Production maturity | v1.0 (best) | Good | Good | Maturing | You own it |
| Multi-agent support | Excellent | Excellent | Good (handoffs) | Growing | DIY |
| State management | Best (graph state) | Good | Basic | Basic | DIY |
| Model agnostic | Yes | Yes | Yes (100+ LLMs) | Claude-focused | Yes |
| MCP support | Limited | A2A added | Evolving | Native (originator) | Can add |
| Durable execution | Yes | No | No | No | DIY |
| Human-in-the-loop | Built-in | Limited | Limited | Limited | DIY |
| Community size | Largest | Large (100K+) | Growing | Smaller | N/A |

### Recommendation for Your Project

**Primary recommendation: LangGraph** — for the following reasons:
1. Your Coach agent needs multi-turn stateful conversations (roleplays, feedback loops) — LangGraph's graph-based state machines are purpose-built for this.
2. Durable execution matters for Slack — users send messages asynchronously, and the agent needs to resume seamlessly.
3. Model-agnostic — you can start with Claude and switch or multi-model later without rewriting the framework layer.
4. Production-proven at Klarna and Replit scale.
5. Human-in-the-loop for manager oversight of coaching sessions.

**Alternative: CrewAI** — if you value faster time-to-prototype and want the Coach/Assistant collaboration to be first-class.

**Future consideration:** Regardless of framework choice, adopt MCP for tool connections (HubSpot, BigQuery, Gmail). MCP is becoming the USB standard for AI tools, and both LangGraph and Claude Agent SDK support it.

---

## 6. Deep Dive: LLM Provider

The LLM is the reasoning engine behind everything — tool selection, coaching quality, response generation, and instruction-following. This choice impacts cost, quality, latency, and vendor dependency.

### Option A: Claude (Anthropic) — Sonnet 4.5 / Opus 4.6

**Pros:**
- Best tool-use accuracy: 0.920 tool selection score — 92% accuracy in choosing the right API/function during task execution (best among all tested models).
- Best instruction-following: requires 60% fewer guardrails for multi-step conditional workflows. Critical for a Coach agent that must follow complex roleplay scripts and scoring rubrics.
- SWE-bench leader: Sonnet 4.5 scores 79.6% (with Opus at similar levels) — indicates strong ability to handle complex, multi-step reasoning.
- Prompt caching: cuts costs by up to 90% for repeated queries. Enormous savings when the same playbook context is used across coaching sessions.
- MCP originator: native support for Model Context Protocol, which is becoming the standard for tool integration.
- 200K context window (1M in beta). Enough to hold substantial deal context + playbook chunks.

**Cons:**
- More expensive than Gemini: Sonnet 4.5 at $3/$15 per million tokens vs. Gemini 2.5 Pro at $1.25/$10.
- Smaller context window than Gemini (200K vs. 1M).
- Weaker multimodal capabilities compared to Gemini (less relevant for your Slack text-based use case).

**Pricing:** Sonnet 4.5/4.6: $3 input / $15 output per 1M tokens. Opus 4.6: $5/$25. Haiku 4.5: $1/$5 (for lightweight tasks).

**Best use case for your project:** The Coach agent, where tool selection accuracy and instruction-following directly impact coaching quality. A Coach that picks the wrong HubSpot API call or ignores a scoring rubric ruins the experience.

---

### Option B: GPT-4.1 / GPT-4o (OpenAI)

**Pros:**
- GPT-4.1 aggressive pricing: $2 input / $8 output (cheapest major frontier model after Gemini).
- Strong multimodal support — handles text, images, audio natively.
- Largest ecosystem and community. Most tutorials, most integrations, most third-party tools.
- MMLU leader (88.7%) — broadest general knowledge base.
- GPT-4o delivers half the latency of previous models.

**Cons:**
- Lower tool-use accuracy than Claude (no published equivalent to Claude's 0.920 score).
- Lower SWE-bench score (54.6% for GPT-4.1 vs. Claude's 72.5+%). Indicates weaker complex reasoning.
- OpenAI's deprecation cycle is aggressive — GPT-4o and GPT-4.1 already deprecated in favor of GPT-5.x family as of early 2026. Risk of forced migrations.
- No native MCP support.

**Pricing:** GPT-4.1: $2/$8. GPT-4o: $5/$20 (now deprecated).

**Best use case for your project:** If budget is the top constraint and you're comfortable with lower tool-use accuracy. Good for the Assistant agent's simpler tasks (email drafts, CRM lookups) where tool selection is less critical.

---

### Option C: Gemini 2.5 Pro (Google)

**Pros:**
- Cheapest frontier model: $1.25 input / $10 output per 1M tokens.
- 1 million token context window — can hold enormous amounts of deal history, playbook content, and conversation context simultaneously.
- Strong coding and reasoning (63.8% SWE-bench, 86.7% AIME 2025). Tops LMArena leaderboard in hard prompts, coding, math, and creative writing.
- True multimodal: text, images, audio, and video simultaneously.
- Native Google Cloud integration — seamless with BigQuery, Gmail, and other Google services you're already using.

**Cons:**
- Tool-use accuracy not benchmarked as precisely as Claude's. Anecdotal reports suggest it's good but not best-in-class.
- Less robust instruction-following for complex multi-step agent workflows compared to Claude.
- Google's AI product lifecycle can be unpredictable (rapid deprecations, rebrandings).
- Enterprise market share still growing (smaller than OpenAI and Anthropic in enterprise adoption).

**Pricing:** $1.25/$10 per 1M tokens. Gemini 2.5 Flash even cheaper for lightweight tasks.

**Best use case for your project:** If you want to minimize costs AND you're already deep in the Google Cloud stack (BigQuery + Gmail + Google Workspace). The 1M context window is genuinely powerful for loading large amounts of deal history. Strong candidate for the Assistant agent's research and analytics functions.

---

### Option D: Multi-Model Strategy (Recommended)

**What it is:** Use different LLMs for different agents/tasks based on their strengths, rather than committing to a single provider.

**How this would work for your project:**
```
Coach Agent (quality-critical):
  → Claude Sonnet 4.5 for coaching, roleplay, feedback
  → Reason: Best tool-use accuracy + instruction-following

Assistant Agent (cost-sensitive, high-volume):
  → Gemini 2.5 Pro for research briefs, CRM queries, analytics
  → Reason: Cheapest + 1M context + native Google integration

Lightweight Tasks (classification, routing, summaries):
  → Claude Haiku 4.5 or Gemini Flash
  → Reason: Fastest, cheapest for simple operations
```

**Pros:**
- Optimize cost vs. quality per task. Coach gets the best model; routine tasks get the cheapest.
- No single-vendor dependency. If one provider has an outage or price hike, you can reroute.
- Each model plays to its strengths.

**Cons:**
- More complex to maintain (multiple API keys, different prompt formats, different tool-calling patterns).
- Prompt engineering needs to be adapted per model.
- Testing and evaluation across models adds overhead.

**Estimated monthly cost (for a 10-person sales team, ~500 interactions/day):**
- Claude Sonnet for Coach: ~$50-150/month (with prompt caching)
- Gemini for Assistant: ~$30-80/month
- Haiku/Flash for routing: ~$5-15/month
- Total LLM cost: ~$85-245/month

---

### LLM Summary Matrix

| Factor | Claude Sonnet 4.5 | GPT-4.1 | Gemini 2.5 Pro | Multi-Model |
|--------|-------------------|---------|----------------|-------------|
| Tool-use accuracy | Best (0.920) | Good | Good | Best per task |
| Instruction-following | Best (60% fewer guardrails) | Good | Good | Best per task |
| Context window | 200K (1M beta) | 128K | 1M | Varies |
| Cost per 1M tokens (in/out) | $3/$15 | $2/$8 | $1.25/$10 | Optimized |
| MCP support | Native | No | No | Partial |
| Google Cloud integration | Via API | Via API | Native | Mixed |
| Ecosystem maturity | Strong | Largest | Growing | N/A |
| Deprecation risk | Low | High (aggressive cycle) | Medium | Spread |

### Recommendation for Your Project

**Primary: Multi-model strategy** with Claude Sonnet as the lead for the Coach agent and Gemini 2.5 Pro for the Assistant agent's data-heavy work.

**Rationale:**
1. The Coach agent's quality depends on tool-use accuracy and instruction-following — Claude leads here by a significant margin.
2. The Assistant agent processes large volumes of CRM/analytics data — Gemini's 1M context and native Google integration (BigQuery, Gmail) make it natural.
3. Prompt caching on Claude (up to 90% savings) makes the Coach cost-effective despite higher per-token pricing.
4. LangGraph is model-agnostic, so a multi-model strategy is straightforward to implement.

---

## 7. Implementation Architecture — How the Pieces Wire Together

This is the concrete "what connects to what" diagram. Every arrow is a real API call, SDK method, or protocol handshake.

### 7.1 Full System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SLACK WORKSPACE                                │
│                                                                             │
│  Rep DMs bot    │  /coach command   │  /assist command   │  #pipeline channel│
│  @coach mention │  Thread replies   │  Button clicks     │  Scheduled posts  │
└────────┬────────┴─────────┬─────────┴──────────┬─────────┴─────────┬────────┘
         │                  │                    │                   │
         ▼                  ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SLACK BOLT SDK (Python)                              │
│                                                                             │
│  • Socket Mode (dev) / HTTP Events (prod)                                  │
│  • Event handlers: message, app_mention, slash_command, action             │
│  • Middleware: auth, rate limiting, logging                                 │
│  • Sends typing indicator while agent processes                            │
│  • Formats LangGraph output → Slack Block Kit messages                     │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     ROUTER / TRIAGE     │
                    │   (LangGraph subgraph)  │
                    │                         │
                    │  LLM: Claude Haiku 4.5  │
                    │  (fast, cheap routing)  │
                    │                         │
                    │  Decides:               │
                    │  • Coach or Assistant?   │
                    │  • Which sub-workflow?   │
                    │  • Direct answer?        │
                    └───────┬─────────┬───────┘
                            │         │
              ┌─────────────▼─┐   ┌───▼──────────────┐
              │  COACH AGENT  │   │ ASSISTANT AGENT   │
              │  (LangGraph   │   │ (LangGraph        │
              │   subgraph)   │   │  subgraph)        │
              │               │   │                   │
              │ LLM: Claude   │   │ LLM: Gemini 2.5   │
              │ Sonnet 4.5    │   │ Pro               │
              └───────┬───────┘   └────────┬──────────┘
                      │                    │
         ┌────────────▼────────────────────▼──────────────┐
         │              SHARED TOOL LAYER                  │
         │                  (via MCP)                      │
         │                                                 │
         │  ┌──────────┐ ┌──────────┐ ┌────────────────┐ │
         │  │ HubSpot  │ │ BigQuery │ │    Gmail       │ │
         │  │ MCP      │ │ MCP      │ │    MCP         │ │
         │  │ Server   │ │ Server   │ │    Server      │ │
         │  └────┬─────┘ └────┬─────┘ └───────┬────────┘ │
         │       │            │               │           │
         │  ┌────┴─────┐ ┌───┴──────┐ ┌──────┴────────┐ │
         │  │ Web      │ │ Vector   │ │  Memory       │ │
         │  │ Search   │ │ DB (RAG) │ │  Store        │ │
         │  │ (Tavily) │ │ (Qdrant/ │ │  (Redis/      │ │
         │  │          │ │ Weaviate)│ │  Postgres)    │ │
         │  └──────────┘ └──────────┘ └───────────────┘ │
         └────────────────────────────────────────────────┘
```

### 7.2 The Slack → LangGraph Connection (The Critical Wiring)

This is the most important integration point. LangChain provides an official `langgraph-messaging-integrations` repo for exactly this.

**How it works:**

```
1. Rep types "/coach roleplay discovery call" in Slack
                    │
2. Slack sends event to your server
   (Socket Mode for dev, HTTP webhook for prod)
                    │
3. Slack Bolt event handler receives it:
   ┌────────────────────────────────────────────┐
   │  @app.command("/coach")                     │
   │  async def handle_coach(ack, say, command): │
   │      await ack()  # acknowledge Slack       │
   │      thread_id = command["channel_id"]      │
   │      user_input = command["text"]           │
   │                                             │
   │      # Create or resume LangGraph thread    │
   │      config = {"configurable": {            │
   │          "thread_id": thread_id,            │
   │          "user_id": command["user_id"]      │
   │      }}                                     │
   │                                             │
   │      # Invoke the graph                     │
   │      result = await graph.ainvoke(          │
   │          {"messages": [HumanMessage(        │
   │              content=user_input)]},          │
   │          config=config                       │
   │      )                                      │
   │                                             │
   │      # Send response back to Slack          │
   │      await say(                              │
   │          text=result["messages"][-1].content,│
   │          thread_ts=command["ts"]             │
   │      )                                      │
   └────────────────────────────────────────────┘
                    │
4. LangGraph graph executes:
   Router → Coach subgraph → RAG retrieval → LLM → Response
                    │
5. Response sent back to Slack thread
```

**Key detail: Thread-based state persistence.** Each Slack thread maps to a LangGraph thread_id. When a rep continues a conversation in the same thread, LangGraph loads the full state (conversation history, roleplay context, score tracking) from its checkpointer. This is how the Coach "remembers" that it's mid-roleplay.

**Two deployment options:**

| Option | How | Best for |
|--------|-----|----------|
| **Self-hosted** | FastAPI server + Slack Bolt + LangGraph library. You run everything on Cloud Run / ECS / VM. | Full control, lower cost at scale |
| **LangGraph Platform** | Deploy graph to LangGraph Cloud. Add Slack webhook routes using their messaging integration. LangGraph handles persistence, scaling, monitoring. | Faster setup, managed infra, built-in observability |

### 7.3 The Router Agent (Triage Layer)

The Router is a lightweight LangGraph subgraph that classifies incoming messages and routes them. It runs on Claude Haiku (fast, ~100ms, cheap).

```
┌────────────────────────────────────────────────────┐
│                  ROUTER GRAPH                       │
│                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐ │
│  │  Parse    │───▶│  Classify    │───▶│  Route   │ │
│  │  Input    │    │  Intent      │    │  to      │ │
│  │          │    │              │    │  Agent   │ │
│  └──────────┘    └──────────────┘    └────┬─────┘ │
│                                           │       │
└───────────────────────────────────────────┼───────┘
                                            │
                    ┌───────────────────────┬┘
                    ▼                       ▼
            ┌──────────────┐      ┌────────────────┐
            │ COACH graph  │      │ ASSISTANT graph │
            └──────────────┘      └────────────────┘

Intent categories:
• coaching/roleplay/feedback/training  →  Coach
• research/crm/email/pipeline/admin    →  Assistant
• simple question (no tools needed)    →  Direct LLM answer
• ambiguous                            →  Ask user to clarify
```

### 7.4 Coach Agent Graph (Detailed)

The Coach is the most complex graph — it manages multi-turn roleplays, scoring, and personalized feedback.

```
┌──────────────────────────────────────────────────────────────────┐
│                    COACH AGENT GRAPH                              │
│                    LLM: Claude Sonnet 4.5                         │
│                                                                   │
│  ┌─────────┐    ┌───────────┐    ┌────────────────┐             │
│  │ Classify │───▶│ Load      │───▶│ Choose         │             │
│  │ Request  │    │ Rep       │    │ Workflow        │             │
│  │ Type     │    │ Profile   │    │                │             │
│  └─────────┘    └───────────┘    └───┬───┬───┬────┘             │
│                                      │   │   │                   │
│              ┌───────────────────────┘   │   └──────────┐       │
│              ▼                           ▼               ▼       │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────┐ │
│  │   ROLEPLAY       │  │  POST-CALL        │  │  PREP        │ │
│  │   WORKFLOW        │  │  FEEDBACK         │  │  WORKFLOW    │ │
│  │                   │  │                   │  │              │ │
│  │ 1. RAG: Pull ICP, │  │ 1. RAG: Pull call │  │ 1. HubSpot: │ │
│  │    objections,    │  │    transcript     │  │    Get deal  │ │
│  │    battle cards   │  │ 2. RAG: Pull      │  │ 2. RAG: Pull │ │
│  │ 2. Generate buyer │  │    playbook       │  │    playbook  │ │
│  │    persona        │  │    criteria       │  │ 3. Web: Co.  │ │
│  │ 3. Run multi-turn │  │ 3. LLM: Score    │  │    research  │ │
│  │    conversation   │  │    against rubric │  │ 4. BigQuery: │ │
│  │ 4. Score each turn│  │ 4. LLM: Generate │  │    History   │ │
│  │ 5. Final debrief  │  │    action items   │  │ 5. Generate  │ │
│  │                   │  │ 5. Update rep     │  │    brief     │ │
│  │                   │  │    skill profile  │  │              │ │
│  └──────────────────┘  └───────────────────┘  └──────────────┘ │
│              │                   │                    │          │
│              └───────────────────┴────────────────────┘          │
│                               │                                  │
│                    ┌──────────▼──────────┐                       │
│                    │  Update Rep Profile │                       │
│                    │  (BigQuery / Memory)│                       │
│                    └──────────┬──────────┘                       │
│                               │                                  │
│                    ┌──────────▼──────────┐                       │
│                    │  Format & Return    │                       │
│                    │  to Slack           │                       │
│                    └────────────────────┘                       │
└──────────────────────────────────────────────────────────────────┘
```

**Roleplay multi-turn loop (the most complex part):**
```
                    ┌─────────────┐
                    │ Generate    │
                    │ Buyer       │◄──────────────────┐
                    │ Response    │                    │
                    └──────┬──────┘                    │
                           │                           │
                    ┌──────▼──────┐                    │
                    │ Send to     │                    │
                    │ Slack       │                    │
                    │ (as buyer)  │                    │
                    └──────┬──────┘                    │
                           │                           │
                    ┌──────▼──────┐                    │
                    │ WAIT for    │  ← Durable exec:  │
                    │ rep reply   │    graph pauses,   │
                    │ in thread   │    state persists   │
                    └──────┬──────┘                    │
                           │                           │
                    ┌──────▼──────┐     ┌──────────┐  │
                    │ Score       │────▶│ More     │──┘
                    │ rep's turn  │ yes │ turns?   │
                    └──────┬──────┘     └──────────┘
                           │ no
                    ┌──────▼──────┐
                    │ Generate    │
                    │ Final       │
                    │ Debrief     │
                    └─────────────┘
```

This is where LangGraph's durable execution is critical — the graph pauses at "WAIT for rep reply" and resumes exactly where it left off when the rep responds in the Slack thread, even hours later.

### 7.5 Assistant Agent Graph (Detailed)

The Assistant handles admin automation, research, and pipeline management.

```
┌──────────────────────────────────────────────────────────────────┐
│                  ASSISTANT AGENT GRAPH                            │
│                  LLM: Gemini 2.5 Pro                              │
│                                                                   │
│  ┌─────────┐    ┌───────────────┐                                │
│  │ Classify │───▶│ Choose         │                                │
│  │ Request  │    │ Workflow       │                                │
│  └─────────┘    └──┬───┬───┬──┬─┘                                │
│                    │   │   │  │                                   │
│       ┌────────────┘   │   │  └─────────────────┐               │
│       ▼                ▼   ▼                    ▼               │
│  ┌─────────┐  ┌──────────┐ ┌──────────┐  ┌──────────────┐     │
│  │RESEARCH │  │CRM       │ │EMAIL     │  │PIPELINE      │     │
│  │BRIEF    │  │UPDATE    │ │DRAFT     │  │HEALTH        │     │
│  │         │  │          │ │          │  │              │     │
│  │1.HubSpot│  │1.Parse   │ │1.HubSpot:│  │1.HubSpot:   │     │
│  │  deal   │  │  Slack   │ │  Get deal│  │  Pull all    │     │
│  │  context│  │  message │ │  context │  │  open deals  │     │
│  │2.Web:   │  │2.Extract │ │2.RAG:    │  │2.BigQuery:   │     │
│  │  company│  │  entities│ │  Pull    │  │  Win rate    │     │
│  │  news   │  │3.HubSpot:│ │  email   │  │  trends      │     │
│  │3.BigQuery│ │  Update  │ │  template│  │3.Flag stale  │     │
│  │  history│  │  contact/│ │3.Gmail:  │  │  deals,      │     │
│  │4.RAG:   │  │  deal    │ │  Create  │  │  missing     │     │
│  │  playbook│ │4.Confirm │ │  draft   │  │  data        │     │
│  │5.Generate│ │  to user │ │4.Confirm │  │4.Generate    │     │
│  │  brief  │  │          │ │  to user │  │  digest      │     │
│  └─────────┘  └──────────┘ └──────────┘  └──────────────┘     │
│                                                                   │
│                    ┌──────────────────┐                           │
│                    │ Format & Return  │                           │
│                    │ to Slack         │                           │
│                    └─────────────────┘                           │
└──────────────────────────────────────────────────────────────────┘
```

### 7.6 MCP Tool Wiring (How Tools Connect)

MCP (Model Context Protocol) is the standard for connecting agents to external services. Each service gets its own MCP server, and your agents are MCP clients.

```
┌─────────────────────────────────────────────────────┐
│              YOUR APPLICATION                        │
│                                                      │
│  LangGraph Agent (MCP Client)                       │
│       │                                              │
│       ├──── MCP Protocol ────▶ HubSpot MCP Server   │
│       │                        (Official — Public Beta)
│       │                        • Read: contacts, companies,
│       │                          deals, tickets, notes
│       │                        • Write: create/update deals,
│       │                          contacts, log activities
│       │                        • Auth: OAuth 2.0 via HubSpot
│       │                                              │
│       ├──── MCP Protocol ────▶ BigQuery MCP Server   │
│       │                        (Google Official — Managed)
│       │                        • Query: Run SQL on your datasets
│       │                        • Schema: Inspect tables
│       │                        • Auth: Google Service Account
│       │                        • Auto-enabled after Mar 17, 2026
│       │                                              │
│       ├──── MCP Protocol ────▶ Gmail MCP Server      │
│       │                        (Community — shinzo-labs
│       │                         or GongRzhe)
│       │                        • Read: search, get messages
│       │                        • Write: create drafts, send
│       │                        • Auth: OAuth 2.0 via Google
│       │                                              │
│       ├──── MCP Protocol ────▶ Web Search MCP Server │
│       │                        (Tavily or custom)
│       │                        • Search: web queries
│       │                        • Extract: page content
│       │                                              │
│       └──── MCP Protocol ────▶ Vector DB MCP Server  │
│                                (Custom — wraps Qdrant/
│                                 Weaviate API)
│                                • Search: semantic + keyword
│                                • Index: add/update documents
│                                • Auth: API key
└─────────────────────────────────────────────────────┘

Key advantage of MCP: Each server is a standalone process.
You can develop, test, and deploy them independently.
Add a new tool = add a new MCP server. No agent code changes.
```

**Existing MCP servers you can use off-the-shelf:**

| Service | MCP Server | Status | Notes |
|---------|-----------|--------|-------|
| HubSpot | `developers.hubspot.com/mcp` | Official, Public Beta | Read-only currently; community forks add write |
| HubSpot (extended) | `shinzo-labs/hubspot-mcp` | Community, MIT | Full CRUD, 106 tools |
| BigQuery | Google Managed Remote MCP | Official, GA | Auto-enabled, fully managed |
| BigQuery | `LucasHild/mcp-server-bigquery` | Community | Lightweight alternative |
| Gmail | `shinzo-labs/gmail-mcp` | Community, MIT | Full API coverage |
| Gmail | `GongRzhe/Gmail-MCP-Server` | Community | Auto-auth, Claude Desktop tested |
| Gmail | `MarkusPfundstein/mcp-gsuite` | Community | Gmail + Calendar + Docs |
| Web Search | `tavily-mcp` | Official (Tavily) | Optimized for RAG/agents |

### 7.7 Multi-Model Wiring in LangGraph

Each node in your LangGraph graph can use a different LLM. Here's how:

```python
# Model initialization
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Router: fast, cheap
router_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")

# Coach: highest quality
coach_llm = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    # Enable prompt caching for playbook context
)

# Assistant: cost-effective, large context
assistant_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    # 1M context for large data loads
)

# Each node uses its own LLM
def router_node(state):
    response = router_llm.invoke(state["messages"])
    return {"route": parse_route(response)}

def coach_node(state):
    # RAG retrieval happens here
    context = rag_retrieve(state["messages"][-1].content)
    response = coach_llm.invoke(
        [SystemMessage(content=COACH_PROMPT + context)]
        + state["messages"]
    )
    return {"messages": [response]}

def assistant_node(state):
    response = assistant_llm.invoke(state["messages"])
    return {"messages": [response]}
```

### 7.8 RAG Wiring (How Knowledge Flows)

```
┌─────────────────────────────────────────────────────────────┐
│                     INDEXING PIPELINE                         │
│                    (Runs on schedule / trigger)               │
│                                                              │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐             │
│  │ Source     │──▶│ Chunker   │──▶│ Embedding │──▶ Vector DB│
│  │ Loader    │   │           │   │ Model     │             │
│  └───────────┘   └───────────┘   └───────────┘             │
│                                                              │
│  Sources & cadences:                                         │
│  • Playbooks (manual upload, on change)                      │
│  • HubSpot notes (webhook/hourly API pull)                   │
│  • BigQuery exports (daily scheduled query)                  │
│  • Call transcripts (after each call, via Gong/HubSpot API) │
│  • Web research (on-demand, cached)                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     QUERY PIPELINE                           │
│                   (Runs at every agent request)              │
│                                                              │
│  User query                                                  │
│      │                                                       │
│      ▼                                                       │
│  ┌──────────┐   ┌───────────────┐   ┌──────────────┐       │
│  │ Embed    │──▶│ Hybrid Search │──▶│ Reranker     │       │
│  │ Query    │   │ (Vector +     │   │ (Cohere      │       │
│  │ (Voyage  │   │  BM25 keyword)│   │  Rerank v4)  │       │
│  │  3.5)    │   │ Top 50 results│   │ Top 5 results│       │
│  └──────────┘   └───────────────┘   └──────┬───────┘       │
│                                             │                │
│                                      ┌──────▼───────┐       │
│                                      │ Inject into  │       │
│                                      │ LLM context  │       │
│                                      │ as system    │       │
│                                      │ message      │       │
│                                      └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 7.9 State & Memory Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY LAYERS                             │
│                                                              │
│  Layer 1: CONVERSATION MEMORY (per Slack thread)            │
│  ├── Storage: LangGraph checkpointer (Postgres/Redis)       │
│  ├── Contains: full message history, agent state             │
│  ├── Lifetime: duration of the thread/session                │
│  └── Maps to: Slack thread_ts → LangGraph thread_id         │
│                                                              │
│  Layer 2: REP PROFILE MEMORY (per sales rep)                │
│  ├── Storage: Postgres / BigQuery                            │
│  ├── Contains: skill scores, weak areas, coaching history,  │
│  │   preferred style, completed roleplays                    │
│  ├── Lifetime: persistent (grows over time)                  │
│  └── Loaded: at start of every Coach session                 │
│                                                              │
│  Layer 3: TEAM KNOWLEDGE (shared)                           │
│  ├── Storage: Vector DB (Qdrant/Weaviate)                   │
│  ├── Contains: playbooks, battle cards, best practices,     │
│  │   call transcripts, deal patterns                         │
│  ├── Lifetime: persistent, updated on schedule               │
│  └── Accessed: via RAG at query time                         │
│                                                              │
│  Layer 4: LIVE DATA (real-time)                             │
│  ├── Storage: External APIs (HubSpot, BigQuery, Gmail, Web) │
│  ├── Contains: current deal status, latest emails, fresh news│
│  ├── Lifetime: real-time (no caching, or short TTL cache)    │
│  └── Accessed: via MCP tool calls at runtime                 │
└─────────────────────────────────────────────────────────────┘
```

### 7.10 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRODUCTION DEPLOYMENT                         │
│                                                                  │
│  Option A: Self-Hosted (Google Cloud — natural for BigQuery)    │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Cloud Run   │  │ Cloud SQL    │  │ Qdrant Cloud       │    │
│  │ (or GKE)    │  │ (Postgres)   │  │ (or Weaviate Cloud)│    │
│  │             │  │              │  │                    │    │
│  │ • FastAPI   │  │ • LangGraph  │  │ • Vector storage   │    │
│  │ • Slack Bolt│  │   checkpoints│  │ • RAG index         │    │
│  │ • LangGraph │  │ • Rep        │  │                    │    │
│  │   runtime   │  │   profiles   │  │                    │    │
│  │ • MCP       │  │ • App state  │  │                    │    │
│  │   clients   │  │              │  │                    │    │
│  └──────┬──────┘  └──────────────┘  └────────────────────┘    │
│         │                                                       │
│         ├───▶ HubSpot API (external)                           │
│         ├───▶ BigQuery API (same GCP project)                  │
│         ├───▶ Gmail API (same GCP project)                     │
│         ├───▶ Tavily API (external)                            │
│         ├───▶ Claude API (Anthropic — external)                │
│         └───▶ Gemini API (same GCP project / Vertex AI)        │
│                                                                  │
│  Option B: LangGraph Platform (Managed)                        │
│                                                                  │
│  ┌──────────────────────────────────┐                          │
│  │ LangGraph Cloud                  │                          │
│  │ • Hosts your graph               │                          │
│  │ • Built-in persistence           │                          │
│  │ • Built-in observability          │                          │
│  │ • Slack webhook integration       │                          │
│  │ • Auto-scaling                    │                          │
│  │ • You configure MCP connections   │                          │
│  └──────────────────────────────────┘                          │
│                                                                  │
│  Recommendation: Start with Option B (faster to ship),         │
│  migrate to Option A when you need cost control at scale.      │
└─────────────────────────────────────────────────────────────────┘
```

### 7.11 Observability & Monitoring

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY STACK                        │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Langfuse     │  │ LangSmith    │  │ Custom Metrics   │  │
│  │ (or LangSmith│  │ (if using    │  │                  │  │
│  │  — pick one) │  │  LG Platform)│  │ • Response time  │  │
│  │              │  │              │  │ • Tool call freq │  │
│  │ • Traces     │  │ • Traces     │  │ • RAG hit rate   │  │
│  │ • Token costs│  │ • Playground │  │ • User ratings   │  │
│  │ • Latency    │  │ • Datasets   │  │ • Error rate     │  │
│  │ • Evals      │  │ • Evals      │  │ • Cost per query │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Phases (Revised)

### Phase 1: Foundation + Prototype (Weeks 1–3)
- Set up Slack app with Bolt SDK (Socket Mode for dev)
- Scaffold LangGraph project with Router + one simple graph
- Connect HubSpot MCP server (official, read-only)
- Connect BigQuery MCP server (Google managed)
- Set up ChromaDB locally for RAG prototyping
- Simple commands: `/research [company]`, `/deal [deal-name]`
- Deploy to LangGraph Platform (or local Docker)

### Phase 2: Assistant Agent — MVP (Weeks 4–6)
- Build Assistant subgraph with Gemini 2.5 Pro
- Pre-meeting research briefs (HubSpot + Web + BigQuery)
- Follow-up email drafts (Gmail MCP server)
- Pipeline health alerts (scheduled + Slack channel)
- Migrate from ChromaDB → Qdrant/Weaviate for production RAG
- Set up Voyage AI embeddings + recursive chunking pipeline
- Basic CRM update from Slack messages

### Phase 3: Coach Agent — MVP (Weeks 7–10)
- Build Coach subgraph with Claude Sonnet 4.5
- Roleplay mode in Slack threads (multi-turn with durable execution)
- RAG: Index sales playbooks, battle cards, ICP docs
- Post-call feedback workflow (manual note input first)
- Rep profile storage (Postgres or BigQuery)
- Add Cohere Rerank to RAG pipeline

### Phase 4: Intelligence & Polish (Weeks 11–14)
- BigQuery analytics integration (win/loss patterns, benchmarks)
- Manager digest (weekly Slack summary + channel post)
- Cross-agent coordination (Coach calls Assistant tools)
- Semantic chunking for call transcripts
- Human-in-the-loop for manager approval workflows
- Observability: Langfuse or LangSmith integration
- Load testing and cost optimization

---

## 9. Mermaid Architecture Diagrams

All architecture diagrams are available as renderable Mermaid code in the companion file:
**`architecture-diagrams.mermaid`**

The file contains 12 diagrams:

| # | Diagram | What It Shows |
|---|---------|---------------|
| 1 | Full System Architecture | Top-level: Slack → Bolt → Router → Coach/Assistant → MCP Tools |
| 2 | Slack ↔ LangGraph Connection | Sequence diagram: event flow, state persistence, thread mapping |
| 3 | Router Agent Graph | Intent classification and routing to Coach vs. Assistant |
| 4 | Coach Agent Graph | 3 workflows: roleplay, post-call feedback, meeting prep |
| 5 | Assistant Agent Graph | 4 workflows: research, CRM update, email draft, pipeline health |
| 6 | MCP Tool Wiring | How agents connect to HubSpot, BigQuery, Gmail, Web, Vector DB |
| 7 | RAG Pipeline | Indexing pipeline (sources → chunker → embedder) + query pipeline |
| 8 | Memory Architecture | 4 layers: conversation, rep profile, team knowledge, live data |
| 9 | Deployment Architecture | GCP self-hosted: Cloud Run + Cloud SQL + external services |
| 10 | Coach Roleplay State Machine | Multi-turn durable execution with pause/resume |
| 11 | Implementation Timeline | 14-week Gantt chart across 4 phases |
| 12 | End-to-End Data Flow | Sequence: meeting prep request from Slack through all services |

To render: paste any diagram into [mermaid.live](https://mermaid.live), VS Code Mermaid extension, or any Mermaid-compatible tool.

---

## 10. Open Questions — Resolved

### Q3: Hosting / Infrastructure

**Decision: Start on LangGraph Platform (managed), migrate to GCP self-hosted at scale.**

Rationale:
- LangGraph Platform gives you 1-click deployment, built-in persistence, observability, and auto-scaling. This shaves 2-3 weeks off Phase 1.
- When you need cost control or custom infra (likely at 50+ users), migrate to GCP self-hosted: Cloud Run (compute) + Cloud SQL Postgres (state) + Qdrant Cloud (vectors).
- GCP is natural because you're already on BigQuery and Gmail — same project, same IAM, same billing.

Estimated infra cost (self-hosted, 10-person team):
- Cloud Run: ~$30-50/month (auto-scaling, pay per request)
- Cloud SQL (Postgres): ~$30-50/month (small instance)
- Qdrant Cloud: ~$27-100/month (depending on quantization)
- Total infra: ~$87-200/month (on top of ~$85-245/month LLM costs)
- **Grand total: ~$170-445/month for a 10-person sales team**

---

### Q4: Should Agents Share Memory / Context?

**Decision: Shared tool layer, separated conversation memory, shared rep profiles.**

Architecture:
- **Shared:** Both agents access the same MCP tools (HubSpot, BigQuery, Gmail, RAG vector DB). No data duplication.
- **Shared:** Both agents read/write the same rep profile store. If the Coach scores a rep on discovery skills, the Assistant can reference that when generating a research brief ("focus on areas where this rep needs practice").
- **Separated:** Conversation memory is per-thread, per-agent. A coaching thread's state doesn't bleed into an assistant request. Each LangGraph subgraph maintains its own state.
- **Cross-agent calls (Phase 4):** The Coach can invoke Assistant tools (e.g., "pull the latest Acme deal data") via the shared MCP layer. The Coach doesn't need to know it's talking to the Assistant — it just calls the HubSpot MCP tool.

This gives you isolation where it matters (conversations) and shared context where it helps (rep profiles, CRM data, knowledge base).

---

### Q5: Voice Input Support (like Pam) or Text-Only in Slack?

**Decision: Text-only for MVP. Voice as a Phase 5 add-on.**

Rationale:
- Pam's voice-first design makes sense for field reps who are driving between meetings. Your team operates in Slack, which is inherently text-first.
- Slack supports audio/video clips in messages (since 2022). A future enhancement could let reps send voice clips that get transcribed and processed by the agent.
- Adding voice in Phase 1 would double the complexity: you'd need a speech-to-text pipeline (Whisper, Deepgram, or AssemblyAI), voice activity detection, and a different UX flow.
- If field reps need voice later, the architecture supports it cleanly: voice clip → Whisper transcription → same LangGraph pipeline. The agent doesn't care whether the input was typed or spoken.

Phase 5 voice roadmap (if needed):
1. Slack voice clip → Whisper API transcription → inject as text message
2. Optional: dedicated mobile app or phone number → Twilio/Vonage → transcription → agent
3. Optional: text-to-speech for agent responses (less likely needed in Slack)

---

### Q6: How to Handle PII / Sensitive Deal Data in LLM Context?

**Decision: Defense-in-depth with 6 layers of protection.**

This is critical — your agents will handle contact names, email addresses, deal values, company information, and potentially financial data.

**Layer 1: Data Minimization**
- Only retrieve the specific fields needed for each task. Don't dump entire contact records into context.
- The RAG pipeline should chunk and index content, not full database exports.
- MCP tool responses should be filtered to relevant fields before injection into LLM context.

**Layer 2: Access Control (Least Privilege)**
- HubSpot MCP: OAuth scoped to minimum required permissions. Read-only where possible. Write only for specific operations (log activity, update deal stage).
- BigQuery MCP: Service account with read-only access to specific datasets. No access to billing, HR, or unrelated data.
- Gmail MCP: User-level OAuth — each rep authorizes their own Gmail. Agent can only access emails the rep has access to.
- Vector DB: API key with scoped permissions. No admin access from the agent.

**Layer 3: PII Detection & Redaction**
- Run a PII detection pipeline (Microsoft Presidio, Google DLP API, or custom regex) on:
  - Data flowing INTO the RAG index (redact SSNs, credit card numbers from call transcripts)
  - Data flowing INTO LLM context (sanitize before sending to Claude/Gemini API)
  - Data flowing OUT of the agent (catch any leaked PII in responses)
- Maintain a "PII canary" test set to validate the pipeline catches known sensitive patterns.

**Layer 4: LLM Provider Data Policies**
- Both Anthropic (Claude) and Google (Gemini) offer zero-data-retention API options for enterprise:
  - Anthropic: API data is not used for training. Enterprise plans offer additional data handling guarantees.
  - Google: Vertex AI offers data residency controls, no training on customer data, and SOC 2 compliance.
- Use API-based access (not consumer chat), which provides stronger data handling guarantees.

**Layer 5: Audit Logging**
- Log every tool call, every MCP request, every LLM invocation — but redact PII from logs.
- Immutable audit trail: who accessed what data, when, for what purpose.
- LangSmith/Langfuse traces give you this for free within the agent framework.
- Align with SOC 2 Type 2 requirements if you plan to pursue certification.

**Layer 6: Network & Encryption**
- All API calls over HTTPS/TLS (enforced by default for all services).
- Encrypt data at rest in Postgres and Qdrant.
- If self-hosted on GCP, use VPC Service Controls to restrict data egress.

**What NOT to worry about (yet):**
- You don't need homomorphic encryption or on-prem models for a 10-person internal sales tool.
- GDPR applies if you have EU customers/contacts in HubSpot — worth noting but manageable with data minimization.
- SOC 2 certification is a future consideration if you ever productize this for external customers.

---

### Q7: Single Slack App with Two Agents, or Two Separate Apps?

**Decision: Single Slack app, two internal subgraphs.**

Rationale:
- **Single app = single OAuth flow, single install, single permission set.** Two apps means your admin installs twice, manages two sets of permissions, and users must remember which app to talk to.
- The Router subgraph handles the "which agent?" question transparently. The rep just talks to "@SalesBot" — they don't need to know there are two agents behind it.
- Slash commands differentiate explicitly when needed: `/coach` goes to Coach, `/assist` goes to Assistant. DMs and @mentions go through the Router.
- A single Slack app can still run two LangGraph subgraphs internally — this is an implementation detail, not a Slack concern.
- Future benefit: if you add a third agent (e.g., a "Forecaster" for pipeline predictions), you add a subgraph and a route — no new Slack app needed.

Naming suggestion: A single bot named something like **"Jam"** (inspired by WeJam) or **"SalesBot"** or a custom name that fits your team culture.

Slack app configuration:
- Bot scopes: `chat:write`, `commands`, `app_mentions:read`, `channels:history`, `groups:history`, `im:history`, `im:write`
- Slash commands: `/coach`, `/assist`, `/research`, `/pipeline`, `/deal`
- Event subscriptions: `message.im`, `message.groups`, `app_mention`
- Interactive components: buttons (for confirmations), modals (for settings)

---

### Q8: Budget / Cost Constraints

**Decision: Need Izzy's input. Here's the full cost breakdown to discuss.**

**Monthly cost estimate for 10-person sales team (~500 interactions/day):**

| Category | Component | Low Est. | High Est. |
|----------|-----------|----------|-----------|
| **LLM APIs** | Claude Sonnet (Coach) | $50 | $150 |
| | Gemini 2.5 Pro (Assistant) | $30 | $80 |
| | Claude Haiku (Router) | $5 | $15 |
| **RAG** | Voyage AI embeddings | $5 | $20 |
| | Cohere Rerank | $5 | $15 |
| | Qdrant Cloud (Vector DB) | $27 | $100 |
| **Infrastructure** | Cloud Run (compute) | $30 | $50 |
| | Cloud SQL Postgres | $30 | $50 |
| | Redis (optional cache) | $0 | $25 |
| **Tools** | Tavily (web search) | $0 | $50 |
| | HubSpot API | $0 | $0 |
| | BigQuery API | $0 | $10 |
| | Gmail API | $0 | $0 |
| **Observability** | Langfuse/LangSmith | $0 | $50 |
| **TOTAL** | | **$182** | **$615** |

Notes:
- HubSpot, BigQuery, Gmail APIs are free (within existing subscriptions/quotas).
- Tavily offers a free tier (1,000 searches/month); paid starts at $50/month for 10,000.
- Claude prompt caching could reduce Coach LLM costs by up to 90%.
- Langfuse has a free self-hosted option; LangSmith free tier covers small teams.

**Comparison to alternatives:**
- Hiring a dedicated sales ops person: ~$5,000-8,000/month
- WeJam/Gong/Mindtickle subscription: ~$50-150/user/month = $500-1,500/month
- Your custom build: ~$182-615/month + development time

**Development cost:**
- If you build in-house: 14 weeks of developer time
- If you hire a contractor: ~$15K-40K for the full build
- Ongoing maintenance: ~5-10 hours/month

**⚠️ Izzy — what's your comfortable monthly budget for running costs? And are you building this yourself, hiring a developer, or contracting it out? This affects our Phase 1 approach significantly.**

---

---

## 11. Build Strategy: Vibe-Coded POC → Hire → Full Rollout

### The Two-Phase Approach

```
PHASE A: YOU (Izzy) vibe-code a POC          PHASE B: HIRED DEV rebuilds for production
┌────────────────────────────────────┐       ┌──────────────────────────────────────┐
│  Goal: Executive demo & approval   │       │  Goal: Production rollout to team     │
│  Timeline: 2-3 weeks              │       │  Timeline: 6-8 weeks                 │
│  Tools: Claude Code / Cursor +     │       │  Tools: Claude Code + Opus 4.5       │
│          Opus, vibe coding         │       │  Dev: Senior FS @ €3,000/month       │
│  Output: Working demo in Slack     │       │  Output: Hardened, scalable, secure   │
│  Budget: ~$50-100 API costs        │       │  Budget: €3,000/mo + ~$300-500 infra │
└────────────────────────────────────┘       └──────────────────────────────────────┘
```

---

### PHASE A: Vibe-Coded Proof of Concept (You, 2-3 Weeks)

#### What You CAN Demo (Realistically)

The POC should demonstrate the **core value propositions** — enough to make executives say "yes, fund this." You don't need production quality, error handling, or security. You need "wow" moments.

**Week 1: Foundation + Assistant Demo (5-7 days)**

What you build:
- Slack app (Bolt SDK, Socket Mode) — your bot appears in Slack
- Single LangGraph graph with Claude Sonnet as the LLM
- HubSpot MCP server connected (read-only)
- Two working slash commands:
  - `/research Acme Corp` → pulls HubSpot deal data + web search + generates a research brief
  - `/deal Acme Corp` → shows deal status, recent activities, next steps from HubSpot

What executives see:
- A rep types `/research Acme Corp` in Slack and gets a rich, context-aware research brief with deal history, company news, and suggested talking points — in 15 seconds.
- "This is what your reps get before every meeting, automatically."

Vibe coding approach:
- Use Claude Code / Cursor to scaffold the entire Slack Bolt app
- Install the official HubSpot MCP server (`npm install @hubspot/mcp-server`)
- Use LangGraph's quickstart template
- Prompt: "Build a Slack Bolt app that receives /research commands, calls HubSpot API for deal data, runs a web search, and generates a meeting prep brief using Claude Sonnet"

**Week 2: Coach Demo + Email Draft (5-7 days)**

What you build:
- `/coach roleplay` → starts a multi-turn sales roleplay in a Slack thread
- The bot plays a buyer persona, the rep practices their pitch
- After 3-4 turns, the bot gives a score and feedback
- `/draft-email Acme Corp` → generates a follow-up email draft based on deal context
- Basic RAG: index 2-3 of your actual sales playbook pages into ChromaDB

What executives see:
- A rep starts a roleplay, practices handling a pricing objection with a realistic AI buyer, and gets scored with specific feedback and improvement suggestions.
- A rep asks for a follow-up email and gets a draft that references the actual deal context from HubSpot.
- "This is 24/7 coaching and admin automation, in the tool your team already uses."

Vibe coding approach:
- Extend the LangGraph graph with a Coach subgraph
- Use ChromaDB (pip install, runs locally) for quick RAG
- Index your playbook PDFs using LangChain's document loaders
- The roleplay doesn't need durable execution for the demo — just a simple loop

**Week 3: Polish + Pipeline Digest (3-5 days)**

What you build:
- `/pipeline` → generates a pipeline health summary from HubSpot (stale deals, at-risk deals, missing data)
- Connect BigQuery for one or two analytics queries ("win rate by deal stage", "average close time")
- Clean up Slack Block Kit formatting — make responses look professional
- Record a demo video or prepare a live walkthrough

What executives see:
- A manager types `/pipeline` and gets a digest of the entire sales pipeline with flagged risks and data quality issues.
- Combined with the research brief and coaching demo, this shows a complete picture: coaching + admin automation + management visibility.

#### POC Demo Script for Executive Presentation

```
1. OPEN: "Our sales team spends 4+ hours/week on admin. Here's how we fix that."

2. RESEARCH BRIEF (60 seconds)
   → /research [real customer name]
   → Bot returns: company overview, deal status, recent news, talking points
   → "Before every meeting, every rep gets this. Automatically."

3. COACHING ROLEPLAY (3 minutes)
   → /coach roleplay discovery call
   → Bot plays buyer, rep handles objections
   → Bot scores and gives feedback
   → "24/7 coaching. New reps practice safely. Managers track progress."

4. EMAIL DRAFT (60 seconds)
   → /draft-email [real customer name]
   → Bot generates contextual follow-up
   → "Follow-ups drafted in seconds, not 20 minutes."

5. PIPELINE HEALTH (60 seconds)
   → /pipeline
   → Bot flags stale deals, missing data, at-risk deals
   → "Managers get this digest every morning. No more pipeline review meetings."

6. CLOSE: "Running cost: ~$300-500/month. 10x cheaper than any SaaS tool.
   We need one senior developer to take this to production in 8 weeks."
```

#### What the POC Does NOT Need

- Production error handling (it's a demo — if it breaks, restart)
- Security / PII handling (you're demoing with your own data)
- Durable execution (roleplay can be simple loop, not persistent)
- Multi-model routing (use Claude for everything in the POC)
- Reranking (basic RAG is fine for demo)
- Observability / logging (not needed for demo)
- Deployment to cloud (run locally or on a dev server)

#### Key Decision: MCP in the POC — Yes, Include It

**Original plan:** Use direct API calls (HubSpot SDK, BigQuery client) for simplicity.
**Revised decision:** Use MCP servers in the POC. Here's why:

**Arguments FOR MCP in the POC:**

1. **The POC becomes a real pilot, not just a demo.** With MCP, you're running the actual production architecture — not a throwaway prototype that gets scrapped. Executives see the real system, not a mock-up.

2. **Zero throwaway code.** Direct API wrappers in tools/hubspot.py would be discarded entirely when the hired dev rebuilds with MCP. With MCP in the POC, the tool integration layer carries forward to production unchanged.

3. **It's actually not hard anymore.** The `langchain-mcp-adapters` library makes MCP tools plug directly into LangGraph with almost zero setup:
   - `pip install langchain-mcp-adapters`
   - HubSpot has an official MCP server (public beta)
   - Google has a managed BigQuery MCP server (auto-enabled)
   - Gmail has community servers (shinzo-labs)
   - Basic setup: ~15-30 minutes per server, not days

4. **Tool discovery is automatic.** MCP servers expose their available tools dynamically. The agent discovers what it can do at startup — no manual tool definitions needed. This is less code to write than direct API wrappers.

5. **Adds to the executive story.** "This uses the same open protocol (MCP) that Anthropic created and that Google, HubSpot, Slack, and thousands of others have adopted. We're not building a fragile custom integration — we're plugging into the industry standard."

6. **Adding a new tool = adding a new MCP server.** During the pilot, if a rep says "can it also check Salesforce?" or "can it read Notion?", you answer "yes, there's an MCP server for that" instead of "we'd need to write a custom API wrapper."

**Arguments AGAINST (and why they're now weaker):**

1. ~~"More moving parts"~~ → With `langchain-mcp-adapters`, MCP tools appear as regular LangGraph tools. The complexity is hidden behind a clean abstraction.

2. ~~"Harder to debug"~~ → Fair point for custom MCP servers, but the official HubSpot and Google servers are well-tested. If a tool call fails, the error message is clear.

3. ~~"Slower to prototype"~~ → In 2024, yes. In 2026, no. Setup is ~15-30 minutes per server with existing packages.

4. "One more dependency" → True. But `langchain-mcp-adapters` is a thin wrapper maintained by LangChain — the same team maintaining LangGraph. Low risk.

**Revised verdict:** MCP goes into the POC. The extra 1-2 hours of setup pays for itself in pilot readiness and zero throwaway code. The POC becomes something that can actually be piloted with real reps, not just demonstrated to executives.

#### POC Tech Stack (Revised — With MCP)

| Component | POC Choice | Why |
|-----------|-----------|-----|
| Framework | LangGraph | Validates production architecture |
| LLM | Claude Sonnet 4.5 only | Simplify — multi-model comes later |
| MCP Adapter | langchain-mcp-adapters | Bridges MCP tools ↔ LangGraph seamlessly |
| HubSpot | Official HubSpot MCP Server | Production-ready, public beta, read + community forks for write |
| BigQuery | Google Managed MCP Server | Auto-enabled, fully managed |
| Gmail | shinzo-labs/gmail-mcp | Community server, MIT, full API coverage |
| Vector DB | ChromaDB (local) | pip install, zero config |
| Embeddings | OpenAI text-embedding-3-small | Cheapest, easiest |
| Web Search | Tavily | Free tier, optimized for agents |
| Slack | Bolt SDK (Socket Mode) | Works locally, no server needed |
| Hosting | Your laptop | Socket Mode connects directly to Slack |

#### POC Cost Estimate

| Item | Cost |
|------|------|
| Claude API (Sonnet, ~1000 calls during dev) | ~$30-50 |
| OpenAI embeddings | ~$2-5 |
| Tavily web search (free tier) | $0 |
| HubSpot / BigQuery / Gmail APIs | $0 |
| Claude Code subscription (for vibe coding) | Included in your existing plan |
| **Total POC cost** | **~$32-55** |

---

### PHASE B: Post-Hire Production Rollout (Senior Dev, 6-8 Weeks)

#### Developer Profile Needed

**Senior Full-Stack Developer @ €3,000/month**

Must-have skills:
- Python (FastAPI, async programming)
- LangGraph / LangChain experience (or willingness to learn fast with Claude Code)
- Slack API / Bolt SDK
- REST API integrations (HubSpot, Google APIs)
- Basic DevOps (Docker, Cloud Run or similar)
- Familiar with AI-assisted development (Claude Code + Opus 4.5)

Nice-to-have:
- MCP server development
- Vector databases (Qdrant/Weaviate)
- RAG pipelines
- GCP experience (BigQuery, Cloud SQL)

#### The Claude Code + Opus 4.5 Acceleration Factor

Based on current data (early 2026), a senior developer using Claude Code + Opus:
- Completes multi-day development work in hours (Anthropic's own benchmarks)
- 50-75% reduction in tool calling errors and build/lint errors
- Opus 4.5 can manage subagent teams — the dev can run parallel Claude Code agents on different components
- Realistic acceleration: **2.5-3x faster** than traditional development

This means your 14-week roadmap compresses to roughly **6-8 weeks** with one senior dev on Claude Code.

#### Post-Hire Rollout Timeline (6-8 Weeks)

**Week 1-2: Rebuild Foundation (from POC → Production)**

The dev does NOT build on top of your POC. They rebuild it properly using the architecture we designed. The POC proved the concept; now we need production quality.

| Task | Details | Claude Code helps |
|------|---------|-------------------|
| Scaffold LangGraph project | Proper project structure, config, env management | Opus generates full scaffold in hours |
| Slack Bolt app (HTTP mode) | Production webhooks, proper error handling, rate limiting | Bolt SDK setup is well-documented for Opus |
| Router subgraph | Intent classification with Haiku | Simple graph, Opus builds in 1-2 hours |
| HubSpot MCP integration | Official server + write operations | MCP servers are plug-and-play |
| BigQuery MCP integration | Google managed server | Already auto-enabled |
| Gmail MCP integration | shinzo-labs server + OAuth setup | Needs OAuth flow — Opus helps with boilerplate |
| Deploy to Cloud Run | Docker container, Cloud SQL, basic CI/CD | Opus generates Dockerfiles and cloud configs |

**Week 3-4: Assistant Agent — Production**

| Task | Details | Claude Code helps |
|------|---------|-------------------|
| Assistant subgraph (Gemini 2.5 Pro) | Research, CRM update, email, pipeline workflows | Opus builds each workflow as a subgraph |
| RAG pipeline setup | Qdrant Cloud + Voyage AI embeddings + recursive chunking | Opus generates indexing pipeline code |
| Index sales playbooks | Process and embed your actual playbook docs | Document loader + chunker, mostly automated |
| Pipeline health scheduler | Cron job → generates digest → posts to Slack channel | Simple scheduled task |
| Email draft → Gmail | Actually create drafts in Gmail (not just display in Slack) | Gmail MCP handles this |
| Error handling + retries | Production-grade resilience | Opus excels at adding retry/fallback patterns |
| **Milestone: Assistant Agent pilot with 2-3 reps** | | |

**Week 5-6: Coach Agent — Production**

| Task | Details | Claude Code helps |
|------|---------|-------------------|
| Coach subgraph (Claude Sonnet) | Roleplay, post-call feedback, meeting prep | Most complex graph — Opus helps with state management |
| Durable execution | LangGraph checkpointer with Postgres | Critical for roleplay pause/resume |
| Multi-turn roleplay loop | Buyer persona generation, scoring, debrief | Opus builds the graph, you refine the prompts |
| Rep profile storage | Postgres table + read/write at session start/end | Standard CRUD, Opus handles quickly |
| Cohere Rerank integration | Add reranking to RAG pipeline | API integration, straightforward |
| Index call transcripts | Semantic chunking for unstructured notes | More complex chunking pipeline |
| **Milestone: Coach Agent pilot with 2-3 reps** | | |

**Week 7-8: Harden + Full Team Rollout**

| Task | Details | Claude Code helps |
|------|---------|-------------------|
| PII detection pipeline | Presidio or Google DLP on data in/out | Opus generates detection code, you configure rules |
| Access control | OAuth scoping, least privilege per MCP server | Config-heavy, Opus helps with boilerplate |
| Observability | Langfuse/LangSmith integration for traces + costs | Framework integration, well-documented |
| Manager digest | Weekly automated pipeline summary to managers | Scheduled LangGraph execution |
| Load testing | Simulate 10 concurrent users, measure latency + cost | Opus writes load test scripts |
| Prompt optimization | Refine system prompts based on pilot feedback | Iterative, human-driven with Claude assistance |
| Documentation | Internal docs for the team: how to use each command | Opus generates docs from code |
| **Milestone: Full team rollout (10 reps)** | | |

#### Post-Rollout: Month 3+ (Ongoing, ~10-15 hrs/week maintenance)

- Cross-agent coordination (Coach calls Assistant tools)
- Semantic chunking for call transcripts
- Advanced analytics from BigQuery
- Rep skill leaderboard
- Voice input (Phase 5, if requested)
- Fine-tuning evaluation (if specific behavioral gaps identified)

#### Post-Hire Cost Summary

| Category | Monthly Cost |
|----------|-------------|
| Developer salary | €3,000 |
| LLM APIs (Claude + Gemini + Haiku) | $85-245 |
| Infrastructure (Cloud Run + Postgres + Qdrant) | $87-200 |
| RAG (Voyage + Cohere Rerank) | $10-35 |
| Misc (Tavily, observability) | $0-100 |
| **Total monthly** | **~€3,200-3,600 ($3,400-3,800)** |

After the initial 8-week build, the developer shifts to maintenance + feature development (~60% capacity), freeing them to work on other projects or accelerate the feature roadmap.

---

### Full Timeline Summary

```
┌────────────────────────────────────────────────────────────────────┐
│                        COMPLETE TIMELINE                           │
│                                                                    │
│  PHASE A: POC (Izzy, vibe coding)                                 │
│  ├── Week 1: Foundation + Research Brief demo         ████░░░░░░  │
│  ├── Week 2: Coach Roleplay + Email Draft demo        ████████░░  │
│  └── Week 3: Pipeline Digest + Polish + Exec Demo     ██████████  │
│                                                                    │
│  ⏸️  Executive Approval + Hire Developer (1-3 weeks)               │
│                                                                    │
│  PHASE B: Production (Senior Dev + Claude Code + Opus)            │
│  ├── Week 1-2: Rebuild foundation + deploy to cloud   ████░░░░░░  │
│  ├── Week 3-4: Assistant Agent + RAG → pilot 2-3 reps ████████░░  │
│  ├── Week 5-6: Coach Agent + durable exec → pilot     ████████░░  │
│  └── Week 7-8: Security + polish → full team rollout  ██████████  │
│                                                                    │
│  TOTAL: POC in 3 weeks → Approval → Production in 8 weeks        │
│  TEAM USING IT: ~11-14 weeks from today                           │
└────────────────────────────────────────────────────────────────────┘
```

---

## Updated Decisions Log

| # | Question | Status | Decision |
|---|----------|--------|----------|
| 1 | Which LLM to use as the backbone? | **Recommended** | Multi-model: Claude Sonnet (Coach) + Gemini 2.5 Pro (Assistant) + Haiku (routing) |
| 2 | Agent framework choice? | **Recommended** | LangGraph (production-proven, stateful, durable, model-agnostic) |
| 3 | Hosting/infrastructure? | **Decided** | Start LangGraph Platform (managed) → migrate GCP self-hosted at scale |
| 4 | Should agents share memory/context? | **Decided** | Shared tools & rep profiles; separated conversation memory |
| 5 | Voice input support? | **Decided** | Text-only for MVP. Voice as Phase 5 add-on if needed. |
| 6 | PII/sensitive data handling? | **Decided** | 6-layer defense: minimization, access control, PII detection, LLM data policies, audit logging, encryption |
| 7 | Single or dual Slack app? | **Decided** | Single Slack app, Router handles routing, `/coach` and `/assist` commands |
| 8 | Budget/cost constraints? | **Decided** | POC: ~$32-55 total. Post-hire: ~€3,200-3,600/month (dev + infra + APIs). Senior dev @ €3,000/mo. |
| 11 | Build approach? | **Decided** | Izzy vibe-codes POC (2-3 weeks) → exec approval → hire senior FS dev (€3K/mo) on Claude Code + Opus → production in 6-8 weeks |
| 9 | Fine-tuning vs RAG? | **Decided** | Layered: Prompt Eng + RAG + Tool Use. Fine-tuning deferred 6+ months. |
| 10 | MCP adoption? | **Decided** | Yes — MCP for all tool integrations. |

---

## 6. Session Notes

### Session 1 — March 4, 2026
- Researched WeJam's Lisa (AI Sales Coach) and Pam (AI Sales Assistant)
- Defined initial vision: two Slack-based agents for Izzy's sales team
- Data sources: HubSpot, BigQuery, Internet
- Action channels: Gmail, HubSpot CRM
- Created initial architecture sketch and phased implementation plan
- **Deep dive: Fine-tuning vs RAG vs Prompt Engineering**
  - Decided on a **layered approach**: Prompt Engineering (base) → RAG (core knowledge) → Agentic Tool Use (live data) → Fine-tuning (future, only if needed)
  - RAG is the backbone — it grounds the Coach in your playbooks, deal history, and best practices without retraining
  - Fine-tuning deferred 6+ months — your data is dynamic, you're still defining the coaching model, and HubSpot themselves chose RAG for their sales AI
  - Key RAG decisions still open: vector DB choice, embedding model, chunking strategy
- **Deep dive: RAG implementation choices**
  - Analyzed 5 vector DBs (Pinecone, Weaviate, Qdrant, ChromaDB, pgvector) with pros/cons/pricing/use cases
  - Analyzed 4 embedding model families (OpenAI, Cohere, Voyage AI, Open-Source) with benchmarks and pricing
  - Analyzed 4 chunking strategies (Fixed, Recursive, Semantic, Agentic) with accuracy benchmarks
  - Analyzed retrieval methods (pure vector, keyword, hybrid) and 4 reranking options (Cohere, ColBERT, Cross-Encoder, none)
  - Mapped knowledge sources and sync strategies (playbooks, HubSpot, BigQuery, transcripts)
  - **Decisions still open:** Which vector DB, embedding model, and reranker to go with
- **Deep dive: Agent framework choices**
  - Analyzed 5 options: LangGraph, CrewAI, OpenAI Agents SDK, Anthropic Claude Agent SDK, Custom/No Framework
  - LangGraph recommended: production-proven (v1.0), graph-based state machines (ideal for Coach roleplay), durable execution (critical for Slack), model-agnostic, human-in-the-loop built in
  - CrewAI as alternative for faster prototyping with role-based collaboration
- **Deep dive: LLM provider choices**
  - Analyzed Claude, GPT-4.1, Gemini 2.5 Pro, and multi-model strategy
  - Multi-model recommended: Claude Sonnet for Coach (best tool-use 0.920, best instruction-following), Gemini 2.5 Pro for Assistant (cheapest, 1M context, native Google integration), Haiku/Flash for lightweight routing
  - Estimated LLM cost for 10-person team: ~$85-245/month
- **Deep dive: Implementation architecture — full wiring diagram**
  - Mapped the complete system: Slack Bolt → Router (Haiku) → Coach (Claude Sonnet) / Assistant (Gemini) → MCP tools
  - Detailed the Slack ↔ LangGraph connection using official `langgraph-messaging-integrations`
  - Designed Router graph (intent classification), Coach graph (roleplay with durable execution), Assistant graph (4 workflows)
  - Mapped all MCP servers: HubSpot (official beta), BigQuery (Google managed), Gmail (community), Web Search (Tavily)
  - Documented multi-model wiring in LangGraph (different LLM per node)
  - Designed RAG wiring: indexing pipeline (sources → chunker → embedder → vector DB) + query pipeline (embed → hybrid search → rerank → LLM)
  - Designed 4-layer memory architecture: conversation (per thread), rep profile (persistent), team knowledge (RAG), live data (MCP tools)
  - Laid out deployment: self-hosted on GCP (Cloud Run + Cloud SQL + Qdrant) vs. LangGraph Platform (managed)
  - Revised implementation phases into 4 concrete phases with specific deliverables per week
- **Mermaid architecture diagrams**
  - Created 12 renderable Mermaid diagrams in `architecture-diagrams.mermaid`
  - Covers: full system, Slack↔LangGraph sequence, Router/Coach/Assistant graphs, MCP wiring, RAG pipeline, memory architecture, deployment, roleplay state machine, Gantt timeline, end-to-end data flow
- **Resolved all open questions:**
  - Q3 Hosting: Start LangGraph Platform (managed) → migrate GCP self-hosted at scale
  - Q4 Shared memory: Shared tools & rep profiles; separated conversation memory per thread
  - Q5 Voice: Text-only for MVP. Voice as Phase 5 via Whisper transcription if needed
  - Q6 PII: 6-layer defense-in-depth (minimization, access control, PII detection, LLM policies, audit logs, encryption)
  - Q7 Slack app: Single app with Router handling intent. `/coach` and `/assist` commands.
  - Q8 Budget: Estimated $182-615/month running costs. Awaiting Izzy's budget + build-vs-hire decision.
- **Build strategy: Vibe-coded POC → Hire → Full Rollout**
  - Izzy confirmed: vibe-code POC personally, then hire senior FS dev @ €3,000/month
  - POC scope designed: 3-week sprint with 5 demo-able features (research brief, roleplay, email draft, pipeline digest, deal lookup)
  - Executive demo script written: 7-minute walkthrough hitting all value propositions
  - POC tech stack simplified: Claude Sonnet only (no multi-model), ChromaDB (local), Socket Mode (no server)
  - POC cost: ~$32-55 total in API calls
  - Post-hire timeline: 6-8 weeks to full team rollout (2.5-3x acceleration from Claude Code + Opus)
    - Weeks 1-2: Rebuild foundation from POC → production quality
    - Weeks 3-4: Assistant Agent + RAG pipeline → pilot with 2-3 reps
    - Weeks 5-6: Coach Agent + durable execution → pilot with 2-3 reps
    - Weeks 7-8: Security hardening + polish → full team rollout (10 reps)
  - Total timeline: POC in 3 weeks → approval → production in 8 weeks → **team using it ~11-14 weeks from today**
  - Monthly running cost post-launch: ~€3,200-3,600 (dev + infra + APIs)
- **POC Tooling Decision: Claude Code vs. Cowork (here) vs. Cursor**
  - **Claude Code is the best tool for this POC** — it runs in your terminal, has full filesystem access, can create and run Python projects, manage dependencies, and iterate fast with Opus
  - Cowork (here) can help with planning, research, brainstorming, and creating individual files — but it runs in a sandboxed VM and can't run a persistent Slack bot server or manage your local dev environment
  - The POC needs: a running Python process (Slack Bolt server), access to your local network (Socket Mode), package management (pip/uv), and iterative debugging — all of which are Claude Code's sweet spot
  - **Workflow:** Continue using Cowork for brainstorming and planning sessions. Use Claude Code for building the actual code.
- **Next:** Izzy to install Claude Code, set up Python env, start POC Week 1. Continue brainstorming sessions here.

---

*This document is the single source of truth for our brainstorming sessions. It will be updated after each session.*
