# Hierarchical Multi-Agent Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Rearchitect SalesCoach AI from Triage-based workflow to Hierarchical Multi-Agent Architecture with Manager orchestrating specialist agents.

**Architecture:** Centralized Manager Agent receives requests, classifies intent, dispatches to registered specialists via typed envelopes, aggregates results, passes through Reviewer gate, delivers to client.

**Tech Stack:** Python 3.11+, LangGraph, SQLite, asyncio, dataclasses, Pydantic for validation.

---

## File Structure

**New Files to Create:**
```
src/
├── core/
│   ├── envelope.py          # TaskEnvelope, TaskStatus, ProgressState, AggregatedResult
│   ├── errors.py            # SpecialistError hierarchy
│   ├── progress.py          # ProgressCallback, ProgressTracker
│   ├── invoker.py           # invoke_specialist() wrapper
│   ├── recovery.py          # recover_orphaned_tasks()
│   ├── cost.py              # CostRecord, COST_TIERS
│   └── __init__.py
├── specialists/
│   ├── registry.py          # SpecialistDescriptor, register_specialist()
│   ├── __init__.py          # Explicit imports
│   └── [future specialists]
├── graphs/
│   ├── manager.py           # Manager Agent
│   └── reviewer_agent.py    # Enhanced with revision loop
├── prompts/
│   └── intent_classification.py  # LLM prompt + keyword fallback
└── handlers/
    └── slack/
        ├── commands.py      # Split from app.py
        └── actions.py
```

**Files to Modify:**
- `app.py` — Route to Manager instead of Triage
- `db.py` — Add checkpoint methods

---

## Phase 1: Core Foundation

### Task 1: TaskEnvelope and Status Types

**Files:**
- Create: `core/envelope.py`
- Test: `tests/core/test_envelope.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_envelope.py
from core.envelope import TaskEnvelope, TaskStatus, ProgressState
from uuid import uuid4
from datetime import datetime

def test_task_envelope_creation():
    envelope = TaskEnvelope(
        task_id=uuid4(),
        specialist_name="coach",
        parent_request_id=uuid4(),
        input_data={"scenario": "discovery_call"}
    )
    assert envelope.status == TaskStatus.PENDING
    assert envelope.progress is None
    assert envelope.retry_count == 0

def test_progress_state_with_steps():
    progress = ProgressState(
        percent=50,
        message="Analyzing competitors",
        current_step=3,
        total_steps=5,
        step_label="Competitive analysis"
    )
    assert progress.percent == 50
    assert progress.current_step == 3
    assert progress.step_label == "Competitive analysis"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_envelope.py -v
# Expected: ModuleNotFoundError: No module named 'core'
```

- [ ] **Step 3: Create core/__init__.py**

```python
# core/__init__.py
from .envelope import TaskEnvelope, TaskStatus, ProgressState, AggregatedResult
from .errors import SpecialistError, TransientError, ValidationError, SystemError
from .progress import ProgressCallback, ProgressTracker

__all__ = [
    "TaskEnvelope",
    "TaskStatus",
    "ProgressState",
    "AggregatedResult",
    "SpecialistError",
    "TransientError",
    "ValidationError",
    "SystemError",
    "ProgressCallback",
    "ProgressTracker",
]
```

- [ ] **Step 4: Write envelope.py implementation**

```python
# core/envelope.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4
from datetime import datetime


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
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    step_label: Optional[str] = None


@dataclass
class TaskEnvelope:
    task_id: UUID = field(default_factory=uuid4)
    specialist_name: str = ""
    parent_request_id: UUID = field(default_factory=uuid4)
    input_data: Any = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output_data: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    progress: Optional[ProgressState] = None


@dataclass
class AggregatedResult:
    request_id: UUID
    component_results: dict[str, Any]
    success_count: int
    failure_count: int
    aggregated_content: str
    confidence_score: float
    warnings: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/core/test_envelope.py::test_task_envelope_creation -v
pytest tests/core/test_envelope.py::test_progress_state_with_steps -v
# Expected: PASS
```

- [ ] **Step 6: Commit**

```bash
git add core/envelope.py core/__init__.py tests/core/test_envelope.py
git commit -m "feat: add TaskEnvelope, TaskStatus, ProgressState, AggregatedResult

- TaskEnvelope: typed message envelope for Manager↔Specialist communication
- TaskStatus: PENDING, RUNNING, COMPLETED, FAILED, RETRYING, CANCELLED
- ProgressState: structured progress with step tracking (N of M)
- AggregatedResult: parallel fan-out aggregation with success_rate
"
```

---

### Task 2: Error Hierarchy

