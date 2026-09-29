"""Generate the task-specific MatrAIx personas used by this assignment."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent / "dimensions.json"
OUT = Path(__file__).resolve().parent / "personas"

# Every arm carries the same dimensions. Profiles below only override the
# neutral baseline, keeping the experiment compact and comparable.
BASE_VALUES = {
    "age_bracket": "35-44",
    "highest_education": "Bachelor's",
    "life_stage": "Mid-life",
    "socioeconomic_band": "Middle",
    "tech_savviness": "Comfortable",
    "skill_budgeting": "Intermediate",
    "risk_tolerance": "Balanced",
    "decision_style": "Analytical",
    "trust_level": "Verifying",
    "cog_detail_orientation": "Moderate",
    "cog_patience": "Moderate",
    "cog_attention_span": "Average",
    "cog_precision_of_language": "Average",
    "pref_detail_brief_vs_full": "Balanced",
    "pref_plan_vs_spontaneous": "Balanced",
    "device_context": "Desktop, focused",
    "economic_motivation": "Value-driven",
    "lstyle_shopping_style": "Researcher",
    "val_community": "Moderate",
    "val_family": "Moderate",
    "val_privacy": "Moderate",
    "topic_social_media": "Neutral",
    "att_social_media": "Neutral",
    "fam_hospitality_management": "Aware",
    "ind_hospitality": "None",
    "topic_volunteering": "Neutral",
    "lifex_service_history": "None",
    "ind_nonprofit": "None",
    "topic_gaming": "Neutral",
    "topic_collecting": "Neutral",
    "lstyle_gaming_freq": "Rarely",
    "topic_parenting": "Neutral",
    "demo_parental_status": "Not a parent",
    "demo_children_count": "None",
    "lstyle_diet_type": "Omnivore",
    "lstyle_fashion_sense": "Practical",
    "ind_beauty_cosmetics": "None",
    "val_beauty_aesthetics": "Moderate",
    "trait_appreciation_of_beauty": "Moderate",
    "topic_fitness": "Neutral",
    "topic_cycling": "Neutral",
    "sport_cycling": "None",
    "lstyle_exercise_freq": "Monthly",
}
DIMENSIONS = tuple(BASE_VALUES)


def _p(note: str, **values: str) -> dict:
    return {"note": note, "values": values}


PROFILES = {
    # Baltimore event night
    "event-pro": _p(
        "Experienced event planner who verifies official pages and records details.",
        age_bracket="35-44", highest_education="Master's", socioeconomic_band="Upper-middle",
        tech_savviness="Digital native", cog_detail_orientation="Very high",
        cog_precision_of_language="Very precise", pref_detail_brief_vs_full="Every detail",
        pref_plan_vs_spontaneous="Highly planned", fam_hospitality_management="Expert",
        ind_hospitality="Experienced"),
    "young-casual-planner": _p(
        "Young casual planner who wants a convenient night out with little process detail.",
        age_bracket="18-24", highest_education="Some college", life_stage="Student",
        socioeconomic_band="Lower-middle", tech_savviness="Digital native",
        decision_style="Intuitive", cog_detail_orientation="Low", cog_patience="Low",
        cog_attention_span="Short", cog_precision_of_language="Loose",
        pref_detail_brief_vs_full="Brief-leaning", pref_plan_vs_spontaneous="Spontaneous",
        device_context="Mobile, on-the-go", lstyle_shopping_style="Impulse buyer"),
    "older-city-visitor": _p(
        "Older visitor who is cautious with websites and wants a short, usable plan.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Cautious", trust_level="Skeptical",
        cog_detail_orientation="Low", cog_attention_span="Short",
        cog_precision_of_language="Vague", pref_detail_brief_vs_full="Just the gist",
        device_context="Accessibility tool"),

    # Chapel Hill/Carrboro pantry loop
    "community-organizer": _p(
        "Long-term community organizer who checks that local resources are real and current.",
        age_bracket="45-54", highest_education="Bachelor's", tech_savviness="Comfortable",
        cog_detail_orientation="High", cog_precision_of_language="Precise",
        pref_detail_brief_vs_full="Detail-leaning", pref_plan_vs_spontaneous="Highly planned",
        val_community="Core value", topic_volunteering="Passionate",
        lifex_service_history="Activist / organizer", ind_nonprofit="Experienced"),
    "keto-budget-shopper": _p(
        "Phone-first bargain shopper focused on low-carb food and quick errands.",
        age_bracket="25-34", highest_education="Vocational / cert", life_stage="Early career",
        socioeconomic_band="Lower-middle", tech_savviness="Digital native",
        skill_budgeting="Advanced", risk_tolerance="Risk-tolerant", decision_style="Intuitive",
        cog_detail_orientation="Low", cog_patience="Low", cog_attention_span="Short",
        pref_detail_brief_vs_full="Brief-leaning", pref_plan_vs_spontaneous="Spontaneous",
        device_context="Mobile, on-the-go", economic_motivation="Cost-sensitive",
        lstyle_shopping_style="Bargain hunter", lstyle_diet_type="Keto/low-carb"),
    "older-local-errand-runner": _p(
        "Older local resident who values community but wants only a simple errand route.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        socioeconomic_band="Lower-middle", tech_savviness="Reluctant",
        risk_tolerance="Cautious", cog_detail_orientation="Low", cog_attention_span="Short",
        cog_precision_of_language="Loose", pref_detail_brief_vs_full="Just the gist",
        device_context="Accessibility tool", economic_motivation="Cost-sensitive",
        val_community="Important", lifex_service_history="Occasional volunteer"),

    # Pokemon gift
    "pokemon-collector": _p(
        "Teen collector who knows Pokemon product names and cares about exact editions.",
        age_bracket="13-17", highest_education="Secondary", life_stage="Student",
        socioeconomic_band="Lower-middle", tech_savviness="Digital native",
        skill_budgeting="Beginner", risk_tolerance="Risk-tolerant",
        cog_detail_orientation="High", cog_patience="Low", cog_precision_of_language="Precise",
        pref_detail_brief_vs_full="Brief-leaning", device_context="Mobile, on-the-go",
        topic_gaming="Passionate", topic_collecting="Passionate", lstyle_gaming_freq="Daily"),
    "practical-parent": _p(
        "Practical parent balancing a child's interests, stock reliability, and price.",
        age_bracket="35-44", highest_education="Bachelor's", life_stage="Parent of young kids",
        tech_savviness="Comfortable", skill_budgeting="Advanced", risk_tolerance="Cautious",
        pref_plan_vs_spontaneous="Planned", economic_motivation="Cost-sensitive",
        val_family="Core value", topic_parenting="Interested",
        demo_parental_status="Parent of minors", demo_children_count="2 children",
        topic_gaming="Neutral", topic_collecting="Interested"),
    "gift-grandparent": _p(
        "Grandparent unfamiliar with Pokemon who wants a safe, easy gift choice.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Risk-averse", trust_level="Skeptical",
        cog_detail_orientation="Low", cog_attention_span="Short",
        cog_precision_of_language="Vague", pref_detail_brief_vs_full="Just the gist",
        device_context="Accessibility tool", val_family="Core value",
        demo_parental_status="Grandparent", demo_children_count="Adult children",
        topic_gaming="Indifferent", lstyle_gaming_freq="Never"),

    # Coordinated holiday bundle
    "gift-stylist": _p(
        "Design-trained gift stylist who cares about a coherent visual theme and exact options.",
        age_bracket="25-34", highest_education="Master's", life_stage="Early career",
        socioeconomic_band="Upper-middle", tech_savviness="Digital native",
        cog_detail_orientation="Very high", cog_patience="High",
        cog_precision_of_language="Very precise", pref_detail_brief_vs_full="Every detail",
        pref_plan_vs_spontaneous="Highly planned", lstyle_fashion_sense="Trend-setter",
        val_beauty_aesthetics="Core value", trait_appreciation_of_beauty="Signature"),
    "busy-budget-parent": _p(
        "Busy parent who prioritizes price, pickup today, and age-appropriate gifts.",
        age_bracket="35-44", highest_education="Bachelor's", life_stage="Parent of young kids",
        skill_budgeting="Advanced", cog_patience="Low", cog_attention_span="Short",
        pref_detail_brief_vs_full="Brief-leaning", pref_plan_vs_spontaneous="Planned",
        device_context="Mobile, on-the-go", economic_motivation="Cost-sensitive",
        lstyle_shopping_style="Bargain hunter", val_family="Core value",
        topic_parenting="Passionate", demo_parental_status="Parent of minors",
        demo_children_count="2 children"),
    "traditional-grandparent": _p(
        "Traditional grandparent who values family suitability over online shopping details.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Cautious", trust_level="Skeptical",
        cog_detail_orientation="Low", cog_attention_span="Short",
        pref_detail_brief_vs_full="Just the gist", device_context="Accessibility tool",
        lstyle_shopping_style="Brand loyal", val_family="Core value",
        demo_parental_status="Grandparent", demo_children_count="Adult children"),

    # Colorado outreach
    "nonprofit-program-manager": _p(
        "Nonprofit program manager who expects verified organizations, exact offers, and sourced ranges.",
        age_bracket="35-44", highest_education="Master's", tech_savviness="Digital native",
        decision_style="Analytical", cog_detail_orientation="Very high", cog_patience="High",
        cog_attention_span="Very long", cog_precision_of_language="Very precise",
        pref_detail_brief_vs_full="Every detail", val_community="Core value",
        topic_volunteering="Passionate", lifex_service_history="Long-term volunteer",
        ind_nonprofit="Veteran"),
    "student-volunteer": _p(
        "Enthusiastic student volunteer with little nonprofit or socioeconomic research experience.",
        age_bracket="18-24", highest_education="Some college", life_stage="Student",
        socioeconomic_band="Lower-middle", tech_savviness="Digital native",
        skill_budgeting="Beginner", decision_style="Intuitive", cog_detail_orientation="Low",
        cog_patience="Low", cog_attention_span="Short", pref_detail_brief_vs_full="Brief-leaning",
        device_context="Mobile, on-the-go", val_community="Core value",
        topic_volunteering="Passionate", lifex_service_history="Occasional volunteer"),
    "cautious-local-donor": _p(
        "Cautious local donor who wants plain language and proof before trusting organizations.",
        age_bracket="55-64", highest_education="Secondary", life_stage="Empty nester",
        tech_savviness="Cautious adopter", risk_tolerance="Risk-averse",
        decision_style="Deliberative", trust_level="Skeptical", cog_detail_orientation="Moderate",
        cog_precision_of_language="Average", pref_detail_brief_vs_full="Just the gist",
        val_community="Important", topic_volunteering="Interested",
        lifex_service_history="Occasional volunteer"),

    # Toddler Christmas and Grinch nails
    "craft-beauty-creator": _p(
        "Craft and beauty creator parenting a toddler, comfortable reproducing visual tutorials.",
        age_bracket="25-34", highest_education="Bachelor's", life_stage="Parent of young kids",
        tech_savviness="Digital native", cog_detail_orientation="Very high",
        cog_precision_of_language="Precise", pref_detail_brief_vs_full="Every detail",
        lstyle_shopping_style="Researcher", val_family="Core value", topic_parenting="Passionate",
        demo_parental_status="Parent of minors", demo_children_count="1 child",
        ind_beauty_cosmetics="Experienced", val_beauty_aesthetics="Core value",
        trait_appreciation_of_beauty="Signature"),
    "busy-first-time-parent": _p(
        "First-time parent who prioritizes toddler safety, low mess, and fast setup.",
        age_bracket="25-34", highest_education="Vocational / cert", life_stage="Parent of young kids",
        tech_savviness="Comfortable", risk_tolerance="Cautious", cog_detail_orientation="Moderate",
        cog_patience="Low", cog_attention_span="Short", pref_detail_brief_vs_full="Brief-leaning",
        device_context="Mobile, on-the-go", economic_motivation="Cost-sensitive",
        val_family="Core value", topic_parenting="Passionate",
        demo_parental_status="New parent", demo_children_count="1 child"),
    "caregiver-grandparent": _p(
        "Grandparent caregiver who wants simple toddler activities and has little online beauty-shopping experience.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Risk-averse", cog_detail_orientation="Low",
        cog_attention_span="Short", cog_precision_of_language="Loose",
        pref_detail_brief_vs_full="Just the gist", device_context="Accessibility tool",
        val_family="Core value", topic_parenting="Interested",
        demo_parental_status="Grandparent", demo_children_count="Adult children",
        ind_beauty_cosmetics="None", val_beauty_aesthetics="Minor"),

    # StyleSeat haircut
    "beauty-power-user": _p(
        "Beauty-platform power user who understands ratings and is comfortable booking online.",
        age_bracket="25-34", highest_education="Bachelor's", life_stage="Early career",
        tech_savviness="Digital native", risk_tolerance="Balanced", trust_level="Verifying",
        cog_detail_orientation="High", cog_precision_of_language="Precise",
        pref_plan_vs_spontaneous="Planned", device_context="Mobile, on-the-go",
        lstyle_shopping_style="Researcher", ind_beauty_cosmetics="Experienced",
        val_beauty_aesthetics="Core value", trait_appreciation_of_beauty="Strong"),
    "budget-student-client": _p(
        "Budget student who wants the soonest acceptable haircut with minimal browsing.",
        age_bracket="18-24", highest_education="Some college", life_stage="Student",
        socioeconomic_band="Low income", tech_savviness="Digital native",
        skill_budgeting="Beginner", decision_style="Intuitive", cog_detail_orientation="Low",
        cog_patience="Low", cog_attention_span="Very short", pref_detail_brief_vs_full="Just the gist",
        pref_plan_vs_spontaneous="Spontaneous", device_context="Mobile, on-the-go",
        economic_motivation="Cost-sensitive", lstyle_shopping_style="Bargain hunter"),
    "low-tech-senior-client": _p(
        "Low-tech senior who distrusts online booking and wants a clearly reputable stylist.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Risk-averse", decision_style="Deliberative",
        trust_level="Skeptical", cog_detail_orientation="Moderate", cog_patience="High",
        cog_precision_of_language="Loose", pref_detail_brief_vs_full="Brief-leaning",
        device_context="Accessibility tool", ind_beauty_cosmetics="None"),

    # Strava post
    "strava-cyclist": _p(
        "Avid cyclist and active social-media user who posts rides without hesitation.",
        age_bracket="25-34", highest_education="Bachelor's", life_stage="Early career",
        tech_savviness="Digital native", risk_tolerance="Risk-tolerant", trust_level="Trusting",
        cog_patience="Low", pref_detail_brief_vs_full="Just the gist",
        device_context="Mobile, on-the-go", val_privacy="Minor",
        topic_social_media="Passionate", att_social_media="Enthusiast",
        topic_fitness="Passionate", topic_cycling="Passionate", sport_cycling="Play",
        lstyle_exercise_freq="Daily"),
    "privacy-conscious-rider": _p(
        "Regular cyclist who uses technology but verifies privacy and audience before posting.",
        age_bracket="45-54", highest_education="Master's", socioeconomic_band="Upper-middle",
        tech_savviness="Comfortable", risk_tolerance="Cautious", decision_style="Deliberative",
        trust_level="Skeptical", cog_detail_orientation="High", cog_precision_of_language="Precise",
        val_privacy="Core value", topic_social_media="Neutral", att_social_media="Skeptical",
        topic_fitness="Interested", topic_cycling="Passionate", sport_cycling="Play",
        lstyle_exercise_freq="Weekly"),
    "older-fitness-beginner": _p(
        "Older fitness beginner who is reluctant with apps and dislikes public social posting.",
        age_bracket="65-74", highest_education="Secondary", life_stage="Retirement",
        tech_savviness="Reluctant", risk_tolerance="Risk-averse", trust_level="Skeptical",
        cog_detail_orientation="Low", cog_attention_span="Short",
        cog_precision_of_language="Vague", pref_detail_brief_vs_full="Just the gist",
        device_context="Accessibility tool", val_privacy="Core value",
        topic_social_media="Averse", att_social_media="Opposed", topic_fitness="Interested",
        topic_cycling="Neutral", sport_cycling="Casual", lstyle_exercise_freq="Monthly"),
}


def main() -> None:
    schema = {d["id"]: d for d in json.loads(SCHEMA.read_text(encoding="utf-8"))["dimensions"]}
    missing = [d for d in DIMENSIONS if d not in schema]
    assert not missing, f"not in dimensions.json: {missing}"

    OUT.mkdir(parents=True, exist_ok=True)
    for name, profile in PROFILES.items():
        values = BASE_VALUES | profile["values"]
        assert set(values) == set(DIMENSIONS), f"{name} has unknown dimensions"
        attributes = {}
        for dim_id in DIMENSIONS:
            spec, value = schema[dim_id], values[dim_id]
            assert value in spec["values"], (
                f"{name}.{dim_id}: {value!r} not allowed; options: {spec['values']}"
            )
            attributes[dim_id] = {
                "value": value,
                "label": spec["label"],
                "category": spec["category"],
            }
        doc = {
            "persona_id": f"assignment-{name}",
            "version": "3.0",
            "source": "hand-specified from MatrAIx dimensions.json",
            "note": profile["note"],
            "attributes": attributes,
        }
        path = OUT / f"{name}.yaml"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        print(f"wrote {path} ({len(attributes)} dimensions)")


if __name__ == "__main__":
    main()
