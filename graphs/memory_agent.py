"""Memory agent for Hive Mind orchestration.

SQLite-backed memory system for storing and retrieving:
- User preferences
- Project lessons
- Execution failures
- Successful patterns
"""

import sqlite3
import json
from datetime import datetime
from typing import Any, Literal
from db import get_db, generate_id


# ─────────────────────────────────────────────────────────────────────────────
# Database Schema Extensions
# ─────────────────────────────────────────────────────────────────────────────

def init_memory_tables():
    """Initialize memory tables. Call this during app startup."""
    with get_db() as conn:
        conn.executescript("""
            -- User preferences (persistent across sessions)
            CREATE TABLE IF NOT EXISTS user_preferences (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, preference_key)
            );
            CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id);

            -- Project lessons (learned from executions)
            CREATE TABLE IF NOT EXISTS project_lessons (
                id TEXT PRIMARY KEY,
                lesson_text TEXT NOT NULL,
                context_tags TEXT NOT NULL,
                confidence_score REAL DEFAULT 0.5,
                source_task_type TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                times_used INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_lessons_tags ON project_lessons(context_tags);
            CREATE INDEX IF NOT EXISTS idx_lessons_confidence ON project_lessons(confidence_score);

            -- Execution failures (for learning)
            CREATE TABLE IF NOT EXISTS execution_failures (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                workflow_type TEXT,
                error_message TEXT NOT NULL,
                root_cause TEXT,
                resolution TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                recurrence_count INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_failures_type ON execution_failures(task_type);

            -- Successful patterns (for reinforcement)
            CREATE TABLE IF NOT EXISTS successful_patterns (
                id TEXT PRIMARY KEY,
                pattern_name TEXT NOT NULL,
                description TEXT NOT NULL,
                applicable_workflows TEXT NOT NULL,
                example_context TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                times_applied INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_patterns_workflows ON successful_patterns(applicable_workflows);
        """)


# ─────────────────────────────────────────────────────────────────────────────
# User Preferences
# ─────────────────────────────────────────────────────────────────────────────

def get_user_preferences(user_id: str) -> dict[str, Any]:
    """Get all preferences for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return {row["preference_key"]: json.loads(row["preference_value"]) for row in rows}


def get_user_preference(user_id: str, key: str, default: Any = None) -> Any:
    """Get a single preference for a user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT preference_value FROM user_preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, key)
        ).fetchone()
        if row:
            return json.loads(row["preference_value"])
        return default


