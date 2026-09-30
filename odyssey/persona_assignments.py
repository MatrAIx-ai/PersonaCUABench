"""Which personas ask for which task.

Every task belongs to a domain family, and every family has the same four
roles: the domain expert, the cautious senior, the budget-conscious young user
and the practical one (whose exact shape varies by family, as the team's
persona tree defines it). A task is therefore run by its family's four personas
plus the `none` control, and the mapping is derived rather than hand-written --
a hand-written map for 71 tasks goes stale the first time the task set changes.

    python odyssey/persona_assignments.py             # print the assignment
    python odyssey/persona_assignments.py --check     # verify every task is covered
    python odyssey/persona_assignments.py --write     # freeze it to JSON for others
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "persona_assignments.json"

# A task's domain, as the v1 manifest spells it, to its family. REAL's sandbox
# sites join the family whose questions they ask: booking a table is food, a
# stay or a ride is travel, an inbox is productivity, hiring is professional.
DOMAIN_FAMILY = {
    "Travel": "travel",
    "Staynb (Airbnb)": "travel",
    "Udriver (Uber)": "travel",
    "Science": "science",
    "Tech": "tech",
    "Community": "community",
    "Art": "art",
    "Lifestyle": "lifestyle",
    "Zilloft (Zillow)": "lifestyle",
    "Ecommerce": "ecommerce",
    "Health": "health",
    "Food": "food",
    "DashDish (DoorDash)": "food",
    "OpenDining (OpenTable)": "food",
    "GoMail (Gmail)": "productivity",
    "GoCalendar (Google Calendar)": "productivity",
    "NetworkIn (LinkedIn)": "professional",
    "TopWork (Upwork)": "professional",
}

# The four roles, and the persona key each family uses for them. Travel keeps
# the names its personas were first written under; every other family follows
# "<family>-<role>".
ROLES = ("expert", "senior", "young", "practical")
# Every family uses <family>-<role>; only travel keeps the names its four
# personas were first written under, because results already reference them.
OVERRIDES = {
    ("travel", "expert"): "travel-expert",
    ("travel", "senior"): "elderly-novice",
    ("travel", "young"): "budget-student",
    ("travel", "practical"): "non-native-speaker",
}


def persona_key(family: str, role: str) -> str:
    return OVERRIDES.get((family, role), f"{family}-{role}")


def family_of(task: dict) -> str:
    domain = task.get("domain")
    if domain not in DOMAIN_FAMILY:
        raise SystemExit(
            f"task {task.get('task_id', '?')[:12]} has domain {domain!r}, which no "
            f"family claims. Add it to DOMAIN_FAMILY in {Path(__file__).name} and "
            f"make sure that family's four personas exist.")
    return DOMAIN_FAMILY[domain]


def personas_for(task: dict) -> list[str]:
    family = family_of(task)
    return [persona_key(family, role) for role in ROLES]


def assignment(catalog=None) -> dict[str, list[str]]:
    """task_id -> the four persona keys that will ask for it."""
    import task_router

    catalog = catalog or task_router.TaskCatalog.load()
    out: dict[str, list[str]] = {}
    for suite in catalog.suites.values():
        for task in suite.tasks:
            out[task["task_id"]] = personas_for(task)
    return out


def missing_personas(assigned: dict[str, list[str]]) -> list[str]:
    """Persona keys with no YAML on disk."""
    wanted = {name for names in assigned.values() for name in names}
    return sorted(name for name in wanted
                  if not (HERE / "personas" / f"{name}.yaml").is_file())


def main() -> None:
    import task_router

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="fail unless every task has four personas that exist")
    ap.add_argument("--write", action="store_true",
                    help=f"freeze the mapping to {FROZEN.name}")
    args = ap.parse_args()

    catalog = task_router.TaskCatalog.load()
    assigned = assignment(catalog)
    families = Counter()
    for suite in catalog.suites.values():
        for task in suite.tasks:
            families[family_of(task)] += 1

    print(f"{len(assigned)} tasks, {len(ROLES)} personas each, "
          f"{len({n for v in assigned.values() for n in v})} distinct personas")
    print(f"{'family':<14}{'tasks':>6}  personas")
    for family, count in sorted(families.items()):
        print(f"{family:<14}{count:>6}  "
              + ", ".join(persona_key(family, role) for role in ROLES))

    absent = missing_personas(assigned)
    if absent:
        print(f"\nMISSING {len(absent)} persona file(s) under odyssey/personas/:")
        for name in absent:
            print(f"  {name}.yaml")
        print("Add them to PROFILES in odyssey/make_personas.py and regenerate.")

    if args.check:
        for task_id, names in assigned.items():
            if len(names) != len(ROLES) or len(set(names)) != len(ROLES):
                raise SystemExit(f"task {task_id[:12]} has a broken assignment: {names}")
        if absent:
            raise SystemExit(f"{len(absent)} assigned persona(s) have no file")
        print("\nassignment check: every task has four existing personas")

    if args.write:
        FROZEN.write_text(json.dumps(assigned, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        print(f"\nwrote {FROZEN.relative_to(HERE.parent)} ({len(assigned)} tasks)")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(HERE))
    main()
