"""Render persona requests into native ClawBench task directories."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path

from run import PersonaUser, load_dotenv

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ASSIGNMENTS = json.loads((HERE / "persona_assignments.json").read_text())
CASES = {
    "clawbench-v1-794": "test-cases/v1/794-beauty-personal-care-salon-booking-styleseat",
    "clawbench-v2-1102": "test-cases/v2/v2-1102-fitness-social-post-strava",
}


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--clawbench", type=Path, default=REPO.parent / "ClawBench")
    ap.add_argument("--out", type=Path, default=HERE / "claw_cases")
    ap.add_argument("--model", default=os.environ.get("QWEN_MODEL", "qwen/qwen3.8-27b"))
    ap.add_argument("--provider", default="qwen")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    for task_key, relative in CASES.items():
        source = args.clawbench / relative / "task.json"
        task = json.loads(source.read_text(encoding="utf-8"))
        goal = task["instruction"]
        for persona in ("none", *ASSIGNMENTS[task_key]):
            user = PersonaUser(
                {"confirmed_task": goal},
                None if persona == "none" else HERE / "personas" / f"{persona}.yaml",
                args.model, args.provider,
            )
            print(f"\n=== {task_key} persona={persona} ===\n{user.opening}")
            if args.preview:
                continue
            rendered = copy.deepcopy(task)
            rendered["instruction"] = user.opening
            rendered["metadata"]["persona"] = persona
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
