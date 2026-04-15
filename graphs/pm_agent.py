"""PM Agent for Hive Mind orchestration.

Decomposes complex requests into typed TaskGraph DAGs.
"""

import json
from datetime import datetime
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage

from llm_factory import get_llm
from graphs.contracts import (
    TaskInput, TaskOutput, Task, TaskGraph, TaskStatus,
    AgentRole, WorkflowType
)
from prompts.pm_prompt import PM_PROMPT


# Initialize LLM
pm_llm = get_llm()


def parse_task_graph_response(response_text: str) -> dict:
    """Parse the JSON response from PM agent."""
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Return minimal valid structure
        return {
            "tasks": [],
            "dependencies": {},
            "metadata": {}
        }


def create_task_graph(state: dict) -> dict:
    """Create a task graph from the user's request.

    Args:
        state: PMState with original_request, user_id

    Returns:
        dict with task_graph populated
    """
    original_request = state.get("original_request", "")
    user_id = state.get("user_id", "")

    # Build prompt with context
    prompt = PM_PROMPT.format(request=original_request)

    response = pm_llm.invoke([
        SystemMessage(content="You are a PM agent that decomposes requests into executable task graphs."),
        HumanMessage(content=prompt)
    ])

    parsed = parse_task_graph_response(response.content)

    # Convert parsed tasks to Task objects
    tasks = []
    dependencies = {}

    for task_data in parsed.get("tasks", []):
        task_id = task_data.get("id", f"task_{len(tasks)}")

        task_input = TaskInput(
            goal=task_data.get("goal", ""),
            role=task_data.get("role", "researcher"),
            file_scope=task_data.get("file_scope", []),
            depends_on=task_data.get("depends_on", []),
            context_from=task_data.get("context_from", []),
            constraints=task_data.get("constraints", {})
        )

        task = Task(
            id=task_id,
            input=task_input,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat()
        )

        tasks.append(task)

        # Build dependency map
        if task_data.get("depends_on"):
            dependencies[task_id] = task_data["depends_on"]

    # Create TaskGraph
    task_graph = TaskGraph(
        id=f"graph_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        tasks=tasks,
        dependencies=dependencies,
        metadata={
            "original_request": original_request,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "total_tasks": len(tasks)
        }
    )

    return {"task_graph": task_graph}


def get_ready_tasks(task_graph: TaskGraph, completed_tasks: list[str]) -> list[str]:
    """Get task IDs that are ready to execute.

    A task is ready if:
    - It's in PENDING status
    - All its dependencies are in completed_tasks
    """
    ready = []

    for task in task_graph.tasks:
        if task.status != TaskStatus.PENDING:
            continue

        # Check dependencies
        task_deps = task_graph.dependencies.get(task.id, [])
        if all(dep in completed_tasks for dep in task_deps):
            ready.append(task.id)

    return ready


def select_batch(state: dict) -> dict:
    """Select the next batch of tasks to execute.

    Args:
        state: DAGExecutorState with task_graph, completed_tasks

    Returns:
        dict with current_batch populated
    """
    task_graph = state.get("task_graph")
    completed_tasks = state.get("completed_tasks", [])

    if not task_graph:
        return {"current_batch": []}

    ready = get_ready_tasks(task_graph, completed_tasks)

    # Limit batch size for parallel execution
    max_batch_size = 5
    current_batch = ready[:max_batch_size]

    return {"current_batch": current_batch}


