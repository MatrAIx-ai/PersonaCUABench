"""What each setting, model and task cost, and how long it took.

Reads the accounting every run writes and rolls it up the three ways a paper
needs it: per setting, per CUA model, and per task. Judge spend is reported
beside browsing spend rather than folded into it, because they scale
differently -- browsing cost grows with steps, judging with trajectory length.

    python odyssey/cost_report.py                        # odyssey/results
    python odyssey/cost_report.py path/to/results --csv out.csv
    python odyssey/cost_report.py --by persona
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE_ROLES = ("rubric_judge", "experience_judge", "persona_fidelity_judge")
# The collaborator's endpoint. Calls that went there are their bill, not ours,
# whatever the record says -- results written before that distinction existed
# priced Azure at the OpenRouter list price and charged it to us.
AZURE_PROVIDERS = ("openai",)
AZURE_BACKENDS = ("azure-openai-compatible",)


def is_azure(provider: str | None, backend: str | None = None) -> bool:
    return (provider or "") in AZURE_PROVIDERS or (backend or "") in AZURE_BACKENDS


def split_costs(calls: list[dict]) -> tuple[float, float]:
    """(ours, theirs) over individual model calls."""
    ours = theirs = 0.0
    for call in calls or []:
        amount = call.get("cost_usd")
        if is_azure(call.get("provider")):
            # list_cost_usd exists on newer records; on older ones the
            # mispriced cost_usd is the same estimate under a wrong name.
            theirs += call.get("list_cost_usd") or amount or 0.0
        else:
            ours += amount or 0.0
    return ours, theirs


def cells(results: Path):
    """Every result with accounting, as flat rows ready to group."""
    for path in sorted(results.rglob("result.json")):
        if any(part.startswith("_") for part in path.parts):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        acct = record.get("accounting")
        if not isinstance(acct, dict):
            continue              # a run from before accounting existed
        by_role = acct.get("by_role") or {}
        run = record.get("run") or {}
        arm = run.get("arm") or {}
        calls = acct.get("calls") or []
        ours_calls, azure_calls = split_costs(calls)
        # The post-hoc judges live in their own blocks, each with its own meter
        # and its own provider, so each block is attributed on its own.
        blocks = [(record.get("experience") or {}).get(side) or {}
                  for side in ("a", "b")]
        blocks.append(record.get("persona_fidelity") or {})
        judge_cost = judge_ms = 0.0
        for block in blocks:
            block_acct = block.get("accounting") or {}
            amount = block_acct.get("cost_usd") or 0.0
            judge_ms += block_acct.get("model_ms", 0)
            if is_azure(block.get("provider"), block.get("backend")):
                azure_calls += block_acct.get("list_cost_usd") or amount
            else:
                judge_cost += amount
        # The inline rubric judge bills into the run's own meter, so its share
        # is already in the call split; count only its visible total here.
        inline_judge = sum((by_role.get(role) or {}).get("cost_usd", 0.0)
                           for role in JUDGE_ROLES)
        if not is_azure(arm.get("provider"), arm.get("backend")):
            judge_cost += inline_judge
        judge_ms += sum((by_role.get(role) or {}).get("ms", 0) for role in JUDGE_ROLES)
        agent = {**(by_role.get("agent") or {})}
        agent_ours = 0.0 if is_azure(arm.get("provider"), arm.get("backend")) \
            else agent.get("cost_usd", 0.0)
        if is_azure(arm.get("provider"), arm.get("backend")) and not calls:
            # A record from before per-call attribution: its agent total is the
            # list-price estimate of what Azure was asked to do.
            azure_calls += agent.get("list_cost_usd") or agent.get("cost_usd", 0.0)
        azure_cost = azure_calls
        yield {
            "setting": record.get("setting") or "(none)",
            "suite": record.get("suite_id") or "(none)",
            "task": (record.get("task_id") or "?")[:12],
            "level": record.get("level") or "?",
            "persona": record.get("persona") or "?",
            "replicate": str(record.get("replicate_id") or "?"),
            "model": ((run.get("arm") or {}).get("model")) or "?",
            "provider": ((run.get("arm") or {}).get("provider")) or "?",
            "steps": run.get("steps") or 0,
            "score": (record.get("judgement") or {}).get("score"),
            "wall_seconds": acct.get("cell_wall_seconds") or 0.0,
            "agent_ms": agent.get("ms", 0),
            "judge_ms": judge_ms,
            "prompt_tokens": acct.get("prompt_tokens", 0),
            "completion_tokens": acct.get("completion_tokens", 0),
            "agent_cost": round(agent_ours, 6),
            "judge_cost": round(judge_cost, 6),
            "total_cost": round(agent_ours + judge_cost, 6),
            "azure_cost": round(azure_cost, 6),
            "unpriced_calls": acct.get("unpriced_calls", 0),
            "path": str(path),
        }


def group(rows: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        bucket = out.setdefault(row[key], {
            "cells": 0, "wall_seconds": 0.0, "steps": 0, "prompt_tokens": 0,
            "completion_tokens": 0, "agent_cost": 0.0, "judge_cost": 0.0,
            "total_cost": 0.0, "azure_cost": 0.0, "unpriced_calls": 0})
        bucket["cells"] += 1
        for field in ("wall_seconds", "steps", "prompt_tokens", "completion_tokens",
                      "agent_cost", "judge_cost", "total_cost", "azure_cost",
                      "unpriced_calls"):
            bucket[field] += row[field]
    return out


def table(title: str, grouped: dict[str, dict], label: str) -> None:
    if not grouped:
        return
    print(f"\n{title}")
    width = max(len(label), max(len(k) for k in grouped)) + 2
    print(f"{label:<{width}}{'cells':>6}{'min/cell':>10}{'steps':>7}"
          f"{'in tok':>12}{'out tok':>9}{'agent $':>10}{'judge $':>9}"
          f"{'ours $':>9}{'azure $':>10}")
    for name in sorted(grouped):
        b = grouped[name]
        cells_n = b["cells"] or 1
        print(f"{name:<{width}}{b['cells']:>6}{b['wall_seconds'] / cells_n / 60:>10.1f}"
              f"{b['steps'] / cells_n:>7.1f}{b['prompt_tokens']:>12,}"
              f"{b['completion_tokens']:>9,}{b['agent_cost']:>10.2f}"
              f"{b['judge_cost']:>9.2f}{b['total_cost']:>9.2f}"
              f"{b['azure_cost']:>10.2f}")
    totals = {f: sum(b[f] for b in grouped.values())
              for f in ("cells", "wall_seconds", "agent_cost", "judge_cost",
                        "total_cost", "azure_cost")}
    print(f"{'TOTAL':<{width}}{totals['cells']:>6}"
          f"{totals['wall_seconds'] / 3600:>9.1f}h{'':>7}{'':>12}{'':>9}"
          f"{totals['agent_cost']:>10.2f}{totals['judge_cost']:>9.2f}"
          f"{totals['total_cost']:>9.2f}{totals['azure_cost']:>10.2f}")
    if totals["azure_cost"]:
        print("  'azure $' is the collaborator's endpoint at list price, not our "
              "spend; 'ours $' is what our own keys were charged")
    unpriced = sum(b["unpriced_calls"] for b in grouped.values())
    if unpriced:
        print(f"  note: {unpriced} model calls had no price (provider reported none "
              f"and the model is not in odyssey/models.json) -- dollars are a floor")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", default=str(HERE / "results"))
    ap.add_argument("--by", default="", choices=["", "persona", "replicate", "level"],
                    help="one extra breakdown beyond setting / model / task")
    ap.add_argument("--csv", help="also write one row per cell here, for the paper")
    args = ap.parse_args()

    rows = list(cells(Path(args.results)))
    if not rows:
        print(f"no results with accounting under {args.results}\n"
              "(runs recorded before the accounting change have none; rerun or "
              "treat their cost as unknown)")
        return

    table("by setting", group(rows, "setting"), "setting")
    table("by CUA model", group(rows, "model"), "model")
    table("by task", group(rows, "task"), "task")
    if args.by:
        table(f"by {args.by}", group(rows, args.by), args.by)

    if args.csv:
        fields = [k for k in rows[0] if k != "path"] + ["path"]
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {len(rows)} cell rows -> {args.csv}")


if __name__ == "__main__":
    main()
