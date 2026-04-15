# Hierarchical Multi-Agent Architecture Design

**Date:** 2026-04-15
**Status:** Draft
**Author:** Claude (with Izzy)
**Reviewers:** TBD

---

## Executive Summary

This document specifies the rearchitecture of SalesCoach AI from a Triage-based workflow system to a **Hierarchical Multi-Agent Architecture** with a Centralized Orchestrator (Manager) coordinating specialist agents. The design supports:

- **Long-running workflows** (minutes to hours) with async execution and SQLite checkpointing
- **Parallel fan-out** delegation to multiple specialists simultaneously
- **Universal quality gate** — all specialist output passes through Reviewer Agent
- **Code-first specialist registry** with declarative registration and type-safe interfaces
- **Structured progress reporting** with step tracking (N of M)

The architecture evolves from the current Triage → Coach/Assistant → DAG → Reviewer flow, providing a clear migration path while enabling future extensibility.

---

## 1. Current State Analysis

### 1.1 Existing Architecture

```
Slack Command → app.py → Triage Graph
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
    DIRECT              WORKFLOW               COMPLEX
    (DirectExecutor)    (Coach/Assistant)      (PM Agent → DAG Executor)
                                                 ↓
                                            Reviewer Agent
                                                 ↓
                                            Slack Response
```

**Key components:**
- `graphs/triage.py` — Three-way classification (DIRECT/WORKFLOW/COMPLEX)
- `graphs/coach_typed.py` — Roleplay, feedback, meeting prep (typed)
- `graphs/assistant_typed.py` — Research, deal lookup, email draft (typed)
- `graphs/pm_agent.py` — Task decomposition into DAGs
- `graphs/dag_executor.py` — Parallel batch execution with SQLite checkpoints
- `graphs/reviewer_agent.py` — Output validation
- `graphs/contracts.py` — Typed contracts (TaskInput, TaskOutput, Artifact types)

### 1.2 Technical Debt

| Issue | Impact | Resolution in New Architecture |
|-------|--------|-------------------------------|
| `app.py` (~7500 lines) | Hard to maintain, mixes concerns | Split into `handlers/`, `orchestration/`, `formatters/` |
| Duplicate graphs (typed + untyped) | Confusion, maintenance burden | Remove untyped versions |
| Inconsistent state management | Bugs, unclear contracts | Unified `TaskEnvelope` pattern |
| Hardcoded paths | Deployment friction | Environment-based configuration |
| No specialist discovery | Manual wiring, fragile imports | Declarative registry |
| Silent failures | Lost context, hard debugging | Structured error handling |

---

## 2. Target Architecture

### 2.1 Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                     │
│  Slack Commands │ Web API │ Webhooks │ Scheduled Triggers                │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      MANAGER AGENT (Orchestrator)                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  1. Intent Classification  →  2. Specialist Selection              │  │
│  │  3. Task Dispatch (async)  →  4. Progress Tracking                 │  │
│  │  5. Result Aggregation     →  6. Reviewer Gate                     │  │
│  │  7. Response Formatting    →  8. Delivery                          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ↓                           ↓                           ↓
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│   COACH      │           │  ASSISTANT   │           │   RESEARCH   │
│  Specialist  │           │  Specialist  │           │  Specialist  │
│  - roleplay  │           │  - lookup    │           │  - web       │
│  - feedback  │           │  - email     │           │  - rag       │
│  - prep      │           │  - pipeline  │           │  - analysis  │
└──────────────┘           └──────────────┘           └──────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      REVIEWER AGENT (Quality Gate)                       │
│  Validates: Completeness │ Accuracy │ Format │ Quality Score            │
│  Decision: approved │ changes_required │ blocked                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      SHARED SERVICES LAYER                               │
│  SQLite Checkpoints │ Progress Tracker │ Error Handler │ Logger         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Architectural Principles

1. **Centralized Orchestration** — Manager owns all client communication and task coordination
2. **Specialist Isolation** — Each specialist has a single responsibility, well-defined interface, and no direct client access
3. **Async Execution** — All specialist tasks run asynchronously with crash-safe checkpoints
4. **Universal Review** — No output reaches the client without Reviewer validation
5. **Type-Safe Contracts** — All communication uses typed envelopes with validated schemas
6. **Observable by Default** — Progress, errors, and lifecycle events are logged and queryable

---

## 3. Component Specifications

### 3.1 Manager Agent

**Location:** `graphs/manager.py`