def set_user_preference(user_id: str, key: str, value: Any) -> None:
    """Set a preference for a user."""
    pref_id = generate_id()
    with get_db() as conn:
        # Check if exists
        existing = conn.execute(
            "SELECT id FROM user_preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, key)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE user_preferences
                   SET preference_value = ?, updated_at = datetime('now')
                   WHERE user_id = ? AND preference_key = ?""",
                (json.dumps(value), user_id, key)
            )
        else:
            conn.execute(
                """INSERT INTO user_preferences (id, user_id, preference_key, preference_value)
                   VALUES (?, ?, ?, ?)""",
                (pref_id, user_id, key, json.dumps(value))
            )


def delete_user_preference(user_id: str, key: str) -> None:
    """Delete a preference for a user."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM user_preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, key)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Project Lessons
# ─────────────────────────────────────────────────────────────────────────────

def record_lesson(lesson_text: str, context_tags: list[str], confidence_score: float = 0.5,
                  source_task_type: str | None = None) -> str:
    """Record a lesson learned from execution."""
    lesson_id = generate_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO project_lessons (id, lesson_text, context_tags, confidence_score, source_task_type)
               VALUES (?, ?, ?, ?, ?)""",
            (lesson_id, lesson_text, json.dumps(context_tags), confidence_score, source_task_type)
        )
    return lesson_id


def query_lessons(context_tags: list[str], min_confidence: float = 0.3, limit: int = 5) -> list[dict[str, Any]]:
    """Query lessons relevant to given context tags."""
    with get_db() as conn:
        # Simple tag matching - lessons that share any context tag
        rows = conn.execute(
            """SELECT * FROM project_lessons
               WHERE confidence_score >= ?
               AND context_tags LIKE ?
               ORDER BY confidence_score DESC, times_used DESC
               LIMIT ?""",
            (min_confidence, f'%{json.dumps(context_tags)}%', limit)
        ).fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["context_tags"] = json.loads(result["context_tags"])
            results.append(result)
        return results


def increment_lesson_usage(lesson_id: str) -> None:
    """Increment the usage count for a lesson."""
    with get_db() as conn:
        conn.execute(
            "UPDATE project_lessons SET times_used = times_used + 1 WHERE id = ?",
            (lesson_id,)
        )


def update_lesson_confidence(lesson_id: str, new_confidence: float) -> None:
    """Update the confidence score for a lesson."""
    with get_db() as conn:
        conn.execute(
            "UPDATE project_lessons SET confidence_score = ? WHERE id = ?",
            (new_confidence, lesson_id)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Execution Failures
# ─────────────────────────────────────────────────────────────────────────────

def record_failure(task_type: str, error_message: str, workflow_type: str | None = None,
                   root_cause: str | None = None, resolution: str | None = None) -> str:
    """Record an execution failure."""
    failure_id = generate_id()
    with get_db() as conn:
        # Check if similar failure exists
        existing = conn.execute(
            """SELECT id, recurrence_count FROM execution_failures
               WHERE task_type = ? AND error_message = ?""",
            (task_type, error_message)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE execution_failures
                   SET recurrence_count = recurrence_count + 1,
                       root_cause = COALESCE(?, root_cause),
                       resolution = COALESCE(?, resolution)
                   WHERE id = ?""",
                (root_cause, resolution, existing["id"])
            )
            return existing["id"]
        else:
            conn.execute(
                """INSERT INTO execution_failures
                   (id, task_type, workflow_type, error_message, root_cause, resolution)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (failure_id, task_type, workflow_type, error_message, root_cause, resolution)
            )
            return failure_id


def get_similar_failures(task_type: str, workflow_type: str | None = None) -> list[dict[str, Any]]:
    """Get similar failures for context injection."""
    with get_db() as conn:
        query = "SELECT * FROM execution_failures WHERE task_type = ?"
        params = [task_type]

        if workflow_type:
            query += " AND workflow_type = ?"
            params.append(workflow_type)

        query += " ORDER BY created_at DESC LIMIT 5"

        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_failure_root_causes(task_type: str) -> list[str]:
    """Get known root causes for a task type."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT root_cause FROM execution_failures
               WHERE task_type = ? AND root_cause IS NOT NULL""",
            (task_type,)
        ).fetchall()
        return [row["root_cause"] for row in rows if row["root_cause"]]


# ─────────────────────────────────────────────────────────────────────────────
# Successful Patterns
# ─────────────────────────────────────────────────────────────────────────────

def record_pattern(pattern_name: str, description: str, applicable_workflows: list[str],
                   example_context: str | None = None) -> str:
    """Record a successful pattern."""
    pattern_id = generate_id()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO successful_patterns
               (id, pattern_name, description, applicable_workflows, example_context)
               VALUES (?, ?, ?, ?, ?)""",
            (pattern_id, pattern_name, description, json.dumps(applicable_workflows), example_context)
        )
    return pattern_id


def query_patterns(workflow_type: str) -> list[dict[str, Any]]:
    """Query patterns applicable to a workflow."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM successful_patterns
               WHERE applicable_workflows LIKE ?
               ORDER BY times_applied DESC""",
            (f'%{workflow_type}%',)
        ).fetchall()

        results = []
        for row in rows:
            result = dict(row)
            result["applicable_workflows"] = json.loads(result["applicable_workflows"])
            results.append(result)
        return results


