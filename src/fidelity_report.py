"""Summarise persona-fidelity verdicts, export a human annotation sheet, and
measure how well the LLM judge agrees with human annotators.

persona_fidelity_judge.py scores every declared target 0/1/2 (2 = expressed).
This reads those verdicts back out of the result records:

    python src/fidelity_report.py --results <dir>                       # tables
    python src/fidelity_report.py --results <dir> --sheet s.csv --cells 10
    python src/fidelity_report.py --results <dir> --kappa s.csv         # agreement

The sheet samples --cells cells per persona group, every target of a sampled
cell on its own row, and leaves the LLM's score out so annotators are blind to
it. Annotators fill `human_1`, `human_2`, ... with 0/1/2; --kappa compares every
pair of raters it finds (the LLM and each human column).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path

GROUPS = ("expert", "senior", "young", "practical")


def load(results: Path) -> list[dict]:
    """One row per (cell, target) with a complete LLM verdict."""
    rows = []
    for path in sorted(results.rglob("result.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        fidelity = record.get("persona_fidelity") or {}
        if fidelity.get("status") != "complete":
            continue
        cell = f"{record['task_id'][:12]}/{record['persona']}"
        utterances = "\n\n".join(
            f"[turn {i}] {t['text']}" for i, t in enumerate(
                (t for t in record["run"]["conversation"] if t["role"] == "user"), 1))
        for target in fidelity["targets"]:
            rows.append({
                "item": f"{cell}/{target['attribute']}",
                "cell": cell,
                "group": record["persona"].rsplit("-", 1)[-1],
                "domain": record["persona"].rsplit("-", 1)[0],
                "attribute": target["attribute"],
                "expected_value": target["expected_value"],
                "llm": target["score"],
                "contradicted": target["contradicted"],
                "utterances": utterances,
            })
    return rows


def summary(rows: list[dict]) -> None:
    def line(label: str, scores: list[dict]) -> str:
        n = len(scores)
        expressed = sum(r["llm"] == 2 for r in scores) / n
        contradicted = sum(r["contradicted"] for r in scores) / n
        mean = sum(r["llm"] for r in scores) / n
        return (f"  {label:28} n={n:5}  mean={mean:.2f}  "
                f"expressed={expressed:6.1%}  contradicted={contradicted:5.1%}")

    print(f"{len({r['cell'] for r in rows})} cells, {len(rows)} targets\n")
    print(line("all", rows))
    for key in ("group", "attribute"):
        print(f"\nby {key}")
        buckets = defaultdict(list)
        for r in rows:
            buckets[r[key]].append(r)
        for label in sorted(buckets, key=lambda k: (GROUPS + (k,)).index(k)):
            print(line(label, buckets[label]))


def write_sheet(rows: list[dict], path: Path, per_group: int, seed: int) -> None:
    cells_by_group = defaultdict(set)
    for r in rows:
        cells_by_group[r["group"]].add(r["cell"])
    rng = random.Random(seed)
    chosen = {c for cells in cells_by_group.values()
              for c in rng.sample(sorted(cells), min(per_group, len(cells)))}
    # Cells in random order, so one task's four personas are not read side by
    # side; a cell's targets stay together so its text is read once.
    order = sorted(chosen)
    rng.shuffle(order)
    rank = {cell: i for i, cell in enumerate(order)}
    picked = sorted((r for r in rows if r["cell"] in chosen), key=lambda r: rank[r["cell"]])
    fields = ["item", "attribute", "expected_value", "utterances", "human_1", "human_2"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in picked:
            writer.writerow({**r, "human_1": "", "human_2": ""})
    print(f"wrote {len(picked)} rows from {len(chosen)} cells to {path}")


def cohen_kappa(a: list[int], b: list[int], weighted: bool) -> float:
    """Cohen's kappa over labels 0/1/2; quadratic weights when `weighted`."""
    k, n = 3, len(a)
    w = [[((i - j) ** 2 / (k - 1) ** 2) if weighted else float(i != j)
          for j in range(k)] for i in range(k)]
    observed = sum(w[x][y] for x, y in zip(a, b)) / n
    pa = [a.count(i) / n for i in range(k)]
    pb = [b.count(i) / n for i in range(k)]
    expected = sum(w[i][j] * pa[i] * pb[j] for i in range(k) for j in range(k))
    return 1.0 if expected == 0 else 1 - observed / expected


def agreement(rows: list[dict], sheet: Path) -> None:
    llm = {r["item"]: r["llm"] for r in rows}
    with sheet.open(encoding="utf-8") as f:
        annotated = list(csv.DictReader(f))
    raters = {"llm": {}}
    for row in annotated:
        if row["item"] in llm:
            raters["llm"][row["item"]] = llm[row["item"]]
        for col, value in row.items():
            if col.startswith("human") and value.strip() in {"0", "1", "2"}:
                raters.setdefault(col, {})[row["item"]] = int(value)
    for x, y in combinations(raters, 2):
        items = sorted(set(raters[x]) & set(raters[y]))
        if not items:
            continue
        a = [raters[x][i] for i in items]
        b = [raters[y][i] for i in items]
        exact = sum(p == q for p, q in zip(a, b)) / len(items)
        binary = cohen_kappa([2 * (v == 2) for v in a], [2 * (v == 2) for v in b], False)
        print(f"{x:>8} vs {y:<8} n={len(items):4}  agree={exact:6.1%}  "
              f"kappa={cohen_kappa(a, b, False):.3f}  "
              f"weighted={cohen_kappa(a, b, True):.3f}  expressed-kappa={binary:.3f}")


def _check() -> None:
    assert cohen_kappa([0, 1, 2, 2], [0, 1, 2, 2], False) == 1.0
    assert abs(cohen_kappa([0, 0, 1, 1], [0, 1, 0, 1], False)) < 1e-9
    # a 0-vs-2 miss costs more than a 1-vs-2 miss only when weighted
    near = cohen_kappa([0, 1, 2, 2], [0, 1, 2, 1], True)
    far = cohen_kappa([0, 1, 2, 2], [0, 1, 2, 0], True)
    assert near > far
    print("ok")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path)
    ap.add_argument("--sheet", type=Path, help="write a blind annotation sheet here")
    ap.add_argument("--cells", type=int, default=10, help="cells per persona group")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--kappa", type=Path, help="an annotated sheet to score")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _check()
    rows = load(args.results)
    if args.sheet:
        write_sheet(rows, args.sheet, args.cells, args.seed)
    elif args.kappa:
        agreement(rows, args.kappa)
    else:
        summary(rows)


if __name__ == "__main__":
    main()
