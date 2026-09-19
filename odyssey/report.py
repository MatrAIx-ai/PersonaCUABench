"""Persona x task score table over everything under odyssey/results/.

    python odyssey/report.py            # latest run per (task, persona, model)
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
TASKS = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
ORDER = [t["task_id"][:12] for t in TASKS]
LEVEL = {t["task_id"][:12]: t["level"] for t in TASKS}


def main() -> None:
    # (task, arm) -> (run stamp, score, step budget). Keyed on the stamp in the
    # directory name rather than on path order, which is not chronological.
    # rglob, not a fixed depth: a model id containing "/" used to write the run
    # directory one level deeper, and those results still have to be read.
    best: dict[tuple[str, str], tuple[str, dict, int | None]] = {}
    for path in sorted(RESULTS.rglob("result.json")):
        # _-prefixed folders hold runs kept for the record but not comparable
        # (a different step budget, a probe on another model).
        if any(part.startswith("_") for part in path.relative_to(RESULTS).parts):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        judged = rec.get("judgement")
        if not judged:
            continue
        arm = f"{rec['persona']}/{rec['run']['arm']['model']}"
        key = (rec["task_id"][:12], arm)
        stamp = path.parent.name.rsplit("__", 1)[-1]
        if key not in best or stamp > best[key][0]:
            best[key] = (stamp, judged, rec["run"].get("max_steps"))

    # A score compared across different step budgets is not a comparison.
    budgets = {v[2] for v in best.values() if v[2] is not None}
    if len(budgets) > 1:
        print(f"WARNING: mixed step budgets in these results: {sorted(budgets)}\n")

    if not best:
        print(f"no judged results under {RESULTS}")
        return

    table(best, "score: every rubric item", "score")
    # Only the items the persona actually voiced (or the agent asked about).
    # A gap between the two tables is the conversation's, not the agent's.
    print()
    table(best, "score: communicated items only", "score_communicated")


def table(best: dict, title: str, field: str) -> None:
    scores = {k: v[1].get(field) for k, v in best.items()}
    arms = sorted({a for _, a in scores})
    print(title)
    width = max(len(a) for a in arms) + 2
    print(f"{'task':<14}{'level':<8}" + "".join(f"{a:<{width}}" for a in arms))
    totals: dict[str, list[float]] = defaultdict(list)
    for task in ORDER:
        row = f"{task:<14}{LEVEL[task]:<8}"
        for arm in arms:
            s = scores.get((task, arm))
            row += f"{'-' if s is None else f'{s:.2f}':<{width}}"
            if s is not None:
                totals[arm].append(s)
        print(row)
    mean = f"{'MEAN':<14}{'':<8}"
    for arm in arms:
        v = totals[arm]
        mean += f"{(sum(v) / len(v) if v else 0):.2f}".ljust(width)
    print(mean)


if __name__ == "__main__":
    main()
