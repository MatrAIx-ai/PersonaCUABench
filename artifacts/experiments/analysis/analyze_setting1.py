#!/usr/bin/env python3
"""Dated post-hoc analysis for science-education Setting 1 blocks.

Computes the tables the maintainers' Shopping formal report uses, from the result.json
files one or more replicate blocks contain:

- raw task completion, task x arm, with the six-task macro per arm
- cell-macro and rubric-micro completion, communicated coverage, communicated-only score
- per-persona paired delta against `none` on the same task and replicate
- experience judge A/B means per P1-P5, exact and within-one agreement
- the full-task-perfect slice (judgement.score == 1.0), where Persona Factor 2 is asked
- per-cell run facts: steps, ask_user count, stop reason
- per-cell environment evidence (Google /sorry, 403, Access Denied, CAPTCHA/Cloudflare,
  DNS, timeouts, empty reads) as INPUT to the manual KEEP / EXCLUDE_RERUN audit. The
  audit itself is a per-cell human judgement, as in the Shopping report: a block only
  excludes a cell when it stops required or communicated evidence from being reachable.

Nothing here writes to a result.json. Summaries are descriptive; a single hand-built
profile per group supports archetype-level statements only.

    python3 work/analyze_setting1.py artifacts/experiments/2026-09-28/science-education-main-setting1-r1
    python3 work/analyze_setting1.py BLOCK1 BLOCK2 BLOCK3 --md out.md
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent / "repo"
TASKS = json.loads((REPO / "odyssey" / "tasks.json").read_text())
TASK_N = {t["task_id"][:12]: i for i, t in enumerate(TASKS, 1)}
SHORT = {1: "T1 LGM study", 2: "T2 mini lesson", 3: "T3 AI explainer",
         4: "T4 grad outreach", 5: "T5 law schools", 6: "T6 MH evidence"}
ARMS = ["none", "education-faculty-advisor", "education-k12-teacher",
        "education-first-gen-applicant", "education-parent-helper"]
ARM_LABEL = {"none": "none (control)", "education-faculty-advisor": "Faculty advisor",
             "education-k12-teacher": "K-12 teacher",
             "education-first-gen-applicant": "First-gen applicant",
             "education-parent-helper": "Parent helper"}
PS = ["P1_asked_for", "P2_readable_for_them", "P3_actionable", "P4_gap_handling", "P5_overall"]
ENV = {
    "google_sorry": r"google\.[a-z.]+/sorry",
    "http_403": r"\b403\b",
    "access_denied": r"(?i)access denied",
    "captcha_cf": r"(?i)captcha|cloudflare|verify you are human|are you a robot|just a moment",
    "dns": r"(?i)ERR_NAME_NOT_RESOLVED|dns",
    "timeout": r"(?i)timeout|timed out|ERR_TIMED_OUT",
    "conn": r"(?i)ERR_CONNECTION|net::ERR",
}


def load(blocks: list[Path]) -> list[dict]:
    rows = []
    for b in blocks:
        rep = b.name.rsplit("-", 1)[-1]
        for p in sorted((b / "results").glob("*/*/result.json")):
            r = json.loads(p.read_text())
            run, j = r.get("run") or {}, r.get("judgement") or {}
            tr = run.get("trajectory") or []
            blob = "\n".join(str(t.get("result_preview", "")) + " " +
                             json.dumps(t.get("args", {}), ensure_ascii=False) for t in tr)
            env = {k: len(re.findall(v, blob)) for k, v in ENV.items()}
            gs_ok = sum(1 for t in tr if "google.com/search" in str(t.get("result_preview", ""))
                        and "/sorry" not in str(t.get("result_preview", "")))
            empty = sum(1 for t in tr if t.get("tool") == "read_page"
                        and len(str(t.get("result_preview", "")).strip()) < 40)
            rows.append({
                "rep": rep, "block": b.name, "path": str(p.relative_to(REPO)),
                "task": TASK_N.get(r["task_id"][:12]), "arm": r.get("persona"),
                "model": p.parent.name.split("__")[1],
                "score": j.get("score"), "met": j.get("met"), "total": j.get("total"),
                "comm": j.get("communicated"), "score_comm": j.get("score_communicated"),
                "verdicts": j.get("verdicts") or {},
                "steps": run.get("steps"), "stop": run.get("stop_reason"),
                "asked": sum(1 for t in tr if t.get("tool") == "ask_user"),
                "env": env, "google_ok": gs_ok, "empty_reads": empty,
                "exp": r.get("experience") or {},
            })
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


def f(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def report(rows: list[dict]) -> str:
    out = []
    reps = sorted({r["rep"] for r in rows})
    models = sorted({r["model"] for r in rows})
    out.append(f"# science-education Setting 1 — post-hoc summary\n")
    out.append(f"Replicates: {', '.join(reps)}. Executors: {', '.join(models)}. "
               f"Cells: {len(rows)}.\n")

    for model in models:
        mr = [r for r in rows if r["model"] == model]
        out.append(f"\n## Executor `{model}`\n")
        # completion table, averaged over replicates
        out.append("### Raw task completion (mean over replicates)\n")
        out.append("| arm | " + " | ".join(SHORT[t] for t in range(1, 7)) + " | 6-task macro |")
        out.append("|---|" + "---:|" * 7)
        arm_macro = {}
        for a in ARMS:
            cells = [mean([r["score"] for r in mr if r["arm"] == a and r["task"] == t]) for t in range(1, 7)]
            arm_macro[a] = mean(cells)
            out.append(f"| {ARM_LABEL[a]} | " + " | ".join(f(c) for c in cells) +
                       f" | **{f(arm_macro[a], 4)}** |")
        sc = [r for r in mr if r["score"] is not None]
        met = sum(r["met"] or 0 for r in sc); tot = sum(r["total"] or 0 for r in sc)
        cm = sum(r["comm"] or 0 for r in sc)
        out.append("")
        out.append(f"- cell-macro completion `{f(mean([r['score'] for r in sc]), 4)}`; "
                   f"rubric micro `{met}/{tot} = {f(met / tot if tot else None, 4)}`")
        out.append(f"- communicated coverage: cell-macro "
                   f"`{f(mean([(r['comm'] or 0) / r['total'] for r in sc if r['total']]), 4)}`; "
                   f"micro `{cm}/{tot} = {f(cm / tot if tot else None, 4)}`")
        out.append(f"- communicated-only: cell-macro `{f(mean([r['score_comm'] for r in sc]), 4)}`")

        out.append("\n### Persona effect: paired delta vs `none` (same task, same replicate)\n")
        out.append("| persona | completion delta | coverage | communicated-only | mean asks |")
        out.append("|---|---:|---:|---:|---:|")
        for a in ARMS[1:]:
            ds, cov, sco, asks = [], [], [], []
            for r in mr:
                if r["arm"] != a:
                    continue
                base = [b for b in mr if b["arm"] == "none" and b["task"] == r["task"] and b["rep"] == r["rep"]]
                if base and r["score"] is not None and base[0]["score"] is not None:
                    ds.append(r["score"] - base[0]["score"])
                if r["total"]:
                    cov.append((r["comm"] or 0) / r["total"])
                sco.append(r["score_comm"]); asks.append(r["asked"])
            out.append(f"| {ARM_LABEL[a]} | {f(mean(ds))} | {f(mean(cov))} | {f(mean(sco))} | {f(mean(asks), 2)} |")
        base_asks = mean([r["asked"] for r in mr if r["arm"] == "none"])
        out.append(f"\n`none` mean asks: {f(base_asks, 2)} — the attribution baseline for persona-arm questions.")

        ex = [r for r in mr if r["exp"].get("a") and r["exp"].get("b")]
        if ex:
            out.append("\n### Persona experience judge (P1–P5, 1–5), A/B are two independent Terra calls\n")
            out.append("| dimension | A mean | B mean | exact | within-one |")
            out.append("|---|---:|---:|---:|---:|")
            ex_all = w_all = n_all = 0
            for pdim in PS:
                A = [r["exp"]["a"].get(pdim, {}).get("score") for r in ex]
                B = [r["exp"]["b"].get(pdim, {}).get("score") for r in ex]
                pairs = [(x, y) for x, y in zip(A, B) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
                exact = sum(1 for x, y in pairs if x == y); w1 = sum(1 for x, y in pairs if abs(x - y) <= 1)
                ex_all += exact; w_all += w1; n_all += len(pairs)
                an = [x for x in A if isinstance(x, (int, float))]; bn = [y for y in B if isinstance(y, (int, float))]
                out.append(f"| {pdim} | {f(mean(an), 2)} (n={len(an)}) | {f(mean(bn), 2)} (n={len(bn)}) | "
                           f"{exact}/{len(pairs)} | {w1}/{len(pairs)} |")
            out.append(f"| **all** | | | **{ex_all}/{n_all}** | **{w_all}/{n_all}** |")

            out.append("\n### P5 overall by persona (A/B mean)\n")
            out.append("| arm | P5 all cells | P5 on full-task-perfect cells (score == 1.0) |")
            out.append("|---|---:|---:|")
            for a in ARMS:
                c = [r for r in ex if r["arm"] == a]
                p5 = [mean([r["exp"][k].get("P5_overall", {}).get("score") for k in ("a", "b")
                            if isinstance(r["exp"][k].get("P5_overall", {}).get("score"), (int, float))]) for r in c]
                perf = [v for v, r in zip(p5, c) if r["score"] == 1.0]
                out.append(f"| {ARM_LABEL[a]} | {f(mean(p5), 2)} (n={len(p5)}) | "
                           f"{f(mean(perf), 2)} (n={len(perf)}) |")

    out.append("\n## Per-cell run facts and environment evidence (input to the manual audit)\n")
    out.append("| rep | task | arm | model | score | comm | steps | asks | stop | google ok/sorry | 403 | denied | captcha/CF | dns | timeout | empty reads |")
    out.append("|---|---|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|")
    for r in sorted(rows, key=lambda r: (r["rep"], r["task"] or 0, ARMS.index(r["arm"]) if r["arm"] in ARMS else 9, r["model"])):
        e = r["env"]
        out.append(f"| {r['rep']} | {r['task']} | {r['arm'].replace('education-', '')} | {r['model']} | "
                   f"{f(r['score'])} | {r['comm']}/{r['total']} | {r['steps']} | {r['asked']} | {r['stop']} | "
                   f"{r['google_ok']}/{e['google_sorry']} | {e['http_403']} | {e['access_denied']} | "
                   f"{e['captcha_cf']} | {e['dns']} | {e['timeout']} | {r['empty_reads']} |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("blocks", nargs="+", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--executors", help="comma-separated substrings of the model dir name to keep, "
                                        "e.g. gpt-5.6-terra,qwen3.8,minimax-m3,glm-5.3,claude-opus-5.5")
    a = ap.parse_args()
    blocks = [b if b.is_absolute() else (REPO / b) for b in a.blocks]
    rows = load(blocks)
    if a.executors:
        keep = [e.strip() for e in a.executors.split(",") if e.strip()]
        rows = [r for r in rows if any(k in r["model"] for k in keep)]
    text = report(rows)
    if a.md:
        a.md.write_text(text)
    if a.json:
        a.json.write_text(json.dumps([{k: v for k, v in r.items() if k != "verdicts"} for r in rows], indent=1))
    print(text)


if __name__ == "__main__":
    main()
