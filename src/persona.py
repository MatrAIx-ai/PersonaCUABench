"""Render a persona.yaml into a role-play system prompt.

A persona.yaml is self-describing -- every dimension carries its value, label and
category -- so rendering needs no schema:

    attributes:
      age_bracket:    {value: 75-84, label: Age bracket, category: "Demographic: Core"}
      tech_savviness: {value: Reluctant, label: Tech savviness, category: "Expertise: Domains"}

Attributes are grouped into sections by category, and placeholder values
("None", "N/A", ...) are dropped. Adapted from MatrAIx Agent_PersonaBench's
evaluation/src/persona.py so this folder runs on its own; the wording is kept
identical.

    python src/persona.py src/personas/elderly-novice.yaml
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_NULLISH = frozenset({
    "", "none", "n/a", "na", "null", "undefined", "none notable",
    "not applicable", "prefer not to say", "no coding activity",
    "not a developer", "no interest", "unknown",
})

# (heading, category matchers). A matcher ending in ":" matches by prefix.
_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Identity", ("Demographic: Core", "Demographic: Cultural",
                  "Demographic: Family", "Demographic: Life Events")),
    ("Career & education", ("Professional: Career", "Professional: Industry",
                            "Learning: Academic", "Learning: Style", "Developer:")),
    ("Language & communication", ("Linguistic: Language", "Linguistic: Communication")),
    ("Personality & values", ("Personality: Big Five", "Personality: Character",
                              "Personality: MBTI", "Personality: Relationships",
                              "Values & Motivation", "Risk & Decision")),
    ("Current interaction state", ("State: Emotional", "Behavior: Time", "Behavior: Work")),
    ("Worldview", ("Worldview: Beliefs",)),
    ("Interests", ("Interests: Topics", "Interests: Hobbies", "Interests: Media",
                   "Interests: Culture", "Interests: Sports", "Interests: Food")),
    ("Skills & expertise", ("Expertise: Domains", "Expertise: Skills",
                            "Skills: Tools", "Skills: Programming")),
    ("Lifestyle & health", ("Health: Physical", "Health: Fitness", "Health: Lifestyle",
                            "Behavior: Preferences", "Behavior: Habits")),
)


def load_persona(source: str | os.PathLike) -> dict:
    """Load a persona.yaml (a file, or a directory containing one)."""
    p = Path(source)
    path = p / "persona.yaml" if p.is_dir() else p
    if not path.is_file():
        raise FileNotFoundError(f"no persona.yaml at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _keepable(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(v).strip() for v in value if str(v).strip())
    else:
        text = str(value).strip()
    return None if not text or text.lower() in _NULLISH else text


def _section_for(category: str) -> str:
    for heading, matchers in _SECTIONS:
        for m in matchers:
            if m.endswith(":"):
                if category.startswith(m):
                    return heading
            elif category == m or category.startswith(f"{m}:"):
                return heading
    return "Other attributes"


def build_dimension_narrative(persona: dict) -> list[str]:
    """The persona's attributes as markdown section blocks, in section order."""
    grouped: dict[str, list[tuple[str, str]]] = {}
    for dim_id, spec in (persona.get("attributes") or {}).items():
        if isinstance(spec, dict):
            raw, label = spec.get("value"), str(spec.get("label") or dim_id.replace("_", " "))
            category = str(spec.get("category") or "")
        else:
            raw, label, category = spec, dim_id.replace("_", " "), ""
        value = _keepable(raw)
        if value is not None:
            grouped.setdefault(_section_for(category), []).append((label.strip(), value))

    order = [h for h, _ in _SECTIONS] + ["Other attributes"]
    return ["\n".join([f"### {h}"] + [f"- {label}: {value}" for label, value in grouped[h]])
            for h in order if grouped.get(h)]


def persona_system_prompt(source: str | os.PathLike, role: str = "a person") -> str:
    """The full persona as a role-play system prompt."""
    profile = "\n\n".join(build_dimension_narrative(load_persona(source)))
    return (
        f"You are role-playing {role} with the following profile. Stay fully in "
        f"character: let these traits shape your choices and language naturally, "
        f"the way a real person with this profile would behave. Do not announce "
        f"that you are role-playing.\n\n"
        f"# Your profile\n\n{profile}"
    )


if __name__ == "__main__":
    import sys

    print(persona_system_prompt(sys.argv[1] if len(sys.argv) > 1 else "."))
