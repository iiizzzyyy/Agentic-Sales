"""Reviewer Agent for Hive Mind orchestration.

Output validation with read-only critique pattern (ACC-Collab).
Reviews outputs for:
- Completeness (all data sources included)
- Accuracy (numbers match source)
- Format (Slack Block Kit valid)
- Quality (actionable, clear)
"""

import json
from typing import Any, Literal
from langchain_core.messages import SystemMessage, HumanMessage

from llm_factory import get_llm
from graphs.contracts import ReviewResult, ReviewDecision, TaskOutput, Artifact
from prompts.reviewer_prompt import REVIEWER_PROMPT


# Initialize LLM
reviewer_llm = get_llm()


def parse_review_response(response_text: str) -> dict:
    """Parse the JSON response from Reviewer agent."""
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Default to changes_required with generic feedback
        return {
            "decision": "changes_required",
            "feedback": ["Could not parse review response"],
            "quality_score": 5.0
        }


def reviewer_node(state: dict) -> dict:
    """Review output from a task or graph execution.

    Args:
        state: ReviewerState with output_to_review, task_id

    Returns:
        dict with review_result populated
    """
    output_to_review = state.get("output_to_review", {})
    task_id = state.get("task_id", "")
    context = state.get("context", {})

    # Build review prompt
    prompt = REVIEWER_PROMPT.format(
        output=json.dumps(output_to_review, indent=2),
        task_id=task_id,
        context=json.dumps(context, indent=2)
    )

    response = reviewer_llm.invoke([
        SystemMessage(content="You are a Reviewer agent that validates output quality."),
        HumanMessage(content=prompt)
    ])

    parsed = parse_review_response(response.content)

    review_result = ReviewResult(
        decision=parsed.get("decision", "changes_required"),
        feedback=parsed.get("feedback", []),
        suggested_changes=parsed.get("suggested_changes", []),
        quality_score=float(parsed.get("quality_score", 5.0))
    )

    return {"review_result": review_result}


def review_output(output: TaskOutput, task_id: str = "", context: dict | None = None) -> ReviewResult:
    """Review a task output.

    Args:
        output: TaskOutput to review
        task_id: Optional task ID for context
        context: Optional context dict

    Returns:
        ReviewResult with decision and feedback
    """
    state = {
        "output_to_review": {
            "status": output.status,
            "artifacts": _summarize_artifacts(output.artifacts),
            "handoff_notes": output.handoff_notes,
            "error": output.error
        },
        "task_id": task_id,
        "context": context or {}
    }

    result = reviewer_node(state)
    return result.get("review_result")


def _summarize_artifacts(artifacts: dict) -> dict:
    """Summarize artifacts for review (avoid sending full content)."""
    summary = {}
    for name, artifact in artifacts.items():
        if hasattr(artifact, '__dict__'):
            # Summarize dataclass fields
            summary[name] = {
                k: str(v)[:200] if isinstance(v, str) else v
                for k, v in artifact.__dict__.items()
            }
        else:
            summary[name] = str(artifact)[:500]
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_completeness(output: TaskOutput, expected_sources: list[str] | None = None) -> tuple[bool, list[str]]:
    """Validate that output includes all expected data sources.

    Args:
        output: TaskOutput to validate
        expected_sources: List of expected data sources (e.g., ["hubspot", "rag", "web"])

    Returns:
        (is_complete, missing_sources)
    """
    feedback = []

    # Check if task succeeded
    if output.status == "failed":
        return (False, ["Task failed - no output to validate"])

    # Check for artifacts
    if not output.artifacts:
        feedback.append("No artifacts produced")

    # Check handoff notes
    if not output.handoff_notes:
        feedback.append("No handoff notes provided")

    # Check expected sources if provided
    if expected_sources:
        handoff = output.handoff_notes.lower()
        artifacts_str = str(output.artifacts).lower()
        combined = handoff + " " + artifacts_str

        for source in expected_sources:
            if source.lower() not in combined:
                feedback.append(f"Missing data from source: {source}")

    return (len(feedback) == 0, feedback)


def validate_format(output: TaskOutput, format_type: str = "slack") -> tuple[bool, list[str]]:
    """Validate output format.

    Args:
        output: TaskOutput to validate
        format_type: Expected format ("slack", "json", "text")

    Returns:
        (is_valid, format_errors)
    """
    feedback = []

    if format_type == "slack":
        # Check for Slack Block Kit compatibility
        # - No raw HTML tags
        # - Limited use of special characters
        # - Proper use of *bold*, _italic_, etc.

        handoff = output.handoff_notes or ""

        # Check for problematic patterns
        if "<" in handoff and ">" in handoff:
            feedback.append("Avoid HTML-like tags in Slack messages")

        # Check for proper formatting
        if handoff and not any(marker in handoff for marker in ["*", "_", "```", "•", "-"]):
            feedback.append("Consider using Slack formatting (bold, lists, etc.)")

    return (len(feedback) == 0, feedback)