def execute_batch(state: dict, mcp_tools: list | None = None) -> dict:
    """Execute a batch of tasks in parallel.

    Args:
        state: DAGExecutorState with current_batch, task_graph
        mcp_tools: Optional MCP tools for executor

    Returns:
        dict with updated task_graph, artifacts
    """
    from tools.executor import DirectExecutor
    from graphs.contracts import Artifact

    task_graph = state.get("task_graph")
    current_batch = state.get("current_batch", [])
    existing_artifacts = state.get("artifacts", {})

    if not task_graph or not current_batch:
        return {"task_graph": task_graph, "artifacts": existing_artifacts}

    executor = DirectExecutor(mcp_tools)
    new_artifacts = {}

    # Execute tasks in batch (sequentially for now, can be parallelized)
    for task_id in current_batch:
        # Find task in graph
        task = next((t for t in task_graph.tasks if t.id == task_id), None)
        if not task:
            continue

        # Inject context from dependencies
        context = _build_task_context(task, task_graph, existing_artifacts)

        # Execute task
        try:
            output = executor.execute_single_task(task.input)
            task.output = output
            task.status = output.status
            task.completed_at = datetime.now().isoformat()

            # Store artifacts
            if output.artifacts:
                for artifact_name, artifact in output.artifacts.items():
                    artifact_key = f"{task_id}_{artifact_name}"
                    new_artifacts[artifact_key] = artifact

        except Exception as e:
            task.output = TaskOutput(
                status="failed",
                error=str(e),
                handoff_notes=f"Failed during batch execution: {task.input.goal}"
            )
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()

    return {"task_graph": task_graph, "artifacts": {**existing_artifacts, **new_artifacts}}


def _build_task_context(task: Task, task_graph: TaskGraph, artifacts: dict) -> str:
    """Build context string from dependent task artifacts."""
    context_parts = []

    for dep_id in task.input.depends_on:
        # Find artifact keys from this task
        for key, artifact in artifacts.items():
            if key.startswith(dep_id):
                context_parts.append(f"From {dep_id}: {_artifact_to_string(artifact)}")

    return "\n\n".join(context_parts) if context_parts else ""


def _artifact_to_string(artifact) -> str:
    """Convert artifact to string for context injection."""
    if hasattr(artifact, '__dict__'):
        # Dataclass - convert to readable string
        parts = []
        for key, value in artifact.__dict__.items():
            if isinstance(value, str) and len(value) < 500:
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
    return str(artifact)


def post_batch(state: dict) -> dict:
    """Process batch completion and update state.

    Args:
        state: DAGExecutorState with current_batch, task_graph

    Returns:
        dict with updated completed_tasks, cleared current_batch
    """
    task_graph = state.get("task_graph")
    current_batch = state.get("current_batch", [])
    completed_tasks = state.get("completed_tasks", [])

    # Add completed tasks from batch
    if task_graph:
        for task_id in current_batch:
            task = next((t for t in task_graph.tasks if t.id == task_id), None)
            if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                if task_id not in completed_tasks:
                    completed_tasks.append(task_id)

    return {
        "completed_tasks": completed_tasks,
        "current_batch": []
    }


def should_continue(state: dict) -> bool:
    """Check if there are more tasks to execute.

    Args:
        state: DAGExecutorState with task_graph, completed_tasks

    Returns:
        True if there are pending tasks ready to execute
    """
    task_graph = state.get("task_graph")
    completed_tasks = state.get("completed_tasks", [])

    if not task_graph:
        return False

    # Check if any tasks are still pending and ready
    ready = get_ready_tasks(task_graph, completed_tasks)
    return len(ready) > 0


def build_pm_graph(mcp_tools=None):
    """Build the PM agent graph.

    This is a subgraph that creates task graphs from requests.
    """
    from langgraph.graph import StateGraph, START, END
    from graphs.contracts import PMState

    graph = StateGraph(PMState)

    # Add nodes
    graph.add_node("create_task_graph", create_task_graph)

    # Add edges
    graph.add_edge(START, "create_task_graph")
    graph.add_edge("create_task_graph", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function
# ─────────────────────────────────────────────────────────────────────────────

def decompose_request(request: str, user_id: str) -> TaskGraph:
    """Convenience function to decompose a request into a task graph.

    Args:
        request: Natural language request
        user_id: Slack user ID

    Returns:
        TaskGraph with tasks and dependencies
    """
    state = {
        "original_request": request,
        "user_id": user_id,
        "messages": []
    }

    result = create_task_graph(state)
    return result.get("task_graph")