def increment_pattern_usage(pattern_id: str) -> None:
    """Increment the usage count for a pattern."""
    with get_db() as conn:
        conn.execute(
            "UPDATE successful_patterns SET times_applied = times_applied + 1 WHERE id = ?",
            (pattern_id,)
        )


# ─────────────────────────────────────────────────────────────────────────────
# Memory Agent Class
# ─────────────────────────────────────────────────────────────────────────────

class MemoryAgent:
    """Agent for managing memory operations."""

    def __init__(self):
        pass

    def update_project_memory(self, task_output: dict, context_tags: list[str]) -> dict:
        """Extract and store lessons from task execution.

        Args:
            task_output: TaskOutput dict from completed task
            context_tags: Tags for context (e.g., ["qbr", "research", "hubspot"])

        Returns:
            dict with lessons_recorded, patterns_recorded counts
        """
        result = {"lessons_recorded": 0, "patterns_recorded": 0, "failures_recorded": 0}

        # Check for failures
        if task_output.get("status") == "failed" and task_output.get("error"):
            record_failure(
                task_type=context_tags[0] if context_tags else "unknown",
                error_message=task_output["error"],
                workflow_type=context_tags[1] if len(context_tags) > 1 else None
            )
            result["failures_recorded"] = 1

        # Extract lessons from handoff_notes
        handoff_notes = task_output.get("handoff_notes", "")
        if handoff_notes:
            # Look for lesson-like statements
            lesson_indicators = ["learned", "discovered", "important", "note:", "remember"]
            for indicator in lesson_indicators:
                if indicator.lower() in handoff_notes.lower():
                    record_lesson(
                        lesson_text=handoff_notes,
                        context_tags=context_tags,
                        confidence_score=0.7
                    )
                    result["lessons_recorded"] += 1
                    break

        return result

    def inject_memory_context(self, user_id: str, context_tags: list[str],
                               workflow_type: str | None = None) -> str:
        """Build memory context string for injection into prompts.

        Args:
            user_id: Slack user ID
            context_tags: Tags for context matching
            workflow_type: Optional workflow type for pattern matching

        Returns:
            Formatted memory context string for prompt injection
        """
        context_parts = []

        # Get user preferences
        prefs = get_user_preferences(user_id)
        if prefs:
            prefs_str = ", ".join(f"{k}={v}" for k, v in prefs.items())
            context_parts.append(f"USER PREFERENCES: {prefs_str}")

        # Get relevant lessons
        lessons = query_lessons(context_tags, min_confidence=0.3, limit=3)
        if lessons:
            lessons_str = "\n".join(f"- {l['lesson_text']}" for l in lessons)
            context_parts.append(f"RELEVANT LESSONS:\n{lessons_str}")

        # Get patterns for this workflow
        if workflow_type:
            patterns = query_patterns(workflow_type)
            if patterns:
                patterns_str = "\n".join(f"- {p['pattern_name']}: {p['description']}" for p in patterns)
                context_parts.append(f"SUCCESSFUL PATTERNS:\n{patterns_str}")

        # Get known failure modes to avoid
        if context_tags:
            failures = get_similar_failures(context_tags[0], workflow_type)
            if failures:
                failure_str = "\n".join(f"- AVOID: {f['error_message']} (cause: {f['root_cause']})"
                                        for f in failures if f.get('root_cause'))
                context_parts.append(f"KNOWN FAILURE MODES:\n{failure_str}")

        return "\n\n".join(context_parts) if context_parts else ""


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

_memory_agent = MemoryAgent()


def update_memory(task_output: dict, context_tags: list[str]) -> dict:
    """Convenience function to update memory from task output."""
    return _memory_agent.update_project_memory(task_output, context_tags)


def inject_memory(user_id: str, context_tags: list[str], workflow_type: str | None = None) -> str:
    """Convenience function to inject memory context."""
    return _memory_agent.inject_memory_context(user_id, context_tags, workflow_type)