**Responsibilities:**
1. Receive incoming requests (Slack, API, webhooks, scheduled)
2. Classify intent and determine required capabilities
3. Query Specialist Registry for matching specialists
4. Dispatch tasks asynchronously (single or parallel fan-out)
5. Track progress via callbacks and checkpoints
6. Aggregate results from multiple specialists
7. Route aggregated output to Reviewer Agent
8. Format and deliver response to client

**Key Interfaces:**

```python
class ManagerAgent:
    async def handle_request(self, request: ClientRequest) -> ClientResponse:
        """Main entry point for all requests."""

    def classify_intent(self, content: str) -> IntentClassification:
        """Analyze request content to determine required capabilities."""

    def select_specialists(self, intent: IntentClassification) -> list[SpecialistDescriptor]:
        """Query registry for specialists that can handle this intent."""

    async def dispatch_task(self, envelope: TaskEnvelope) -> TaskEnvelope:
        """Dispatch task to specialist, track progress, handle retries."""

    async def aggregate_results(self, envelopes: list[TaskEnvelope]) -> AggregatedResult:
        """Combine results from multiple specialists into unified output."""
```

**State Management:**
- Request state tracked via `parent_request_id`
- Checkpoints persisted to `task_checkpoints` table
- In-flight requests tracked in memory (with SQLite backup)

**Concurrency Configuration:**

```python
@dataclass
class SpecialistDescriptor:
    # ... existing fields ...

    # Concurrency controls
    max_concurrent: int = 5  # Max simultaneous invocations
    queue_size: int = 100    # Pending task buffer
    priority: int = 0        # Higher = more urgent (for queue ordering)
```

**Queue Behavior:**

When `max_concurrent` is reached:
1. Task is queued (up to `queue_size`)
2. When queue is full, reject with `429 Too Many Requests` and `Retry-After` header
3. Priority ordering: higher priority tasks jump ahead in queue

```python
class TaskQueue:
    def __init__(self, max_concurrent: int, queue_size: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue = asyncio.PriorityQueue(maxsize=queue_size)

    async def enqueue(self, envelope: TaskEnvelope, priority: int) -> bool:
        """Returns False if queue is full."""
        try:
            self.queue.put_nowait((-priority, envelope))  # Negative for max-heap
            return True
        except asyncio.QueueFull:
            return False

    async def acquire(self) -> bool:
        """Wait for capacity. Returns True when acquired."""
        await self.semaphore.acquire()
        return True

    def release(self):
        self.semaphore.release()
```

### 3.2 Specialist Registry

**Location:** `specialists/registry.py`

**Purpose:** Declarative registration and discovery of specialist agents.

**Data Structures:**

```python
@dataclass
class RetryPolicy:
    max_retries: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    exponential_backoff: bool = True
    retry_on: list[str] = field(default_factory=lambda: ["timeout", "rate_limit"])

@dataclass
class SpecialistDescriptor:
    # Core identity
    name: str
    capabilities: list[str]
    handler: Callable
    input_schema: Type
    output_schema: Type

    # Execution config
    timeout_minutes: int = 30
    supports_parallel: bool = True
    cost_tier: str = "standard"

    # Versioning
    version: str = "1.0.0"

    # Tags for filtering
    tags: list[str] = field(default_factory=lambda: [])

    # Retry policy
    retry_policy: Optional[RetryPolicy] = field(default_factory=RetryPolicy)

# Global registry
SPECIALISTS: dict[str, SpecialistDescriptor] = {}
```

**Decorator API:**

```python
def register_specialist(
    name: str,
    capabilities: list[str],
    input_schema: Type,
    output_schema: Type,
    timeout_minutes: int = 30,
    supports_parallel: bool = True,
    cost_tier: str = "standard",
    version: str = "1.0.0",
    tags: list[str] = None,
    retry_policy: Optional[RetryPolicy] = None
) -> Callable:
    """Register a specialist agent in the global registry."""
```

**Query API:**

```python
def find_specialist(capability: str, **filters) -> Optional[SpecialistDescriptor]:
    """Find first specialist matching capability and filters."""

def find_specialists(capability: str = None, tags_include: list[str] = None,
                     cost_tier__in: list[str] = None) -> list[SpecialistDescriptor]:
    """Find all specialists matching criteria."""

def get_specialist_by_name(name: str) -> Optional[SpecialistDescriptor]:
    """Get specialist by exact name."""
```

### 3.3 Task Envelope

**Location:** `core/envelope.py`

