# Hive Mind Orchestration Implementation Plan

## Context

**Decision:** Full Hive Mind adoption (Option C) with all advanced features.

**Why:** Maximum long-term scalability, self-improving system through memory, typed contracts everywhere for reliability, and dynamic task decomposition for complex sales workflows.

**Goal:** Transform SalesCoach AI from static workflow routing to a dynamic, self-improving multi-agent system.

---

## Architecture Decision: SQLite vs ChromaDB

### Recommendation: **Use BOTH, for different purposes**

| System | Purpose | Why |
|--------|---------|-----|
| **SQLite** | Task graph state, execution checkpoints, memory records, structured data | ACID transactions, relational queries, fast lookups, Hive Mind proven pattern |
| **ChromaDB** | RAG (playbooks, transcripts, battlecards), semantic memory, embedding-based retrieval | Vector search, semantic similarity, existing investment |

### Detailed Breakdown

**SQLite should store:**
- TaskGraph state (tasks, dependencies, status)
- DAG execution checkpoints (fault tolerance)
- Memory records (lessons learned, user preferences, failure/success patterns)
- Artifact metadata (what was produced, by which task, timestamps)
- User session state (for long-running complex tasks)

**ChromaDB should store:**
- Sales playbooks (existing use)
- Call transcripts (existing use)
- Battlecards (existing use)
- **NEW:** Successful task artifacts (for few-shot examples)
- **NEW:** Failed task patterns (for memory injection)

### Why Not Just ChromaDB?

1. **Transactional integrity:** Task state updates need ACID guarantees
2. **Relational queries:** "Find all tasks that depend on task X" requires joins
3. **Checkpointing:** LangGraph's SQLite checkpointers are production-tested
4. **Performance:** Integer lookups vs. vector similarity for state tracking

### Why Not Just SQLite?

1. **Semantic search:** "Find similar objection handling scenarios" needs embeddings
2. **Existing investment:** RAG system already uses ChromaDB effectively
3. **Pattern matching:** Semantic similarity for memory injection

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR LAYER                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │   Triage    │  │  Architect   │  │   PM (Task Graph)   │ │
│  │  (simple/   │  │  (codebase   │  │  (decompose into    │ │
│  │   complex)  │  │   review)    │  │   executable DAG)   │ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Coach      │  │  Assistant   │  │  Specialist         │ │
│  │  Agent      │  │  Agent       │  │  Agents             │ │
│  │             │  │              │  │  - Research         │ │
│  │  - roleplay │  │  - research  │  │  - Email            │ │
│  │  - feedback │  │  - deal      │  │  - CRM              │ │
│  │  - prep     │  │  - email     │  │  - RAG              │ │
│  │             │  │  - pipeline  │  │  - Web Search       │ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     QUALITY LAYER                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────┐ │
│  │  Reviewer   │  │  Test        │  │  Memory             │ │
│  │  (output    │  │  (validation │  │  (lessons learned,  │ │
│  │   quality)  │  │   checks)    │  │   context injection)│ │
│  └─────────────┘  └──────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Core Infrastructure)

**Goal:** Establish the Hive Mind backbone while keeping existing functionality working.

#### 1.1 Typed Contracts System
**File:** `graphs/contracts.py` (NEW)

Define all typed contracts:
- `TaskInput`, `TaskOutput`
- Artifact types: `ResearchBrief`, `DealStatus`, `EmailDraft`, `PipelineDigest`, `RoleplayDebrief`, `MeetingPrepBrief`
- `AgentState` extensions for typed state

#### 1.2 Triage Graph (Replaces Router)
**File:** `graphs/triage.py` (NEW — replaces `graphs/router.py`)

Three-way classification:
- **DIRECT:** Single tool call (e.g., "Show pipeline") → `DirectExecutor`
- **WORKFLOW:** Single workflow (e.g., "Roleplay discovery call") → Coach/Assistant subgraphs
- **COMPLEX:** Multi-step task (e.g., "Prepare for QBR") → PM Agent

#### 1.3 Memory System Foundation
**File:** `graphs/memory_agent.py` (NEW)

SQLite-backed memory:
- `user_preferences` table
- `project_lessons` table
- `execution_failures` table
- `successful_patterns` table

#### 1.4 Direct Executor
**File:** `tools/executor.py` (NEW)

Execute single tool calls for DIRECT path with typed output.

---

### Phase 2: Complex Task Execution

**Goal:** Enable dynamic task decomposition and parallel execution.

#### 2.1 PM Agent
**File:** `graphs/pm_agent.py` (NEW)

Task graph creation:
- Parse natural language request
- Identify required data sources
- Build dependency graph
- Assign roles to tasks

#### 2.2 DAG Executor
**File:** `graphs/dag_executor.py` (NEW)

LangGraph StateGraph with:
- Parallel batch execution
- SQLite checkpointing (fault tolerance)
- Artifact passing between tasks
- Dynamic task injection (new messages update live DAG)

#### 2.3 Concurrency Model
**File:** `graphs/concurrency.py` (NEW)

- Per-project write lock (prevent concurrent file modifications)
- Reader/writer separation (readers run parallel, writers serialized)
- Cross-project parallelism

---

### Phase 3: Quality & Self-Improvement

**Goal:** Add output validation and memory-driven improvement.

#### 3.1 Reviewer Agent
**File:** `graphs/reviewer_agent.py` (NEW)

