"""Emit odyssey/personas/*.yaml from the 1290-dim MatrAIx schema in odyssey/dimensions.json.

All personas carry the SAME dimension set and differ only in the values, so any
behavioural difference on a task is attributable to the values, not to one
persona simply having more attributes rendered into its prompt.

Every value is checked against the schema's allowed values -- a typo fails here
rather than silently rendering a dimension the schema never defined.

    python odyssey/make_personas.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent / "dimensions.json"   # MatrAIx persona schema
OUT = Path(__file__).resolve().parent / "personas"

# 32 shopping-relevant dimensions, picked from the 1290-dim space. Every
# profile is compatible with the fixed facts shared by the six Shopping tasks
# (parent/family context and a household with cars), while varying purchasing
# resources, decision style, risk, detail preference, and technology use.
DIMENSIONS = (
    "age_bracket", "socioeconomic_band", "demo_parental_status",
    "demo_driver_status", "seniority", "domain", "role_function",
    "primary_language", "english_proficiency", "tech_savviness",
    "skill_budgeting", "skill_research", "ind_e_commerce", "topic_cars",
    "topic_fashion", "topic_sports", "lstyle_shopping_style",
    "lstyle_frugality", "lstyle_fashion_sense", "lstyle_subscription_count",
    "economic_motivation", "pref_save_vs_spend", "risk_tolerance",
    "decision_style", "trust_level", "time_pressure", "att_online_reviews",
    "cog_detail_orientation", "cog_patience", "pref_detail_brief_vs_full",
    "device_context", "health_vision",
)

PROFILES: dict[str, dict] = {
    "shopping-budget-young-parent": {
        "note": "Budget-conscious, phone-first young parent and daily driver; "
                "digitally fluent, quick to compare prices, and low on patience.",
        "values": {
            "age_bracket": "25-34",
            "socioeconomic_band": "Lower-middle",
            "demo_parental_status": "Parent of minors",
            "demo_driver_status": "Daily driver",
            "seniority": "Entry",
            "domain": "Education",
            "role_function": "Operations",
            "primary_language": "English",
            "english_proficiency": "Native",
            "tech_savviness": "Digital native",
            "skill_budgeting": "Intermediate",
            "skill_research": "Intermediate",
            "ind_e_commerce": "Experienced",
            "topic_cars": "Interested",
            "topic_fashion": "Interested",
            "topic_sports": "Passionate",
            "lstyle_shopping_style": "Bargain hunter",
            "lstyle_frugality": "Frugal saver",
            "lstyle_fashion_sense": "Trend-follower",
            "lstyle_subscription_count": "3-5",
            "economic_motivation": "Cost-sensitive",
            "pref_save_vs_spend": "Hard saver",
            "risk_tolerance": "Risk-tolerant",
            "decision_style": "Intuitive",
            "trust_level": "Trusting",
            "time_pressure": "Deadline",
            "att_online_reviews": "Enthusiast",
            "cog_detail_orientation": "Low",
            "cog_patience": "Low",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "device_context": "Mobile, on-the-go",
            "health_vision": "Corrected",
        },
    },
    "shopping-cautious-retiree": {
        "note": "Retired grandparent in a multigenerational household; cautious "
                "with money, risk, and technology, with low vision and a gist preference.",
        "values": {
            "age_bracket": "65-74",
            "socioeconomic_band": "Middle",
            "demo_parental_status": "Grandparent",
            "demo_driver_status": "Licensed, rarely drives",
            "seniority": "Retired",
            "domain": "Skilled Trades",
            "role_function": "Operations",
            "primary_language": "English",
            "english_proficiency": "Native",
            "tech_savviness": "Reluctant",
            "skill_budgeting": "Intermediate",
            "skill_research": "Beginner",
            "ind_e_commerce": "Some exposure",
            "topic_cars": "Neutral",
            "topic_fashion": "Indifferent",
            "topic_sports": "Neutral",
            "lstyle_shopping_style": "Minimalist",
            "lstyle_frugality": "Frugal saver",
            "lstyle_fashion_sense": "Classic",
            "lstyle_subscription_count": "0-2",
            "economic_motivation": "Cost-sensitive",
            "pref_save_vs_spend": "Hard saver",
            "risk_tolerance": "Risk-averse",
            "decision_style": "Deliberative",
            "trust_level": "Skeptical",
            "time_pressure": "No rush",
            "att_online_reviews": "Skeptical",
            "cog_detail_orientation": "Moderate",
            "cog_patience": "High",
            "pref_detail_brief_vs_full": "Just the gist",
            "device_context": "Accessibility tool",
            "health_vision": "Low vision",
        },
    },
    "shopping-busy-parent": {
        "note": "Time-pressed middle-income operations manager, parent, and daily "
                "driver who prioritizes family practicality and overall value.",
        "values": {
            "age_bracket": "35-44",
            "socioeconomic_band": "Middle",
            "demo_parental_status": "Parent of minors",
            "demo_driver_status": "Daily driver",
            "seniority": "Manager",
            "domain": "Business & Management",
            "role_function": "Operations",
            "primary_language": "English",
            "english_proficiency": "Native",
            "tech_savviness": "Comfortable",
            "skill_budgeting": "Advanced",
            "skill_research": "Intermediate",
            "ind_e_commerce": "Some exposure",
            "topic_cars": "Interested",
            "topic_fashion": "Neutral",
            "topic_sports": "Interested",
            "lstyle_shopping_style": "Researcher",
            "lstyle_frugality": "Balanced",
            "lstyle_fashion_sense": "Practical",
            "lstyle_subscription_count": "3-5",
            "economic_motivation": "Value-driven",
            "pref_save_vs_spend": "Saver-leaning",
            "risk_tolerance": "Cautious",
            "decision_style": "Consensus-driven",
            "trust_level": "Verifying",
            "time_pressure": "Deadline",
            "att_online_reviews": "Positive",
            "cog_detail_orientation": "Moderate",
            "cog_patience": "Low",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "device_context": "Mobile, on-the-go",
            "health_vision": "Normal",
        },
    },
    "shopping-premium-researcher": {
        "note": "Affluent parent and e-commerce research director who is highly "
                "analytical, detail-oriented, evidence-seeking, and quality-first.",
        "values": {
            "age_bracket": "45-54",
            "socioeconomic_band": "High income",
            "demo_parental_status": "Parent of adults",
            "demo_driver_status": "Daily driver",
            "seniority": "Director",
            "domain": "Business & Management",
            "role_function": "Research",
            "primary_language": "English",
            "english_proficiency": "Native",
            "tech_savviness": "Digital native",
            "skill_budgeting": "Master",
            "skill_research": "Master",
            "ind_e_commerce": "Veteran",
            "topic_cars": "Passionate",
            "topic_fashion": "Passionate",
            "topic_sports": "Interested",
            "lstyle_shopping_style": "Researcher",
            "lstyle_frugality": "Spender",
            "lstyle_fashion_sense": "Trend-setter",
            "lstyle_subscription_count": "6-10",
            "economic_motivation": "Premium-seeking",
            "pref_save_vs_spend": "Spender-leaning",
            "risk_tolerance": "Balanced",
            "decision_style": "Analytical",
            "trust_level": "Verifying",
            "time_pressure": "No rush",
            "att_online_reviews": "Skeptical",
            "cog_detail_orientation": "Very high",
            "cog_patience": "High",
            "pref_detail_brief_vs_full": "Every detail",
            "device_context": "Desktop, focused",
            "health_vision": "Normal",
        },
    },
}


def main() -> None:
    schema = {d["id"]: d for d in json.loads(SCHEMA.read_text(encoding="utf-8"))["dimensions"]}
    missing = [d for d in DIMENSIONS if d not in schema]
    assert not missing, f"not in dimensions.json: {missing}"

    OUT.mkdir(parents=True, exist_ok=True)
    for name, profile in PROFILES.items():
        assert set(profile["values"]) == set(DIMENSIONS), (
            f"{name} must set exactly the shared dimension set; "
            f"missing={set(DIMENSIONS) - set(profile['values'])} "
            f"extra={set(profile['values']) - set(DIMENSIONS)}"
        )
        attributes = {}
        for dim_id in DIMENSIONS:
            spec, value = schema[dim_id], profile["values"][dim_id]
            assert value in spec["values"], (
                f"{name}.{dim_id}: {value!r} not allowed; options: {spec['values']}"
            )
            attributes[dim_id] = {
                "value": value,
                "label": spec["label"],
                "category": spec["category"],
            }
        doc = {
            "persona_id": f"odyssey-{name}",
            "version": "2.0",
            "source": "hand-specified from dimensions.json (MatrAIx 1290-dim schema)",
            "note": profile["note"],
            "attributes": attributes,
        }
        path = OUT / f"{name}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"wrote {path} ({len(attributes)} dimensions)")


if __name__ == "__main__":
    main()
