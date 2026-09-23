"""Emit odyssey/personas/*.yaml from the 1290-dim MatrAIx schema in odyssey/dimensions.json.

Both personas carry the SAME dimension set and differ only in the values, so any
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

# 38 travel-relevant dimensions, picked from the 1290-dim space: who they are,
# how much travel/transit expertise they carry, how they handle money and risk,
# how they read and how much detail they want, and the physical/tech constraints
# that shape a browsing session.
DIMENSIONS = (
    "age_bracket",
    "primary_language",
    "english_proficiency",
    "highest_education",
    "seniority",
    "years_experience",
    "linkedin_activity",
    "life_stage",
    "risk_tolerance",
    "decision_style",
    "device_context",
    "accessibility_needs",
    "media_diet",
    "fam_art_history",
    "fam_film_studies",
    "fam_computer_networking",
    "fam_game_development",
    "fam_graphic_design",
    "fam_project_management",
    "skill_system_design",
    "skill_project_management",
    "skill_time_management",
    "skill_design_thinking",
    "skill_drawing",
    "skill_networking",
    "tool_webflow",
    "topic_technology",
    "topic_film",
    "topic_visual_art",
    "topic_social_media",
)

PROFILES: dict[str, dict] = {
    "entertainment-power-user": {
        "note": (
            "An online-native entertainment fan who follows streaming, Reddit "
            "discussion, games, and visual culture; wants precise sources and "
            "enough detail to compare options."
        ),
        "values": {
            "age_bracket": "25-34",
            "primary_language": "English",
            "english_proficiency": "Native",
            "highest_education": "Bachelor's",
            "seniority": "Mid",
            "years_experience": "3-5",
            "linkedin_activity": "Lurker",
            "life_stage": "Early career",
            "risk_tolerance": "Balanced",
            "decision_style": "Analytical",
            "device_context": "Desktop, focused",
            "accessibility_needs": "None",
            "media_diet": "Social-media-heavy",
            "fam_art_history": "Aware",
            "fam_film_studies": "Proficient",
            "fam_computer_networking": "Aware",
            "fam_game_development": "Familiar",
            "fam_graphic_design": "Familiar",
            "fam_project_management": "Familiar",
            "skill_system_design": "Beginner",
            "skill_project_management": "Intermediate",
            "skill_time_management": "Advanced",
            "skill_design_thinking": "Intermediate",
            "skill_drawing": "Beginner",
            "skill_networking": "Intermediate",
            "tool_webflow": "Tried it",
            "topic_technology": "Passionate",
            "topic_film": "Passionate",
            "topic_visual_art": "Interested",
            "topic_social_media": "Passionate",
        },
    },
    "creative-beginner": {
        "note": (
            "A student experimenting with drawing, image references, React, and "
            "simple visual projects; prefers approachable explanations and clear "
            "visual examples over technical jargon."
        ),
        "values": {
            "age_bracket": "18-24",
            "primary_language": "English",
            "english_proficiency": "Native",
            "highest_education": "Some college",
            "seniority": "Student / intern",
            "years_experience": "0-2",
            "linkedin_activity": "Inactive",
            "life_stage": "Student",
            "risk_tolerance": "Cautious",
            "decision_style": "Intuitive",
            "device_context": "Desktop, focused",
            "accessibility_needs": "None",
            "media_diet": "Video-first",
            "fam_art_history": "Aware",
            "fam_film_studies": "Familiar",
            "fam_computer_networking": "None",
            "fam_game_development": "Aware",
            "fam_graphic_design": "Aware",
            "fam_project_management": "None",
            "skill_system_design": "None",
            "skill_project_management": "Beginner",
            "skill_time_management": "Intermediate",
            "skill_design_thinking": "Beginner",
            "skill_drawing": "Beginner",
            "skill_networking": "None",
            "tool_webflow": "Never used",
            "topic_technology": "Interested",
            "topic_film": "Interested",
            "topic_visual_art": "Passionate",
            "topic_social_media": "Interested",
        },
    },
    "career-switcher": {
        "note": (
            "A methodical mid-career professional exploring a transition into Los "
            "Angeles post-production and entertainment technology; wants concrete "
            "requirements, credible sources, costs, and realistic next steps."
        ),
        "values": {
            "age_bracket": "35-44",
            "primary_language": "English",
            "english_proficiency": "Native",
            "highest_education": "Bachelor's",
            "seniority": "Mid",
            "years_experience": "11-20",
            "linkedin_activity": "Job seeker",
            "life_stage": "Career change",
            "risk_tolerance": "Cautious",
            "decision_style": "Analytical",
            "device_context": "Desktop, focused",
            "accessibility_needs": "None",
            "media_diet": "Long-form",
            "fam_art_history": "Aware",
            "fam_film_studies": "Familiar",
            "fam_computer_networking": "Familiar",
            "fam_game_development": "None",
            "fam_graphic_design": "Aware",
            "fam_project_management": "Proficient",
            "skill_system_design": "Intermediate",
            "skill_project_management": "Advanced",
            "skill_time_management": "Advanced",
            "skill_design_thinking": "Intermediate",
            "skill_drawing": "Beginner",
            "skill_networking": "Intermediate",
            "tool_webflow": "Never used",
            "topic_technology": "Passionate",
            "topic_film": "Passionate",
            "topic_visual_art": "Interested",
            "topic_social_media": "Neutral",
        },
    },
    "budget-student": {
        "note": "College student on a tight budget: phone-first, fluent with apps "
                "but no travel expertise, spontaneous, wants it quick and cheap.",
        "values": {
            "age_bracket": "18-24",
            "region": "North America",
            "urbanicity": "Dense urban",
            "socioeconomic_band": "Low income",
            "demo_driver_status": "Non-driver",
            "lifex_travel_breadth": "A few countries",
            "lifex_geographic_mobility": "Moved nationally",
            "ind_travel_tourism": "None",
            "ind_transportation": "None",
            "seniority": "Student / intern",
            "tech_savviness": "Digital native",
            "skill_budgeting": "Beginner",
            "skill_driving": "None",
            "fam_urban_planning": "Aware",
            "topic_travel": "Interested",
            "topic_technology": "Interested",
            "lstyle_travel_freq": "Occasional",
            "lstyle_planning_horizon": "Day-to-day",
            "lstyle_frugality": "Frugal saver",
            "att_public_transit": "Positive",
            "att_new_technology": "Enthusiast",
            "risk_tolerance": "Risk-tolerant",
            "dospert_financial_risk_tolerance": "High",
            "cog_detail_orientation": "Low",
            "cog_patience": "Low",
            "cog_attention_span": "Short",
            "cog_big_picture_vs_detail": "Big-picture",
            "cog_risk_framing": "Opportunity-focused",
            "health_mobility": "Full",
            "health_vision": "Corrected",
            "health_assistive_tech": "None",
            "pref_plan_vs_spontaneous": "Spontaneous",
            "pref_save_vs_spend": "Hard saver",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "accessibility_needs": "None",
            "device_context": "Mobile, on-the-go",
            "economic_motivation": "Cost-sensitive",
            "habit_budget_tracking": "Rarely",
        },
    },
    "non-native-speaker": {
        "note": "Recent immigrant with limited English: capable adult, uses a phone "
                "translator, unfamiliar with local websites and customs, careful with money.",
        "values": {
            "age_bracket": "25-34",
            "region": "East Asia",
            "urbanicity": "Dense urban",
            "socioeconomic_band": "Lower-middle",
            "demo_driver_status": "Non-driver",
            "lifex_travel_breadth": "A few countries",
            "lifex_geographic_mobility": "Moved internationally",
            "ind_travel_tourism": "None",
            "ind_transportation": "None",
            "seniority": "Entry",
            "tech_savviness": "Comfortable",
            "skill_budgeting": "Intermediate",
            "skill_driving": "None",
            "fam_urban_planning": "None",
            "topic_travel": "Interested",
            "topic_technology": "Neutral",
            "lstyle_travel_freq": "Occasional",
            "lstyle_planning_horizon": "Weekly",
            "lstyle_frugality": "Frugal saver",
            "att_public_transit": "Positive",
            "att_new_technology": "Neutral",
            "risk_tolerance": "Cautious",
            "dospert_financial_risk_tolerance": "Low",
            "cog_detail_orientation": "Moderate",
            "cog_patience": "High",
            "cog_attention_span": "Average",
            "cog_big_picture_vs_detail": "Big-picture",
            "cog_risk_framing": "Threat-focused",
            "health_mobility": "Full",
            "health_vision": "Normal",
            "health_assistive_tech": "None",
            "pref_plan_vs_spontaneous": "Planned",
            "pref_save_vs_spend": "Saver-leaning",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "accessibility_needs": "Language barrier",
            "device_context": "Mobile, on-the-go",
            "economic_motivation": "Cost-sensitive",
            "habit_budget_tracking": "Weekly",
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