**Files:**
- Create: `core/errors.py`
- Test: `tests/core/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_errors.py
from core.errors import SpecialistError, TransientError, ValidationError, SystemError

def test_transient_error_has_retry_after():
    err = TransientError("timeout", retry_after_ms=5000)
    assert err.retry_after_ms == 5000
    assert isinstance(err, SpecialistError)

def test_validation_error_has_field():
    err = ValidationError("missing required field", field="company_id")
    assert err.field == "field"
    assert isinstance(err, SpecialistError)

def test_system_error_is_critical():
    err = SystemError("database corruption detected")
    assert str(err) == "database corruption detected"
    assert isinstance(err, SpecialistError)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_errors.py -v
# Expected: ModuleNotFoundError: No module named 'core.errors'
```

- [ ] **Step 3: Write errors.py implementation**

```python
# core/errors.py
class SpecialistError(Exception):
    """Base exception for all specialist errors."""
    pass


class TransientError(SpecialistError):
    """Retryable errors: timeout, rate_limit, temporary_unavailable."""

    def __init__(self, message: str, retry_after_ms: int = None):
        super().__init__(message)
        self.retry_after_ms = retry_after_ms
        self.message = message


class ValidationError(SpecialistError):
    """Input validation failed — don't retry."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.field = field
        self.message = message


class SystemError(SpecialistError):
    """Critical — escalate to Manager immediately."""
    pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_errors.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add core/errors.py tests/core/test_errors.py
git commit -m "feat: add error hierarchy (TransientError, ValidationError, SystemError)

- SpecialistError: base exception
- TransientError: retryable (timeout, rate_limit)
- ValidationError: no retry (invalid input)
- SystemError: escalate immediately
"
```

---

### Task 3: Progress Callback (Async-Safe)

**Files:**
- Create: `core/progress.py`
- Test: `tests/core/test_progress.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_progress.py
import pytest
import asyncio
from core.envelope import TaskEnvelope, ProgressState
from core.progress import ProgressTracker
from db import save_checkpoint

@pytest.mark.asyncio
async def test_progress_tracker_calls_save_checkpoint(mocker):
    envelope = TaskEnvelope(specialist_name="test", input_data={})
    mock_save = mocker.patch("core.progress.save_checkpoint", new_callable=asyncio.CoroutineMock)

    tracker = ProgressTracker(envelope)
    await tracker(ProgressState(percent=50, message="Working"))

    assert mock_save.called
    assert envelope.progress.percent == 50

@pytest.mark.asyncio
async def test_progress_tracker_is_thread_safe(mocker):
    envelope = TaskEnvelope(specialist_name="test", input_data={})
    mock_save = mocker.patch("core.progress.save_checkpoint", new_callable=asyncio.CoroutineMock)
    tracker = ProgressTracker(envelope)

    # Fire multiple concurrent progress updates
    await asyncio.gather(
        tracker(ProgressState(percent=10, message="Step 1")),
        tracker(ProgressState(percent=50, message="Step 2")),
        tracker(ProgressState(percent=100, message="Done")),
    )

    assert mock_save.call_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_progress.py -v
# Expected: ModuleNotFoundError
```

- [ ] **Step 3: Write progress.py implementation**

```python
# core/progress.py
import asyncio
from typing import Protocol
from .envelope import TaskEnvelope, ProgressState

# Import will work once db.py has save_checkpoint
from db import save_checkpoint


class ProgressCallback(Protocol):
    async def __call__(self, progress: ProgressState) -> None:
        """Report progress update. Thread-safe; persists to SQLite."""


class ProgressTracker:
    """Async-safe progress tracker with SQLite persistence."""

    def __init__(self, envelope: TaskEnvelope):
        self.envelope = envelope
        self._lock = asyncio.Lock()

    async def __call__(self, progress: ProgressState):
        """Thread-safe progress reporting with SQLite persistence."""
        async with self._lock:
            self.envelope.progress = progress
            await save_checkpoint(self.envelope)
            # Log at debug level to avoid noise
            import logging
            logging.debug(f"Progress: {progress.percent}% - {progress.message}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_progress.py -v
# Expected: PASS (may need to mock db.save_checkpoint)
```

- [ ] **Step 5: Commit**

```bash
git add core/progress.py tests/core/test_progress.py
git commit -m "feat: add async-safe ProgressTracker with SQLite persistence

- ProgressCallback: Protocol for progress reporting
- ProgressTracker: uses asyncio.Lock for thread safety
- Persists each progress update to task_checkpoints table
"
```

---

### Task 4: Cost Attribution (COST_TIERS)

