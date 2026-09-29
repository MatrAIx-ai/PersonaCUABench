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

# 32 science-and-education dimensions, picked from the 1290-dim space: where the
# person sits in the education system, how much statistical, teaching and research
# expertise they carry, how they talk, what state their request is in, and how they
# relate to technology, AI and trust. All four profiles set exactly these fields and
# differ only in the values.
#
# Deliberately left out: health_mental_health, health_neurodivergence, health_vision,
# health_text_size_need and accessibility_needs. Task 6 is itself about eating-disorder
# research and task 2 is itself about easier-to-scan text, so a persona carrying those
# traits would make it impossible to tell whether the agent was serving the rubric or
# the persona. No value below is one persona.py drops as nullish ("None", "Not
# applicable"), so all four personas render all 32 attributes.
DIMENSIONS = (
    "age_bracket", "life_stage", "highest_education", "institution_tier",
    "academic_field", "demo_employment_status", "role_function", "seniority",
    "socioeconomic_band", "fam_statistics", "fam_pedagogy", "skill_research",
    "skill_fact_checking", "skill_technical_writing", "att_higher_education",
    "register", "cog_formality", "cog_directness", "cog_politeness",
    "cog_use_of_jargon", "pref_detail_brief_vs_full", "english_proficiency",
    "primary_language", "cog_abstraction", "intent", "time_pressure", "prior_context",
    "query_complexity", "tech_savviness", "att_ai", "trust_level", "cog_attention_span"
)

PROFILES: dict[str, dict] = {
    "education-faculty-advisor": {
        "note": "Tenured social scientist who advises graduate students: expert in"
                " statistics and research, blunt, jargon-heavy, verifies claims.",
        "values": {
            "age_bracket":               "55-64",
            "life_stage":                "Empty nester",
            "highest_education":         "Doctorate",
            "institution_tier":          "Top-tier research",
            "academic_field":            "Social science",
            "demo_employment_status":    "Full-time",
            "role_function":             "Teaching",
            "seniority":                 "Lead / Principal",
            "socioeconomic_band":        "Upper-middle",
            "fam_statistics":            "Expert",
            "fam_pedagogy":              "Proficient",
            "skill_research":            "Master",
            "skill_fact_checking":       "Master",
            "skill_technical_writing":   "Master",
            "att_higher_education":      "Positive",
            "register":                  "Technical jargon",
            "cog_formality":             "Formal",
            "cog_directness":            "Blunt",
            "cog_politeness":            "Brusque",
            "cog_use_of_jargon":         "Heavy",
            "pref_detail_brief_vs_full": "Brief-leaning",
            "english_proficiency":       "Native",
            "primary_language":          "English",
            "cog_abstraction":           "Abstract",
            "intent":                    "Get task done",
            "time_pressure":             "Moderate",
            "prior_context":             "Cold start",
            "query_complexity":          "Multi-step",
            "tech_savviness":            "Cautious adopter",
            "att_ai":                    "Skeptical",
            "trust_level":               "Verifying",
            "cog_attention_span":        "Very long",
        },
    },
    "education-k12-teacher": {
        "note": "Middle-school humanities teacher: expert in teaching, casual and"
                " talkative, wants every detail, trusting.",
        "values": {
            "age_bracket":               "35-44",
            "life_stage":                "Parent of young kids",
            "highest_education":         "Master's",
            "institution_tier":          "Mid-tier university",
            "academic_field":            "Humanities",
            "demo_employment_status":    "Full-time",
            "role_function":             "Teaching",
            "seniority":                 "Senior",
            "socioeconomic_band":        "Middle",
            "fam_statistics":            "Familiar",
            "fam_pedagogy":              "Expert",
            "skill_research":            "Advanced",
            "skill_fact_checking":       "Intermediate",
            "skill_technical_writing":   "Advanced",
            "att_higher_education":      "Neutral",
            "register":                  "Colloquial",
            "cog_formality":             "Casual",
            "cog_directness":            "Balanced",
            "cog_politeness":            "Polite",
            "cog_use_of_jargon":         "Moderate",
            "pref_detail_brief_vs_full": "Every detail",
            "english_proficiency":       "Native",
            "primary_language":          "English",
            "cog_abstraction":           "Balanced",
            "intent":                    "Brainstorm",
            "time_pressure":             "No rush",
            "prior_context":             "Long ongoing project",
            "query_complexity":          "Open-ended creative",
            "tech_savviness":            "Comfortable",
            "att_ai":                    "Positive",
            "trust_level":               "Trusting",
            "cog_attention_span":        "Long",
        },
    },
    "education-first-gen-applicant": {
        "note": "First-in-family community-college student, Spanish-dominant with"
                " intermediate English: digitally fluent, wants the gist, under a"
                " deadline.",
        "values": {
            "age_bracket":               "25-34",
            "life_stage":                "Student",
            "highest_education":         "Some college",
            "institution_tier":          "Community college",
            "academic_field":            "Interdisciplinary",
            "demo_employment_status":    "Part-time",
            "role_function":             "Operations",
            "seniority":                 "Student / intern",
            "socioeconomic_band":        "Low income",
            "fam_statistics":            "Aware",
            "fam_pedagogy":              "Aware",
            "skill_research":            "Beginner",
            "skill_fact_checking":       "Beginner",
            "skill_technical_writing":   "Beginner",
            "att_higher_education":      "Enthusiast",
            "register":                  "Code-switching",
            "cog_formality":             "Neutral",
            "cog_directness":            "Direct",
            "cog_politeness":            "Neutral",
            "cog_use_of_jargon":         "Avoids jargon",
            "pref_detail_brief_vs_full": "Just the gist",
            "english_proficiency":       "Intermediate (B1-B2)",
            "primary_language":          "Spanish",
            "cog_abstraction":           "Very concrete",
            "intent":                    "Learn / explain",
            "time_pressure":             "Deadline",
            "prior_context":             "Returning user",
            "query_complexity":          "Simple factual",
            "tech_savviness":            "Digital native",
            "att_ai":                    "Enthusiast",
            "trust_level":               "Trusting",
            "cog_attention_span":        "Short",
        },
    },
    "education-parent-helper": {
        "note": "Bookkeeper researching on behalf of their children: very formal"
                " and indirect, reluctant with technology, skeptical.",
        "values": {
            "age_bracket":               "45-54",
            "life_stage":                "Mid-life",
            "highest_education":         "Vocational / cert",
            "institution_tier":          "Online / bootcamp",
            "academic_field":            "Business",
            "demo_employment_status":    "Full-time",
            "role_function":             "Finance",
            "seniority":                 "Mid",
            "socioeconomic_band":        "Lower-middle",
            "fam_statistics":            "Proficient",
            "fam_pedagogy":              "Familiar",
            "skill_research":            "Intermediate",
            "skill_fact_checking":       "Advanced",
            "skill_technical_writing":   "Intermediate",
            "att_higher_education":      "Positive",
            "register":                  "Formal / standard",
            "cog_formality":             "Very formal",
            "cog_directness":            "Indirect",
            "cog_politeness":            "Very polite",
            "cog_use_of_jargon":         "Light",
            "pref_detail_brief_vs_full": "Detail-leaning",
            "english_proficiency":       "Native",
            "primary_language":          "English",
            "cog_abstraction":           "Concrete",
            "intent":                    "Decide",
            "time_pressure":             "Moderate",
            "prior_context":             "Frustrated re-ask",
            "query_complexity":          "Ambiguous / underspecified",
            "tech_savviness":            "Reluctant",
            "att_ai":                    "Neutral",
            "trust_level":               "Skeptical",
            "cog_attention_span":        "Average",
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
