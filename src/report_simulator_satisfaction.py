"""Summarise simulator_satisfaction.json written by simulator_satisfaction.py.

For each model and suite, none vs persona:
  sat       the person's own satisfaction (1-5) at handoff, and after checking
            the site (REAL only)
  P5        the outside experience judge's overall score, for comparison
  AUC       how well a score separates passed from failed cells: the chance a
            random passed cell scores higher than a random failed one (0.5 is a
            coin flip). REAL: checker pass vs fail. Odysseys: every rubric item
            met vs none met.
  thinks done | failed
            share of failed cells where the person believes the task was done

    python src/report_simulator_satisfaction.py [src/results/s1]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def passed(suite, score):
    if suite == "real":
        return {1: True, 0: False}.get(score)
    return True if score >= 0.999 else False if score <= 0.001 else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", default=str(HERE / "results" / "s1"))
    args = ap.parse_args()

    groups = defaultdict(list)
    for out in Path(args.results).rglob("simulator_satisfaction.json"):
        sat = json.loads(out.read_text(encoding="utf-8"))
        record = json.loads((out.parent / "result.json").read_text(encoding="utf-8"))
        handoff = sat.get("handoff") or {}
        if handoff.get("error") or "satisfaction" not in handoff:
            continue
        verified = sat.get("verified") or {}
        p5 = ((((record.get("experience") or {}).get("a") or {}).get("P5_overall")) or {}).get("score")
        model = ((record.get("run_config") or {}).get("agent") or {}).get("model")
        suite = record.get("suite_id")
        arm = "none" if record["persona"] == "none" else "persona"
        groups[(model, suite, arm)].append({
            "score": record["judgement"]["score"],
            "h": handoff["satisfaction"], "h_done": handoff.get("believes_done"),
            "v": verified.get("satisfaction"), "v_done": verified.get("believes_done"),
            "p5": p5 if isinstance(p5, (int, float)) and not isinstance(p5, bool) else None,
        })

    head = (f"{'model':30} {'suite':9} {'arm':8} {'n':>4} {'score':>6} {'P5':>5} {'sat@h':>6} "
            f"{'sat@v':>6} | {'AUC P5':>6} {'AUC@h':>6} {'AUC@v':>6} | "
            f"{'thinks done|failed @h':>21} {'@v':>6}")
    print(head)
    print("-" * len(head))
    for (model, suite, arm), cells in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        def split(key):
            pos = [c[key] for c in cells if passed(suite, c["score"]) is True and c[key] is not None]
            neg = [c[key] for c in cells if passed(suite, c["score"]) is False and c[key] is not None]
            return auc(pos, neg)
        failed = [c for c in cells if passed(suite, c["score"]) is False]
        thinks = lambda k: (mean([c[k] == "yes" for c in failed if c[k]]) if failed else float("nan"))
        v_vals = [c["v"] for c in cells if c["v"] is not None]
        print(f"{str(model)[:30]:30} {suite:9} {arm:8} {len(cells):>4} "
              f"{mean([c['score'] for c in cells]):6.3f} "
              f"{mean([c['p5'] for c in cells if c['p5'] is not None]):5.2f} "
              f"{mean([c['h'] for c in cells]):6.2f} {mean(v_vals) if v_vals else float('nan'):6.2f} | "
              f"{split('p5'):6.2f} {split('h'):6.2f} {split('v'):6.2f} | "
              f"{thinks('h_done'):>21.0%} {thinks('v_done') if v_vals else float('nan'):>6.0%}"
              f"   (failed n={len(failed)})")


if __name__ == "__main__":
    main()