**Files:**
- Create: `core/cost.py`
- Test: `tests/core/test_cost.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_cost.py
from core.cost import CostRecord, COST_TIERS, calculate_cost

def test_cost_tiers_defined():
    assert "fast" in COST_TIERS
    assert "standard" in COST_TIERS
    assert "expensive" in COST_TIERS

def test_cost_record_creation():
    from uuid import uuid4
    from datetime import datetime
    record = CostRecord(
        task_id=uuid4(),
        specialist_name="research",
        input_tokens=1000,
        output_tokens=500,
        model="claude-sonnet-4-6",
        cost_usd=0.015,
        timestamp=datetime.now()
    )
    assert record.input_tokens == 1000
    assert record.cost_usd == 0.015
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_cost.py -v
# Expected: ModuleNotFoundError
```

- [ ] **Step 3: Write cost.py implementation**

```python
# core/cost.py
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime


@dataclass
class CostRecord:
    task_id: UUID
    specialist_name: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float
    timestamp: datetime


# Model routing by cost tier
COST_TIERS = {
    "fast": {"model": "qwen3.5:397b-cloud", "max_tokens": 2000},
    "standard": {"model": "claude-sonnet-4-6", "max_tokens": 4000},
    "expensive": {"model": "claude-opus-4-6", "max_tokens": 8000},
}


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate USD cost based on model pricing."""
    # Pricing per 1M tokens (approximate)
    PRICING = {
        "qwen3.5:397b-cloud": {"input": 0.0, "output": 0.0},  # Local
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    }
    pricing = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_cost.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add core/cost.py tests/core/test_cost.py
git commit -m "feat: add cost attribution (CostRecord, COST_TIERS)

- CostRecord: track tokens and cost per task
- COST_TIERS: fast (local), standard, expensive (opus)
- calculate_cost(): USD calculation from model pricing
"
```

---

## Phase 2: Specialist Registry

### Task 5: SpecialistDescriptor and Registry

**Files:**
- Create: `specialists/registry.py`
- Create: `specialists/__init__.py`
- Test: `tests/specialists/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/specialists/test_registry.py
from specialists.registry import (
    SpecialistDescriptor, RetryPolicy, register_specialist,
    SPECIALISTS, find_specialist, find_specialists, get_specialist_by_name
)

def test_retry_policy_defaults():
    policy = RetryPolicy()
    assert policy.max_retries == 3
    assert policy.exponential_backoff is True

def test_specialist_descriptor_creation():
    def dummy_handler(input, progress): pass
    spec = SpecialistDescriptor(
        name="test",
        capabilities=["test_capability"],
        handler=dummy_handler,
        input_schema=dict,
        output_schema=dict,
        version="1.0.0",
        tags=["test", "experimental"]
    )
    assert spec.name == "test"
    assert "test_capability" in spec.capabilities
    assert "experimental" in spec.tags

def test_register_specialist_decorator():
    @register_specialist(
        name="test_specialist",
        capabilities=["test"],
        input_schema=dict,
        output_schema=dict,
    )
    def test_handler(input, progress):
        return {"result": "ok"}

    assert "test_specialist" in SPECIALISTS
    assert SPECIALISTS["test_specialist"].name == "test_specialist"

def test_find_specialist_by_capability():
    results = find_specialists(capability="test")
    assert len(results) >= 1

def test_get_specialist_by_name():
    spec = get_specialist_by_name("test_specialist")
    assert spec is not None
    assert spec.name == "test_specialist"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/specialists/test_registry.py -v
# Expected: ModuleNotFoundError
```

- [ ] **Step 3: Create specialists/__init__.py**

```python
# specialists/__init__.py
# Explicit imports trigger @register_specialist decorators at startup
from . import registry  # noqa: F401

# Future: add specialist modules here as they're created
# from . import coach, assistant, research

__all__ = ["registry"]
```

- [ ] **Step 4: Write registry.py implementation**