**Purpose:** Typed message envelope for all Manager↔Specialist communication.

```python
class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

@dataclass
class ProgressState:
    percent: int  # 0-100
    message: str
    current_step: Optional[int] = None  # e.g., 3
    total_steps: Optional[int] = None    # e.g., 7
    step_label: Optional[str] = None     # e.g., "Competitive analysis"

@dataclass
class TaskEnvelope:
    # Identity
    task_id: UUID
    specialist_name: str
    parent_request_id: UUID  # For tracing

    # Payload
    input_data: Any  # Validated against specialist.input_schema

    # Lifecycle
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Result or error
    output_data: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0

    # Progress tracking
    progress: Optional[ProgressState] = None
```

### 3.4 Error Handling

**Location:** `core/errors.py`

**Error Hierarchy:**

```python
class SpecialistError(Exception):
    """Base exception for all specialist errors."""

class TransientError(SpecialistError):
    """Retryable errors: timeout, rate_limit, temporary_unavailable."""
    def __init__(self, message: str, retry_after_ms: int = None):
        self.retry_after_ms = retry_after_ms

class ValidationError(SpecialistError):
    """Input validation failed — don't retry."""
    def __init__(self, message: str, field: str = None):
        self.field = field

class SystemError(SpecialistError):
    """Critical — escalate to Manager immediately."""
```

**Error Handling Strategy:**

| Error Type | Examples | Behavior |
|------------|----------|----------|
| Transient | timeout, rate_limit, temporary_unavailable | Retry with exponential backoff per retry_policy |
| Validation | invalid_input, schema_mismatch, missing_required_field | Return error to Manager — no retry |
| System | database_corruption, authentication_failure, out_of_memory | Escalate immediately — may require intervention |

### 3.5 Progress Reporting

**Location:** `core/progress.py`

**Callback Pattern (Async-Safe):**

```python
class ProgressCallback(Protocol):
    async def __call__(self, progress: ProgressState) -> None:
        """Report progress update. Thread-safe; persists to SQLite."""

# Specialist signature
SpecialistHandler = Callable[
    [Any, Optional[ProgressCallback]],  # input_data, progress_cb
    Any  # output_data
]
```

**Thread-Safe Implementation:**

```python
class ProgressTracker:
    def __init__(self, envelope: TaskEnvelope):
        self.envelope = envelope
        self._lock = asyncio.Lock()

    async def __call__(self, progress: ProgressState):
        """Async-safe progress reporting with SQLite persistence."""
        async with self._lock:
            self.envelope.progress = progress
            await save_checkpoint(self.envelope)
            logger.debug(f"Progress: {progress.percent}% - {progress.message}")
```
```

**Usage Example:**

```python
@register_specialist(
    name="research",
    capabilities=["web_search", "company_research", "competitor_analysis"],
    input_schema=ResearchInput,
    output_schema=ResearchOutput,
)
def research_agent(input: ResearchInput, progress: ProgressCallback = None) -> ResearchOutput:
    progress(ProgressState(
        percent=10,
        message="Starting research...",
        current_step=1,
        total_steps=5,
        step_label="Searching knowledge base"
    ))

    # ... RAG search ...

    progress(ProgressState(
        percent=50,
        message="Analyzing competitors...",
        current_step=3,
        total_steps=5,
        step_label="Competitive analysis"
    ))

    # ... web search ...

    progress(ProgressState(
        percent=100,
        message="Research complete",
        current_step=5,
        total_steps=5,
        step_label="Finalizing report"
    ))

    return ResearchOutput(...)
```

### 3.6 Reviewer Agent

**Location:** `graphs/reviewer_agent.py` (existing, enhanced)

**Purpose:** Quality gate for all specialist output.

**Validation Criteria:**
1. **Completeness** — Does the output address all parts of the request?
2. **Accuracy** — Are facts correct and properly sourced?
3. **Format** — Does the output match the expected schema?
4. **Quality Score** — Overall quality rating (0-100)

**Decision Types:**
- `approved` — Output is ready for client delivery
- `changes_required` — Output needs revision (include specific feedback)
- `blocked` — Critical issues prevent delivery (escalate to human)

**Enhanced Interface:**

```python
@dataclass
class ReviewResult:
    decision: Literal["approved", "changes_required", "blocked"]
    quality_score: int  # 0-100
    feedback: Optional[str] = None  # For changes_required
    blocked_reason: Optional[str] = None  # For blocked
    max_revisions: int = 2  # Allow 2 revision attempts before escalation
    revision_context: Optional[dict] = None  # Prior output, feedback history

