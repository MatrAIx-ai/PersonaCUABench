"""Emit odyssey/personas/*.yaml from the 1290-dim MatrAIx schema in odyssey/dimensions.json.

Both personas carry the SAME dimension set and differ only in the values, so any
behavioural difference on a task is attributable to the values, not to one
persona simply having more attributes rendered into its prompt.

Every value is checked against the schema's allowed values -- a typo fails here
rather than silently rendering a dimension the schema never defined.

    python odyssey/make_personas.py             # write odyssey/personas/*.yaml
    python odyssey/make_personas.py --check     # fail if they no longer match
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent / "dimensions.json"   # MatrAIx persona schema
OUT = Path(__file__).resolve().parent / "personas"

# The 32 dimensions every persona in every domain carries, picked from the
# 1290-dim space. The five the team agreed no persona may be silent on come
# first, because the persona tree branches on exactly them:
#
#   age            age_bracket
#   education      highest_education
#   income         demo_household_income      (socioeconomic_band is the coarse band)
#   expertise      seniority + tech_savviness + the family's own skill dimensions
#   time pressure  time_pressure
#
# The rest say how they handle money and risk, how they read and how much detail
# they want, and the physical and device constraints that shape a session.
# Everyone gets these; a family adds four or five of its own below.
CORE_DIMENSIONS = (
    # the five branching dimensions (expertise is per-family, plus these two)
    "age_bracket", "highest_education", "demo_household_income", "time_pressure",
    "seniority", "tech_savviness",
    # who else they are
    "region", "urbanicity", "socioeconomic_band", "lifex_geographic_mobility",
    # money
    "skill_budgeting", "lstyle_frugality", "economic_motivation",
    "habit_budget_tracking", "pref_save_vs_spend",
    # technology
    "topic_technology", "att_new_technology", "device_context",
    # risk
    "risk_tolerance", "dospert_financial_risk_tolerance", "cog_risk_framing",
    # how they read and decide
    "cog_detail_orientation", "cog_patience", "cog_attention_span",
    "cog_big_picture_vs_detail", "pref_detail_brief_vs_full",
    "lstyle_planning_horizon", "pref_plan_vs_spontaneous",
    # what the session has to accommodate
    "health_mobility", "health_vision", "health_assistive_tech",
    "accessibility_needs",
)

# The axes the team agreed every persona must carry a value for, because the
# persona tree branches on them. Expertise is the family's own skill dimensions
# plus seniority, so it appears here as seniority and is checked per family.
BRANCHING_DIMENSIONS = (
    "age_bracket", "highest_education", "demo_household_income", "seniority",
    "time_pressure",
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

# Every domain family carries the same four roles, so a role's baseline is written
# once here and each persona overrides what makes them that person.  The merge is
# what lands in PROFILES, so every profile still holds a complete values dict and
# the schema check below still sees every value.
#
#   A "expert"    domain professional, evidence-driven, wants every detail
#   B "senior"    65-84, cautious, reluctant with tech, an accessibility need
#   C "young"     18-34, low income, phone-first, impatient, cost-sensitive
#   D "practical" 35-54, time-pressured, wants concise actionable answers
#
# Every family keeps all four roles; what each family changes is the values, so
# D is a non-native speaker in travel, a parent hunting school resources in
# science, and a technology-cautious teacher in tech.
_ROLE_BASE: dict[str, dict[str, str]] = {
    "expert": {
        "age_bracket": "35-44",
        "highest_education": "Master's",
        "demo_household_income": "$100k-200k",
        "time_pressure": "Moderate",
        "seniority": "Senior",
        "tech_savviness": "Digital native",
        "region": "North America",
        "urbanicity": "Dense urban",
        "socioeconomic_band": "Upper-middle",
        "lifex_geographic_mobility": "Moved nationally",
        "skill_budgeting": "Advanced",
        "lstyle_frugality": "Balanced",
        "economic_motivation": "Value-driven",
        "habit_budget_tracking": "Monthly",
        "pref_save_vs_spend": "Balanced",
        "topic_technology": "Interested",
        "att_new_technology": "Positive",
        "device_context": "Desktop, focused",
        "risk_tolerance": "Balanced",
        "dospert_financial_risk_tolerance": "Average",
        "cog_risk_framing": "Balanced",
        "cog_detail_orientation": "Very high",
        "cog_patience": "High",
        "cog_attention_span": "Very long",
        "cog_big_picture_vs_detail": "Detail",
        "pref_detail_brief_vs_full": "Every detail",
        "lstyle_planning_horizon": "Monthly",
        "pref_plan_vs_spontaneous": "Highly planned",
        "health_mobility": "Full",
        "health_vision": "Corrected",
        "health_assistive_tech": "None",
        "accessibility_needs": "None",
    },
    "senior": {
        "age_bracket": "65-74",
        "highest_education": "Secondary",
        "demo_household_income": "$25k-50k",
        "time_pressure": "No rush",
        "seniority": "Retired",
        "tech_savviness": "Reluctant",
        "region": "North America",
        "urbanicity": "Suburban",
        "socioeconomic_band": "Lower-middle",
        "lifex_geographic_mobility": "Moved within region",
        "skill_budgeting": "Intermediate",
        "lstyle_frugality": "Frugal saver",
        "economic_motivation": "Cost-sensitive",
        "habit_budget_tracking": "Monthly",
        "pref_save_vs_spend": "Hard saver",
        "topic_technology": "Indifferent",
        "att_new_technology": "Skeptical",
        "device_context": "Accessibility tool",
        "risk_tolerance": "Risk-averse",
        "dospert_financial_risk_tolerance": "Very low",
        "cog_risk_framing": "Threat-focused",
        "cog_detail_orientation": "Moderate",
        "cog_patience": "Moderate",
        "cog_attention_span": "Short",
        "cog_big_picture_vs_detail": "Big-picture",
        "pref_detail_brief_vs_full": "Just the gist",
        "lstyle_planning_horizon": "Weekly",
        "pref_plan_vs_spontaneous": "Planned",
        "health_mobility": "Mild limitation",
        "health_vision": "Low vision",
        "health_assistive_tech": "Magnifier",
        "accessibility_needs": "Visual",
    },
    "young": {
        "age_bracket": "25-34",
        "highest_education": "Some college",
        "demo_household_income": "<$25k",
        "time_pressure": "Moderate",
        "seniority": "Entry",
        "tech_savviness": "Digital native",
        "region": "North America",
        "urbanicity": "Dense urban",
        "socioeconomic_band": "Low income",
        "lifex_geographic_mobility": "Moved nationally",
        "skill_budgeting": "Beginner",
        "lstyle_frugality": "Frugal saver",
        "economic_motivation": "Cost-sensitive",
        "habit_budget_tracking": "Rarely",
        "pref_save_vs_spend": "Saver-leaning",
        "topic_technology": "Passionate",
        "att_new_technology": "Enthusiast",
        "device_context": "Mobile, on-the-go",
        "risk_tolerance": "Risk-tolerant",
        "dospert_financial_risk_tolerance": "High",
        "cog_risk_framing": "Opportunity-focused",
        "cog_detail_orientation": "Low",
        "cog_patience": "Low",
        "cog_attention_span": "Short",
        "cog_big_picture_vs_detail": "Big-picture",
        "pref_detail_brief_vs_full": "Brief-leaning",
        "lstyle_planning_horizon": "Day-to-day",
        "pref_plan_vs_spontaneous": "Spontaneous",
        "health_mobility": "Full",
        "health_vision": "Corrected",
        "health_assistive_tech": "None",
        "accessibility_needs": "None",
    },
    "practical": {
        "age_bracket": "45-54",
        "highest_education": "Bachelor's",
        "demo_household_income": "$50k-100k",
        "time_pressure": "Deadline",
        "seniority": "Manager",
        "tech_savviness": "Comfortable",
        "region": "North America",
        "urbanicity": "Suburban",
        "socioeconomic_band": "Middle",
        "lifex_geographic_mobility": "Moved within region",
        "skill_budgeting": "Intermediate",
        "lstyle_frugality": "Balanced",
        "economic_motivation": "Value-driven",
        "habit_budget_tracking": "Monthly",
        "pref_save_vs_spend": "Balanced",
        "topic_technology": "Neutral",
        "att_new_technology": "Positive",
        "device_context": "Mobile, on-the-go",
        "risk_tolerance": "Cautious",
        "dospert_financial_risk_tolerance": "Low",
        "cog_risk_framing": "Balanced",
        "cog_detail_orientation": "High",
        "cog_patience": "Low",
        "cog_attention_span": "Average",
        "cog_big_picture_vs_detail": "Both",
        "pref_detail_brief_vs_full": "Brief-leaning",
        "lstyle_planning_horizon": "Weekly",
        "pref_plan_vs_spontaneous": "Planned",
        "health_mobility": "Full",
        "health_vision": "Corrected",
        "health_assistive_tech": "None",
        "accessibility_needs": "None",
    },
}



# --------------------------------------------------------------------------- #
# Domain families
# --------------------------------------------------------------------------- #
# The shared dimensions above describe anyone. What separates a food expert from
# a health expert is domain knowledge, and the MatrAIx schema has 50 industry,
# 143 familiarity, 64 skill and 80 topic dimensions for exactly that. Each family
# adds a few of its own, so a Gmail persona is not described by its attitude to
# public transit and a cook is not an expert at nothing in particular.
#
# Every family gets exactly five, so every persona is described by the same
# number of dimensions and a travel persona is as richly drawn as a food one.
FAMILY_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "travel": ("ind_travel_tourism", "ind_transportation", "lifex_travel_breadth",
               "topic_travel", "lstyle_travel_freq"),
    "science": ("ind_education", "fam_statistics", "skill_research", "topic_science",
                "skill_mathematics"),
    "tech": ("ind_consumer_electronics", "fam_computer_networking", "skill_coding",
             "skill_debugging", "acad_computer_science"),
    "community": ("ind_nonprofit", "ind_government", "skill_facilitation",
                  "topic_volunteering", "val_community"),
    "art": ("ind_fine_art", "fam_art_history", "skill_drawing",
            "trait_appreciation_of_beauty", "skill_design_thinking"),
    "lifestyle": ("ind_apparel", "ind_real_estate", "lstyle_fashion_sense",
                  "topic_interior_design", "topic_fashion"),
    "ecommerce": ("ind_e_commerce", "ind_retail", "skill_negotiation",
                  "lstyle_shopping_style", "att_brand_loyalty"),
    "health": ("ind_healthcare", "ind_fitness_wellness", "fam_nutrition",
               "topic_fitness", "lstyle_exercise_freq"),
    "food": ("ind_food_beverage", "ind_hospitality", "skill_cooking",
             "topic_cooking", "lstyle_diet_type"),
    "productivity": ("skill_time_management", "skill_writing",
                     "habit_inbox_zero_discipline", "fam_organizational_psychology",
                     "topic_productivity"),
    "professional": ("ind_consulting", "skill_networking", "val_career_success",
                     "lifex_career_path_shape", "skill_leadership"),
}

# What each role knows about its own domain. The expert works in it, the senior
# has lived alongside it without studying it, the young one is enthusiastic and
# untrained, the practical one is competent and busy. A profile overrides any of
# these the moment the person is not the default.
FAMILY_DEFAULTS: dict[str, dict[str, dict[str, str]]] = {
    "travel": {
        "expert": {"ind_travel_tourism": "Veteran", "ind_transportation": "Experienced",
                   "lifex_travel_breadth": "Global nomad", "topic_travel": "Passionate",
                   "lstyle_travel_freq": "Frequent flyer"},
        "senior": {"ind_travel_tourism": "None", "ind_transportation": "None",
                   "lifex_travel_breadth": "Never left country",
                   "topic_travel": "Neutral", "lstyle_travel_freq": "Rare"},
        "young": {"ind_travel_tourism": "None", "ind_transportation": "None",
                  "lifex_travel_breadth": "A few countries",
                  "topic_travel": "Interested", "lstyle_travel_freq": "Occasional"},
        "practical": {"ind_travel_tourism": "Some exposure",
                      "ind_transportation": "Some exposure",
                      "lifex_travel_breadth": "A few countries",
                      "topic_travel": "Neutral", "lstyle_travel_freq": "Occasional"},
    },
    "science": {
        "expert": {"ind_education": "Veteran", "fam_statistics": "Expert",
                   "skill_research": "Master", "topic_science": "Passionate",
                   "skill_mathematics": "Master"},
        "senior": {"ind_education": "Some exposure", "fam_statistics": "Aware",
                   "skill_research": "Beginner", "topic_science": "Interested",
                   "skill_mathematics": "Beginner"},
        "young": {"ind_education": "None", "fam_statistics": "Aware",
                  "skill_research": "Beginner", "topic_science": "Interested",
                  "skill_mathematics": "Intermediate"},
        "practical": {"ind_education": "Some exposure", "fam_statistics": "Familiar",
                      "skill_research": "Intermediate", "topic_science": "Neutral",
                      "skill_mathematics": "Intermediate"},
    },
    "tech": {
        "expert": {"ind_consumer_electronics": "Veteran",
                   "fam_computer_networking": "Expert", "skill_coding": "Master",
                   "skill_debugging": "Master", "acad_computer_science": "Passionate"},
        "senior": {"ind_consumer_electronics": "None",
                   "fam_computer_networking": "None", "skill_coding": "None",
                   "skill_debugging": "None", "acad_computer_science": "Averse"},
        "young": {"ind_consumer_electronics": "Some exposure",
                  "fam_computer_networking": "Aware", "skill_coding": "Beginner",
                  "skill_debugging": "Beginner", "acad_computer_science": "Passionate"},
        "practical": {"ind_consumer_electronics": "Some exposure",
                      "fam_computer_networking": "Familiar", "skill_coding": "Beginner",
                      "skill_debugging": "Intermediate", "acad_computer_science": "Neutral"},
    },
    "community": {
        "expert": {"ind_nonprofit": "Veteran", "ind_government": "Experienced",
                   "skill_facilitation": "Master", "topic_volunteering": "Passionate",
                   "val_community": "Core value"},
        "senior": {"ind_nonprofit": "Some exposure", "ind_government": "Some exposure",
                   "skill_facilitation": "Beginner", "topic_volunteering": "Interested",
                   "val_community": "Important"},
        "young": {"ind_nonprofit": "Some exposure", "ind_government": "None",
                  "skill_facilitation": "Beginner", "topic_volunteering": "Passionate",
                  "val_community": "Important"},
        "practical": {"ind_nonprofit": "Some exposure", "ind_government": "None",
                      "skill_facilitation": "Intermediate",
                      "topic_volunteering": "Neutral", "val_community": "Moderate"},
    },
    "art": {
        "expert": {"ind_fine_art": "Veteran", "fam_art_history": "Expert",
                   "skill_drawing": "Master",
                   "trait_appreciation_of_beauty": "Signature",
                   "skill_design_thinking": "Master"},
        "senior": {"ind_fine_art": "Some exposure", "fam_art_history": "Familiar",
                   "skill_drawing": "Beginner",
                   "trait_appreciation_of_beauty": "Strong",
                   "skill_design_thinking": "Beginner"},
        "young": {"ind_fine_art": "None", "fam_art_history": "Aware",
                  "skill_drawing": "Intermediate",
                  "trait_appreciation_of_beauty": "Strong",
                  "skill_design_thinking": "Intermediate"},
        "practical": {"ind_fine_art": "None", "fam_art_history": "Aware",
                      "skill_drawing": "Beginner",
                      "trait_appreciation_of_beauty": "Moderate",
                      "skill_design_thinking": "Intermediate"},
    },
    "lifestyle": {
        "expert": {"ind_apparel": "Veteran", "ind_real_estate": "Some exposure",
                   "lstyle_fashion_sense": "Trend-setter",
                   "topic_interior_design": "Passionate", "topic_fashion": "Passionate"},
        "senior": {"ind_apparel": "None", "ind_real_estate": "Some exposure",
                   "lstyle_fashion_sense": "Classic",
                   "topic_interior_design": "Neutral", "topic_fashion": "Indifferent"},
        "young": {"ind_apparel": "Some exposure", "ind_real_estate": "None",
                  "lstyle_fashion_sense": "Trend-follower",
                  "topic_interior_design": "Interested", "topic_fashion": "Passionate"},
        "practical": {"ind_apparel": "None", "ind_real_estate": "Some exposure",
                      "lstyle_fashion_sense": "Practical",
                      "topic_interior_design": "Interested", "topic_fashion": "Neutral"},
    },
    "ecommerce": {
        "expert": {"ind_e_commerce": "Veteran", "ind_retail": "Experienced",
                   "skill_negotiation": "Advanced",
                   "lstyle_shopping_style": "Researcher", "att_brand_loyalty": "Neutral"},
        "senior": {"ind_e_commerce": "None", "ind_retail": "Some exposure",
                   "skill_negotiation": "Intermediate",
                   "lstyle_shopping_style": "Brand loyal", "att_brand_loyalty": "Enthusiast"},
        "young": {"ind_e_commerce": "Some exposure", "ind_retail": "Some exposure",
                  "skill_negotiation": "Beginner",
                  "lstyle_shopping_style": "Bargain hunter", "att_brand_loyalty": "Skeptical"},
        "practical": {"ind_e_commerce": "Some exposure", "ind_retail": "None",
                      "skill_negotiation": "Intermediate",
                      "lstyle_shopping_style": "Minimalist", "att_brand_loyalty": "Positive"},
    },
    "health": {
        "expert": {"ind_healthcare": "Veteran", "ind_fitness_wellness": "Experienced",
                   "fam_nutrition": "Expert", "topic_fitness": "Passionate",
                   "lstyle_exercise_freq": "Daily"},
        "senior": {"ind_healthcare": "Some exposure", "ind_fitness_wellness": "None",
                   "fam_nutrition": "Aware", "topic_fitness": "Neutral",
                   "lstyle_exercise_freq": "Rarely"},
        "young": {"ind_healthcare": "None", "ind_fitness_wellness": "Some exposure",
                  "fam_nutrition": "Familiar", "topic_fitness": "Passionate",
                  "lstyle_exercise_freq": "Weekly"},
        "practical": {"ind_healthcare": "Some exposure",
                      "ind_fitness_wellness": "Some exposure",
                      "fam_nutrition": "Familiar", "topic_fitness": "Interested",
                      "lstyle_exercise_freq": "Weekly"},
    },
    "food": {
        "expert": {"ind_food_beverage": "Veteran", "ind_hospitality": "Experienced",
                   "skill_cooking": "Master", "topic_cooking": "Passionate",
                   "lstyle_diet_type": "Omnivore"},
        "senior": {"ind_food_beverage": "Some exposure", "ind_hospitality": "None",
                   "skill_cooking": "Advanced", "topic_cooking": "Interested",
                   "lstyle_diet_type": "Flexitarian"},
        "young": {"ind_food_beverage": "Some exposure", "ind_hospitality": "None",
                  "skill_cooking": "Beginner", "topic_cooking": "Interested",
                  "lstyle_diet_type": "Vegetarian"},
        "practical": {"ind_food_beverage": "None", "ind_hospitality": "None",
                      "skill_cooking": "Intermediate", "topic_cooking": "Neutral",
                      "lstyle_diet_type": "Omnivore"},
    },
    "productivity": {
        "expert": {"skill_time_management": "Master", "skill_writing": "Advanced",
                   "habit_inbox_zero_discipline": "Daily",
                   "fam_organizational_psychology": "Proficient",
                   "topic_productivity": "Passionate"},
        "senior": {"skill_time_management": "Intermediate", "skill_writing": "Intermediate",
                   "habit_inbox_zero_discipline": "Rarely",
                   "fam_organizational_psychology": "None",
                   "topic_productivity": "Indifferent"},
        "young": {"skill_time_management": "Beginner", "skill_writing": "Intermediate",
                  "habit_inbox_zero_discipline": "Never",
                  "fam_organizational_psychology": "Aware",
                  "topic_productivity": "Interested"},
        "practical": {"skill_time_management": "Advanced", "skill_writing": "Intermediate",
                      "habit_inbox_zero_discipline": "Weekly",
                      "fam_organizational_psychology": "Familiar",
                      "topic_productivity": "Interested"},
    },
    "professional": {
        "expert": {"ind_consulting": "Veteran", "skill_networking": "Master",
                   "val_career_success": "Core value",
                   "lifex_career_path_shape": "Linear climb", "skill_leadership": "Master"},
        "senior": {"ind_consulting": "Some exposure", "skill_networking": "Intermediate",
                   "val_career_success": "Moderate",
                   "lifex_career_path_shape": "Linear climb", "skill_leadership": "Advanced"},
        "young": {"ind_consulting": "None", "skill_networking": "Beginner",
                  "val_career_success": "Important",
                  "lifex_career_path_shape": "Just starting", "skill_leadership": "Beginner"},
        "practical": {"ind_consulting": "Some exposure", "skill_networking": "Advanced",
                      "val_career_success": "Important",
                      "lifex_career_path_shape": "Pivoted once", "skill_leadership": "Advanced"},
    },
}


def family_of_key(name: str) -> str:
    """The family a persona key belongs to: the part before its role."""
    family = name.split("-", 1)[0]
    if family not in FAMILY_DIMENSIONS:
        raise AssertionError(
            f"persona {name!r} names family {family!r}, which is not in "
            f"FAMILY_DIMENSIONS ({sorted(FAMILY_DIMENSIONS)})")
    return family


def dimensions_for(family: str) -> tuple[str, ...]:
    """Everyone's dimensions, plus this family's own."""
    if family not in FAMILY_DIMENSIONS:
        raise AssertionError(
            f"unknown persona family {family!r}; known: {sorted(FAMILY_DIMENSIONS)}")
    repeated = [d for d in FAMILY_DIMENSIONS[family] if d in CORE_DIMENSIONS]
    # A dimension in both places would be rendered twice and would let one
    # family quietly carry a different value for a shared trait.
    assert not repeated, f"family {family} repeats core dimension(s): {repeated}"
    return tuple(CORE_DIMENSIONS) + FAMILY_DIMENSIONS[family]


def _p(role: str, note: str, family: str = "", **overrides: str) -> dict:
    """A persona: the role baseline, the family's defaults, this person on top.

    `family` defaults to the one the persona key names (see PROFILES below); the
    role's domain defaults fill in what the profile does not say itself.
    """
    values = {**_ROLE_BASE[role], **overrides}
    # `overrides` is what this author actually asked for; the baseline is shared
    # across families and is filtered to the family's dimensions later, while an
    # override outside them is a mistake that must be reported.
    return {"note": note, "role": role, "family": family, "values": values,
            "explicit": tuple(overrides)}


PROFILES: dict[str, dict] = {
    # --- travel: flights, stays, rides, itineraries (Staynb, Udriver)
    "travel-expert": _p(
        "expert",
        "Career travel and transit professional: deep domain expertise, high tech "
        "fluency, plans in detail, no physical or access constraints.",
        seniority="Lead / Principal", lifex_geographic_mobility="Serial relocator",
        topic_technology="Passionate", att_new_technology="Enthusiast",
        cog_big_picture_vs_detail="Both", health_vision="Normal",
        habit_budget_tracking="Weekly",
    ),
    "travel-senior": _p(
        "senior",
        "Retired and rarely travels, cautious with money and with new technology, "
        "mild mobility and vision limits, wants the gist.",
        age_bracket="75-84", socioeconomic_band="Low income",
        demo_household_income="<$25k", lstyle_planning_horizon="Day-to-day",
    ),
    "travel-young": _p(
        "young",
        "College student on a tight budget: phone-first, fluent with apps but no "
        "travel expertise, spontaneous, wants it quick and cheap.",
        age_bracket="18-24", seniority="Student / intern",
        pref_save_vs_spend="Hard saver", topic_technology="Interested",
    ),
    "travel-practical": _p(
        "practical",
        "Recent immigrant with limited English: capable adult on a schedule, uses a "
        "phone translator, unfamiliar with local booking sites and customs.",
        age_bracket="25-34", region="East Asia", seniority="Entry",
        socioeconomic_band="Lower-middle", demo_household_income="$25k-50k",
        accessibility_needs="Language barrier", att_new_technology="Neutral",
        cog_patience="High", cog_detail_orientation="Moderate",
        cog_risk_framing="Threat-focused", lstyle_frugality="Frugal saver",
        pref_save_vs_spend="Saver-leaning", economic_motivation="Cost-sensitive",
        habit_budget_tracking="Weekly", health_vision="Normal",
        lifex_geographic_mobility="Moved internationally",
    ),
    # --- science: study help, degree programmes, research methods, teaching material
    "science-expert": _p(
        "expert",
        "Tenured researcher who reads the methods section first and wants every "
        "citation, deadline and eligibility clause spelled out.",
        age_bracket="45-54", region="Western Europe", urbanicity="Small town",
        seniority="Lead / Principal", lifex_geographic_mobility="Serial relocator",
        lstyle_planning_horizon="Yearly",
        topic_technology="Passionate", skill_budgeting="Master",
        cog_patience="Very high", cog_big_picture_vs_detail="Detail-obsessed",
        habit_budget_tracking="Weekly", health_vision="Normal", cog_risk_framing="Balanced",
    ),
    "science-senior": _p(
        "senior",
        "Retired schoolteacher auditing a continuing-education course: careful and "
        "well-read, but wants the gist in large type.",
        urbanicity="Small town", socioeconomic_band="Middle",
        skill_budgeting="Advanced", health_mobility="Full",
        lstyle_planning_horizon="Monthly", cog_detail_orientation="High",
        cog_patience="High", habit_budget_tracking="Weekly",
        cog_big_picture_vs_detail="Both", region="Western Europe",
    ),
    "science-young": _p(
        "young",
        "Undergraduate cramming the night before: wants the answer, not the reading "
        "list.",
        age_bracket="18-24", seniority="Student / intern",
        lifex_geographic_mobility="Moved within region", topic_technology="Interested",
        skill_budgeting="None", cog_attention_span="Very short",
        cog_detail_orientation="None", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never",
        urbanicity="Small town", health_vision="Normal", ),
    "science-practical": _p(
        "practical",
        "Parent hunting down free school resources for a child's project: patient, "
        "penny-watching, not a scientist.",
        age_bracket="35-44", seniority="Mid", socioeconomic_band="Lower-middle",
        urbanicity="Small town", tech_savviness="Cautious adopter",
        att_new_technology="Neutral", skill_budgeting="Advanced",
        lstyle_frugality="Frugal saver", pref_save_vs_spend="Hard saver",
        economic_motivation="Cost-sensitive", cog_detail_orientation="Moderate",
        cog_patience="High", pref_detail_brief_vs_full="Balanced",
        habit_budget_tracking="Weekly", region="Latin America",
        health_vision="Normal", lifex_geographic_mobility="Never left hometown",
    ),
    # --- tech: consumer hardware, software troubleshooting, subscriptions, literacy
    "tech-expert": _p(
        "expert",
        "Infrastructure engineer who reads spec sheets and changelogs for fun and "
        "expects exact model numbers and version caveats.",
        age_bracket="25-34", seniority="Lead / Principal",
        socioeconomic_band="High income", topic_technology="Passionate",
        att_new_technology="Enthusiast",
        risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Daily", region="East Asia",
        lifex_geographic_mobility="Moved internationally", cog_risk_framing="Opportunity-focused", lstyle_planning_horizon="Weekly",
        lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning",
    ),
    "tech-senior": _p(
        "senior",
        "Eighty-year-old who assumes every pop-up is a scam and wants the recurring "
        "charges on the phone bill explained plainly.",
        age_bracket="75-84", urbanicity="Small town", tech_savviness="Avoidant",
        att_new_technology="Opposed", topic_technology="Averse",
        health_mobility="Moderate limitation", cog_patience="Low",
        cog_attention_span="Very short", habit_budget_tracking="Daily", region="North America",
        lifex_geographic_mobility="Never left hometown", skill_budgeting="Beginner", cog_big_picture_vs_detail="Big-picture",
    ),
    "tech-young": _p(
        "young",
        "Nineteen-year-old PC builder and gamer: knows the hardware, blows the "
        "budget, reads only the benchmark number.",
        age_bracket="18-24", seniority="Student / intern", urbanicity="Rural",
        lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_attention_span="Very short",
        habit_budget_tracking="Never", region="Western Europe",
        lifex_geographic_mobility="Never left hometown", skill_budgeting="Intermediate",
        lstyle_planning_horizon="Monthly",
    ),
    "tech-practical": _p(
        "practical",
        "Middle-school teacher vetting classroom software on a district budget: "
        "capable but deliberately slow to adopt anything new.",
        seniority="Mid", socioeconomic_band="Lower-middle", urbanicity="Small town",
        tech_savviness="Cautious adopter", att_new_technology="Skeptical",
        topic_technology="Neutral", skill_budgeting="Advanced", cog_patience="High",
        cog_attention_span="Long", cog_risk_framing="Threat-focused",
        pref_detail_brief_vs_full="Detail-leaning", device_context="Desktop, focused",
        economic_motivation="Cost-sensitive", habit_budget_tracking="Weekly",
        region="North America", health_vision="Normal",
        ),
    # --- community: local events, food pantries, donations, holidays, volunteering
    "community-expert": _p(
        "expert",
        "Nonprofit programme director who runs the city's pantry network and tracks "
        "every hour, dollar and eligibility rule.",
        age_bracket="45-54", seniority="Director", socioeconomic_band="Middle",
        lifex_geographic_mobility="Never left hometown",
        lstyle_planning_horizon="Yearly", skill_budgeting="Master",
        cog_patience="Very high", habit_budget_tracking="Weekly",
        health_vision="Normal", cog_attention_span="Long",
        cog_risk_framing="Opportunity-focused",
    ),
    "community-senior": _p(
        "senior",
        "Church volunteer coordinator in her late seventies, lifelong local, needs "
        "a ride to everything she signs up for.",
        age_bracket="75-84", urbanicity="Small town", socioeconomic_band="Low income",
        lifex_geographic_mobility="Never left hometown",
        health_mobility="Uses mobility aid",
        cog_patience="High",
        habit_budget_tracking="Weekly", cog_attention_span="Average",
        skill_budgeting="Advanced", cog_big_picture_vs_detail="Detail",
    ),
    "community-young": _p(
        "young",
        "Student mutual-aid organiser: coordinates a donation drive from a group "
        "chat and cares who the money reaches.",
        age_bracket="18-24", seniority="Student / intern",
        lifex_geographic_mobility="Never left hometown",
        topic_technology="Interested",
        cog_detail_orientation="Moderate", cog_patience="High",
        economic_motivation="Cost-sensitive", habit_budget_tracking="Weekly",
        region="Sub-Saharan Africa", health_vision="Normal",
        lstyle_planning_horizon="Monthly",
        cog_attention_span="Short", urbanicity="Small town",
        cog_risk_framing="Balanced", ),
    "community-practical": _p(
        "practical",
        "Suburban parent organising the block's holiday potluck around two jobs and "
        "a school run: wants the shortest workable plan.",
        age_bracket="35-44", seniority="Mid", lstyle_planning_horizon="Monthly",
        pref_plan_vs_spontaneous="Highly planned", cog_patience="Moderate",
        cog_attention_span="Short", habit_budget_tracking="Weekly",
        region="North America", health_vision="Normal",
        cog_risk_framing="Opportunity-focused", ),
    # --- art: crafts, decoration, creative projects
    "art-expert": _p(
        "expert",
        "Working studio artist and gallery exhibitor: exacting about materials and "
        "willing to pay for the right pigment.",
        region="Western Europe", seniority="Founder", socioeconomic_band="Lower-middle",
        tech_savviness="Comfortable", topic_technology="Neutral",
        lstyle_frugality="Spender", pref_save_vs_spend="Spender-leaning",
        economic_motivation="Premium-seeking",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Weekly",
        urbanicity="Small town", cog_risk_framing="Opportunity-focused",
        health_vision="Normal", lstyle_planning_horizon="Yearly",
    ),
    "art-senior": _p(
        "senior",
        "Rural quilter with arthritic hands and a magnifier: decades of craft "
        "skill, no patience for a website.",
        urbanicity="Small town", socioeconomic_band="Lower-middle",
        health_mobility="Moderate limitation", skill_budgeting="Advanced",
        cog_detail_orientation="Very high", cog_patience="Very high",
        lstyle_planning_horizon="Monthly", habit_budget_tracking="Weekly",
        lifex_geographic_mobility="Never left hometown", cog_attention_span="Average",
        cog_big_picture_vs_detail="Detail", lstyle_frugality="Balanced", cog_risk_framing="Balanced",
        region="Eastern Europe",
    ),
    "art-young": _p(
        "young",
        "Makes small craft goods to resell online, shops from a phone, chases "
        "whatever is trending this week.",
        urbanicity="Suburban", topic_technology="Interested", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_detail_orientation="Moderate",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never", lifex_geographic_mobility="Moved within region",
        health_vision="Normal", lstyle_planning_horizon="Day-to-day", ),
    "art-practical": _p(
        "practical",
        "Redecorating one room over a weekend: has the budget, not the time, wants "
        "three good options and a shopping list.",
        age_bracket="35-44", seniority="Senior", socioeconomic_band="Upper-middle",
        lstyle_frugality="Spender", pref_save_vs_spend="Spender-leaning",
        economic_motivation="Premium-seeking",
        dospert_financial_risk_tolerance="Average", cog_detail_orientation="Moderate",
        lstyle_planning_horizon="Monthly", device_context="Desktop, focused",
        habit_budget_tracking="Rarely",
    ),
    # --- lifestyle: clothing, gifts, home, personal organisation, housing listings
    "lifestyle-expert": _p(
        "expert",
        "Personal stylist and professional organiser: knows fit, fabric and brand "
        "tiers cold and itemises everything.",
        region="Western Europe", seniority="Founder", skill_budgeting="Master", economic_motivation="Premium-seeking",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Daily",
        health_vision="Normal",
        cog_risk_framing="Opportunity-focused", lstyle_planning_horizon="Weekly",
    ),
    "lifestyle-senior": _p(
        "senior",
        "Widower in his late seventies downsizing to a one-bedroom: anxious about "
        "the move, counts every dollar of it.",
        age_bracket="75-84", socioeconomic_band="Middle",
        health_mobility="Uses mobility aid", cog_patience="High", lstyle_planning_horizon="Monthly",
        pref_plan_vs_spontaneous="Highly planned", habit_budget_tracking="Daily",
        region="Southeast Asia", lifex_geographic_mobility="Moved nationally",
        cog_attention_span="Average", cog_big_picture_vs_detail="Both",
    ),
    "lifestyle-young": _p(
        "young",
        "Furnishing a first apartment on a deposit-sized budget: hunts secondhand "
        "and walks away from anything over the number.",
        seniority="Entry", socioeconomic_band="Low income",
        skill_budgeting="Intermediate", pref_save_vs_spend="Hard saver",
        topic_technology="Interested",
        cog_detail_orientation="Moderate", cog_patience="Moderate",
        pref_plan_vs_spontaneous="Balanced", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Weekly", region="East Asia",
        health_vision="Normal", cog_big_picture_vs_detail="Detail",
    ),
    "lifestyle-practical": _p(
        "practical",
        "Buying birthday gifts and household replacements between meetings: decide "
        "it now, one link, done.",
        seniority="Manager", cog_detail_orientation="Moderate",
        cog_attention_span="Short", cog_big_picture_vs_detail="Big-picture",
        pref_detail_brief_vs_full="Just the gist", pref_plan_vs_spontaneous="Balanced",
        lstyle_planning_horizon="Day-to-day", habit_budget_tracking="Weekly",
        region="Western Europe", lifex_geographic_mobility="Moved nationally",
        cog_risk_framing="Opportunity-focused",
    ),
    # --- ecommerce: product comparison, sneakers, cars, deals
    "ecommerce-expert": _p(
        "expert",
        "Retail category buyer: compares unit prices, return windows and warranty "
        "terms before anything else.",
        seniority="Senior", topic_technology="Passionate", skill_budgeting="Master", risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Daily", urbanicity="Suburban",
        lifex_geographic_mobility="Moved within region", cog_risk_framing="Threat-focused", health_vision="Normal",
        lstyle_planning_horizon="Weekly",
    ),
    "ecommerce-senior": _p(
        "senior",
        "Retired mechanic replacing a truck: sure he will be upsold, so every "
        "number gets checked twice.",
        urbanicity="Rural", socioeconomic_band="Middle",
        health_mobility="Full", cog_detail_orientation="High", cog_patience="High",
        pref_detail_brief_vs_full="Just the gist",
        habit_budget_tracking="Daily",
        region="North America", lifex_geographic_mobility="Never left hometown",
        cog_big_picture_vs_detail="Detail",
        cog_attention_span="Long", ),
    "ecommerce-young": _p(
        "young",
        "Sneaker resale hunter: drop times, stock alerts and resale margins, "
        "decided in seconds on a phone.",
        age_bracket="18-24", seniority="Student / intern",
        lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_patience="None",
        cog_attention_span="Very short", cog_detail_orientation="None",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never",
        region="MENA", lifex_geographic_mobility="Moved internationally",
        health_vision="Corrected",
        lstyle_planning_horizon="Day-to-day", ),
    "ecommerce-practical": _p(
        "practical",
        "Comparing family SUVs with a firm ceiling and a trade-in: wants the three- "
        "row, safety-rated shortlist and the total cost.",
        socioeconomic_band="Middle",
        skill_budgeting="Advanced",
        cog_detail_orientation="Very high", cog_attention_span="Long",
        lstyle_planning_horizon="Monthly", pref_save_vs_spend="Saver-leaning",
        device_context="Desktop, focused", habit_budget_tracking="Weekly",
        urbanicity="Rural", health_vision="Normal",
        cog_risk_framing="Threat-focused", ),
    # --- health: gyms, yoga, clinics, surgeons, fitness plans
    "health-expert": _p(
        "expert",
        "Physiotherapist who screens credentials and contraindications before "
        "recommending anything and cites the evidence.",
        seniority="Senior", lstyle_planning_horizon="Yearly", risk_tolerance="Cautious",
        dospert_financial_risk_tolerance="Low", cog_risk_framing="Threat-focused",
        cog_patience="Very high", economic_motivation="Premium-seeking",
        health_vision="Normal", habit_budget_tracking="Rarely", region="Oceania",
        urbanicity="Small town", lifex_geographic_mobility="Moved within region",
        cog_attention_span="Long",
        att_new_technology="Neutral",
        socioeconomic_band="High income",
    ),
    "health-senior": _p(
        "senior",
        "Eighty-one, six weeks after a hip replacement: needs low-impact classes "
        "she can actually get to, and no surprises.",
        age_bracket="75-84", socioeconomic_band="Middle",
        health_mobility="Uses mobility aid", tech_savviness="Avoidant",
        topic_technology="Averse", cog_patience="High",
        region="Oceania", cog_detail_orientation="Low",
        cog_big_picture_vs_detail="Big-picture only", cog_attention_span="Very short",
        lstyle_planning_horizon="Day-to-day", skill_budgeting="Beginner",
    ),
    "health-young": _p(
        "young",
        "Trains six days a week on the cheapest membership in town and pushes past "
        "what a coach would advise.",
        health_vision="Normal", risk_tolerance="Risk-seeking", topic_technology="Interested",
        cog_detail_orientation="Moderate", cog_attention_span="Short",
        pref_plan_vs_spontaneous="Planned", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Monthly", region="Western Europe", urbanicity="Suburban",
        lifex_geographic_mobility="Moved within region",
        cog_big_picture_vs_detail="Detail", ),
    "health-practical": _p(
        "practical",
        "Fitting a realistic fitness plan into a manager's calendar: tell me the "
        "three sessions a week that work and where.",
        socioeconomic_band="Upper-middle", seniority="Manager",
        health_mobility="Mild limitation", cog_patience="None",
        cog_attention_span="Short", dospert_financial_risk_tolerance="Average",
        pref_plan_vs_spontaneous="Highly planned", lstyle_planning_horizon="Weekly",
        economic_motivation="Value-driven", habit_budget_tracking="Rarely",
        region="East Asia", urbanicity="Dense urban", ),
    # --- food: recipes, meal prep, catering, restaurant booking, delivery
    "food-expert": _p(
        "expert",
        "Line-cook-turned-caterer: thinks in yields, substitutions and allergen "
        "handling, and wants grams, not cups.",
        age_bracket="25-34", region="Western Europe", seniority="Lead / Principal",
        socioeconomic_band="Middle", skill_budgeting="Master",
        lstyle_planning_horizon="Day-to-day", cog_patience="Very high",
        cog_big_picture_vs_detail="Detail-obsessed",
        economic_motivation="Premium-seeking", habit_budget_tracking="Daily",
        urbanicity="Small town", cog_risk_framing="Opportunity-focused", lstyle_frugality="Spender", cog_attention_span="Long",
        risk_tolerance="Risk-tolerant",
    ),
    "food-senior": _p(
        "senior",
        "Cooks for two on a fixed income with a low-sodium restriction: wants "
        "simple swaps, not a new cuisine.",
        urbanicity="Rural", socioeconomic_band="Low income",
        skill_budgeting="Master", cog_detail_orientation="Very high",
        cog_patience="High", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Daily", region="Southeast Asia",
        lifex_geographic_mobility="Moved nationally",
        cog_attention_span="Average", cog_big_picture_vs_detail="Both",
        topic_technology="Averse",
    ),
    "food-young": _p(
        "young",
        "Cooks almost nothing: delivery, twenty-minute recipes and whatever has a "
        "promo code on it tonight.",
        skill_budgeting="None", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", cog_detail_orientation="None",
        cog_attention_span="Very short", cog_patience="None",
        dospert_financial_risk_tolerance="Very high",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never", urbanicity="Suburban",
        lifex_geographic_mobility="Never left hometown",
        health_vision="Normal",
    ),
    "food-practical": _p(
        "practical",
        "Plans weeknight dinners for a family of four every Sunday: one list, one "
        "shop, nothing exotic.",
        age_bracket="35-44", seniority="Mid", skill_budgeting="Advanced",
        lstyle_frugality="Frugal saver", pref_save_vs_spend="Saver-leaning",
        economic_motivation="Cost-sensitive", pref_plan_vs_spontaneous="Highly planned",
        cog_detail_orientation="Very high", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Weekly", region="Latin America",
        lifex_geographic_mobility="Moved nationally", health_vision="Normal", cog_risk_framing="Threat-focused",
    ),
    # --- productivity: GoMail / GoCalendar inbox triage and scheduling
    "productivity-expert": _p(
        "expert",
        "Chief of staff who lives in someone else's inbox and calendar: rules, "
        "labels, conflicts and time zones, all explicit.",
        seniority="Director", topic_technology="Passionate",
        att_new_technology="Enthusiast", risk_tolerance="Cautious",
        dospert_financial_risk_tolerance="Low", cog_patience="Very high",
        cog_big_picture_vs_detail="Detail-obsessed", skill_budgeting="Advanced",
        habit_budget_tracking="Weekly", region="Eastern Europe", urbanicity="Suburban",
        lifex_geographic_mobility="Moved internationally",
        health_vision="Normal", ),
    "productivity-senior": _p(
        "senior",
        "Semi-retired consultant with four thousand unread messages: comfortable "
        "money, no interest in learning the interface.",
        socioeconomic_band="Upper-middle", lstyle_frugality="Balanced",
        pref_save_vs_spend="Balanced", economic_motivation="Indifferent",
        dospert_financial_risk_tolerance="Low", cog_detail_orientation="Low",
        cog_patience="Low", habit_budget_tracking="Rarely", region="Western Europe",
        cog_big_picture_vs_detail="Big-picture only",
        cog_attention_span="Average", lifex_geographic_mobility="Moved internationally",
        skill_budgeting="Advanced",
    ),
    "productivity-young": _p(
        "young",
        "First office job, runs the whole inbox from a phone between other tabs and "
        "misses half the calendar invites.",
        socioeconomic_band="Lower-middle", urbanicity="Suburban",
        health_vision="Normal",
        cog_attention_span="Very short", pref_plan_vs_spontaneous="Highly spontaneous",
        habit_budget_tracking="Never", region="Eastern Europe",
        lstyle_frugality="Balanced", pref_save_vs_spend="Spender-leaning",
    ),
    "productivity-practical": _p(
        "practical",
        "Triages the inbox in the ten minutes between meetings: what needs an "
        "answer today, and nothing else.",
        socioeconomic_band="Upper-middle", urbanicity="Dense urban",
        skill_budgeting="Advanced",
        cog_patience="None", cog_attention_span="Short",
        cog_big_picture_vs_detail="Big-picture",
        pref_detail_brief_vs_full="Just the gist", lstyle_planning_horizon="Day-to-day",
        economic_motivation="Indifferent", habit_budget_tracking="Rarely",
        health_vision="Normal",
        cog_risk_framing="Opportunity-focused",
    ),
    # --- professional: job search, hiring, networking, freelance marketplaces
    "professional-expert": _p(
        "expert",
        "Talent lead who screens dozens of profiles a week: wants titles, dates, "
        "comp bands and the sourcing rationale.",
        seniority="Director", lifex_geographic_mobility="Serial relocator",
        risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High", lstyle_planning_horizon="Yearly",
        skill_budgeting="Master", cog_patience="High",
        cog_risk_framing="Opportunity-focused", health_vision="Normal",
        habit_budget_tracking="Monthly", region="South Asia", urbanicity="Dense urban", cog_attention_span="Long",
    ),
    "professional-senior": _p(
        "senior",
        "Retired at sixty-eight, now wants part-time work: strong track record, no "
        "idea how modern job sites behave.",
        urbanicity="Small town", lifex_geographic_mobility="Never left hometown",
        topic_technology="Averse", att_new_technology="Opposed",
        cog_detail_orientation="High", cog_attention_span="Average",
        skill_budgeting="Advanced", habit_budget_tracking="Daily",
        region="North America", cog_big_picture_vs_detail="Both", lstyle_planning_horizon="Monthly",
    ),
    "professional-young": _p(
        "young",
        "New graduate firing off applications from a phone on the bus: volume over "
        "tailoring, checks nothing twice.",
        age_bracket="18-24", seniority="Student / intern", urbanicity="Suburban",
        lifex_geographic_mobility="Never left hometown",
        risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_patience="None",
        cog_attention_span="Very short", habit_budget_tracking="Never",
        health_vision="Normal", skill_budgeting="Intermediate", lstyle_planning_horizon="Weekly",
        cog_big_picture_vs_detail="Big-picture only", region="Latin America",
    ),
    "professional-practical": _p(
        "practical",
        "Mid-career switcher with a mortgage: needs the shortlist that actually "
        "pays, and will not gamble on it.",
        seniority="Senior", topic_technology="Interested",
        lstyle_frugality="Frugal saver", pref_save_vs_spend="Saver-leaning",
        economic_motivation="Cost-sensitive", cog_patience="Moderate",
        cog_attention_span="Average", cog_risk_framing="Threat-focused",
        lstyle_planning_horizon="Monthly", device_context="Desktop, focused",
        habit_budget_tracking="Daily", region="Oceania", urbanicity="Small town",
        health_vision="Normal", lifex_geographic_mobility="Moved nationally",
        dospert_financial_risk_tolerance="Very low", risk_tolerance="Risk-averse",
    ),
}


def main(check: bool = False) -> None:
    schema = {d["id"]: d for d in json.loads(SCHEMA.read_text(encoding="utf-8"))["dimensions"]}
    missing = [d for d in CORE_DIMENSIONS if d not in schema]
    assert not missing, f"not in dimensions.json: {missing}"
    evaluation_unknown = [d for d in EVALUATION_DIMENSIONS if d not in CORE_DIMENSIONS]
    assert not evaluation_unknown, (
        f"evaluation dimensions absent from CORE_DIMENSIONS: {evaluation_unknown}"
    )
    assert len(set(EVALUATION_DIMENSIONS)) == len(EVALUATION_DIMENSIONS), (
        "duplicate EVALUATION_DIMENSIONS"
    )

    # Two personas with identical values are one persona wearing two names, and any
    # difference the benchmark reports between them is noise.
    # A family's own dimensions must exist too, or a persona would claim
    # expertise the schema has no word for.
    absent = [d for d in BRANCHING_DIMENSIONS if d not in CORE_DIMENSIONS]
    assert not absent, (
        f"the persona tree branches on {absent}, so every persona needs them; "
        f"add them to CORE_DIMENSIONS")
    for family, dims in FAMILY_DIMENSIONS.items():
        unknown = [d for d in dims if d not in schema]
        assert not unknown, f"family {family}: not in dimensions.json: {unknown}"
        # Same count everywhere, or a persona in one domain is drawn in more
        # detail than one in another and the two cannot be compared.
        assert len(dims) == 5, (
            f"family {family} has {len(dims)} own dimensions, not 5: {dims}")
        assert len(set(dims)) == 5, f"family {family} repeats a dimension: {dims}"
        for role, values in FAMILY_DEFAULTS.get(family, {}).items():
            extra = set(values) - set(dims)
            assert not extra, f"{family}/{role} sets dimensions outside the family: {extra}"
            for dim_id, value in values.items():
                assert value in schema[dim_id]["values"], (
                    f"{family}/{role}.{dim_id}: {value!r} not allowed; "
                    f"options: {schema[dim_id]['values']}")

    seen: dict[str, str] = {}
    for name, profile in PROFILES.items():
        family = profile.get("family") or family_of_key(name)
        role = profile.get("role")
        defaults = FAMILY_DEFAULTS.get(family, {}).get(role, {}) if role else {}
        wanted = dimensions_for(family)
        stray = [d for d in profile.get("explicit", ()) if d not in wanted]
        assert not stray, (
            f"{name} sets {stray}, which belong to another family; "
            f"{family} has {sorted(set(wanted) - set(CORE_DIMENSIONS))}")
        # The profile wins over the family default, the default fills the gaps,
        # and the shared role baseline contributes only what this family uses.
        profile["values"] = {k: v for k, v in
                             {**defaults, **profile["values"]}.items() if k in wanted}
        profile["family"] = family
        key = json.dumps(profile["values"], sort_keys=True)
        assert key not in seen, f"{name} has the same values as {seen[key]}"
        seen[key] = name

    OUT.mkdir(parents=True, exist_ok=True)
    stale: list[str] = []
    for name, profile in PROFILES.items():
        wanted = dimensions_for(profile["family"])
        assert set(profile["values"]) == set(wanted), (
            f"{name} must set exactly its family's dimension set "
            f"({profile['family']}); "
            f"missing={set(wanted) - set(profile['values'])} "
            f"extra={set(profile['values']) - set(wanted)}"
        )
        attributes = {}
        for dim_id in wanted:
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
            "version": "2.1",
            "family": profile["family"],
            "source": "hand-specified from dimensions.json (MatrAIx 1290-dim schema)",
            "note": profile["note"],
            "evaluation_dimensions": list(EVALUATION_DIMENSIONS),
            "attributes": attributes,
        }
        path = OUT / f"{name}.yaml"
        text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
        if check:
            if not path.is_file():
                stale.append(f"{path.name} is missing")
            elif path.read_text(encoding="utf-8") != text:
                stale.append(f"{path.name} differs from what this file would write")
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path} ({len(attributes)} dimensions)")

    if check:
        # Only the top level: the matched-pair suites live in subdirectories and
        # are generated by make_matched_personas.py, not here.
        extra = sorted(f.name for f in OUT.glob("*.yaml") if f.stem not in PROFILES)
        for name in extra:
            stale.append(f"{name} has no profile and is left over from an older set")
        if stale:
            raise SystemExit("personas are stale; rerun python odyssey/make_personas.py\n  "
                             + "\n  ".join(stale))
        print(f"{len(PROFILES)} personas match make_personas.py, "
              f"{len(CORE_DIMENSIONS)} shared + 5 family dimensions each")


if __name__ == "__main__":
    import sys

    main(check="--check" in sys.argv[1:])