```python
# specialists/registry.py
from dataclasses import dataclass, field
from typing import Callable, Any, Type, Optional


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

    # Concurrency controls
    max_concurrent: int = 5
    queue_size: int = 100
    priority: int = 0


# Global registry — populated at startup
SPECIALISTS: dict[str, SpecialistDescriptor] = {}


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
    retry_policy: Optional[RetryPolicy] = None,
    max_concurrent: int = 5,
    queue_size: int = 100,
    priority: int = 0,
) -> Callable:
    """Register a specialist agent in the global registry."""
    def decorator(func: Callable) -> Callable:
        SPECIALISTS[name] = SpecialistDescriptor(
            name=name,
            capabilities=capabilities,
            handler=func,
            input_schema=input_schema,
            output_schema=output_schema,
            timeout_minutes=timeout_minutes,
            supports_parallel=supports_parallel,
            cost_tier=cost_tier,
            version=version,
            tags=tags or [],
            retry_policy=retry_policy or RetryPolicy(),
            max_concurrent=max_concurrent,
            queue_size=queue_size,
            priority=priority,
        )
        return func
    return decorator


def find_specialist(capability: str, **filters) -> Optional[SpecialistDescriptor]:
    """Find first specialist matching capability and filters."""
    for spec in SPECIALISTS.values():
        if capability in spec.capabilities:
            match = True
            for key, value in filters.items():
                if getattr(spec, key, None) != value:
                    match = False
                    break
            if match:
                return spec
    return None


def find_specialists(
    capability: str = None,
    tags_include: list[str] = None,
    cost_tier__in: list[str] = None,
    supports_parallel: bool = None,
) -> list[SpecialistDescriptor]:
    """Find all specialists matching criteria."""
    results = []
    for spec in SPECIALISTS.values():
        match = True

        if capability and capability not in spec.capabilities:
            match = False

        if tags_include:
            if not any(tag in spec.tags for tag in tags_include):
                match = False

        if cost_tier__in and spec.cost_tier not in cost_tier__in:
            match = False

        if supports_parallel is not None and spec.supports_parallel != supports_parallel:
            match = False

        if match:
            results.append(spec)

    return results


def get_specialist_by_name(name: str) -> Optional[SpecialistDescriptor]:
    """Get specialist by exact name."""
    return SPECIALISTS.get(name)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/specialists/test_registry.py -v
# Expected: PASS
```

- [ ] **Step 6: Commit**

```bash
git add specialists/registry.py specialists/__init__.py tests/specialists/test_registry.py
git commit -m "feat: add Specialist Registry with declarative registration

- SpecialistDescriptor: name, capabilities, handler, schemas, config
- RetryPolicy: max_retries, backoff, retry conditions
- @register_specialist(): decorator for registration
- find_specialist(), find_specialists(), get_specialist_by_name(): query API
- Concurrency controls: max_concurrent, queue_size, priority
"
```

---

### Task 6: Specialist Invocation Protocol

**Files:**
- Create: `core/invoker.py`
- Test: `tests/core/test_invoker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_invoker.py
import pytest
import asyncio
from core.envelope import TaskEnvelope, TaskStatus
from core.invoker import invoke_specialist
from specialists.registry import SpecialistDescriptor, RetryPolicy

@pytest.mark.asyncio
async def test_invoke_specialist_success(mocker):
    async def mock_handler(input_data, progress):
        return {"result": "success"}

    descriptor = SpecialistDescriptor(
        name="test",
        capabilities=["test"],
        handler=mock_handler,
        input_schema=dict,
        output_schema=dict,
        timeout_minutes=5,
    )
    envelope = TaskEnvelope(
        specialist_name="test",
        input_data={"key": "value"}
    )
    async def mock_progress(progress_state): pass

    result = await invoke_specialist(descriptor, envelope, mock_progress)

    assert result.status == TaskStatus.COMPLETED
    assert result.output_data == {"result": "success"}

@pytest.mark.asyncio
async def test_invoke_specialist_timeout(mocker):
    async def mock_handler(input_data, progress):
        await asyncio.sleep(10)  # Will timeout
        return {"result": "success"}

    descriptor = SpecialistDescriptor(
        name="test",
        capabilities=["test"],
        handler=mock_handler,
        input_schema=dict,
        output_schema=dict,
        timeout_minutes=1,  # 1 minute timeout
    )
    envelope = TaskEnvelope(specialist_name="test", input_data={})
    async def mock_progress(progress_state): pass

    result = await invoke_specialist(descriptor, envelope, mock_progress)

    assert result.status == TaskStatus.FAILED
    assert "Timeout" in result.error
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_invoker.py -v
# Expected: ModuleNotFoundError
```

- [ ] **Step 3: Write invoker.py implementation**

```python
# core/invoker.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from .envelope import TaskEnvelope, TaskStatus, ProgressState
from .errors import TransientError, ValidationError, SystemError
from .progress import ProgressCallback
from db import save_checkpoint

# Thread pool for blocking operations (LangGraph graphs)
_executor = ThreadPoolExecutor(max_workers=10)


async def invoke_specialist(
    descriptor: "SpecialistDescriptor",
    envelope: TaskEnvelope,
    progress_cb: ProgressCallback,
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
                await progress_cb(state)

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
            # Retry logic would go here (scheduler integration)

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

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_invoker.py -v
# Expected: PASS (may need to mock save_checkpoint)
```

- [ ] **Step 5: Commit**