Output validation:
- Completeness checks (all data sources included?)
- Accuracy checks (numbers match source?)
- Format checks (Slack Block Kit valid?)
- **Read-only critique** (ACC-Collab pattern — doesn't modify, only reports issues)

#### 3.2 Memory Injection
**File:** `graphs/memory_injection.py` (NEW)

Before agent execution:
- Query relevant lessons ("What failed last time for QBR prep?")
- Inject into agent prompts
- Track user preferences ("User prefers MEDDIC scoring")

#### 3.3 Memory Extraction
**File:** `graphs/memory_extraction.py` (NEW)

After agent execution:
- Extract lessons learned
- Record successful patterns
- Log failures with root cause

---

### Phase 4: Integration & Migration

**Goal:** Wire everything together and migrate existing code.

#### 4.1 App.py Integration
**File:** `app.py` (MODIFY)

- Replace `router_graph` with `triage_graph`
- Update command handlers to use typed contracts
- Add HiveMindOrchestrator wrapper

#### 4.2 Coach Subgraph Migration
**File:** `graphs/coach.py` (MODIFY)

- Update nodes to accept `TaskInput`, return `TaskOutput`
- Use typed artifacts instead of unstructured dicts

#### 4.3 Assistant Subgraph Migration
**File:** `graphs/assistant.py` (MODIFY)

- Update nodes to accept `TaskInput`, return `TaskOutput`
- Use typed artifacts instead of unstructured dicts

#### 4.4 Architect Agent (Optional Enhancement)
**File:** `graphs/architect_agent.py` (NEW)

Pre-execution codebase/data review:
- "What data sources exist for this task?"
- "What RAG collections are relevant?"
- Produces `ArchitectureBrief` for PM Agent

---

## File Summary

### New Files

| File | Purpose |
|------|---------|
| `graphs/contracts.py` | Typed contracts (TaskInput, TaskOutput, Artifacts) |
| `graphs/triage.py` | Three-way classification (replaces router.py) |
| `graphs/memory_agent.py` | Memory storage and retrieval (SQLite) |
| `graphs/memory_injection.py` | Inject lessons into prompts |
| `graphs/memory_extraction.py` | Extract lessons from executions |
| `graphs/pm_agent.py` | Task graph creation |
| `graphs/dag_executor.py` | DAG execution with checkpointing |
| `graphs/concurrency.py` | Writer/reader locks, per-project serialization |
| `graphs/reviewer_agent.py` | Output validation |
| `graphs/architect_agent.py` | Pre-execution data source review |
| `tools/executor.py` | Direct tool execution for DIRECT path |

### Modified Files

| File | Changes |
|------|---------|
| `app.py` | Use triage_graph, add HiveMindOrchestrator, typed contracts |
| `graphs/coach.py` | Migrate nodes to typed contracts |
| `graphs/assistant.py` | Migrate nodes to typed contracts |
| `db.py` | Add memory tables (user_preferences, project_lessons, etc.) |

### Deleted Files

| File | Reason |
|------|--------|
| `graphs/router.py` | Replaced by triage.py |

---

## Verification Strategy

### Unit Tests (Manual — No Formal Suite)

1. **Triage Classification:**
   - "Show pipeline" → DIRECT
   - "Roleplay discovery call" → WORKFLOW
   - "Prepare for QBR" → COMPLEX

2. **DAG Execution:**
   - Create task graph with parallel + sequential tasks
   - Verify artifacts pass correctly between dependent tasks
   - Kill process mid-execution, restart, verify checkpoint recovery

3. **Memory System:**
   - Execute task, verify lesson extracted
   - Execute similar task, verify lesson injected into prompt
   - Change user preference, verify it persists across sessions

4. **Reviewer:**
   - Generate output with missing data, verify reviewer catches it
   - Generate valid output, verify reviewer approves

### End-to-End Test (Slack)

```
# Simple lookup (DIRECT)
/pipeline

# Single workflow (WORKFLOW)
/coach roleplay discovery call with VP Engineering

# Complex task (COMPLEX)
"Prepare for my QBR meeting next week with Acme Corp"
# Expected: PM creates task graph, DAG executes in parallel batches,
# Reviewer validates, Memory extracts lessons
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Typed contracts break existing flows | Run parallel during migration, compare outputs |
| DAG execution gets stuck | SQLite checkpointing + timeout + auto-retry |
| Memory injection slows execution | Cache recent lessons, inject only high-confidence patterns |
| Reviewer blocks valid outputs | Reviewer is advisory initially, escalate only on clear errors |
| Triage misclassifies complex tasks | Log all classifications, review weekly, refine prompt |

---

## References

### Existing Patterns to Reuse

| Existing File | Pattern to Reuse |
|---------------|------------------|
| `graphs/router.py` | Conditional edge routing pattern |
| `graphs/coach.py` | State management with TypedDict |
| `graphs/assistant.py` | Conditional tool loading (MCP vs mock) |
| `tools/rag.py` | ChromaDB interaction pattern |
| `db.py` | SQLite table creation, CRUD operations |
| `mcp_setup.py` | MCP tool discovery and binding |

### Hive Mind Reference Patterns

| Hive Mind File | Pattern |
|----------------|---------|
| `orchestrator.py` | `_triage_is_simple()` logic |
| `pm_agent.py` | `create_task_graph()` with typed TaskGraph |
| `dag_executor_langgraph.py` | `select_batch → execute_batch → post_batch` loop |
| `memory_agent.py` | `update_project_memory()` with lesson extraction |
