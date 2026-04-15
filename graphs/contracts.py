"""Typed contracts for Hive Mind orchestration.

Defines TaskInput, TaskOutput, artifact types, and enums for typed contracts across all graphs.
"""

from dataclasses import dataclass, field
from typing import Any, Literal
from langgraph.graph import MessagesState


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowType:
    """Workflow types recognized by the system."""
    ROLEPLAY = "roleplay"
    FEEDBACK = "feedback"
    PREP = "prep"
    RESEARCH = "research"
    DEAL = "deal"
    EMAIL = "email"
    PIPELINE = "pipeline"


class Complexity:
    """Task complexity levels for triage."""
    DIRECT = "direct"       # Single tool call
    WORKFLOW = "workflow"   # Single workflow execution
    COMPLEX = "complex"     # Multi-step task requiring decomposition


class AgentRole:
    """Agent roles for task assignment."""
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    CRM_AGENT = "crm_agent"
    EMAIL_AGENT = "email_agent"
    COACH = "coach"
    REVIEWER = "reviewer"
    ARCHITECT = "architect"
    PM = "pm"


class TaskStatus:
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class ReviewDecision:
    """Reviewer agent decisions."""
    APPROVED = "approved"
    CHANGES_REQUIRED = "changes_required"
    BLOCKED = "blocked"


# ─────────────────────────────────────────────────────────────────────────────
# Artifact Types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResearchBrief:
    """Research brief artifact."""
    company_name: str
    overview: str
    recent_news: list[str]
    icp_fit: str
    talking_points: list[str]
    competitors: list[str]
    recommended_approach: str
    sources: list[str] = field(default_factory=list)


@dataclass
class DealStatus:
    """Deal status artifact."""
    deal_name: str
    company_name: str
    amount: float | None
    stage: str
    close_date: str | None
    owner: str
    health: Literal["green", "yellow", "red"]
    next_steps: list[str]
    risks: list[str]
    recent_activity: list[str]


@dataclass
class EmailDraft:
    """Email draft artifact."""
    to_name: str
    to_email: str
    subject: str
    body: str
    tone: str = "professional"
    purpose: str = ""
    follow_up_date: str | None = None


@dataclass
class PipelineDigest:
    """Pipeline health digest artifact."""
    total_deals: int
    total_value: float
    by_stage: dict[str, dict[str, Any]]
    at_risk_deals: list[dict[str, Any]]
    won_this_period: list[dict[str, Any]]
    recommendations: list[str]


@dataclass
class RoleplayDebrief:
    """Roleplay session debrief artifact."""
    scenario: str
    overall_score: float
    strengths: list[str]
    improvements: list[str]
    dimension_scores: dict[str, float]
    recommended_practice: list[str]
    methodology: str


@dataclass
class MeetingPrepBrief:
    """Meeting preparation brief artifact."""
    company_name: str
    meeting_type: str
    attendees: list[dict[str, Any]]
    account_health: str
    recent_activity: list[str]
    open_deals: list[dict[str, Any]]
    talking_points: list[str]
    recommended_agenda: list[str]


@dataclass
class QBRDeck:
    """QBR deck artifact."""
    account_name: str
    period: str
    executive_summary: str
    wins: list[dict[str, Any]]
    losses: list[dict[str, Any]]
    pipeline_overview: dict[str, Any]
    win_loss_analysis: str
    strategic_recommendations: list[str]
    slides: list[dict[str, Any]]


@dataclass
class ExecutiveSummary:
    """Executive summary artifact."""
    title: str
    summary: str
    key_points: list[str]
    recommendations: list[str]
    data_sources: list[str]


@dataclass
class ArchitectureBrief:
    """Architecture brief from Architect agent."""
    data_sources_needed: list[str]
    rag_collections_relevant: list[str]
    mcp_tools_required: list[str]
    estimated_complexity: str
    potential_blockers: list[str]
    recommendations: list[str]


