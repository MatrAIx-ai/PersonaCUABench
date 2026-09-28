"""Emit four Food & Drink personas from the MatrAIx dimension schema.

All profiles carry the same 36 dimensions and differ only in values. This keeps
prompt breadth fixed while varying food expertise, budget, dietary caution,
time pressure, evidence preference, and accessibility.

Every value is validated against odyssey/dimensions.json before YAML is written.

    python odyssey/make_personas.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent / "dimensions.json"
OUT = Path(__file__).resolve().parent / "personas"

# The four profiles are compatible with the fixed facts in all six Food tasks.
# They do not assume a specific city, household role, or permanent location.
DIMENSIONS = (
    "age_bracket", "socioeconomic_band", "seniority", "domain",
    "subject_specialty", "tech_savviness", "skill_cooking",
    "skill_budgeting", "skill_research", "fam_nutrition",
    "fam_hospitality_management", "ind_food_beverage", "ind_restaurants",
    "topic_cooking", "lstyle_diet_type", "lstyle_cooking_freq",
    "lstyle_shopping_style", "lstyle_frugality", "habit_meal_prepping",
    "health_dietary_restriction", "economic_motivation",
    "pref_save_vs_spend", "pref_quality_vs_quantity", "risk_tolerance",
    "dospert_health_safety_risk_tolerance", "decision_style", "trust_level",
    "time_pressure", "att_online_reviews", "cog_detail_orientation",
    "cog_patience", "pref_detail_brief_vs_full", "device_context",
    "health_vision", "accessibility_needs", "health_assistive_tech",
)

PROFILES: dict[str, dict] = {
    "food-budget-novice": {
        "note": "Budget-conscious early-career home cook: mobile-first, digitally "
                "fluent, new to cooking research, and wants quick practical choices.",
        "values": {
            "age_bracket": "25-34",
            "socioeconomic_band": "Lower-middle",
            "seniority": "Entry",
            "domain": "Business & Management",
            "subject_specialty": "Operations",
            "tech_savviness": "Digital native",
            "skill_cooking": "Beginner",
            "skill_budgeting": "Intermediate",
            "skill_research": "Beginner",
            "fam_nutrition": "Aware",
            "fam_hospitality_management": "None",
            "ind_food_beverage": "None",
            "ind_restaurants": "None",
            "topic_cooking": "Interested",
            "lstyle_diet_type": "Flexitarian",
            "lstyle_cooking_freq": "Weekly",
            "lstyle_shopping_style": "Bargain hunter",
            "lstyle_frugality": "Frugal saver",
            "habit_meal_prepping": "Weekly",
            "health_dietary_restriction": "None",
            "economic_motivation": "Cost-sensitive",
            "pref_save_vs_spend": "Hard saver",
            "pref_quality_vs_quantity": "Quantity-leaning",
            "risk_tolerance": "Risk-tolerant",
            "dospert_health_safety_risk_tolerance": "Average",
            "decision_style": "Intuitive",
            "trust_level": "Trusting",
            "time_pressure": "Deadline",
            "att_online_reviews": "Positive",
            "cog_detail_orientation": "Low",
            "cog_patience": "Low",
            "pref_detail_brief_vs_full": "Just the gist",
            "device_context": "Mobile, on-the-go",
            "health_vision": "Corrected",
            "accessibility_needs": "None",
            "health_assistive_tech": "None",
        },
    },
    "food-cautious-dietary-planner": {
        "note": "Older working adult managing a food allergy: cautious about claims "
                "and substitutions, patient, deliberate, and uses magnification.",
        "values": {
            "age_bracket": "55-64",
            "socioeconomic_band": "Middle",
            "seniority": "Senior",
            "domain": "Public Sector",
            "subject_specialty": "Operations",
            "tech_savviness": "Cautious adopter",
            "skill_cooking": "Intermediate",
            "skill_budgeting": "Advanced",
            "skill_research": "Intermediate",
            "fam_nutrition": "Proficient",
            "fam_hospitality_management": "Aware",
            "ind_food_beverage": "None",
            "ind_restaurants": "None",
            "topic_cooking": "Interested",
            "lstyle_diet_type": "Omnivore",
            "lstyle_cooking_freq": "Weekly",
            "lstyle_shopping_style": "Minimalist",
            "lstyle_frugality": "Frugal saver",
            "habit_meal_prepping": "Monthly",
            "health_dietary_restriction": "Allergy",
            "economic_motivation": "Value-driven",
            "pref_save_vs_spend": "Saver-leaning",
            "pref_quality_vs_quantity": "Quality-leaning",
            "risk_tolerance": "Risk-averse",
            "dospert_health_safety_risk_tolerance": "Very low",
            "decision_style": "Deliberative",
            "trust_level": "Skeptical",
            "time_pressure": "No rush",
            "att_online_reviews": "Skeptical",
            "cog_detail_orientation": "High",
            "cog_patience": "High",
            "pref_detail_brief_vs_full": "Detail-leaning",
            "device_context": "Accessibility tool",
            "health_vision": "Low vision",
            "accessibility_needs": "Visual",
            "health_assistive_tech": "Magnifier",
        },
    },
    "food-busy-host": {
        "note": "Time-pressed operations manager and frequent household host who "
                "prioritizes practical menus, reliable logistics, and overall value.",
        "values": {
            "age_bracket": "35-44",
            "socioeconomic_band": "Middle",
            "seniority": "Manager",
            "domain": "Business & Management",
            "subject_specialty": "Operations",
            "tech_savviness": "Comfortable",
            "skill_cooking": "Intermediate",
            "skill_budgeting": "Advanced",
            "skill_research": "Intermediate",
            "fam_nutrition": "Familiar",
            "fam_hospitality_management": "Familiar",
            "ind_food_beverage": "Some exposure",
            "ind_restaurants": "Some exposure",
            "topic_cooking": "Interested",
            "lstyle_diet_type": "Omnivore",
            "lstyle_cooking_freq": "Daily",
            "lstyle_shopping_style": "Researcher",
            "lstyle_frugality": "Balanced",
            "habit_meal_prepping": "Weekly",
            "health_dietary_restriction": "None",
            "economic_motivation": "Value-driven",
            "pref_save_vs_spend": "Saver-leaning",
            "pref_quality_vs_quantity": "Quality-leaning",
            "risk_tolerance": "Cautious",
            "dospert_health_safety_risk_tolerance": "Low",
            "decision_style": "Consensus-driven",
            "trust_level": "Verifying",
            "time_pressure": "Deadline",
            "att_online_reviews": "Positive",
            "cog_detail_orientation": "Moderate",
            "cog_patience": "Low",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "device_context": "Mobile, on-the-go",
            "health_vision": "Normal",
            "accessibility_needs": "None",
            "health_assistive_tech": "None",
        },
    },
    "food-culinary-researcher": {
        "note": "Affluent culinary and hospitality director: expert cook, analytical "
                "researcher, quality-first, evidence-seeking, and highly detailed.",
        "values": {
            "age_bracket": "45-54",
            "socioeconomic_band": "High income",
            "seniority": "Director",
            "domain": "Hospitality",
            "subject_specialty": "Culinary arts",
            "tech_savviness": "Digital native",
            "skill_cooking": "Master",
            "skill_budgeting": "Master",
            "skill_research": "Master",
            "fam_nutrition": "Expert",
            "fam_hospitality_management": "Expert",
            "ind_food_beverage": "Veteran",
            "ind_restaurants": "Veteran",
            "topic_cooking": "Passionate",
            "lstyle_diet_type": "Omnivore",
            "lstyle_cooking_freq": "Daily",
            "lstyle_shopping_style": "Researcher",
            "lstyle_frugality": "Spender",
            "habit_meal_prepping": "Daily",
            "health_dietary_restriction": "None",
            "economic_motivation": "Premium-seeking",
            "pref_save_vs_spend": "Spender-leaning",
            "pref_quality_vs_quantity": "Quality first",
            "risk_tolerance": "Balanced",
            "dospert_health_safety_risk_tolerance": "Average",
            "decision_style": "Analytical",
            "trust_level": "Verifying",
            "time_pressure": "No rush",
            "att_online_reviews": "Skeptical",
            "cog_detail_orientation": "Very high",
            "cog_patience": "Very high",
            "pref_detail_brief_vs_full": "Every detail",
            "device_context": "Desktop, focused",
            "health_vision": "Normal",
            "accessibility_needs": "None",
            "health_assistive_tech": "None",
        },
    },
}


def main() -> None:
    schema = {d["id"]: d for d in json.loads(SCHEMA.read_text(encoding="utf-8"))["dimensions"]}
    missing = [dim for dim in DIMENSIONS if dim not in schema]
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
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"wrote {path} ({len(attributes)} dimensions)")


if __name__ == "__main__":
    main()