```bash
git add core/invoker.py tests/core/test_invoker.py
git commit -m "feat: add Specialist Invocation Protocol

- invoke_specialist(): wraps handler with async execution, timeout, checkpoints
- Thread pool for blocking LangGraph graphs
- Progress callback injection with persistence
- Error handling: Timeout → retry, Validation → fail, Transient → retry
"
```

---

## Phase 3: Manager Agent

### Task 7: Manager Agent Skeleton

**Files:**
- Create: `graphs/manager.py`
- Test: `tests/graphs/test_manager.py`

- [ ] **Step 1-6: Follow TDD pattern** (write test → run fail → implement → run pass → commit)

```python
# graphs/manager.py
import asyncio
from uuid import uuid4
from datetime import datetime
from core.envelope import TaskEnvelope, TaskStatus, AggregatedResult, ProgressState
from core.invoker import invoke_specialist
from core.progress import ProgressTracker
from specialists.registry import SpecialistDescriptor, find_specialists, get_specialist_by_name
from db import save_checkpoint, load_checkpoint


class ManagerAgent:
    """Centralized orchestrator for multi-agent workflows."""

    def __init__(self):
        self.active_requests: dict[UUID, list[TaskEnvelope]] = {}

    async def handle_request(self, request: dict) -> dict:
        """Main entry point for all requests."""
        request_id = uuid4()
        self.active_requests[request_id] = []

        # 1. Classify intent
        intent = await self.classify_intent(request.get("content", ""))

        # 2. Select specialists
        specialists = self.select_specialists(intent)

        if not specialists:
            return {"error": "No specialist found for this request", "intent": intent}

        # 3. Dispatch tasks (parallel fan-out if multiple)
        envelopes = []
        for spec in specialists:
            envelope = TaskEnvelope(
                task_id=uuid4(),
                specialist_name=spec.name,
                parent_request_id=request_id,
                input_data=request,
            )
            envelopes.append(envelope)

        # 4. Execute in parallel if supported
        if len(envelopes) > 1 and all(s.supports_parallel for s in specialists):
            results = await self._dispatch_parallel(envelopes, specialists)
        else:
            results = [await self.dispatch_task(envelopes[0], specialists[0])]

        # 5. Aggregate results
        aggregated = self.aggregate_results(results)

        # 6. Return for reviewer gate
        return {
            "request_id": str(request_id),
            "aggregated_result": aggregated,
            "component_results": {r.specialist_name: r for r in results},
        }

    async def classify_intent(self, content: str) -> dict:
        """LLM-based intent classification with keyword fallback."""
        # TODO: Implement LLM classification with prompts/intent_classification.py
        # For now, simple keyword matching
        from prompts.intent_classification import classify_intent as classify
        return await classify(content)

    def select_specialists(self, intent: dict) -> list[SpecialistDescriptor]:
        """Query registry for specialists matching intent capabilities."""
        primary = intent.get("primary_capability")
        secondary = intent.get("secondary_capabilities", [])

        results = []
        if primary:
            results.extend(find_specialists(capability=primary))
        for cap in secondary:
            results.extend(find_specialists(capability=cap))

        # Deduplicate by name
        seen = set()
        unique = []
        for spec in results:
            if spec.name not in seen:
                seen.add(spec.name)
                unique.append(spec)

        return unique

    async def dispatch_task(
        self, envelope: TaskEnvelope, specialist: SpecialistDescriptor = None
    ) -> TaskEnvelope:
        """Dispatch task to specialist, track progress, handle retries."""
        if specialist is None:
            specialist = get_specialist_by_name(envelope.specialist_name)

        if specialist is None:
            envelope.status = TaskStatus.FAILED
            envelope.error = f"Specialist '{envelope.specialist_name}' not found"
            return envelope

        # Create progress tracker
        tracker = ProgressTracker(envelope)

        # Invoke specialist
        result = await invoke_specialist(specialist, envelope, tracker)

        return result

    async def _dispatch_parallel(
        self, envelopes: list[TaskEnvelope], specialists: list[SpecialistDescriptor]
    ) -> list[TaskEnvelope]:
        """Dispatch multiple tasks in parallel."""
        tasks = [
            self.dispatch_task(env, spec)
            for env, spec in zip(envelopes, specialists)
        ]
        return await asyncio.gather(*tasks)

    def aggregate_results(self, envelopes: list[TaskEnvelope]) -> AggregatedResult:
        """Combine results from multiple specialists."""
        request_id = envelopes[0].parent_request_id if envelopes else uuid4()

        success = [e for e in envelopes if e.status == TaskStatus.COMPLETED]
        failed = [e for e in envelopes if e.status == TaskStatus.FAILED]

        component_results = {
            e.specialist_name: e.output_data for e in success
        }

        # Simple concatenation for now (LLM synthesis later)
        aggregated_content = "\n\n".join(
            str(e.output_data) for e in success
        )

        return AggregatedResult(
            request_id=request_id,
            component_results=component_results,
            success_count=len(success),
            failure_count=len(failed),
            aggregated_content=aggregated_content,
            confidence_score=len(success) / len(envelopes) if envelopes else 0.0,
            warnings=[e.error for e in failed],
        )
```