async def reviewer_node(state: dict) -> dict:
    """Review specialist output and return ReviewResult."""
```

---

### 3.7 Specialist Invocation Protocol

**Location:** `core/invoker.py`

**Purpose:** Define how Manager invokes specialist handlers with async execution, progress injection, and timeout enforcement.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from .envelope import TaskEnvelope, TaskStatus, ProgressState
from .errors import TransientError, ValidationError, SystemError
from .progress import ProgressCallback
from db import save_checkpoint, load_checkpoint

# Thread pool for blocking operations (LangGraph graphs)
_executor = ThreadPoolExecutor(max_workers=10)

async def invoke_specialist(
    descriptor: SpecialistDescriptor,
    envelope: TaskEnvelope,
    progress_cb: ProgressCallback
) -> TaskEnvelope:
    """
    Wraps specialist handler invocation with:
    - Async execution (thread pool for blocking, asyncio for I/O)
    - Progress callback injection
    - Timeout enforcement
    - Checkpoint persistence
    - Retry logic per retry_policy
    """
    envelope.status = TaskStatus.RUNNING
    envelope.started_at = datetime.now()
    await save_checkpoint(envelope)

    try:
        # Enforce timeout
        async with asyncio.timeout(descriptor.timeout_minutes * 60):
            # Wrap progress callback with persistence
            async def persisting_progress(state: ProgressState):
                envelope.progress = state
                await save_checkpoint(envelope)
                progress_cb(state)

            # Invoke handler (blocking → thread pool)
            loop = asyncio.get_event_loop()
            if asyncio.iscoroutinefunction(descriptor.handler):
                output = await descriptor.handler(envelope.input_data, persisting_progress)
            else:
                output = await loop.run_in_executor(
                    _executor,
                    lambda: descriptor.handler(envelope.input_data, persisting_progress)
                )

        envelope.status = TaskStatus.COMPLETED
        envelope.output_data = output
        envelope.completed_at = datetime.now()

    except asyncio.TimeoutError as e:
        envelope.status = TaskStatus.FAILED
        envelope.error = f"Timeout after {descriptor.timeout_minutes}m"
        if envelope.retry_count < descriptor.retry_policy.max_retries:
            envelope.status = TaskStatus.RETRYING
            # Schedule retry with backoff...

    except ValidationError as e:
        envelope.status = TaskStatus.FAILED
        envelope.error = f"Validation: {e.message}"
        # Don't retry validation errors

    except TransientError as e:
        envelope.status = TaskStatus.RETRYING
        envelope.error = str(e)
        envelope.retry_count += 1
        # Apply exponential backoff...

    except Exception as e:
        envelope.status = TaskStatus.FAILED
        envelope.error = f"System: {str(e)}"
        # Escalate to Manager

    await save_checkpoint(envelope)
    return envelope
```

**Handler Signature:**

All specialists must conform to:

```python
def specialist_handler(input_data: Any, progress: ProgressCallback) -> Any:
    """
    Args:
        input_data: Validated against specialist.input_schema
        progress: Async-safe callback to report progress

    Returns:
        Output validated against specialist.output_schema

    Raises:
        ValidationError: For input/data issues (no retry)
        TransientError: For temporary failures (retry)
        SystemError: For critical failures (escalate)
    """
```

---

### 3.8 AggregatedResult Schema

**Location:** `core/envelope.py`

**Purpose:** Define result structure for parallel fan-out aggregation.

```python
@dataclass
class AggregatedResult:
    request_id: UUID
    component_results: dict[str, Any]  # keyed by specialist_name
    success_count: int
    failure_count: int
    aggregated_content: str  # LLM-synthesized or concatenated
    confidence_score: float  # 0-1, based on agreement/failure rate
    warnings: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
```

**Aggregation Strategies:**

| Strategy | Use Case | Implementation |
|----------|----------|----------------|
| **Concatenation** | Independent results (research + email) | Join outputs with section headers |
| **Synthesis** | Overlapping results (multiple research sources) | LLM summarizes and deduplicates |
| **Voting** | Same capability, multiple specialists | Majority wins, include dissenting views |
| **Pipeline** | Sequential dependency (research → email) | Chain outputs: A → B → final |

---

### 3.9 Cost Attribution

**Location:** `core/cost.py`

**Purpose:** Track LLM token usage per task for cost attribution and routing decisions.

