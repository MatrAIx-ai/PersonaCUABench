"""Persona x task score table over everything under odyssey/results/, plus the
task-completion x satisfaction quadrants. Printed, and written to <repo>/results/.

    python odyssey/report.py      # latest run per (task, persona), one folder per
                                  # <backbone>_<condition>, e.g. results/Qwen3.8-27B_C1/
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
_REAL = HERE / "tasks_real.json"
if _REAL.is_file():
    TASKS += json.loads(_REAL.read_text(encoding="utf-8"))
# The first task set (the one on GitHub); its results are still reported.
_V1 = HERE / "tasks_v1.json"
if _V1.is_file():
    _known = {t["task_id"] for t in TASKS}
    TASKS += [t for t in json.loads(_V1.read_text(encoding="utf-8")) if t["task_id"] not in _known]
ORDER = [t["task_id"][:12] for t in TASKS]
LEVEL = {t["task_id"][:12]: t["level"] for t in TASKS}


# A run counts as "task done" when it met this share of the rubric items the
# persona communicated, and as "satisfied" when the experience judge's P5_overall
# reaches this score (1-5).
DONE_AT = 0.8
SATISFIED_AT = 4
QUADRANTS = ("done+satisfied", "done+unsatisfied", "undone+satisfied", "undone+unsatisfied")


def backbone(model: str) -> str:
    """"qwen/qwen3.8-27b" and "Qwen/Qwen3.8-27B" are one model served two ways."""
    return model.rsplit("/", 1)[-1]


def condition(rec: dict) -> str:
    # Results written before run.py recorded a condition were C1 (prompt-only),
    # or C0 when there was no persona.
    return "C0" if rec["persona"] == "none" else rec.get("condition", "c1").upper()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", default=str(HERE / "results"))
    ap.add_argument("--out", default=str(HERE.parent / "results"),
                    help="one <backbone>_<condition>/ folder per group, each with "
                         "report.txt and quadrants.csv")
    args = ap.parse_args()
    results = Path(args.results)

    # (backbone, condition) -> {(task, persona) -> (run stamp, judgement, step budget, record)}.
    # Keyed on the stamp in the directory name rather than on path order, which
    # is not chronological. rglob, not a fixed depth: the layout has changed more
    # than once and older results still have to be read.
    groups: dict[tuple[str, str], dict] = defaultdict(dict)
    names: dict[str, str] = {}
    for path in sorted(results.rglob("result.json")):
        # _-prefixed folders hold runs kept for the record but not comparable
        # (a different step budget, a probe on another model).
        if any(part.startswith("_") for part in path.relative_to(results).parts):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec["task_id"][:12] not in LEVEL or not rec.get("judgement"):
            continue
        bb = backbone(rec["run"]["arm"]["model"])
        # One folder per model whatever the id's case; the capitalised spelling wins.
        names[bb.lower()] = min(names.get(bb.lower(), bb), bb)
        best = groups[(bb.lower(), condition(rec))]
        key = (rec["task_id"][:12], rec["persona"])
        stamp = path.parent.name.rsplit("__", 1)[-1]
        if key not in best or stamp > best[key][0]:
            best[key] = (stamp, rec["judgement"], rec["run"].get("max_steps"), rec)

    if not groups:
        print(f"no judged results under {results}")
        return
    for (bb, cond), best in sorted(groups.items()):
        out = Path(args.out) / f"{names[bb]}_{cond}"
        out.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print(f"=== {names[bb]}_{cond}  ({len(best)} runs) ===\n")
            rows = report(best)
        print(buf.getvalue())
        (out / "report.txt").write_text(buf.getvalue(), encoding="utf-8")
        with open(out / "quadrants.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"-> {out}/report.txt, quadrants.csv\n")


def report(best: dict) -> list[dict]:
    # A score compared across different step budgets is not a comparison.
    budgets = {v[2] for v in best.values() if v[2] is not None}
    if len(budgets) > 1:
        print(f"WARNING: mixed step budgets in these results: {sorted(budgets)}\n")

    table(best, "score: every rubric item", "score")
    # Only the items the persona actually voiced (or the agent asked about).
    # A gap between the two tables is the conversation's, not the agent's.
    print()
    table(best, "score: communicated items only", "score_communicated")
    print()
    return quadrants(best)


def quadrant(done: float | None, p5) -> str | None:
    if done is None or not isinstance(p5, (int, float)) or isinstance(p5, bool):
        return None
    return (("done" if done >= DONE_AT else "undone") + "+" +
            ("satisfied" if p5 >= SATISFIED_AT else "unsatisfied"))


def quadrants(best: dict) -> list[dict]:
    """Task completion x satisfaction, one row per run, counted per persona.

    The off-diagonal cells are the point: done+unsatisfied is a correct answer
    this person could not use; undone+satisfied is an answer that looked fine to
    them while missing what they needed.
    """
    rows = []
    for (task, arm), (_, judged, _, rec) in sorted(best.items()):
        exp = rec.get("experience") or {}
        a = exp.get("a") or {}
        p5 = (a.get("P5_overall") or {}).get("score")
        rows.append({
            "task": task, "level": LEVEL[task], "condition": rec.get("condition", "c1"),
            "persona": rec["persona"], "arm": arm,
            "score": judged.get("score"), "score_communicated": judged.get("score_communicated"),
            "P1": (a.get("P1_asked_for") or {}).get("score"),
            "P2": (a.get("P2_readable_for_them") or {}).get("score"),
            "P3": (a.get("P3_actionable") or {}).get("score"),
            "P4": (a.get("P4_gap_handling") or {}).get("score"),
            "P5": p5,
            "quadrant": quadrant(judged.get("score_communicated")
                                 if judged.get("score_communicated") is not None
                                 else judged.get("score"), p5),
            "unmet_requests": " | ".join(a.get("unmet_requests") or []),
            "missed_gaps": " | ".join(a.get("missed_gaps") or []),
        })

    print(f"task completion (score_communicated >= {DONE_AT}) x "
          f"satisfaction (P5_overall >= {SATISFIED_AT})")
    personas = sorted({r["persona"] for r in rows})
    width = max(len(q) for q in QUADRANTS) + 2
    print(f"{'persona':<30}{'n':>4}  " + "".join(f"{q:>{width}}" for q in QUADRANTS)
          + f"{'unscored':>10}")
    for who in personas + ["ALL"]:
        mine = [r for r in rows if who in ("ALL", r["persona"])]
        n = len(mine)
        cells = "".join(
            f"{sum(r['quadrant'] == q for r in mine):>{width - 7}} ({sum(r['quadrant'] == q for r in mine) / n:>4.0%})"
            for q in QUADRANTS)
        print(f"{who:<30}{n:>4}  {cells}{sum(r['quadrant'] is None for r in mine):>10}")

    odd = [r for r in rows if r["quadrant"] in ("done+unsatisfied", "undone+satisfied")]
    if odd:
        print("\noff-diagonal runs")
        for r in odd:
            print(f"  {r['quadrant']:<18} {r['task']} {r['persona']:<28} "
                  f"comm={r['score_communicated']} P5={r['P5']}")
    return rows


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