- [ ] **Step 5: Commit**

```bash
git add graphs/manager.py tests/graphs/test_manager.py
git commit -m "feat: add Manager Agent skeleton

- handle_request(): main entry point
- classify_intent(): LLM + keyword fallback
- select_specialists(): query registry by capability
- dispatch_task(): invoke specialist with progress tracking
- aggregate_results(): combine parallel fan-out results
"
```

---

### Task 8: Intent Classification Prompt

**Files:**
- Create: `prompts/intent_classification.py`
- Test: `tests/prompts/test_intent_classification.py`

- [ ] **Step 1-6: Follow TDD pattern**

```python
# prompts/intent_classification.py
import re

# LLM prompt template (for future LLM integration)
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

# Keyword fallback rules
KEYWORD_RULES = {
    "roleplay": ["roleplay", "practice", "simulate", "pretend"],
    "feedback": ["feedback", "review", "analyze", "score", "grade"],
    "meeting_prep": ["meeting", "prep", "prepare", "brief"],
    "lookup": ["find", "show", "get", "lookup", "search"],
    "email": ["email", "draft", "write", "compose"],
    "pipeline": ["pipeline", "forecast", "deals", "health"],
    "research": ["research", "company", "competitor", "market"],
}


async def classify_intent(content: str) -> dict:
    """Classify intent using keyword matching (LLM integration TODO)."""
    content_lower = content.lower()

    best_match = None
    best_score = 0

    for capability, keywords in KEYWORD_RULES.items():
        score = sum(1 for kw in keywords if kw in content_lower)
        if score > best_score:
            best_score = score
            best_match = capability

    if best_match:
        return {
            "primary_capability": best_match,
            "secondary_capabilities": [],
            "confidence": min(0.5 + (best_score * 0.15), 0.95),
            "requires_parallel": False,
        }

    return {
        "primary_capability": "unknown",
        "secondary_capabilities": [],
        "confidence": 1.0,
        "requires_parallel": False,
    }
```

- [ ] **Step 5: Commit**

```bash
git add prompts/intent_classification.py tests/prompts/test_intent_classification.py
git commit -m "feat: add Intent Classification with keyword fallback

- INTENT_CLASSIFICATION_PROMPT: LLM prompt template (for future)
- KEYWORD_RULES: capability → keyword mappings
- classify_intent(): returns primary_capability, confidence
"
```

---

## Phase 4: Reviewer Enhancement

### Task 9: Reviewer Revision Loop

**Files:**
- Modify: `graphs/reviewer_agent.py`
- Test: `tests/graphs/test_reviewer_revision.py`

- [ ] **Step 1: Read existing reviewer_agent.py**

```bash
wc -l graphs/reviewer_agent.py
head -50 graphs/reviewer_agent.py
```

- [ ] **Step 2: Add ReviewResult with revision metadata**

```python
# Add to graphs/reviewer_agent.py (after imports)
from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass
class ReviewResult:
    decision: Literal["approved", "changes_required", "blocked"]
    quality_score: int  # 0-100
    feedback: Optional[str] = None
    blocked_reason: Optional[str] = None
    max_revisions: int = 2
    revision_context: Optional[dict] = None
```

- [ ] **Step 3: Update reviewer_node to handle revisions**

```python
# Modify reviewer_node function in graphs/reviewer_agent.py
async def reviewer_node(state: dict) -> dict:
    """Review specialist output and return ReviewResult."""
    output = state.get("task_output", {}).get("artifacts", {})
    task_id = state.get("task_id", "unknown")

    # Build review prompt
    prompt = REVIEWER_PROMPT.format(
        output=output,
        task_id=task_id,
        revision_context=state.get("_revision", {})
    )

    response = await reviewer_llm.ainvoke([
        SystemMessage(content="You are a quality reviewer..."),
        HumanMessage(content=prompt)
    ])

    # Parse response (expecting JSON)
    result = parse_review_response(response.content)

    return {
        "review_result": ReviewResult(
            decision=result["decision"],
            quality_score=result.get("quality_score", 0),
            feedback=result.get("feedback"),
            blocked_reason=result.get("blocked_reason"),
        )
    }
```