```python
@dataclass
class CostRecord:
    task_id: UUID
    specialist_name: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float  # Calculated from model pricing
    timestamp: datetime

# cost_tier usage in routing:
# - "fast" → Use cheaper/faster models (qwen3.5:397b-cloud via Ollama)
# - "standard" → Default model
# - "expensive" → Premium models (o3, high-reasoning) for complex tasks

COST_TIERS = {
    "fast": {"model": "qwen3.5:397b-cloud", "max_tokens": 2000},
    "standard": {"model": "claude-sonnet-4-6", "max_tokens": 4000},
    "expensive": {"model": "claude-opus-4-6", "max_tokens": 8000},
}
```

---

### 3.10 Specialist Discovery

**Location:** `specialists/__init__.py`

**Purpose:** Define how specialist modules are discovered and imported at startup.

**Explicit Import (Recommended for MVP):**

```python
# specialists/__init__.py
from . import coach, assistant, research  # Explicit imports trigger decorators

# This ensures @register_specialist decorators run at import time
# SIMPLE, EXPLICIT, NO MAGIC
```

**Automatic Discovery (Future):**

```python
import pkgutil

def load_all_specialists():
    """Auto-discover and import all specialist modules."""
    for importer, modname, ispkg in pkgutil.iter_modules(__path__):
        if modname != 'registry':  # Don't import registry itself
            __import__(f"specialists.{modname}")
    return SPECIALISTS  # All decorators have run
```

**Startup Sequence:**

```python
# app.py or main.py
from specialists import load_all_specialists

def startup():
    # 1. Load all specialists into registry
    specialists = load_all_specialists()
    logger.info(f"Loaded {len(specialists)} specialists: {list(specialists.keys())}")

    # 2. Initialize Manager with registry
    manager = ManagerAgent(registry=specialists)

    # 3. Run recovery for orphaned tasks
    asyncio.run(recover_orphaned_tasks(manager))
```

---

### 3.11 Migration Rollback Criteria

**Location:** Section 5.4 (Phase 4: Cutover)

**Rollback Triggers:**

Automatic rollback is triggered if ANY of these conditions persist for 15 minutes:

| Metric | Threshold | Action |
|--------|-----------|--------|
| Error rate | > 5% | Flip feature flag to Triage |
| p99 latency | > 2x baseline | Flip feature flag to Triage |
| Reviewer rejection rate | > 40% | Investigate quality regression |
| Checkpoint recovery rate | > 10% of tasks | Investigate crash loop |

**Rollback Procedure:**

```python
async def rollback_to_triage():
    """Graceful rollback from Manager to Triage flow."""
    logger.warning("Initiating rollback to Triage flow")

    # 1. Stop accepting new Manager requests
    MANAGER_ENABLED = False  # Feature flag

    # 2. Drain in-flight Manager tasks
    in_flight = await get_in_flight_tasks()
    logger.info(f"Draining {len(in_flight)} in-flight tasks")

    for task in in_flight:
        # Wait for completion or timeout (5 minutes max)
        try:
            await asyncio.wait_for(task.complete(), timeout=300)
        except asyncio.TimeoutError:
            logger.error(f"Task {task.task_id} timed out during rollback")
            task.status = TaskStatus.CANCELLED
            await save_checkpoint(task)

    # 3. Preserve checkpoints for audit
    logger.info("Checkpoints preserved in task_checkpoints table")

    # 4. Route new requests to Triage
    logger.info("New requests routing to Triage flow")

    # 5. Notify ops team
    await slack_notify("#ops-alerts", "Rolled back to Triage flow. Investigating.")
```

**Canary Deployment (Preferred):**

Instead of big-bang cutover, use gradual rollout:

| Stage | Traffic % | Duration | Success Criteria |
|-------|-----------|----------|------------------|
| 1 | 5% | 1 hour | Error rate < 5% |
| 2 | 25% | 4 hours | p99 latency < 2x baseline |
| 3 | 50% | 8 hours | Reviewer approval > 80% |
| 4 | 100% | Ongoing | All metrics stable |

```python
# Canary routing
CANARY_PERCENTAGE = 5  # Gradually increase

def should_use_canary() -> bool:
    return random.randint(1, 100) <= CANARY_PERCENTAGE
```