def validate_accuracy(output: TaskOutput, source_data: dict | None = None) -> tuple[bool, list[str]]:
    """Validate accuracy of output against source data.

    Args:
        output: TaskOutput to validate
        source_data: Optional source data to compare against

    Returns:
        (is_accurate, accuracy_issues)
    """
    feedback = []

    # If no source data provided, do basic sanity checks
    if not source_data:
        # Check for obvious hallucination markers
        handoff = output.handoff_notes or ""
        artifacts_str = str(output.artifacts)
        combined = handoff + " " + artifacts_str

        uncertainty_markers = ["i think", "probably", "might be", "unsure", "unknown"]
        for marker in uncertainty_markers:
            if marker in combined.lower():
                feedback.append(f"Uncertain language detected: '{marker}'")

        return (len(feedback) == 0, feedback)

    # Compare against source data
    # This is a simplified check - production would do deeper validation
    for key, expected_value in source_data.items():
        output_str = str(output)
        if str(expected_value) not in output_str:
            feedback.append(f"Expected value for {key} not found in output")

    return (len(feedback) == 0, feedback)


# ─────────────────────────────────────────────────────────────────────────────
# Quality Scoring
# ─────────────────────────────────────────────────────────────────────────────

def calculate_quality_score(output: TaskOutput, review_result: ReviewResult | None = None) -> float:
    """Calculate overall quality score (1-10).

    Args:
        output: TaskOutput to score
        review_result: Optional ReviewResult from reviewer agent

    Returns:
        Quality score 1-10
    """
    score = 5.0  # Base score

    # Bonus for successful execution
    if output.status == "success":
        score += 2.0

    # Bonus for having artifacts
    if output.artifacts:
        score += 1.0

    # Bonus for having handoff notes
    if output.handoff_notes:
        score += 1.0

    # Penalty for errors
    if output.error:
        score -= 2.0

    # Adjust based on review result
    if review_result:
        if review_result.decision == "approved":
            score += 1.0
        elif review_result.decision == "blocked":
            score -= 2.0

        # Factor in quality score from review
        if review_result.quality_score:
            score = (score + review_result.quality_score) / 2

    # Clamp to 1-10 range
    return max(1.0, min(10.0, score))


# ─────────────────────────────────────────────────────────────────────────────
# Build Reviewer Graph
# ─────────────────────────────────────────────────────────────────────────────

def build_reviewer_graph():
    """Build the reviewer agent graph."""
    from langgraph.graph import StateGraph, START, END
    from graphs.contracts import ReviewerState

    graph = StateGraph(ReviewerState)

    # Add nodes
    graph.add_node("reviewer", reviewer_node)

    # Add edges
    graph.add_edge(START, "reviewer")
    graph.add_edge("reviewer", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

def review_task_output(
    output: TaskOutput,
    task_id: str = "",
    expected_sources: list[str] | None = None,
    format_type: str = "slack"
) -> ReviewResult:
    """Full review of a task output.

    Args:
        output: TaskOutput to review
        task_id: Optional task ID
        expected_sources: Optional list of expected data sources
        format_type: Expected format type

    Returns:
        ReviewResult with comprehensive feedback
    """
    # Run reviewer agent
    agent_result = review_output(output, task_id)

    # Run validation checks
    completeness_ok, completeness_issues = validate_completeness(output, expected_sources)
    format_ok, format_issues = validate_format(output, format_type)

    # Combine feedback
    all_feedback = agent_result.feedback
    if completeness_issues:
        all_feedback.extend([f"Completeness: {issue}" for issue in completeness_issues])
    if format_issues:
        all_feedback.extend([f"Format: {issue}" for issue in format_issues])

    # Determine final decision
    if agent_result.decision == "blocked":
        final_decision = "blocked"
    elif not completeness_ok or not format_ok:
        final_decision = "changes_required"
    else:
        final_decision = agent_result.decision

    return ReviewResult(
        decision=final_decision,
        feedback=all_feedback,
        suggested_changes=agent_result.suggested_changes,
        quality_score=calculate_quality_score(output, agent_result)
    )