- [ ] **Step 4: Commit**

```bash
git add graphs/reviewer_agent.py
git commit -m "feat: add Reviewer revision loop support

- ReviewResult: decision, quality_score, feedback, max_revisions
- revision_context: prior output and feedback history
- Reviewer handles revision tasks with context
"
```

---

## Phase 5: Database Checkpoints

### Task 10: Checkpoint Schema and Methods

**Files:**
- Modify: `db.py`
- Create: `tests/db/test_checkpoints.py`

- [ ] **Step 1: Read existing db.py structure**

```bash
grep -n "def init_db" db.py
grep -n "CREATE TABLE" db.py
```

- [ ] **Step 2: Add task_checkpoints table to init_db()**

```python
# Add to db.py init_db() function, after existing table creation
cursor.execute("""
CREATE TABLE IF NOT EXISTS task_checkpoints (
    task_id TEXT PRIMARY KEY,
    specialist_name TEXT NOT NULL,
    parent_request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_data TEXT NOT NULL,
    output_data TEXT,
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

CREATE INDEX IF NOT EXISTS idx_parent_request ON task_checkpoints(parent_request_id);
CREATE INDEX IF NOT EXISTS idx_status_inflight ON task_checkpoints(status)
    WHERE status IN ('pending', 'running', 'retrying');
""")
```

- [ ] **Step 3: Add save_checkpoint function**

```python
# Add to db.py
async def save_checkpoint(envelope: "TaskEnvelope") -> None:
    """Persist task envelope to task_checkpoints table."""
    import json
    from datetime import datetime

    conn = get_db_connection()
    cursor = conn.cursor()

    progress = envelope.progress
    cursor.execute("""
        INSERT OR REPLACE INTO task_checkpoints (
            task_id, specialist_name, parent_request_id, status,
            input_data, output_data, error, retry_count,
            progress_percent, progress_message, progress_current_step,
            progress_total_steps, progress_step_label,
            created_at, started_at, completed_at, checkpoint_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (
        str(envelope.task_id),
        envelope.specialist_name,
        str(envelope.parent_request_id),
        envelope.status.value,
        json.dumps(envelope.input_data),
        json.dumps(envelope.output_data) if envelope.output_data else None,
        envelope.error,
        envelope.retry_count,
        progress.percent if progress else 0,
        progress.message if progress else None,
        progress.current_step if progress else None,
        progress.total_steps if progress else None,
        progress.step_label if progress else None,
        envelope.created_at.isoformat(),
        envelope.started_at.isoformat() if envelope.started_at else None,
        envelope.completed_at.isoformat() if envelope.completed_at else None,
    ))

    conn.commit()
    conn.close()


async def load_checkpoint(task_id: UUID) -> Optional["TaskEnvelope"]:
    """Load task envelope from checkpoint."""
    import json
    from core.envelope import TaskEnvelope, TaskStatus, ProgressState

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM task_checkpoints WHERE task_id = ?", (str(task_id),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Reconstruct envelope from row (column indices depend on SELECT order)
    # ... reconstruction logic ...

    return envelope


async def query_orphaned_tasks() -> list["TaskEnvelope"]:
    """Find in-flight tasks that may be orphaned (for recovery)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM task_checkpoints
        WHERE status IN ('running', 'retrying')
          AND checkpoint_at < datetime('now', '-5 minutes')
        ORDER BY checkpoint_at ASC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [load_checkpoint_from_row(row) for row in rows]
```

- [ ] **Step 4: Commit**

```bash
git add db.py tests/db/test_checkpoints.py
git commit -m "feat: add task_checkpoints table and CRUD methods

- task_checkpoints: persist TaskEnvelope to SQLite
- save_checkpoint(): INSERT OR REPLACE
- load_checkpoint(): reconstruct envelope from row
- query_orphaned_tasks(): find in-flight tasks for recovery
"
```

---

## Phase 6: Recovery and Migration

### Task 11: Checkpoint Recovery

**Files:**
- Create: `core/recovery.py`
- Test: `tests/core/test_recovery.py`

- [ ] **Step 1-6: Follow TDD pattern**

