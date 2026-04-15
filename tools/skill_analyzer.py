"""Analyze training history to detect skill gaps using SQLite aggregation."""
from db import get_db


def analyze_skill_gaps(user_id, min_sessions=3):
    """Identify consistent weak skill dimensions for a user.

    Returns dict with:
      - gaps: list of weak dimensions (avg < 6.0)
      - strengths: list of strong dimensions (avg >= 7.5)
      - total_sessions: number of sessions analyzed
      - status: 'ok' | 'insufficient_data'
    """
    with get_db() as conn:
        # Check total sessions
        count = conn.execute(
            "SELECT COUNT(*) FROM training_sessions WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

        if count < min_sessions:
            return {"status": "insufficient_data", "total_sessions": count, "needed": min_sessions}

        # Get dimension averages with trend
        rows = conn.execute("""
            SELECT
                ds.dimension,
                AVG(ds.score) as avg_score,
                COUNT(*) as session_count,
                -- Get the score from the oldest and newest sessions for trend
                (SELECT ds2.score FROM dimension_scores ds2
                 JOIN training_sessions ts2 ON ds2.session_id = ts2.id
                 WHERE ts2.user_id = ? AND ds2.dimension = ds.dimension
                 ORDER BY ts2.timestamp DESC LIMIT 1
                ) as latest_score,
                (SELECT ds3.score FROM dimension_scores ds3
                 JOIN training_sessions ts3 ON ds3.session_id = ts3.id
                 WHERE ts3.user_id = ? AND ds3.dimension = ds.dimension
                 ORDER BY ts3.timestamp ASC LIMIT 1
                ) as oldest_score
            FROM dimension_scores ds
            JOIN training_sessions ts ON ds.session_id = ts.id
            WHERE ts.user_id = ?
            GROUP BY ds.dimension
            HAVING COUNT(*) >= ?
            ORDER BY avg_score ASC
        """, (user_id, user_id, user_id, min_sessions)).fetchall()

        gaps = []
        strengths = []

        for row in rows:
            dim_data = {
                "dimension": row["dimension"],
                "avg_score": round(row["avg_score"], 1),
                "session_count": row["session_count"],
                "latest_score": row["latest_score"],
                "trend": _calc_trend(row["oldest_score"], row["latest_score"]),
                "recommendation": _get_recommendation(row["dimension"], row["avg_score"]),
            }

            if row["avg_score"] < 6.0:
                gaps.append(dim_data)
            elif row["avg_score"] >= 7.5:
                strengths.append(dim_data)

        return {
            "status": "ok",
            "gaps": gaps,
            "strengths": sorted(strengths, key=lambda x: x["avg_score"], reverse=True),
            "total_sessions": count,
        }


def _calc_trend(oldest, latest):
    if oldest is None or latest is None:
        return "unknown"
    diff = latest - oldest
    if diff > 0.5:
        return "improving"
    elif diff < -0.5:
        return "declining"
    return "flat"


RECOMMENDATIONS = {
    "opening": "Practice cold call pattern interrupts and personalized openers",
    "needs_assessment": "Focus on open-ended discovery questions — try SPIN scenarios",
    "active_listening": "Practice paraphrasing and silence — let the prospect talk more",
    "objection_handling": "Run objection-specific roleplays — especially budget and timing",
    "next_steps": "Practice commitment-getting closes — always end with a concrete next step",
    "value_establishment": "Lead with business impact before discussing features",
    "negotiation_discipline": "Practice holding firm on pricing — use value justification",
    "creative_structuring": "Explore multi-year deals, phased rollouts, and bundling",
    "composure": "Practice staying calm under pressure — try aggressive buyer personas",
    "closing_strength": "Work on trial close techniques and urgency creation",
    "competitive_positioning": "Study battle cards and practice 'Why us' storytelling",
    "buyer_understanding": "Ask about evaluation criteria and decision process earlier",
    "evidence_proof": "Lead with case studies and quantified outcomes",
    "strategic_questioning": "Practice Socratic questioning — guide instead of tell",
    "pattern_interrupt": "Try unconventional openers that break the 'not interested' reflex",
    "relevance": "Research the prospect's specific pain before the call",
    "value_in_30s": "Craft and practice a 30-second value prop specific to each vertical",
    # MEDDIC dimensions
    "metrics": "Practice quantifying business impact with specific numbers and ROI",
    "economic_buyer": "Ask who controls the budget and get access to that person",
    "decision_criteria": "Uncover exactly how the prospect will evaluate vendors",
    "decision_process": "Map all stakeholders and approval steps early in the deal",
    "identify_pain": "Dig deeper — ask 'Why is that a problem?' at least twice",
    "champion": "Find someone internally who will advocate for your solution",
    # SPIN dimensions
    "situation_questions": "Gather context but keep situation questions brief",
    "problem_questions": "Uncover specific frustrations and difficulties",
    "implication_questions": "Explore the ripple effects of problems across the org",
    "need_payoff_questions": "Guide the prospect to articulate the value themselves",
    # Challenger dimensions
    "commercial_teaching": "Share unique insights that reframe how they see their problem",
    "tailoring": "Customize your pitch to their specific role and industry",
    "taking_control": "Be assertive — guide the conversation with confidence",
    "constructive_tension": "Respectfully challenge assumptions to create urgency",
    "value_articulation": "Connect your solution to quantified business outcomes",
    # BANT dimensions
    "budget": "Ask about investment range and funding source early",
    "authority": "Identify the decision maker and approval chain",
    "need": "Ensure there's a genuine, compelling business need",
    "timeline": "Determine urgency and expected implementation date",
}


def _get_recommendation(dimension, avg_score):
    base = RECOMMENDATIONS.get(dimension, f"Practice {dimension.replace('_', ' ')} scenarios")
    if avg_score < 4:
        return f"Priority: {base}"
    return base
