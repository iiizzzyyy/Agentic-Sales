"""Block Kit formatter for skill gap analysis."""
import json
from formatters.helpers import timestamp


def format_skill_gaps(user_id, analysis):
    """Format skill gap analysis as Block Kit blocks."""
    if analysis["status"] == "insufficient_data":
        return _format_insufficient_data(user_id, analysis)

    gaps = analysis["gaps"]
    strengths = analysis["strengths"]
    total = analysis["total_sessions"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Skill Analysis", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"<@{user_id}> · Based on {total} training sessions"}]
        },
        {"type": "divider"},
    ]

    # Gaps section
    if gaps:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Areas Needing Improvement*"}
        })
        for gap in gaps:
            trend_icon = {"improving": "↑", "declining": "↓", "flat": "→"}.get(gap["trend"], "")
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":red_circle: *{_format_dimension(gap['dimension'])}* — {gap['avg_score']}/10 {trend_icon}\n"
                        f"_{gap['recommendation']}_"
                    )
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Practice This", "emoji": True},
                    "action_id": "practice_skill_gap",
                    "value": json.dumps({"dimension": gap["dimension"], "scenario_type": _dim_to_scenario(gap["dimension"])}),
                }
            })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":white_check_mark: *No significant skill gaps detected.* All dimensions averaging 6.0+ across sessions."}
        })

    blocks.append({"type": "divider"})

    # Strengths section
    if strengths:
        strength_lines = " · ".join(
            f":large_green_circle: {_format_dimension(s['dimension'])} ({s['avg_score']}/10)"
            for s in strengths[:4]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Strengths:* {strength_lines}"}
        })
        blocks.append({"type": "divider"})

    # Actions
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Training History", "emoji": True},
                "action_id": "view_training_history",
                "value": user_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Start Practice", "emoji": True},
                "action_id": "start_new_practice",
                "style": "primary",
            },
        ]
    })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"SalesCoach AI · {timestamp()}"}]
    })

    fallback = f"Skill Analysis: {len(gaps)} gaps found, {len(strengths)} strengths across {total} sessions"
    return blocks, fallback


def _format_insufficient_data(user_id, analysis):
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                f"Not enough data yet for <@{user_id}>. "
                f"Completed {analysis['total_sessions']} of {analysis['needed']} sessions needed.\n\n"
                f"Run `/coach roleplay` to start building your skill profile."
            )}
        }
    ]
    return blocks, f"Skill analysis: need {analysis['needed'] - analysis['total_sessions']} more sessions"


def _format_dimension(dim):
    return dim.replace("_", " ").title()


def _dim_to_scenario(dim):
    """Map a dimension to its most relevant scenario type."""
    mapping = {
        "opening": "cold_call", "needs_assessment": "discovery", "active_listening": "discovery",
        "objection_handling": "objection", "next_steps": "discovery",
        "value_establishment": "negotiation", "negotiation_discipline": "negotiation",
        "creative_structuring": "negotiation", "composure": "negotiation", "closing_strength": "negotiation",
        "competitive_positioning": "competitive", "buyer_understanding": "competitive",
        "evidence_proof": "competitive", "strategic_questioning": "competitive",
        "pattern_interrupt": "cold_call", "relevance": "cold_call",
        "value_in_30s": "cold_call", "next_step": "cold_call",
        # MEDDIC
        "metrics": "discovery", "economic_buyer": "discovery", "decision_criteria": "discovery",
        "decision_process": "discovery", "identify_pain": "discovery", "champion": "discovery",
        # SPIN
        "situation_questions": "discovery", "problem_questions": "discovery",
        "implication_questions": "discovery", "need_payoff_questions": "discovery",
        # Challenger
        "commercial_teaching": "discovery", "tailoring": "discovery", "taking_control": "negotiation",
        "constructive_tension": "negotiation", "value_articulation": "negotiation",
        # BANT
        "budget": "discovery", "authority": "discovery", "need": "discovery", "timeline": "discovery",
    }
    return mapping.get(dim, "discovery")