```python
# core/recovery.py
import logging
from core.envelope import TaskEnvelope, TaskStatus
from db import query_orphaned_tasks, save_checkpoint

logger = logging.getLogger(__name__)


async def recover_orphaned_tasks(manager: "ManagerAgent"):
    """Called on Manager startup to recover orphaned tasks."""
    orphaned = await query_orphaned_tasks()

    logger.info(f"Found {len(orphaned)} orphaned tasks for recovery")

    for task in orphaned:
        # Determine recovery action
        if task.status == TaskStatus.RUNNING:
            # Was mid-execution — retry from checkpoint
            task.status = TaskStatus.RETRYING
            task.retry_count += 1
            logger.info(f"Recovering orphaned task {task.task_id}")
            await manager.dispatch_task(task)

        elif task.status == TaskStatus.RETRYING:
            # Was mid-backoff — resume retry
            await manager.dispatch_task(task)

        else:
            # Should not happen — log and mark failed
            logger.error(f"Unknown orphaned state for {task.task_id}: {task.status}")
            task.status = TaskStatus.FAILED
            task.error = "Orphaned during recovery"
            await save_checkpoint(task)
```

- [ ] **Step 5: Commit**

```bash
git add core/recovery.py tests/core/test_recovery.py
git commit -m "feat: add checkpoint recovery for orphaned tasks

- recover_orphaned_tasks(): called on Manager startup
- RUNNING tasks → retry with incremented count
- RETRYING tasks → resume retry
- Unknown states → mark FAILED
"
```

---

### Task 12: Migration — Wire Manager to app.py

**Files:**
- Modify: `app.py`
- Create: `handlers/slack/commands.py` (split from app.py)

- [ ] **Step 1: Read app.py structure**

```bash
wc -l app.py
grep -n "def handle_coach" app.py
grep -n "def handle_research" app.py
```

- [ ] **Step 2: Create handlers/slack/commands.py**

```python
# handlers/slack/commands.py
from slack_bolt import App
from graphs.manager import ManagerAgent

manager = ManagerAgent()


async def handle_coach(ack, body, say):
    """Handle /coach command via Manager."""
    await ack()

    request = {
        "content": body.get("text", ""),
        "user_id": body.get("user_id"),
        "channel_id": body.get("channel_id"),
    }

    result = await manager.handle_request(request)

    # Pass to reviewer, then format and respond
    # ... (existing formatting logic)
```

- [ ] **Step 3: Update app.py to import handlers**

```python
# app.py — remove inline handlers, import from handlers/slack/commands.py
from handlers.slack.commands import handle_coach, handle_research, ...

# Update command registrations to use new handlers
app.command("/coach")(handle_coach)
```

- [ ] **Step 4: Commit**

```bash
git add handlers/slack/commands.py app.py
git commit -m "refactor: split Slack command handlers from app.py

- handlers/slack/commands.py: new module for command handlers
- app.py: simplified, delegates to handlers
- Commands now route through Manager Agent
"
```

---

## Testing Strategy

### Task 13: Integration Tests

**Files:**
- Create: `tests/integration/test_manager_flow.py`

- [ ] **Step 1-6: Full end-to-end test**

```python
# tests/integration/test_manager_flow.py
import pytest
from graphs.manager import ManagerAgent
from specialists.registry import SPECIALISTS

@pytest.mark.asyncio
async def test_full_manager_flow():
    """Test: Slack command → Manager → Specialist → Reviewer → Response."""
    manager = ManagerAgent()

    request = {
        "content": "Start a roleplay for a discovery call",
        "user_id": "U123456",
        "channel_id": "C123456",
    }

    result = await manager.handle_request(request)

    assert "request_id" in result
    assert "aggregated_result" in result
    assert result["aggregated_result"].success_count >= 0
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_manager_flow.py
git commit -m "test: add integration test for full Manager flow
"
```

---

## Documentation

### Task 14: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add architecture section**

```markdown
## Architecture (Updated 2026-04-15)

SalesCoach AI now uses a Hierarchical Multi-Agent Architecture:

```
Slack → Manager Agent → Specialists → Reviewer → Response
```

**New components:**
- `graphs/manager.py` — Centralized orchestrator
- `specialists/registry.py` — Declarative specialist registration
- `core/envelope.py` — Typed TaskEnvelope for communication
- `core/invoker.py` — Specialist invocation with timeout/retry

**Running the app:** Same as before (Manager starts automatically)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with new architecture
"
```

---

## Summary

**Total Tasks:** 14
**Estimated Time:** 8-10 hours for experienced developer

**Execution Order:**
1. Tasks 1-4: Core Foundation (envelope, errors, progress, cost)
2. Tasks 5-6: Specialist Registry
3. Tasks 7-8: Manager Agent
4. Task 9: Reviewer Enhancement
5. Task 10: Database Checkpoints
6. Task 11: Recovery
7. Task 12: Migration (wire to app.py)
8. Task 13: Integration Tests
9. Task 14: Documentation

**Plan complete and saved to:** `docs/superpowers/plans/2026-04-15-hierarchical-multi-agent-implementation.md`

---

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
