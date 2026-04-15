"""Load and manage sales methodology definitions."""
import os
import json

METHODOLOGIES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "playbooks", "methodologies"
)

# Built-in fallback dimensions (used when no specific methodology is selected)
DEFAULT_DIMENSIONS = {
    "discovery": [
        {"key": "opening", "label": "Opening", "description": "Personalization, rapport, agenda setting", "weight": 1.0},
        {"key": "needs_assessment", "label": "Needs Assessment", "description": "Question quality, pain point discovery", "weight": 1.0},
        {"key": "active_listening", "label": "Active Listening", "description": "Follow-ups, acknowledgment, building on answers", "weight": 1.0},
        {"key": "objection_handling", "label": "Objection Handling", "description": "Exploration, reframing, evidence use", "weight": 1.0},
        {"key": "next_steps", "label": "Next Steps", "description": "Commitment getting, specificity, follow-up plan", "weight": 1.0},
    ],
    "negotiation": [
        {"key": "value_establishment", "label": "Value Establishment", "description": "Anchoring on value before discussing price", "weight": 1.0},
        {"key": "negotiation_discipline", "label": "Negotiation Discipline", "description": "Holding firm, knowing walk-away points", "weight": 1.0},
        {"key": "creative_structuring", "label": "Creative Structuring", "description": "Multi-year, phased, bundled deal structures", "weight": 1.0},
        {"key": "composure", "label": "Composure", "description": "Staying calm under pressure and silence", "weight": 1.0},
        {"key": "closing_strength", "label": "Closing Strength", "description": "Trial closes, urgency creation, commitment", "weight": 1.0},
    ],
    "cold_call": [
        {"key": "pattern_interrupt", "label": "Pattern Interrupt", "description": "Breaking through with an unconventional opener", "weight": 1.0},
        {"key": "relevance", "label": "Relevance", "description": "Quickly establishing why you're calling and why now", "weight": 1.0},
        {"key": "value_in_30s", "label": "Value in 30 Seconds", "description": "Delivering a compelling value prop before they hang up", "weight": 1.0},
        {"key": "objection_handling", "label": "Objection Handling", "description": "Navigating brush-offs and gatekeepers", "weight": 1.0},
        {"key": "next_step", "label": "Next Step", "description": "Securing a meeting or follow-up commitment", "weight": 1.0},
    ],
    "competitive": [
        {"key": "competitive_positioning", "label": "Competitive Positioning", "description": "Differentiating without badmouthing competitors", "weight": 1.0},
        {"key": "buyer_understanding", "label": "Buyer Understanding", "description": "Understanding evaluation criteria and incumbents", "weight": 1.0},
        {"key": "evidence_proof", "label": "Evidence & Proof", "description": "Using case studies and data to back claims", "weight": 1.0},
        {"key": "strategic_questioning", "label": "Strategic Questioning", "description": "Guiding the buyer to see gaps in alternatives", "weight": 1.0},
        {"key": "closing_strength", "label": "Closing Strength", "description": "Creating urgency to choose you over competitors", "weight": 1.0},
    ],
}


def load_methodology(key):
    """Load a methodology definition. Returns dict with name, description, dimensions."""
    # Try loading from JSON file
    filepath = os.path.join(METHODOLOGIES_DIR, f"{key}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)

    # Fall back to built-in defaults
    if key in DEFAULT_DIMENSIONS:
        return {
            "name": key.replace("_", " ").title(),
            "description": f"Default {key} scoring rubric",
            "dimensions": DEFAULT_DIMENSIONS[key],
        }

    # Ultimate fallback: discovery
    return load_methodology("discovery")


def list_methodologies():
    """List all available methodology names."""
    methods = list(DEFAULT_DIMENSIONS.keys())
    if os.path.exists(METHODOLOGIES_DIR):
        for f in os.listdir(METHODOLOGIES_DIR):
            if f.endswith(".json"):
                name = f[:-5]
                if name not in methods:
                    methods.append(name)
    return methods


def build_scoring_prompt(methodology_key):
    """Build the scoring instruction for the LLM debrief prompt."""
    methodology = load_methodology(methodology_key)
    dimensions_text = "\n".join(
        f"- {d['label']} (1-10): {d['description']}"
        for d in methodology["dimensions"]
    )
    dimension_keys = ", ".join(f'"{d["key"]}"' for d in methodology["dimensions"])

    return f"""Score this roleplay using the **{methodology['name']}** methodology.

Evaluate each dimension on a 1-10 scale:
{dimensions_text}

In your JSON output, use these exact dimension keys: {dimension_keys}
Provide an overall weighted score and cite specific conversation moments for each dimension."""


def get_dimension_keys(methodology_key):
    """Get just the dimension keys for a methodology."""
    methodology = load_methodology(methodology_key)
    return [d["key"] for d in methodology["dimensions"]]
