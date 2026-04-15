"""DAG Executor for Hive Mind orchestration.

LangGraph StateGraph with:
- Parallel batch execution
- SQLite checkpointing for fault tolerance
- Artifact passing between tasks
- Dynamic task injection
"""

import sqlite3
import json
from datetime import datetime
from typing import Any, Literal
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from graphs.contracts import (
    TaskGraph, Task, TaskStatus, TaskInput, TaskOutput,
    DAGExecutorState, Artifact
)
from graphs.pm_agent import get_ready_tasks, select_batch, execute_batch, post_batch, should_continue


# ─────────────────────────────────────────────────────────────────────────────
# SQLite Checkpoint Store
# ─────────────────────────────────────────────────────────────────────────────

CHECKPOINT_DB_PATH = "data/dag_checkpoints.db"


def get_checkpoint_connection():
    """Get SQLite connection for checkpointing."""
    import os
    os.makedirs(os.path.dirname(CHECKPOINT_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(CHECKPOINT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_checkpoint_tables():
    """Initialize checkpoint tables."""
    with get_checkpoint_connection() as conn:
        conn.executescript("""
            -- Execution checkpoints
            CREATE TABLE IF NOT EXISTS checkpoints (
                graph_id TEXT PRIMARY KEY,
                user_id TEXT,
                state_json TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'running'
            );
            CREATE INDEX IF NOT EXISTS idx_checkpoints_user ON checkpoints(user_id);
            CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoints(status);

            -- Task execution log
            CREATE TABLE IF NOT EXISTS task_execution_log (
                id TEXT PRIMARY KEY,
                graph_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                status TEXT,
                error_message TEXT,
                FOREIGN KEY (graph_id) REFERENCES checkpoints(graph_id)
            );
            CREATE INDEX IF NOT EXISTS idx_execution_log_graph ON task_execution_log(graph_id);
        """)


def save_checkpoint(graph_id: str, state: dict, status: str = "running") -> None:
    """Save execution checkpoint to SQLite."""
    with get_checkpoint_connection() as conn:
        # Serialize state (exclude non-serializable fields)
        state_copy = _serialize_state(state)

        existing = conn.execute(
            "SELECT id FROM checkpoints WHERE graph_id = ?",
            (graph_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE checkpoints
                   SET state_json = ?, updated_at = datetime('now'), status = ?
                   WHERE graph_id = ?""",
                (json.dumps(state_copy), status, graph_id)
            )
        else:
            conn.execute(
                """INSERT INTO checkpoints (graph_id, user_id, state_json, status)
                   VALUES (?, ?, ?, ?)""",
                (graph_id, state.get("user_id", ""), json.dumps(state_copy), status)
            )


def load_checkpoint(graph_id: str) -> dict | None:
    """Load execution checkpoint from SQLite."""
    with get_checkpoint_connection() as conn:
        row = conn.execute(
            "SELECT state_json FROM checkpoints WHERE graph_id = ?",
            (graph_id,)
        ).fetchone()

        if row:
            return json.loads(row["state_json"])
        return None


def delete_checkpoint(graph_id: str) -> None:
    """Delete execution checkpoint."""
    with get_checkpoint_connection() as conn:
        conn.execute("DELETE FROM checkpoints WHERE graph_id = ?", (graph_id,))


def _serialize_state(state: dict) -> dict:
    """Serialize state for JSON storage."""
    result = {}
    for key, value in state.items():
        if key == "task_graph" and isinstance(value, TaskGraph):
            result[key] = _serialize_task_graph(value)
        elif key == "artifacts":
            # Convert artifacts to serializable format
            result[key] = {k: _serialize_artifact(v) for k, v in (value or {}).items()}
        elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
            result[key] = value
        else:
            result[key] = str(value)  # Fallback for non-serializable types
    return result


def _serialize_task_graph(graph: TaskGraph) -> dict:
    """Serialize TaskGraph for JSON storage."""
    return {
        "id": graph.id,
        "tasks": [_serialize_task(t) for t in graph.tasks],
        "dependencies": graph.dependencies,
        "metadata": graph.metadata
    }


def _serialize_task(task: Task) -> dict:
    """Serialize Task for JSON storage."""
    return {
        "id": task.id,
        "input": {
            "goal": task.input.goal,
            "role": task.input.role,
            "file_scope": task.input.file_scope,
            "depends_on": task.input.depends_on,
            "context_from": task.input.context_from,
            "constraints": task.input.constraints
        },
        "output": _serialize_output(task.output) if task.output else None,
        "status": task.status,
        "created_at": task.created_at,
        "completed_at": task.completed_at
    }


def _serialize_output(output: TaskOutput) -> dict:
    """Serialize TaskOutput for JSON storage."""
    return {
        "status": output.status,
        "artifacts": {k: _serialize_artifact(v) for k, v in output.artifacts.items()},
        "files_modified": output.files_modified,
        "handoff_notes": output.handoff_notes,
        "error": output.error
    }


def _serialize_artifact(artifact) -> dict:
    """Serialize artifact for JSON storage."""
    if hasattr(artifact, '__dict__'):
        return {"__type__": artifact.__class__.__name__, **artifact.__dict__}
    return {"__type__": "unknown", "value": str(artifact)}


def log_task_execution(graph_id: str, task_id: str, status: str,
                       error_message: str | None = None) -> None:
    """Log task execution for debugging."""
    from db import generate_id

    execution_id = generate_id()
    with get_checkpoint_connection() as conn:
        conn.execute(
            """INSERT INTO task_execution_log
               (id, graph_id, task_id, started_at, completed_at, status, error_message)
               VALUES (?, ?, ?, datetime('now'), datetime('now'), ?, ?)""",
            (execution_id, graph_id, task_id, status, error_message)
        )


# ─────────────────────────────────────────────────────────────────────────────
# DAG Executor Graph
# ─────────────────────────────────────────────────────────────────────────────

def dag_executor_node(state: DAGExecutorState, mcp_tools: list | None = None) -> dict:
    """Execute a batch of tasks in the DAG."""
    task_graph = state.get("task_graph")
    current_batch = state.get("current_batch", [])
    completed_tasks = state.get("completed_tasks", [])
    artifacts = state.get("artifacts", {})

    if not task_graph or not current_batch:
        return {}

    # Execute batch
    result = execute_batch(
        {
            "task_graph": task_graph,
            "current_batch": current_batch,
            "artifacts": artifacts
        },
        mcp_tools
    )

    # Process batch completion
    post_result = post_batch({
        "task_graph": result["task_graph"],
        "current_batch": current_batch,
        "completed_tasks": completed_tasks
    })

    # Save checkpoint
    if task_graph.id:
        save_checkpoint(
            task_graph.id,
            {
                "task_graph": result["task_graph"],
                "completed_tasks": post_result["completed_tasks"],
                "artifacts": result["artifacts"],
                "user_id": state.get("user_id")
            }
        )

    # Log task executions
    for task_id in current_batch:
        task = next((t for t in task_graph.tasks if t.id == task_id), None)
        if task:
            log_task_execution(
                task_graph.id,
                task_id,
                task.status,
                task.output.error if task.output else None
            )

    return {
        "task_graph": result["task_graph"],
        "artifacts": result["artifacts"],
        "completed_tasks": post_result["completed_tasks"]
    }


def build_dag_executor_graph(mcp_tools=None):
    """Build the DAG executor graph with checkpointing.

    This is a subgraph that executes task graphs created by the PM agent.
    """
    graph = StateGraph(DAGExecutorState)

    # Add nodes
    graph.add_node("select_batch", select_batch)
    graph.add_node("execute_batch", lambda state: dag_executor_node(state, mcp_tools))

    # Add edges
    graph.add_edge(START, "select_batch")
    graph.add_edge("select_batch", "execute_batch")
    graph.add_conditional_edges(
        "execute_batch",
        lambda state: "continue" if should_continue(state) else "done",
        {
            "continue": "select_batch",
            "done": END
        }
    )

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Main Orchestrator (Triage → PM → DAG Executor)
# ─────────────────────────────────────────────────────────────────────────────

def build_full_orchestrator_graph(mcp_tools=None):
    """Build the full orchestrator graph: Triage → PM → DAG Executor.

    This combines triage, PM agent, and DAG executor into a single graph.
    """
    from graphs.triage import triage_node, triage_decision, direct_executor_node, workflow_router
    from graphs.pm_agent import create_task_graph

    graph = StateGraph(DAGExecutorState)

    # Triage layer
    graph.add_node("triage", triage_node)
    graph.add_node("direct_executor", lambda state: direct_executor_node(state))
    graph.add_node("pm_agent", create_task_graph)
    graph.add_node("dag_executor", lambda state: dag_executor_node(state, mcp_tools))

    # Conditional routing from triage
    graph.add_edge(START, "triage")
    graph.add_conditional_edges("triage", triage_decision, {
        "direct_executor": "direct_executor",
        "workflow_router": "workflow_router",
        "pm_agent": "pm_agent"
    })

    # Direct executor → END
    graph.add_edge("direct_executor", END)

    # PM → DAG Executor → loop or END
    graph.add_edge("pm_agent", "select_batch")
    graph.add_node("select_batch", select_batch)
    graph.add_edge("select_batch", "dag_executor")
    graph.add_conditional_edges(
        "dag_executor",
        lambda state: "continue" if should_continue(state) else "done",
        {
            "continue": "select_batch",
            "done": END
        }
    )

    # Placeholder for workflow router (coach/assistant)
    def workflow_router_placeholder(state: dict) -> str:
        route = state.get("route", "assistant")
        return route

    graph.add_conditional_edges("workflow_router", workflow_router_placeholder, {
        "coach": "coach",
        "assistant": "assistant"
    })

    # Placeholder nodes for coach/assistant (should be replaced with actual subgraphs)
    def coach_placeholder(state: dict) -> dict:
        return {"messages": state.get("messages", []) + [{"content": "[Coach subgraph]"}]}

    def assistant_placeholder(state: dict) -> dict:
        return {"messages": state.get("messages", []) + [{"content": "[Assistant subgraph]"}]}

    graph.add_node("coach", coach_placeholder)
    graph.add_node("assistant", assistant_placeholder)
    graph.add_edge("coach", END)
    graph.add_edge("assistant", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_dag_executor():
    """Initialize DAG executor (checkpoint tables)."""
    init_checkpoint_tables()