# Union type for all artifacts
Artifact = (
    ResearchBrief | DealStatus | EmailDraft | PipelineDigest |
    RoleplayDebrief | MeetingPrepBrief | QBRDeck | ExecutiveSummary |
    ArchitectureBrief | dict[str, Any]
)


# ─────────────────────────────────────────────────────────────────────────────
# Task Input/Output Contracts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TaskInput:
    """Input contract for all tasks.

    Attributes:
        goal: Natural language description of what to accomplish
        role: Which agent role should execute this task
        file_scope: Which data sources to use (e.g., ["hubspot", "rag", "web"])
        depends_on: List of task IDs this task depends on
        context_from: List of artifact IDs to inject as context
        constraints: Additional constraints (e.g., {"max_turns": 4, "methodology": "MEDDIC"})
    """
    goal: str
    role: Literal[
        "researcher", "writer", "analyst", "crm_agent",
        "email_agent", "coach", "reviewer", "architect", "pm"
    ]
    file_scope: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    context_from: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskOutput:
    """Output contract for all tasks.

    Attributes:
        status: Execution status
        artifacts: Structured outputs from the task
        files_modified: List of files/data sources written to
        handoff_notes: Context for downstream tasks
        error: Error message if failed
    """
    status: Literal["success", "failed", "blocked"]
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    files_modified: list[str] = field(default_factory=list)
    handoff_notes: str = ""
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Task Graph Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    """A single task in the task graph.

    Attributes:
        id: Unique task identifier
        input: Task input contract
        output: Task output contract (populated after execution)
        status: Current execution status
        created_at: Task creation timestamp
        completed_at: Task completion timestamp
    """
    id: str
    input: TaskInput
    output: TaskOutput | None = None
    status: str = TaskStatus.PENDING
    created_at: str = ""
    completed_at: str | None = None


@dataclass
class TaskGraph:
    """A graph of tasks with dependencies.

    Attributes:
        id: Unique graph identifier
        tasks: List of all tasks in the graph
        dependencies: Dict mapping task_id -> list of task_ids it depends on
        metadata: Additional metadata (e.g., original user request)
    """
    id: str
    tasks: list[Task]
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Review Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ReviewResult:
    """Result from Reviewer agent.

    Attributes:
        decision: Approved, changes required, or blocked
        feedback: List of issues found
        suggested_changes: Specific changes to make
        quality_score: 1-10 quality rating
    """
    decision: Literal["approved", "changes_required", "blocked"]
    feedback: list[str] = field(default_factory=list)
    suggested_changes: list[str] = field(default_factory=list)
    quality_score: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Typed State Extensions
# ─────────────────────────────────────────────────────────────────────────────

class TriageState(MessagesState):
    """State for triage graph."""
    complexity: str | None  # DIRECT, WORKFLOW, COMPLEX
    target_tool: str | None  # For DIRECT path
    route: str | None  # For WORKFLOW path (coach/assistant)
    workflow: str | None  # Workflow type
    user_id: str | None
    channel_id: str | None
    thread_ts: str | None
    company_name: str | None
    contact_name: str | None
    contact_email: str | None
    hubspot_context: dict | None
    rag_context: str | None
    web_context: str | None


class PMState(MessagesState):
    """State for PM agent."""
    task_graph: TaskGraph | None
    original_request: str
    user_id: str | None


class DAGExecutorState(MessagesState):
    """State for DAG executor."""
    task_graph: TaskGraph | None
    completed_tasks: list[str]  # Task IDs
    current_batch: list[str]  # Task IDs ready to execute
    artifacts: dict[str, Artifact]  # Artifact ID -> artifact
    user_id: str | None


class ReviewerState(MessagesState):
    """State for reviewer agent."""
    output_to_review: dict[str, Any]
    review_result: ReviewResult | None
    task_id: str | None


class ArchitectState(MessagesState):
    """State for architect agent."""
    request: str
    architecture_brief: ArchitectureBrief | None
    user_id: str | None


class MemoryState(MessagesState):
    """State for memory operations."""
    task_output: TaskOutput | None
    user_id: str | None
    context_tags: list[str]