```
┌─────────────────────────────────────────────────────────────────┐
│                    Revision Loop Flow                            │
└─────────────────────────────────────────────────────────────────┘

Specialist Output
       ↓
Reviewer Node → decision = "changes_required"
       ↓
Manager receives ReviewResult with feedback
       ↓
Manager checks: revision_count < max_revisions?
       ↓ YES
Create revision TaskEnvelope with:
  - original_input_data
  - prior_output_data (in revision_context)
  - reviewer_feedback
  - revision_count = prior + 1
       ↓
Dispatch to SAME specialist (knows its own output)
       ↓
Specialist sees revision context and revises output
       ↓
Back to Reviewer Node
       ↓
┌─────────────────────────────────────────────────────────────────┐
│ If decision = "changes_required" after max_revisions:           │
│   → Escalate to human with feedback chain                       │
└─────────────────────────────────────────────────────────────────┘
```

**Revision Envelope Schema:**

```python
@dataclass
class RevisionContext:
    prior_output: Any  # What the specialist produced before
    reviewer_feedback: str  # What needs to change
    revision_number: int  # Which attempt this is
    feedback_history: list[str]  # All prior feedback (for context)

# Manager passes this in input_data for revision tasks
input_data = {
    **original_request,
    "_revision": RevisionContext(...)
}
```

**Specialist Revision Handling:**

```python
@register_specialist(...)
def coach_agent(input: CoachInput, progress: ProgressCallback) -> CoachOutput:
    if input._revision:
        # Revision mode — see prior output and feedback
        prior = input._revision.prior_output
        feedback = input._revision.reviewer_feedback
        # Revise output based on feedback...
    else:
        # Fresh invocation
        ...
```

---

## 4. Data Flow

### 4.1 Request Lifecycle

```
1. Client Request (Slack/API)
   ↓
2. Manager receives → creates ClientRequest with unique request_id
   ↓
3. Intent Classification (LLM-based)
   ↓
4. Specialist Selection (query registry by capability)
   ↓
5. Task Dispatch (create TaskEnvelope, persist checkpoint, fire async)
   ↓
6. Specialist Execution (with progress callbacks)
   ↓
7. Progress Checkpoints (persisted to SQLite)
   ↓
8. Result Aggregation (if parallel fan-out)
   ↓
9. Reviewer Gate (validate output)
   ↓
10a. Approved → Format → Client Response
10b. Changes Required → Specialist Revision → Re-review
10c. Blocked → Escalate → Human Intervention
```

### 4.2 Checkpoint Schema

```sql
-- Table: task_checkpoints
CREATE TABLE task_checkpoints (
    task_id TEXT PRIMARY KEY,
    specialist_name TEXT NOT NULL,
    parent_request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data TEXT NOT NULL,         -- JSON
    output_data TEXT,                 -- JSON
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    progress_percent INTEGER DEFAULT 0,
    progress_message TEXT,
    progress_current_step INTEGER,
    progress_total_steps INTEGER,
    progress_step_label TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    checkpoint_at TEXT DEFAULT (datetime('now'))
);

-- Index for querying by request
CREATE INDEX idx_parent_request ON task_checkpoints(parent_request_id);

-- Index for querying in-flight tasks
CREATE INDEX idx_status ON task_checkpoints(status) WHERE status IN ('pending', 'running', 'retrying');
```

---

### 4.3 Checkpoint Recovery

**Location:** `core/recovery.py`

**Purpose:** Define crash recovery logic for in-flight tasks after process restart.

**Recovery Trigger:** Manager startup.

**Recovery Query:**

```sql
SELECT * FROM task_checkpoints
WHERE status IN ('running', 'retrying')
  AND checkpoint_at < datetime('now', '-5 minutes')  -- Grace period for in-progress
ORDER BY checkpoint_at ASC;  -- Oldest first (most likely orphaned)
```

**Recovery Strategy:**

```python
async def recover_orphaned_tasks(manager: ManagerAgent):
    """Called on Manager startup to recover orphaned tasks."""
    orphaned = await db.query_orphaned_tasks()

    for task in orphaned:
        envelope = deserialize_envelope(task)

        # Determine recovery action
        if envelope.status == TaskStatus.RUNNING:
            # Was mid-execution — retry from checkpoint
            envelope.status = TaskStatus.RETRYING
            envelope.retry_count += 1
            logger.info(f"Recovering orphaned task {task.task_id}")
            await manager.dispatch_task(envelope)

        elif envelope.status == TaskStatus.RETRYING:
            # Was mid-backoff — resume retry
            await manager.dispatch_task(envelope)

        else:
            # Should not happen — log and mark failed
            logger.error(f"Unknown orphaned state: {envelope}")
            envelope.status = TaskStatus.FAILED
            envelope.error = "Orphaned during recovery"
            await save_checkpoint(envelope)
```

