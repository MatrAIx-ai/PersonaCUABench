"""Pair separation: did flipping one dimension actually move the simulated user?

The fidelity judge scores one arm at a time. The experiment's headline question
is about the pair: the protocol's rule is that a matched pair separates only
when BOTH arms score 2 for their own pole and the cited evidence shows
meaningfully opposite preferences. This reads the judged runs, rebuilds every
(task, axis, replicate) pair, and applies that rule as far as it can be applied
mechanically.

The last clause -- "meaningfully opposite" -- is a semantic judgement, so a pair
that clears the mechanical bar is reported as `separated_pending_evidence_review`
and its two quotes are printed side by side for a human to confirm or reject.
Nothing here overrides a judge; it only pairs up what the judges already wrote.

    python src/pair_separation.py                      # src/results
    python src/pair_separation.py path/to/results --evidence
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("positive", "negative")


def arm_record(record: dict) -> dict | None:
    """The matched-pair identity of a run, or None for a non-matched-pair run."""
    snapshot = ((record.get("run") or {}).get("user") or {}).get("persona_profile")
    pair = (snapshot or {}).get("matched_pair")
    fidelity = record.get("persona_fidelity")
    if not pair or not isinstance(fidelity, dict):
        return None
    if pair.get("arm") not in ARMS:
        return None
    return {
        "suite": record.get("suite_id") or "?",
        "task": (record.get("task_id") or "?")[:12],
        "axis": pair.get("axis_id") or "?",
        "replicate": str(record.get("replicate_id") or "?"),
        "arm": pair["arm"],
        "target_value": pair.get("target_value"),
        "fidelity": fidelity,
    }


def arm_verdict(entry: dict) -> dict:
    """Flatten one arm's fidelity verdict to what the pairing rule needs.

    A matched-pair profile declares exactly one target (its changed dimension),
    so the pair rule reads that target. A guardrail failure has already zeroed
    the scores upstream; it is surfaced here as the reason, not recomputed.
    """
    fidelity = entry["fidelity"]
    guardrail = fidelity.get("communication_guardrail") or {}
    targets = fidelity.get("targets") or []
    target = targets[0] if len(targets) == 1 else None
    return {
        "status": fidelity.get("status"),
        "coverage_failed": guardrail.get("applicable") and guardrail.get("passed") is False,
        "coverage": f"{guardrail.get('communicated')}/{guardrail.get('expected_total')}",
        "score": (target or {}).get("score"),
        "expressed": bool((target or {}).get("expressed")),
        "contradicted": bool((target or {}).get("contradicted")),
        "evidence": ((target or {}).get("evidence") or "").strip(),
        "targets": len(targets),
    }


def classify(pair: dict[str, dict]) -> tuple[str, str]:
    """(verdict, reason) for one (task, axis, replicate) pair."""
    missing = [arm for arm in ARMS if arm not in pair]
    if missing:
        return "incomplete", f"no {', '.join(missing)} arm judged"
    verdicts = {arm: arm_verdict(pair[arm]) for arm in ARMS}
    for arm, v in verdicts.items():
        if v["status"] != "complete":
            return "invalid", f"{arm} arm fidelity status={v['status']}"
        if v["targets"] != 1:
            return "invalid", f"{arm} arm declared {v['targets']} targets, expected 1"
        if v["coverage_failed"]:
            return "invalid", f"{arm} arm communicated only {v['coverage']} rubrics"
    for arm, v in verdicts.items():
        if v["contradicted"]:
            return "not_separated", f"{arm} arm contradicted its own pole"
    weak = [f"{arm}={v['score']}" for arm, v in verdicts.items() if not v["expressed"]]
    if weak:
        return "not_separated", f"arm scored below 2: {', '.join(weak)}"
    # Both poles expressed with no contradiction. Whether the two quotes are
    # *opposite* is a semantic call the protocol reserves for a human.
    return "separated_pending_evidence_review", "both arms scored 2"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", default=str(HERE / "results"))
    ap.add_argument("--evidence", action="store_true",
                    help="print both arms' quoted evidence for every separated pair")
    args = ap.parse_args()

    pairs: dict[tuple[str, str, str, str], dict[str, dict]] = defaultdict(dict)
    for path in sorted(Path(args.results).rglob("result.json")):
        if any(part.startswith("_") for part in path.parts):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entry = arm_record(record)
        if entry:
            key = (entry["suite"], entry["task"], entry["axis"], entry["replicate"])
            pairs[key][entry["arm"]] = entry

    if not pairs:
        print(f"no judged matched-pair runs under {args.results}")
        return

    results = {key: classify(pair) for key, pair in pairs.items()}
    by_axis: dict[str, list[str]] = defaultdict(list)
    for (_, _, axis, _), (verdict, _) in results.items():
        by_axis[axis].append(verdict)

    print("pair separation by axis")
    width = max(len(a) for a in by_axis) + 2
    print(f"{'axis':<{width}}{'separated':>10}{'not sep.':>10}{'invalid':>9}"
          f"{'incomplete':>12}{'pairs':>7}")
    for axis in sorted(by_axis):
        v = by_axis[axis]
        print(f"{axis:<{width}}"
              f"{sum(x.startswith('separated') for x in v):>10}"
              f"{v.count('not_separated'):>10}{v.count('invalid'):>9}"
              f"{v.count('incomplete'):>12}{len(v):>7}")

    print("\nper pair")
    for key in sorted(results):
        suite, task, axis, replicate = key
        verdict, reason = results[key]
        print(f"  {task}  {axis:<22} r={replicate:<4} {verdict:<36} {reason}")

    if args.evidence:
        print("\nevidence for review (a pair separates only if these are genuinely opposite)")
        for key in sorted(results):
            if not results[key][0].startswith("separated"):
                continue
            print(f"\n  {key[1]} / {key[2]} / r={key[3]}")
            for arm in ARMS:
                entry = pairs[key][arm]
                print(f"    {arm:<9} [{entry['target_value']}] "
                      f"{arm_verdict(entry)['evidence'][:220]}")


if __name__ == "__main__":
    main()
