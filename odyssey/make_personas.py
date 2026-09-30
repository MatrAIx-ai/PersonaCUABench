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
# Three families replace D with the role the persona tree names instead:
# travel -> non-native-speaker, science -> school-resource parent helper,
# tech -> technology-cautious middle-school teacher.
_ROLE_BASE: dict[str, dict[str, str]] = {
    "expert": {
        "age_bracket": "35-44",
        "region": "North America",
        "urbanicity": "Dense urban",
        "socioeconomic_band": "Upper-middle",
        "demo_driver_status": "Occasional driver",
        "lifex_travel_breadth": "Well-traveled",
        "lifex_geographic_mobility": "Moved nationally",
        "ind_travel_tourism": "None",
        "ind_transportation": "None",
        "seniority": "Senior",
        "tech_savviness": "Digital native",
        "skill_budgeting": "Advanced",
        "skill_driving": "Intermediate",
        "fam_urban_planning": "Aware",
        "topic_travel": "Interested",
        "topic_technology": "Interested",
        "lstyle_travel_freq": "A few trips/yr",
        "lstyle_planning_horizon": "Monthly",
        "lstyle_frugality": "Balanced",
        "att_public_transit": "Positive",
        "att_new_technology": "Positive",
        "risk_tolerance": "Balanced",
        "dospert_financial_risk_tolerance": "Average",
        "cog_detail_orientation": "Very high",
        "cog_patience": "High",
        "cog_attention_span": "Very long",
        "cog_big_picture_vs_detail": "Detail",
        "cog_risk_framing": "Balanced",
        "health_mobility": "Full",
        "health_vision": "Corrected",
        "health_assistive_tech": "None",
        "pref_plan_vs_spontaneous": "Highly planned",
        "pref_save_vs_spend": "Balanced",
        "pref_detail_brief_vs_full": "Every detail",
        "accessibility_needs": "None",
        "device_context": "Desktop, focused",
        "economic_motivation": "Value-driven",
        "habit_budget_tracking": "Monthly",
    },
    "senior": {
        "age_bracket": "65-74",
        "region": "North America",
        "urbanicity": "Suburban",
        "socioeconomic_band": "Lower-middle",
        "demo_driver_status": "Licensed, rarely drives",
        "lifex_travel_breadth": "A few countries",
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
        "lstyle_planning_horizon": "Weekly",
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
    "young": {
        "age_bracket": "25-34",
        "region": "North America",
        "urbanicity": "Dense urban",
        "socioeconomic_band": "Low income",
        "demo_driver_status": "Non-driver",
        "lifex_travel_breadth": "A few countries",
        "lifex_geographic_mobility": "Moved nationally",
        "ind_travel_tourism": "None",
        "ind_transportation": "None",
        "seniority": "Entry",
        "tech_savviness": "Digital native",
        "skill_budgeting": "Beginner",
        "skill_driving": "None",
        "fam_urban_planning": "Aware",
        "topic_travel": "Interested",
        "topic_technology": "Passionate",
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
        "pref_save_vs_spend": "Saver-leaning",
        "pref_detail_brief_vs_full": "Brief-leaning",
        "accessibility_needs": "None",
        "device_context": "Mobile, on-the-go",
        "economic_motivation": "Cost-sensitive",
        "habit_budget_tracking": "Rarely",
    },
    "practical": {
        "age_bracket": "45-54",
        "region": "North America",
        "urbanicity": "Suburban",
        "socioeconomic_band": "Middle",
        "demo_driver_status": "Daily driver",
        "lifex_travel_breadth": "A few countries",
        "lifex_geographic_mobility": "Moved within region",
        "ind_travel_tourism": "None",
        "ind_transportation": "None",
        "seniority": "Manager",
        "tech_savviness": "Comfortable",
        "skill_budgeting": "Intermediate",
        "skill_driving": "Advanced",
        "fam_urban_planning": "Aware",
        "topic_travel": "Neutral",
        "topic_technology": "Neutral",
        "lstyle_travel_freq": "Occasional",
        "lstyle_planning_horizon": "Weekly",
        "lstyle_frugality": "Balanced",
        "att_public_transit": "Neutral",
        "att_new_technology": "Positive",
        "risk_tolerance": "Cautious",
        "dospert_financial_risk_tolerance": "Low",
        "cog_detail_orientation": "High",
        "cog_patience": "Low",
        "cog_attention_span": "Average",
        "cog_big_picture_vs_detail": "Both",
        "cog_risk_framing": "Balanced",
        "health_mobility": "Full",
        "health_vision": "Corrected",
        "health_assistive_tech": "None",
        "pref_plan_vs_spontaneous": "Planned",
        "pref_save_vs_spend": "Balanced",
        "pref_detail_brief_vs_full": "Brief-leaning",
        "accessibility_needs": "None",
        "device_context": "Mobile, on-the-go",
        "economic_motivation": "Value-driven",
        "habit_budget_tracking": "Monthly",
    },
}


def _p(role: str, note: str, **overrides: str) -> dict:
    """A persona: the role baseline with this person's own values on top."""
    return {"note": note, "values": {**_ROLE_BASE[role], **overrides}}


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
    # --- science: study help, degree programmes, research methods, teaching material
    "science-expert": _p(
        "expert",
        "Tenured researcher who reads the methods section first and wants every "
        "citation, deadline and eligibility clause spelled out.",
        age_bracket="45-54", region="Western Europe", urbanicity="Small town",
        seniority="Lead / Principal", lifex_travel_breadth="Lived abroad",
        lifex_geographic_mobility="Serial relocator",
        lstyle_travel_freq="Frequent flyer", lstyle_planning_horizon="Yearly",
        topic_technology="Passionate", skill_budgeting="Master",
        cog_patience="Very high", cog_big_picture_vs_detail="Detail-obsessed",
        habit_budget_tracking="Weekly", fam_urban_planning="Familiar",
        health_vision="Normal", cog_risk_framing="Balanced",
        att_public_transit="Enthusiast",
    ),
    "science-senior": _p(
        "senior",
        "Retired schoolteacher auditing a continuing-education course: careful and "
        "well-read, but wants the gist in large type.",
        urbanicity="Small town", socioeconomic_band="Middle",
        lifex_travel_breadth="Never left country", topic_travel="Indifferent",
        skill_budgeting="Advanced", fam_urban_planning="Aware", health_mobility="Full",
        lstyle_planning_horizon="Monthly", cog_detail_orientation="High",
        cog_patience="High", habit_budget_tracking="Weekly",
        cog_big_picture_vs_detail="Both", lstyle_travel_freq="Occasional",
        region="Western Europe",
    ),
    "science-young": _p(
        "young",
        "Undergraduate cramming the night before: wants the answer, not the reading "
        "list.",
        age_bracket="18-24", seniority="Student / intern",
        lifex_travel_breadth="Never left country",
        lifex_geographic_mobility="Moved within region", topic_technology="Interested",
        skill_budgeting="None", cog_attention_span="Very short",
        cog_detail_orientation="None", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never",
        urbanicity="Small town", fam_urban_planning="None",
        att_public_transit="Neutral", health_vision="Normal", lstyle_travel_freq="Rare",
        demo_driver_status="Licensed, rarely drives", skill_driving="Beginner",
        topic_travel="Indifferent",
    ),
    "science-helper": _p(
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
        lifex_travel_breadth="Never left country", fam_urban_planning="None",
        health_vision="Normal", lstyle_travel_freq="Rare",
        lifex_geographic_mobility="Never left hometown",
    ),
    # --- tech: consumer hardware, software troubleshooting, subscriptions, literacy
    "tech-expert": _p(
        "expert",
        "Infrastructure engineer who reads spec sheets and changelogs for fun and "
        "expects exact model numbers and version caveats.",
        age_bracket="25-34", seniority="Lead / Principal",
        socioeconomic_band="High income", topic_technology="Passionate",
        topic_travel="Neutral", att_new_technology="Enthusiast",
        lstyle_travel_freq="Occasional", risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High",
        cog_big_picture_vs_detail="Detail-obsessed", demo_driver_status="Non-driver",
        skill_driving="None", habit_budget_tracking="Daily", region="East Asia",
        lifex_geographic_mobility="Moved internationally", fam_urban_planning="None",
        cog_risk_framing="Opportunity-focused", lstyle_planning_horizon="Weekly",
        att_public_transit="Enthusiast", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning",
    ),
    "tech-senior": _p(
        "senior",
        "Eighty-year-old who assumes every pop-up is a scam and wants the recurring "
        "charges on the phone bill explained plainly.",
        age_bracket="75-84", urbanicity="Small town", tech_savviness="Avoidant",
        att_new_technology="Opposed", topic_technology="Averse",
        demo_driver_status="Cannot drive", skill_driving="None",
        health_mobility="Moderate limitation", cog_patience="Low",
        cog_attention_span="Very short", lifex_travel_breadth="Never left country",
        habit_budget_tracking="Daily", region="North America",
        lifex_geographic_mobility="Never left hometown", fam_urban_planning="None",
        skill_budgeting="Beginner", cog_big_picture_vs_detail="Big-picture",
        lstyle_travel_freq="Homebody",
    ),
    "tech-young": _p(
        "young",
        "Nineteen-year-old PC builder and gamer: knows the hardware, blows the "
        "budget, reads only the benchmark number.",
        age_bracket="18-24", seniority="Student / intern", urbanicity="Rural",
        lifex_travel_breadth="Never left country", topic_travel="Indifferent",
        lstyle_travel_freq="Homebody", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_attention_span="Very short",
        habit_budget_tracking="Never", region="Western Europe",
        lifex_geographic_mobility="Never left hometown", att_public_transit="Neutral",
        fam_urban_planning="None", demo_driver_status="Licensed, rarely drives",
        skill_driving="Beginner", skill_budgeting="Intermediate",
        lstyle_planning_horizon="Monthly",
    ),
    "tech-teacher": _p(
        "practical",
        "Middle-school teacher vetting classroom software on a district budget: "
        "capable but deliberately slow to adopt anything new.",
        seniority="Mid", socioeconomic_band="Lower-middle", urbanicity="Small town",
        tech_savviness="Cautious adopter", att_new_technology="Skeptical",
        topic_technology="Neutral", skill_budgeting="Advanced", cog_patience="High",
        cog_attention_span="Long", cog_risk_framing="Threat-focused",
        pref_detail_brief_vs_full="Detail-leaning", device_context="Desktop, focused",
        economic_motivation="Cost-sensitive", habit_budget_tracking="Weekly",
        region="North America", fam_urban_planning="None", health_vision="Normal",
        lifex_travel_breadth="Never left country", lstyle_travel_freq="Rare",
    ),
    # --- community: local events, food pantries, donations, holidays, volunteering
    "community-expert": _p(
        "expert",
        "Nonprofit programme director who runs the city's pantry network and tracks "
        "every hour, dollar and eligibility rule.",
        age_bracket="45-54", seniority="Director", socioeconomic_band="Middle",
        lifex_geographic_mobility="Never left hometown",
        lifex_travel_breadth="A few countries", lstyle_travel_freq="Rare",
        lstyle_planning_horizon="Yearly", fam_urban_planning="Expert",
        att_public_transit="Enthusiast", skill_budgeting="Master",
        cog_patience="Very high", habit_budget_tracking="Weekly",
        health_vision="Normal", cog_attention_span="Long",
        demo_driver_status="Non-driver", skill_driving="None",
        cog_risk_framing="Opportunity-focused",
    ),
    "community-senior": _p(
        "senior",
        "Church volunteer coordinator in her late seventies, lifelong local, needs "
        "a ride to everything she signs up for.",
        age_bracket="75-84", urbanicity="Small town", socioeconomic_band="Low income",
        lifex_geographic_mobility="Never left hometown",
        lifex_travel_breadth="Never left country", demo_driver_status="Cannot drive",
        skill_driving="None", health_mobility="Uses mobility aid",
        att_public_transit="Positive", topic_travel="Indifferent", cog_patience="High",
        habit_budget_tracking="Weekly", cog_attention_span="Average",
        skill_budgeting="Advanced", cog_big_picture_vs_detail="Detail",
        lstyle_travel_freq="Homebody",
    ),
    "community-young": _p(
        "young",
        "Student mutual-aid organiser: coordinates a donation drive from a group "
        "chat and cares who the money reaches.",
        age_bracket="18-24", seniority="Student / intern",
        lifex_geographic_mobility="Never left hometown",
        lifex_travel_breadth="Well-traveled", topic_technology="Interested",
        fam_urban_planning="Familiar", att_public_transit="Enthusiast",
        cog_detail_orientation="Moderate", cog_patience="High",
        economic_motivation="Cost-sensitive", habit_budget_tracking="Weekly",
        region="Sub-Saharan Africa", health_vision="Normal",
        lstyle_travel_freq="Homebody", lstyle_planning_horizon="Monthly",
        cog_attention_span="Short", urbanicity="Small town",
        cog_risk_framing="Balanced", topic_travel="Passionate",
    ),
    "community-practical": _p(
        "practical",
        "Suburban parent organising the block's holiday potluck around two jobs and "
        "a school run: wants the shortest workable plan.",
        age_bracket="35-44", seniority="Mid", skill_driving="Master",
        topic_travel="Interested", lstyle_planning_horizon="Monthly",
        pref_plan_vs_spontaneous="Highly planned", cog_patience="Moderate",
        cog_attention_span="Short", fam_urban_planning="Familiar",
        att_public_transit="Skeptical", habit_budget_tracking="Weekly",
        region="North America", health_vision="Normal",
        lifex_travel_breadth="Never left country",
        cog_risk_framing="Opportunity-focused", lstyle_travel_freq="Rare",
    ),
    # --- art: crafts, decoration, creative projects
    "art-expert": _p(
        "expert",
        "Working studio artist and gallery exhibitor: exacting about materials and "
        "willing to pay for the right pigment.",
        region="Western Europe", seniority="Founder", socioeconomic_band="Lower-middle",
        lifex_travel_breadth="Lived abroad", topic_travel="Passionate",
        tech_savviness="Comfortable", topic_technology="Neutral",
        lstyle_frugality="Spender", pref_save_vs_spend="Spender-leaning",
        economic_motivation="Premium-seeking",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Weekly",
        urbanicity="Small town", fam_urban_planning="None",
        demo_driver_status="Occasional driver", cog_risk_framing="Opportunity-focused",
        health_vision="Normal", lstyle_planning_horizon="Yearly",
    ),
    "art-senior": _p(
        "senior",
        "Rural quilter with arthritic hands and a magnifier: decades of craft "
        "skill, no patience for a website.",
        urbanicity="Small town", socioeconomic_band="Lower-middle",
        demo_driver_status="Occasional driver", skill_driving="Intermediate",
        health_mobility="Moderate limitation", topic_travel="Indifferent",
        att_public_transit="Skeptical", skill_budgeting="Advanced",
        cog_detail_orientation="Very high", cog_patience="Very high",
        lstyle_planning_horizon="Monthly", habit_budget_tracking="Weekly",
        lifex_geographic_mobility="Never left hometown", cog_attention_span="Average",
        cog_big_picture_vs_detail="Detail", lstyle_travel_freq="Homebody",
        lstyle_frugality="Balanced", cog_risk_framing="Balanced",
        region="Eastern Europe",
    ),
    "art-young": _p(
        "young",
        "Makes small craft goods to resell online, shops from a phone, chases "
        "whatever is trending this week.",
        urbanicity="Suburban", lifex_travel_breadth="Never left country",
        topic_technology="Interested", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_detail_orientation="Moderate",
        pref_plan_vs_spontaneous="Highly spontaneous", att_public_transit="Enthusiast",
        habit_budget_tracking="Never", lifex_geographic_mobility="Moved within region",
        demo_driver_status="Occasional driver", skill_driving="Intermediate",
        health_vision="Normal", lstyle_travel_freq="Rare",
        lstyle_planning_horizon="Day-to-day", fam_urban_planning="None",
    ),
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
        region="Western Europe", seniority="Founder", topic_travel="Passionate",
        lstyle_travel_freq="Frequent flyer", lifex_travel_breadth="Global nomad",
        skill_budgeting="Master", demo_driver_status="Non-driver", skill_driving="None",
        att_public_transit="Enthusiast", economic_motivation="Premium-seeking",
        cog_big_picture_vs_detail="Detail-obsessed", habit_budget_tracking="Daily",
        fam_urban_planning="Familiar", health_vision="Normal",
        cog_risk_framing="Opportunity-focused", lstyle_planning_horizon="Weekly",
    ),
    "lifestyle-senior": _p(
        "senior",
        "Widower in his late seventies downsizing to a one-bedroom: anxious about "
        "the move, counts every dollar of it.",
        age_bracket="75-84", socioeconomic_band="Middle",
        demo_driver_status="Cannot drive", skill_driving="None",
        health_mobility="Uses mobility aid", att_public_transit="Skeptical",
        topic_travel="Neutral", cog_patience="High", lstyle_planning_horizon="Monthly",
        pref_plan_vs_spontaneous="Highly planned", habit_budget_tracking="Daily",
        region="Southeast Asia", lifex_geographic_mobility="Moved nationally",
        cog_attention_span="Average", fam_urban_planning="Aware",
        cog_big_picture_vs_detail="Both",
    ),
    "lifestyle-young": _p(
        "young",
        "Furnishing a first apartment on a deposit-sized budget: hunts secondhand "
        "and walks away from anything over the number.",
        seniority="Entry", socioeconomic_band="Low income",
        skill_budgeting="Intermediate", pref_save_vs_spend="Hard saver",
        att_public_transit="Enthusiast", topic_technology="Interested",
        cog_detail_orientation="Moderate", cog_patience="Moderate",
        pref_plan_vs_spontaneous="Balanced", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Weekly", region="East Asia",
        lifex_travel_breadth="Never left country", fam_urban_planning="Familiar",
        health_vision="Normal", lstyle_travel_freq="Rare",
        cog_big_picture_vs_detail="Detail",
    ),
    "lifestyle-practical": _p(
        "practical",
        "Buying birthday gifts and household replacements between meetings: decide "
        "it now, one link, done.",
        seniority="Manager", skill_driving="Master", cog_detail_orientation="Moderate",
        cog_attention_span="Short", cog_big_picture_vs_detail="Big-picture",
        pref_detail_brief_vs_full="Just the gist", pref_plan_vs_spontaneous="Balanced",
        lstyle_planning_horizon="Day-to-day", habit_budget_tracking="Weekly",
        region="Western Europe", fam_urban_planning="None",
        lstyle_travel_freq="A few trips/yr",
        lifex_geographic_mobility="Moved nationally",
        cog_risk_framing="Opportunity-focused",
    ),
    # --- ecommerce: product comparison, sneakers, cars, deals
    "ecommerce-expert": _p(
        "expert",
        "Retail category buyer: compares unit prices, return windows and warranty "
        "terms before anything else.",
        seniority="Senior", topic_technology="Passionate", topic_travel="Neutral",
        demo_driver_status="Daily driver", skill_driving="Advanced",
        skill_budgeting="Master", risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High",
        cog_big_picture_vs_detail="Detail-obsessed", lstyle_travel_freq="Rare",
        habit_budget_tracking="Daily", urbanicity="Suburban",
        lifex_geographic_mobility="Moved within region", fam_urban_planning="None",
        cog_risk_framing="Threat-focused", health_vision="Normal",
        lstyle_planning_horizon="Weekly",
    ),
    "ecommerce-senior": _p(
        "senior",
        "Retired mechanic replacing a truck: sure he will be upsold, so every "
        "number gets checked twice.",
        urbanicity="Rural", socioeconomic_band="Middle",
        demo_driver_status="Daily driver", skill_driving="Master",
        health_mobility="Full", att_public_transit="Opposed",
        cog_detail_orientation="High", cog_patience="High",
        pref_detail_brief_vs_full="Just the gist",
        lifex_travel_breadth="Never left country", habit_budget_tracking="Daily",
        region="North America", lifex_geographic_mobility="Never left hometown",
        fam_urban_planning="None", cog_big_picture_vs_detail="Detail",
        cog_attention_span="Long", lstyle_travel_freq="Homebody",
    ),
    "ecommerce-young": _p(
        "young",
        "Sneaker resale hunter: drop times, stock alerts and resale margins, "
        "decided in seconds on a phone.",
        age_bracket="18-24", seniority="Student / intern",
        lifex_travel_breadth="Never left country", lstyle_frugality="Spender",
        pref_save_vs_spend="Spender-leaning", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_patience="None",
        cog_attention_span="Very short", cog_detail_orientation="None",
        pref_plan_vs_spontaneous="Highly spontaneous", habit_budget_tracking="Never",
        region="MENA", lifex_geographic_mobility="Moved internationally",
        fam_urban_planning="Aware", health_vision="Corrected",
        lstyle_planning_horizon="Day-to-day", lstyle_travel_freq="Occasional",
    ),
    "ecommerce-practical": _p(
        "practical",
        "Comparing family SUVs with a firm ceiling and a trade-in: wants the three- "
        "row, safety-rated shortlist and the total cost.",
        skill_driving="Master", socioeconomic_band="Middle",
        att_public_transit="Skeptical", skill_budgeting="Advanced",
        cog_detail_orientation="Very high", cog_attention_span="Long",
        lstyle_planning_horizon="Monthly", pref_save_vs_spend="Saver-leaning",
        device_context="Desktop, focused", habit_budget_tracking="Weekly",
        urbanicity="Rural", fam_urban_planning="None",
        lifex_travel_breadth="Never left country", health_vision="Normal",
        cog_risk_framing="Threat-focused", lstyle_travel_freq="Rare",
    ),
    # --- health: gyms, yoga, clinics, surgeons, fitness plans
    "health-expert": _p(
        "expert",
        "Physiotherapist who screens credentials and contraindications before "
        "recommending anything and cites the evidence.",
        seniority="Senior", topic_travel="Neutral", lstyle_travel_freq="Occasional",
        lstyle_planning_horizon="Yearly", risk_tolerance="Cautious",
        dospert_financial_risk_tolerance="Low", cog_risk_framing="Threat-focused",
        cog_patience="Very high", economic_motivation="Premium-seeking",
        health_vision="Normal", habit_budget_tracking="Rarely", region="Oceania",
        urbanicity="Small town", fam_urban_planning="None",
        lifex_geographic_mobility="Moved within region",
        demo_driver_status="Daily driver", skill_driving="Advanced",
        lifex_travel_breadth="A few countries", cog_attention_span="Long",
        att_public_transit="Skeptical", att_new_technology="Neutral",
        socioeconomic_band="High income",
    ),
    "health-senior": _p(
        "senior",
        "Eighty-one, six weeks after a hip replacement: needs low-impact classes "
        "she can actually get to, and no surprises.",
        age_bracket="75-84", socioeconomic_band="Middle",
        demo_driver_status="Non-driver", skill_driving="None",
        health_mobility="Uses mobility aid", tech_savviness="Avoidant",
        topic_technology="Averse", att_public_transit="Positive", cog_patience="High",
        lifex_travel_breadth="Never left country", lstyle_travel_freq="Homebody",
        region="Oceania", cog_detail_orientation="Low",
        cog_big_picture_vs_detail="Big-picture only", cog_attention_span="Very short",
        lstyle_planning_horizon="Day-to-day", fam_urban_planning="Aware",
        skill_budgeting="Beginner",
    ),
    "health-young": _p(
        "young",
        "Trains six days a week on the cheapest membership in town and pushes past "
        "what a coach would advise.",
        health_vision="Normal", risk_tolerance="Risk-seeking", topic_travel="Neutral",
        lstyle_travel_freq="Rare", topic_technology="Interested",
        cog_detail_orientation="Moderate", cog_attention_span="Short",
        pref_plan_vs_spontaneous="Planned", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Monthly", region="Western Europe", urbanicity="Suburban",
        demo_driver_status="Occasional driver", skill_driving="Intermediate",
        fam_urban_planning="None", lifex_geographic_mobility="Moved within region",
        cog_big_picture_vs_detail="Detail", att_public_transit="Skeptical",
    ),
    "health-practical": _p(
        "practical",
        "Fitting a realistic fitness plan into a manager's calendar: tell me the "
        "three sessions a week that work and where.",
        socioeconomic_band="Upper-middle", seniority="Manager",
        health_mobility="Mild limitation", cog_patience="None",
        cog_attention_span="Short", dospert_financial_risk_tolerance="Average",
        pref_plan_vs_spontaneous="Highly planned", lstyle_planning_horizon="Weekly",
        economic_motivation="Value-driven", habit_budget_tracking="Rarely",
        region="East Asia", urbanicity="Dense urban", demo_driver_status="Non-driver",
        skill_driving="None", att_public_transit="Positive",
        fam_urban_planning="Familiar", lstyle_travel_freq="A few trips/yr",
    ),
    # --- food: recipes, meal prep, catering, restaurant booking, delivery
    "food-expert": _p(
        "expert",
        "Line-cook-turned-caterer: thinks in yields, substitutions and allergen "
        "handling, and wants grams, not cups.",
        age_bracket="25-34", region="Western Europe", seniority="Lead / Principal",
        socioeconomic_band="Middle", topic_travel="Passionate",
        lifex_travel_breadth="Lived abroad", skill_budgeting="Master",
        lstyle_planning_horizon="Day-to-day", cog_patience="Very high",
        cog_big_picture_vs_detail="Detail-obsessed",
        economic_motivation="Premium-seeking", habit_budget_tracking="Daily",
        urbanicity="Small town", fam_urban_planning="None",
        cog_risk_framing="Opportunity-focused", demo_driver_status="Occasional driver",
        skill_driving="Intermediate", att_public_transit="Positive",
        lstyle_frugality="Spender", cog_attention_span="Long",
        risk_tolerance="Risk-tolerant",
    ),
    "food-senior": _p(
        "senior",
        "Cooks for two on a fixed income with a low-sodium restriction: wants "
        "simple swaps, not a new cuisine.",
        urbanicity="Rural", socioeconomic_band="Low income",
        demo_driver_status="Occasional driver", skill_driving="Intermediate",
        att_public_transit="Skeptical", topic_travel="Indifferent",
        skill_budgeting="Master", cog_detail_orientation="Very high",
        cog_patience="High", lstyle_planning_horizon="Weekly",
        habit_budget_tracking="Daily", region="Southeast Asia",
        lifex_geographic_mobility="Moved nationally",
        lifex_travel_breadth="Never left country", lstyle_travel_freq="Homebody",
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
        pref_plan_vs_spontaneous="Highly spontaneous", topic_travel="Neutral",
        habit_budget_tracking="Never", urbanicity="Suburban",
        lifex_geographic_mobility="Never left hometown",
        demo_driver_status="Licensed, rarely drives", skill_driving="Beginner",
        att_public_transit="Neutral", fam_urban_planning="None", health_vision="Normal",
        lstyle_travel_freq="Homebody",
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
        lifex_geographic_mobility="Moved nationally", fam_urban_planning="None",
        health_vision="Normal", cog_risk_framing="Threat-focused",
        lstyle_travel_freq="Rare",
    ),
    # --- productivity: GoMail / GoCalendar inbox triage and scheduling
    "productivity-expert": _p(
        "expert",
        "Chief of staff who lives in someone else's inbox and calendar: rules, "
        "labels, conflicts and time zones, all explicit.",
        seniority="Director", topic_technology="Passionate",
        att_new_technology="Enthusiast", topic_travel="Neutral",
        lstyle_travel_freq="Occasional", risk_tolerance="Cautious",
        dospert_financial_risk_tolerance="Low", cog_patience="Very high",
        cog_big_picture_vs_detail="Detail-obsessed", skill_budgeting="Advanced",
        habit_budget_tracking="Weekly", region="Eastern Europe", urbanicity="Suburban",
        fam_urban_planning="None", lifex_geographic_mobility="Moved internationally",
        health_vision="Normal", att_public_transit="Neutral",
    ),
    "productivity-senior": _p(
        "senior",
        "Semi-retired consultant with four thousand unread messages: comfortable "
        "money, no interest in learning the interface.",
        socioeconomic_band="Upper-middle", lifex_travel_breadth="Well-traveled",
        lstyle_travel_freq="Occasional", lstyle_frugality="Balanced",
        pref_save_vs_spend="Balanced", economic_motivation="Indifferent",
        dospert_financial_risk_tolerance="Low", cog_detail_orientation="Low",
        cog_patience="Low", habit_budget_tracking="Rarely", region="Western Europe",
        fam_urban_planning="Aware", cog_big_picture_vs_detail="Big-picture only",
        cog_attention_span="Average", lifex_geographic_mobility="Moved internationally",
        skill_budgeting="Advanced",
    ),
    "productivity-young": _p(
        "young",
        "First office job, runs the whole inbox from a phone between other tabs and "
        "misses half the calendar invites.",
        socioeconomic_band="Lower-middle", urbanicity="Suburban",
        lifex_travel_breadth="Never left country", topic_travel="Neutral",
        lstyle_travel_freq="Rare", fam_urban_planning="None", health_vision="Normal",
        cog_attention_span="Very short", pref_plan_vs_spontaneous="Highly spontaneous",
        habit_budget_tracking="Never", region="Eastern Europe",
        demo_driver_status="Occasional driver", skill_driving="Intermediate",
        lstyle_frugality="Balanced", pref_save_vs_spend="Spender-leaning",
        att_public_transit="Neutral",
    ),
    "productivity-practical": _p(
        "practical",
        "Triages the inbox in the ten minutes between meetings: what needs an "
        "answer today, and nothing else.",
        socioeconomic_band="Upper-middle", urbanicity="Dense urban",
        lstyle_travel_freq="A few trips/yr", skill_budgeting="Advanced",
        cog_patience="None", cog_attention_span="Short",
        cog_big_picture_vs_detail="Big-picture",
        pref_detail_brief_vs_full="Just the gist", lstyle_planning_horizon="Day-to-day",
        economic_motivation="Indifferent", habit_budget_tracking="Rarely",
        fam_urban_planning="Familiar", health_vision="Normal",
        att_public_transit="Positive", demo_driver_status="Occasional driver",
        skill_driving="Intermediate", cog_risk_framing="Opportunity-focused",
    ),
    # --- professional: job search, hiring, networking, freelance marketplaces
    "professional-expert": _p(
        "expert",
        "Talent lead who screens dozens of profiles a week: wants titles, dates, "
        "comp bands and the sourcing rationale.",
        seniority="Director", lifex_geographic_mobility="Serial relocator",
        topic_travel="Neutral", risk_tolerance="Risk-tolerant",
        dospert_financial_risk_tolerance="High", lstyle_planning_horizon="Yearly",
        skill_budgeting="Master", cog_patience="High",
        cog_risk_framing="Opportunity-focused", health_vision="Normal",
        habit_budget_tracking="Monthly", demo_driver_status="Non-driver",
        skill_driving="None", region="South Asia", fam_urban_planning="Aware",
        urbanicity="Dense urban", att_public_transit="Enthusiast",
        cog_attention_span="Long",
    ),
    "professional-senior": _p(
        "senior",
        "Retired at sixty-eight, now wants part-time work: strong track record, no "
        "idea how modern job sites behave.",
        urbanicity="Small town", lifex_geographic_mobility="Never left hometown",
        topic_technology="Averse", att_new_technology="Opposed",
        lifex_travel_breadth="A few countries", lstyle_travel_freq="Rare",
        cog_detail_orientation="High", cog_attention_span="Average",
        skill_budgeting="Advanced", habit_budget_tracking="Daily",
        region="North America", fam_urban_planning="None",
        cog_big_picture_vs_detail="Both", lstyle_planning_horizon="Monthly",
    ),
    "professional-young": _p(
        "young",
        "New graduate firing off applications from a phone on the bus: volume over "
        "tailoring, checks nothing twice.",
        age_bracket="18-24", seniority="Student / intern", urbanicity="Suburban",
        lifex_geographic_mobility="Never left hometown",
        lifex_travel_breadth="Never left country", topic_travel="Neutral",
        att_public_transit="Enthusiast", risk_tolerance="Risk-seeking",
        dospert_financial_risk_tolerance="Very high", cog_patience="None",
        cog_attention_span="Very short", habit_budget_tracking="Never",
        health_vision="Normal", fam_urban_planning="None",
        skill_budgeting="Intermediate", lstyle_planning_horizon="Weekly",
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
        fam_urban_planning="None", lifex_travel_breadth="Never left country",
        health_vision="Normal", lstyle_travel_freq="Homebody",
        lifex_geographic_mobility="Moved nationally",
        dospert_financial_risk_tolerance="Very low", risk_tolerance="Risk-averse",
    ),
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

    # Two personas with identical values are one persona wearing two names, and any
    # difference the benchmark reports between them is noise.
    seen: dict[str, str] = {}
    for name, profile in PROFILES.items():
        key = json.dumps(profile["values"], sort_keys=True)
        assert key not in seen, f"{name} has the same values as {seen[key]}"
        seen[key] = name

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
