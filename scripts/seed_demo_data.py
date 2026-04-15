"""Seed the SQLite database with synthetic training data for demos."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, save_training_session, log_engagement, generate_id
from datetime import datetime, timedelta
import random

MOCK_USERS = ["U_SARAH", "U_MIKE", "U_ALEX", "U_JORDAN"]
SCENARIO_TYPES = ["discovery", "negotiation", "competitive", "cold_call", "objection"]
COMPANIES = ["NovaTech", "Apex Systems", "CloudBridge", "Velocity Corp", "QuantumLeap"]

DIMENSION_SETS = {
    "discovery": ["opening", "needs_assessment", "active_listening", "objection_handling", "next_steps"],
    "negotiation": ["value_establishment", "negotiation_discipline", "creative_structuring", "composure", "closing_strength"],
    "competitive": ["competitive_positioning", "buyer_understanding", "evidence_proof", "strategic_questioning"],
    "cold_call": ["pattern_interrupt", "relevance", "value_in_30s", "objection_handling", "next_step"],
    "objection": ["empathy", "reframing", "evidence_use", "pivot_skill", "confidence"],
}


def seed():
    init_db()

    # Skill profiles per user (some users weak in certain areas)
    profiles = {
        "U_SARAH": {"base": 7.5, "weak": ["negotiation_discipline", "composure"], "strong": ["opening", "needs_assessment"]},
        "U_MIKE": {"base": 6.0, "weak": ["needs_assessment", "active_listening", "opening"], "strong": ["objection_handling"]},
        "U_ALEX": {"base": 5.0, "weak": ["opening", "needs_assessment", "value_establishment", "pattern_interrupt"], "strong": []},
        "U_JORDAN": {"base": 7.0, "weak": ["closing_strength"], "strong": ["competitive_positioning", "evidence_proof"]},
    }

    now = datetime.now()
    total_sessions = 0

    for user_id in MOCK_USERS:
        profile = profiles[user_id]
        # Generate 8-15 sessions over the past 30 days
        num_sessions = random.randint(8, 15)
        total_sessions += num_sessions

        for i in range(num_sessions):
            days_ago = random.randint(0, 30)
            scenario_type = random.choice(SCENARIO_TYPES)
            dims = DIMENSION_SETS[scenario_type]
            company = random.choice(COMPANIES)

            # Generate scores based on user profile
            dimensions = {}
            for dim in dims:
                base = profile["base"]
                if dim in profile["weak"]:
                    base -= random.uniform(1.0, 2.5)
                elif dim in profile["strong"]:
                    base += random.uniform(0.5, 1.5)
                # Add slight improvement over time (later sessions score slightly higher)
                time_bonus = (num_sessions - i) * -0.05  # Earlier sessions slightly worse
                score = max(1, min(10, base + random.uniform(-1.0, 1.0) + time_bonus))
                dimensions[dim] = round(score, 1)

            overall = round(sum(dimensions.values()) / len(dimensions), 1)

            save_training_session(
                user_id=user_id,
                session_type="roleplay",
                overall_score=overall,
                dimensions=dimensions,
                scenario=f"{scenario_type.title()} Call — {company}",
                scenario_type=scenario_type,
                strengths=["Good rapport building", "Clear value articulation"],
                improvements=["Ask deeper discovery questions", "Handle silence better"],
                turns=random.randint(3, 6),
                methodology=scenario_type,
                company=company,
                persona=f"VP at {company}",
            )

            # Also log engagement events
            log_engagement(user_id, "command", command="/coach")
            log_engagement(user_id, "debrief", command="/coach", scenario_type=scenario_type)

        # Log some other engagement events
        for _ in range(random.randint(5, 20)):
            cmd = random.choice(["/research", "/deal", "/pipeline", "/ask", "/objection", "/forecast"])
            log_engagement(user_id, "command", command=cmd)

    print(f"Seeded {total_sessions} training sessions for {len(MOCK_USERS)} users")
    print(f"Database: {os.path.abspath('data/salescoach.db')}")


if __name__ == "__main__":
    seed()
