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
        arm_meta = rec["run"]["arm"]
        backend = arm_meta.get("backend") or arm_meta.get("provider") or "unknown"
        arm = f"{rec['persona']}/{arm_meta['model']}@{backend}"
        key = (rec["task_id"][:12], arm)
        stamp = path.parent.name.rsplit("__", 1)[-1]
        if key not in best or stamp > best[key][0]:
            best[key] = (stamp, judged, rec["run"].get("max_steps"),
                         rec.get("experience"), rec.get("persona_fidelity"))

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
    experience(best)
    persona_fidelity(best)


DIMENSIONS = ("P1_asked_for", "P2_readable_for_them", "P3_actionable",
              "P4_gap_handling", "P5_overall")


def dim_score(verdict: dict | None, dim: str) -> float | None:
    """One judge's 1-5 score for one dimension, or None for 'n/a'/missing."""
    raw = ((verdict or {}).get(dim) or {}).get("score")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw) if 1 <= raw <= 5 else None


def experience(best: dict) -> None:
    """The person's axis, kept beside the task axis and never blended into it.

    Two judges scored every run from the same prompt; their scores are reported
    side by side, never averaged, because a hidden disagreement is the thing
    worth seeing. The last block is the only place the two axes meet: the
    experience of the runs that actually did the job, so a readable answer can
    never paper over a task the agent failed.
    """
    scored = {k: v for k, v in best.items() if len(v) > 3 and v[3]}
    if not scored:
        return
    arms = sorted({a for _, a in scored})
    print("\n\nexperience 1-5 per dimension, judge A / judge B (never averaged)")
    width = max(len(a) for a in arms) + 2
    print(f"{'dimension':<24}" + "".join(f"{a:<{width}}" for a in arms))
    for dim in DIMENSIONS:
        row = f"{dim:<24}"
        for arm in arms:
            pairs = [(dim_score(v[3].get("a"), dim), dim_score(v[3].get("b"), dim))
                     for k, v in scored.items() if k[1] == arm]
            a = [x for x, _ in pairs if x is not None]
            b = [y for _, y in pairs if y is not None]
            cell = (f"{sum(a)/len(a):.1f} / {sum(b)/len(b):.1f}" if a and b else "-")
            row += f"{cell:<{width}}"
        print(row)

    # How far apart the two judges are, the way the MatrAIx paper reports it.
    deltas = [d["within_one"] for v in scored.values()
              for d in (v[3].get("agreement") or {}).values() if d]
    if deltas:
        print(f"\njudges within one point: {sum(deltas)}/{len(deltas)} "
              f"({sum(deltas)/len(deltas):.1%})")

    # Style never offsets a failed task: condition on the task being done.
    print("\nP5 among runs that did everything they were asked "
          "(score_communicated = 1.0)")
    for arm in arms:
        done = [v for k, v in scored.items()
                if k[1] == arm and v[1].get("score_communicated") == 1.0]
        vals = [s for v in done for s in
                (dim_score(v[3].get("a"), "P5_overall"),
                 dim_score(v[3].get("b"), "P5_overall")) if s is not None]
        print(f"  {arm:<{width}}{'-' if not vals else f'{sum(vals)/len(vals):.1f}'}"
              f"   ({len(done)} of {sum(1 for k in scored if k[1] == arm)} runs)")


def persona_fidelity(best: dict) -> None:
    """Report target score distributions, separate from CUA quality."""
    scored = {k: v for k, v in best.items()
              if len(v) > 4 and (v[4] or {}).get("status") == "complete"}
    if not scored:
        return
    arms = sorted({arm for _, arm in scored})
    width = max(len(arm) for arm in arms) + 2
    print("\n\npersona fidelity targets: 0=no affirmative evidence, "
          "1=weak, 2=clearly expressed; contradictions reported separately")
    print(f"{'arm':<{width}}score 0   score 1   score 2   contradicted   total")
    for arm in arms:
        records = [value[4] for key, value in scored.items() if key[1] == arm]
        values = [target["score"] for record in records for target in record["targets"]]
        counts = [values.count(score) for score in (0, 1, 2)]
        contradicted = sum(
            bool(target.get("contradicted"))
            for record in records for target in record["targets"]
        )
        print(f"{arm:<{width}}{counts[0]:<10}{counts[1]:<10}{counts[2]:<10}"
              f"{contradicted:<15}{len(values)}")


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