**Idempotency Guarantee:**

Specialist handlers MUST be idempotent:

```python
# Before executing, check if output already exists
existing = await load_checkpoint(envelope.task_id)
if existing and existing.output_data:
    logger.info(f"Task {envelope.task_id} already completed — skipping")
    return existing
```

**Lease Mechanism (Future):**

For high-concurrency deployments, add `claimed_by` and `lease_expires_at`:

```sql
ALTER TABLE task_checkpoints ADD COLUMN claimed_by TEXT;
ALTER TABLE task_checkpoints ADD COLUMN lease_expires_at TEXT;

-- Worker claims task before processing
UPDATE task_checkpoints
SET claimed_by = :worker_id, lease_expires_at = datetime('now', '+5 minutes')
WHERE task_id = :task_id AND (claimed_by IS NULL OR lease_expires_at < datetime('now'));
```

---

### 4.4 Intent Classification

**Location:** `prompts/intent_classification.py`

**Purpose:** LLM-based intent classification to determine required capabilities.

**Prompt Template:**

```python
INTENT_CLASSIFICATION_PROMPT = """
You are an intent classifier for a sales coaching AI system.

Given a user request, classify the required capabilities from this list:
{capabilities}

Capabilities and their meanings:
- roleplay: Simulate buyer conversations (discovery, demo, negotiation)
- feedback: Analyze call transcripts and provide coaching
- meeting_prep: Research and prepare for upcoming meetings
- lookup: Find deals, contacts, companies in CRM
- email: Draft or analyze email communications
- pipeline: Summarize pipeline health and forecasts
- research: Web-based company/competitor research
- web_search: General web information retrieval

Request: "{user_input}"

Respond with JSON:
{{
    "primary_capability": "capability_name",
    "secondary_capabilities": ["optional", "additional"],
    "confidence": 0.95,
    "requires_parallel": false
}}

If no capability matches, set primary_capability to "unknown".
"""
```

**Fallback Chain:**

```python
async def classify_intent(content: str) -> IntentClassification:
    # Try LLM classification
    result = await llm_classify(content)

    if result.primary_capability == "unknown":
        # Fallback: keyword matching
        result = keyword_classify(content)

    if result.primary_capability == "unknown":
        # Fallback: return error to user
        raise NoMatchingSpecialist(
            "I'm not sure which specialist can help with this request. "
            "Please try rephrasing or contact an admin."
        )

    # Cache result for repeated requests (TTL: 5 minutes)
    await cache.set(f"intent:{hash(content)}", result, ttl=300)

    return result
```

**Keyword Fallback Rules:**

```python
KEYWORD_RULES = {
    "roleplay": ["roleplay", "practice", "simulate", "pretend"],
    "feedback": ["feedback", "review", "analyze", "score", "grade"],
    "meeting_prep": ["meeting", "prep", "prepare", "brief"],
    "lookup": ["find", "show", "get", "lookup", "search"],
    "email": ["email", "draft", "write", "compose"],
    "pipeline": ["pipeline", "forecast", "deals", "health"],
    "research": ["research", "company", "competitor", "market"],
}
```

---

## 5. Migration Plan

### 5.1 Phase 1: Foundation (Week 1-2)

- [ ] Create `core/` package with `envelope.py`, `errors.py`, `progress.py`
- [ ] Create `specialists/registry.py` with decorator API
- [ ] Create `graphs/manager.py` skeleton
- [ ] Write tests for core components

### 5.2 Phase 2: Specialist Migration (Week 3-4)

- [ ] Migrate `coach_typed.py` → `specialists/coach.py` with `@register_specialist`
- [ ] Migrate `assistant_typed.py` → `specialists/assistant.py`
- [ ] Keep existing graphs working in parallel
- [ ] Integration tests for migrated specialists

### 5.3 Phase 3: Manager Integration (Week 5-6)

- [ ] Wire Manager to Specialist Registry
- [ ] Implement async dispatch with SQLite checkpoints
- [ ] Implement progress tracking
- [ ] Wire Reviewer Agent gate
- [ ] End-to-end tests for Manager flow

### 5.4 Phase 4: Cutover (Week 7)

