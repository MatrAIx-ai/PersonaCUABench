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
    "age_bracket", "region", "urbanicity", "socioeconomic_band", "demo_driver_status",
    "lifex_travel_breadth", "lifex_geographic_mobility",
    "ind_travel_tourism", "ind_transportation", "seniority",
    "tech_savviness", "skill_budgeting", "skill_driving", "fam_urban_planning",
    "topic_travel", "topic_technology",
    "lstyle_travel_freq", "lstyle_planning_horizon", "lstyle_frugality",
    "att_public_transit", "att_new_technology",
    "risk_tolerance", "dospert_financial_risk_tolerance",
    "cog_detail_orientation", "cog_patience", "cog_attention_span",
    "cog_big_picture_vs_detail", "cog_risk_framing",
    "health_mobility", "health_vision", "health_assistive_tech",
    "pref_plan_vs_spontaneous", "pref_save_vs_spend", "pref_detail_brief_vs_full",
    "accessibility_needs", "device_context", "economic_motivation",
    "habit_budget_tracking",
)

# Only behaviorally observable dimensions belong in the fidelity judge.  The
# judge must not infer age, region or other demographic facts from one request.
# Keeping the same targets for every profile also makes arms comparable.
EVALUATION_DIMENSIONS = (
    "tech_savviness",
    "risk_tolerance",
    "cog_detail_orientation",
    "cog_patience",
    "cog_attention_span",
    "pref_plan_vs_spontaneous",
    "pref_save_vs_spend",
    "pref_detail_brief_vs_full",
    "accessibility_needs",
    "device_context",
    "economic_motivation",
)

PROFILES: dict[str, dict] = {
    "travel-expert": {
        "note": "Career travel/transit professional: deep domain expertise, high "
                "tech fluency, plans in detail, no physical or access constraints.",
        "values": {
            "age_bracket": "35-44",
            "region": "North America",
            "urbanicity": "Dense urban",
            "socioeconomic_band": "Upper-middle",
            "demo_driver_status": "Occasional driver",
            "lifex_travel_breadth": "Global nomad",
            "lifex_geographic_mobility": "Serial relocator",
            "ind_travel_tourism": "Veteran",
            "ind_transportation": "Experienced",
            "seniority": "Lead / Principal",
            "tech_savviness": "Digital native",
            "skill_budgeting": "Advanced",
            "skill_driving": "Advanced",
            "fam_urban_planning": "Proficient",
            "topic_travel": "Passionate",
            "topic_technology": "Passionate",
            "lstyle_travel_freq": "Frequent flyer",
            "lstyle_planning_horizon": "Monthly",
            "lstyle_frugality": "Balanced",
            "att_public_transit": "Enthusiast",
            "att_new_technology": "Enthusiast",
            "risk_tolerance": "Balanced",
            "dospert_financial_risk_tolerance": "Average",
            "cog_detail_orientation": "Very high",
            "cog_patience": "High",
            "cog_attention_span": "Very long",
            "cog_big_picture_vs_detail": "Both",
            "cog_risk_framing": "Balanced",
            "health_mobility": "Full",
            "health_vision": "Normal",
            "health_assistive_tech": "None",
            "pref_plan_vs_spontaneous": "Highly planned",
            "pref_save_vs_spend": "Balanced",
            "pref_detail_brief_vs_full": "Every detail",
            "accessibility_needs": "None",
            "device_context": "Desktop, focused",
            "economic_motivation": "Value-driven",
            "habit_budget_tracking": "Weekly",
        },
    },
    "elderly-novice": {
        "note": "Retired, rarely travels, cautious with money and with new "
                "technology, mild mobility and vision limits, wants the gist.",
        "values": {
            "age_bracket": "75-84",
            "region": "North America",
            "urbanicity": "Suburban",
            "socioeconomic_band": "Low income",
            "demo_driver_status": "Licensed, rarely drives",
            "lifex_travel_breadth": "Never left country",
            "lifex_geographic_mobility": "Moved within region",
            "ind_travel_tourism": "None",
            "ind_transportation": "None",
            "seniority": "Retired",
            "tech_savviness": "Reluctant",
            "skill_budgeting": "Intermediate",
            "skill_driving": "Beginner",
            "fam_urban_planning": "None",
            "topic_travel": "Neutral",
            "topic_technology": "Indifferent",
            "lstyle_travel_freq": "Rare",
            "lstyle_planning_horizon": "Day-to-day",
            "lstyle_frugality": "Frugal saver",
            "att_public_transit": "Neutral",
            "att_new_technology": "Skeptical",
            "risk_tolerance": "Risk-averse",
            "dospert_financial_risk_tolerance": "Very low",
            "cog_detail_orientation": "Moderate",
            "cog_patience": "Moderate",
            "cog_attention_span": "Short",
            "cog_big_picture_vs_detail": "Big-picture",
            "cog_risk_framing": "Threat-focused",
            "health_mobility": "Mild limitation",
            "health_vision": "Low vision",
            "health_assistive_tech": "Magnifier",
            "pref_plan_vs_spontaneous": "Planned",
            "pref_save_vs_spend": "Hard saver",
            "pref_detail_brief_vs_full": "Just the gist",
            "accessibility_needs": "Visual",
            "device_context": "Accessibility tool",
            "economic_motivation": "Cost-sensitive",
            "habit_budget_tracking": "Monthly",
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
    evaluation_unknown = [d for d in EVALUATION_DIMENSIONS if d not in DIMENSIONS]
    assert not evaluation_unknown, (
        f"evaluation dimensions absent from DIMENSIONS: {evaluation_unknown}"
    )
    assert len(set(EVALUATION_DIMENSIONS)) == len(EVALUATION_DIMENSIONS), (
        "duplicate EVALUATION_DIMENSIONS"
    )

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
            "evaluation_dimensions": list(EVALUATION_DIMENSIONS),
            "attributes": attributes,
        }
        path = OUT / f"{name}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"wrote {path} ({len(attributes)} dimensions)")


if __name__ == "__main__":
    main()
