"""Render persona requests into native ClawBench task directories.

ClawBench runs its own harness, which this repo does not have: the four v1
ClawBench tasks cannot be executed or scored here. What this script does is the
part that is ours -- turn each task into one request per assigned persona -- and
write them where that harness expects them, so whoever has it can run them.

    python odyssey/prepare_claw_cases.py --clawbench /path/to/ClawBench --preview
    python odyssey/prepare_claw_cases.py --clawbench /path/to/ClawBench
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

from run import PersonaUser, load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = REPO / "benchmark" / "v1_tasks.json"
# ClawBench's domains are its own; these say which family's four personas ask
# for them. Beauty and Daily Life are closest to lifestyle, Fitness to health,
# Job Search to professional.
CLAW_FAMILIES = {"794": "lifestyle", "1102": "health", "47": "lifestyle",
                 "86": "professional"}


def claw_tasks() -> list[dict]:
    """The ClawBench entries of the v1 manifest -- all of them, not a hardcoded two."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return [t for t in manifest["tasks"] if t.get("source") == "ClawBench"]


def find_case(root: Path, source_id: str) -> Path:
    """The case directory for a ClawBench id, found rather than guessed.

    The layout differs between v1 and v2 and the directory names carry a slug,
    so this looks for the task.json whose id matches instead of hardcoding a
    path that silently points at the wrong case when the harness moves on.
    """
    candidates = []
    for path in sorted(root.rglob("task.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ident = str(data.get("id") or data.get("task_id") or "")
        if ident == source_id or path.parent.name.split("-")[0] == source_id \
                or f"-{source_id}-" in path.parent.name:
            candidates.append(path)
    if not candidates:
        raise SystemExit(
            f"no ClawBench case for id {source_id!r} under {root}. Point "
            f"--clawbench at a checkout that has it.")
    if len(candidates) > 1:
        raise SystemExit(f"id {source_id!r} matches several cases: "
                         + ", ".join(str(c.parent) for c in candidates))
    return candidates[0]


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--clawbench", type=Path, default=REPO.parent / "ClawBench")
    ap.add_argument("--out", type=Path, default=HERE / "claw_cases")
    ap.add_argument("--model", default=os.environ.get("QWEN_MODEL", "qwen/qwen3.8-27b"))
    ap.add_argument("--provider", default="qwen")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    import persona_assignments

    entries = claw_tasks()
    print(f"{len(entries)} ClawBench task(s) in the manifest; "
          f"this repo cannot run or score them -- rendering requests only.")
    for entry in entries:
        source = find_case(args.clawbench, str(entry["source_id"]))
        task = json.loads(source.read_text(encoding="utf-8"))
        goal = task.get("instruction") or entry["instruction"]
        task_key = f"clawbench-{entry['source_id']}"
        # ClawBench's own domains (Beauty, Fitness, Daily Life, Job Search) are
        # not v1 domains, so the family is named here rather than derived.
        family = CLAW_FAMILIES.get(str(entry["source_id"]), "lifestyle")
        assigned = [persona_assignments.persona_key(family, role)
                    for role in persona_assignments.ROLES]
        for persona in ("none", *assigned):
            user = PersonaUser(
                {"confirmed_task": goal},
                None if persona == "none" else HERE / "personas" / f"{persona}.yaml",
                args.model, args.provider,
            )
            print(f"\n=== {task_key} [{entry['domain']}] persona={persona} "
                  f"===\n{user.opening}")
            if args.preview:
                continue
            rendered = copy.deepcopy(task)
            rendered["instruction"] = user.opening
            rendered.setdefault("metadata", {})["persona"] = persona
            rendered["judge_context"] = {
                "rubric": f"Hidden original requirement: {goal}"
            }
            out = args.out / f"{task_key}--{persona}"
            out.mkdir(parents=True, exist_ok=True)
            (out / "task.json").write_text(
                json.dumps(rendered, ensure_ascii=False, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