- [ ] Update `app.py` handlers to use Manager instead of direct Triage
- [ ] Deprecate old Triage flow (keep for rollback)
- [ ] Production deployment with feature flag
- [ ] Monitor metrics, error rates, latency

### 5.5 Phase 5: Cleanup (Week 8)

- [ ] Remove deprecated Triage flow
- [ ] Delete `coach.py`, `assistant.py`, `router.py` (untyped versions)
- [ ] Split `app.py` into `handlers/` directory
- [ ] Update documentation

---

## 6. Testing Strategy

### 6.1 Unit Tests

- Specialist Registry: registration, query, filtering
- Task Envelope: serialization, validation
- Error Handling: retry logic, error categorization
- Progress Reporting: callback invocation, state updates

### 6.2 Integration Tests

- Manager → Specialist dispatch and result collection
- Parallel fan-out execution
- Checkpoint persistence and recovery
- Reviewer Agent validation flow

### 6.3 End-to-End Tests

- Slack command → Manager → Specialist → Reviewer → Slack response
- Long-running workflow with checkpoint recovery
- Error scenarios (timeout, validation failure, system error)

---

## 7. Success Metrics

| Metric | Baseline | Target |
|--------|----------|--------|
| Request latency (p50) | TBD | < 5s for DIRECT, < 30s for COMPLEX |
| Request latency (p99) | TBD | < 10s for DIRECT, < 60s for COMPLEX |
| Error rate | TBD | < 1% |
| Retry success rate | N/A | > 80% of transient errors recovered |
| Specialist coverage | 2 (Coach, Assistant) | 5+ (add Research, Email, Pipeline, etc.) |

---

## 8. Open Questions

1. **Specialist cold start** — Should specialists be lazy-loaded or pre-warmed at startup?
2. **Rate limiting** — Should the Manager enforce per-specialist rate limits?
3. **Cost tracking** — Should we track LLM token usage per task for cost attribution?
4. **Human escalation** — What's the workflow when Reviewer blocks and human intervention is needed?

---

## 9. Appendix: File Structure

```
src/
├── core/
│   ├── envelope.py          # TaskEnvelope, TaskStatus, ProgressState, AggregatedResult
│   ├── errors.py            # SpecialistError, TransientError, ValidationError, SystemError
│   ├── progress.py          # ProgressCallback protocol, ProgressTracker
│   ├── invoker.py           # invoke_specialist(), handler wrapper
│   ├── recovery.py          # recover_orphaned_tasks()
│   ├── cost.py              # CostRecord, COST_TIERS
│   └── __init__.py
├── specialists/
│   ├── registry.py          # SpecialistDescriptor, RetryPolicy, register_specialist()
│   ├── coach.py             # Coach specialist (migrated from coach_typed.py)
│   ├── assistant.py         # Assistant specialist (migrated from assistant_typed.py)
│   ├── research.py          # Research specialist (new)
│   └── __init__.py          # Explicit imports to trigger decorators
├── graphs/
│   ├── manager.py           # Manager Agent (new)
│   ├── reviewer_agent.py    # Reviewer Agent (enhanced with revision loop)
│   ├── contracts.py         # Existing typed contracts (deprecated, migrate to envelope)
│   └── triage.py            # Legacy Triage (deprecated during migration)
├── handlers/
│   ├── slack/
│   │   ├── commands.py      # Slack command handlers (split from app.py)
│   │   └── actions.py       # Interactive action handlers
│   └── api/
│       └── routes.py        # REST API routes (new)
├── prompts/
│   ├── intent_classification.py  # LLM classification prompt + keyword fallback
│   └── ...
├── formatters/
│   └── ...                  # Existing Slack Block Kit formatters
├── app.py                   # Entry point (simplified, delegates to handlers)
└── db.py                    # SQLite operations (enhanced with checkpoint methods)
```

---

## 10. Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-04-15 | 0.1 | Initial draft |
| 2026-04-15 | 0.2 | Addressed spec review feedback: added Specialist Invocation Protocol, Revision Loop, Checkpoint Recovery, Intent Classification, AggregatedResult, Cost Attribution, Specialist Discovery, Migration Rollback Criteria |

---

## 11. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Specialist cold start | **Explicit imports** in `specialists/__init__.py` at startup |
| Rate limiting | **Per-specialist concurrency limits** with `max_concurrent` and `queue_size` |
| Cost tracking | **CostRecord** tracks tokens per task; `cost_tier` routes to appropriate models |
| Human escalation | **Revision loop** with `max_revisions=2`, then escalate to human via Slack notification |
