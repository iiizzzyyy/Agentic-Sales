#!/usr/bin/env python3
"""Seed default training scenarios into the database."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import save_scenario, list_scenarios

DEFAULT_SCENARIOS = [
    {
        "name": "Discovery Call - Initial Qualification",
        "type": "discovery_call",
        "persona": "VP of Sales at mid-market SaaS company",
        "objectives": ["Uncover pain points", "Identify decision makers", "Qualify budget"],
        "difficulty": "beginner",
    },
    {
        "name": "Objection Handling - Price Concerns",
        "type": "objection_handling",
        "persona": "CFO focused on cost reduction",
        "objectives": ["Handle price objection", "Demonstrate ROI", "Reframe value"],
        "difficulty": "intermediate",
    },
    {
        "name": "Negotiation - Enterprise Deal",
        "type": "negotiation",
        "persona": "Procurement director at Fortune 500",
        "objectives": ["Navigate procurement", "Protect margins", "Close win-win"],
        "difficulty": "advanced",
    },
    {
        "name": "Product Demo - Platform Walkthrough",
        "type": "product_demo",
        "persona": "Technical evaluator + business stakeholder",
        "objectives": ["Showcase key features", "Tie features to pain points", "Handle technical questions"],
        "difficulty": "intermediate",
    },
    {
        "name": "Cold Outreach - First Contact",
        "type": "cold_outreach",
        "persona": "Warm lead from webinar attendance",
        "objectives": ["Build rapport", "Uncover interest", "Book meeting"],
        "difficulty": "beginner",
    },
]


def seed_scenarios():
    """Seed default scenarios if they don't exist."""
    existing = list_scenarios(limit=100)
    existing_names = {s["name"] for s in existing}

    created = 0
    for scenario in DEFAULT_SCENARIOS:
        if scenario["name"] not in existing_names:
            save_scenario(
                name=scenario["name"],
                scenario_type=scenario["type"],
                created_by="system",
                persona=scenario["persona"],
                objectives=scenario["objectives"],
                difficulty=scenario["difficulty"],
            )
            created += 1
            print(f"Created: {scenario['name']}")
        else:
            print(f"Skipping (exists): {scenario['name']}")

    print(f"\nDone! Created {created} new scenarios.")
    return created


if __name__ == "__main__":
    seed_scenarios()
