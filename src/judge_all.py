"""Re-judge every saved run with both judges: rubric (task completion) and
experience (satisfaction). Resumable: a record already judged by the current
models is skipped, so re-running the same command picks up where it stopped.

    python src/judge_all.py                        # every result under src/results
    python src/judge_all.py src/results/s1 --workers 8
    python src/judge_all.py --redo                 # re-judge even what is judged

Each record carries the task it ran, so judging never depends on today's task
files: a result whose task has since changed is refused rather than judged
against the wrong rubric.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as pipeline  # noqa: E402
import experience_judge as exp  # noqa: E402

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def needs(record: dict, args) -> tuple[bool, bool]:
    j = record.get("judgement") or {}
    # A REAL task is scored by its own checkers, so a different rubric-judge
    # model is no reason to redo it; only a missing score is.
    by_checker = str(j.get("judge_model") or "").startswith("real-state-checker")
    need_rubric = args.redo or j.get("score") is None or (
        not by_checker and j.get("judge_model") != args.judge_model)
    e = record.get("experience") or {}
    a_ok = "error" not in (e.get("a") or {"error": 1}) and (e.get("a") or {}).get("model") == args.judge_model
    b_ok = not args.judge_b or ("error" not in (e.get("b") or {"error": 1}))
    need_exp = args.redo or not (a_ok and b_ok)
    return need_rubric, need_exp


def load_real_state(path: Path, run_: dict) -> dict:
    """The run with its REAL state loaded back from the sidecar file.

    A run writes the state next to the record because it is a quarter of a
    megabyte; the checkers need the JSON itself, and its hash is verified so a
    swapped file cannot quietly change a score.
    """
    state = run_.get("real_state")
    if not isinstance(state, dict) or "file" not in state:
        return run_
    blob_path = path.parent / state["file"]
    if not blob_path.is_file():
        return {**run_, "real_state": None,
                "real_state_error": f"{state['file']} is missing next to the record"}
    blob = blob_path.read_text(encoding="utf-8")
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    if state.get("sha256") and digest != state["sha256"]:
        return {**run_, "real_state": None,
                "real_state_error": f"{state['file']} does not match its recorded sha256"}
    return {**run_, "real_state": json.loads(blob)}


def judge_one(path: Path, args) -> str:
    record = json.loads(path.read_text(encoding="utf-8"))
    run_ = record.get("run") or {}
    need_rubric, need_exp = needs(record, args)
    # The frozen snapshot, hash-checked: never today's task file.
    task, task_integrity = pipeline.task_for_record(record)

    if need_rubric and task.get("real"):
        # Scored by the task's own checkers; a model is called only for the few
        # tasks that carry an llm_boolean question about the agent's answer.
        meter = pipeline.Meter()
        record["judgement"] = pipeline.judge_real(
            task, load_real_state(path, run_), judge_model=args.judge_model,
            judge_provider=args.judge_provider, meter=meter)
        if meter.calls:
            record["judgement"]["accounting"] = meter.totals()
    elif need_rubric:
        old = record.get("judgement")
        if old and old.get("judge_model") != args.judge_model:
            record.setdefault("judgement_history", []).append(old)
        meter = pipeline.Meter()
        record["judgement"] = pipeline.judge_run(
            task, run_, judge_model=args.judge_model,
            judge_provider=args.judge_provider, meter=meter)
        record["judgement"]["accounting"] = meter.totals()
    if need_exp:
        prompt = exp.build_prompt(record)
        a = exp.score_once(prompt, args.judge_model, args.judge_provider)
        b = exp.score_once(prompt, args.judge_b, args.judge_b_provider) if args.judge_b else None
        record["experience"] = {"a": a, "b": b,
                                "agreement": exp.agreement(a, b) if b else None}
    record["task_integrity"] = task_integrity
    exp._write_record(path, record)      # atomic: a half-written record is a lost run

    j, a = record["judgement"], (record.get("experience") or {}).get("a") or {}
    p5 = (a.get("P5_overall") or {}).get("score")
    err = j.get("error") or a.get("error")
    return (f"{record['task_id'][:12]} {record['persona']:28} "
            f"rubric={j.get('met')}/{j.get('total')} comm={j.get('score_communicated')} "
            f"P5={p5}" + (f"  ERROR: {err}" if err else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", default=str(HERE / "results"))
    ap.add_argument("--judge-model", default="gpt-5.6-terra",
                    help="rubric judge and experience judge A (registry key or raw id)")
    ap.add_argument("--judge-provider", default="")
    ap.add_argument("--judge-b", default="anthropic/claude-opus-4.8",
                    help="experience judge B, a second vendor; empty = skip")
    ap.add_argument("--judge-b-provider", default="openrouter")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    pipeline.load_dotenv()
    args.judge_model, args.judge_provider = pipeline.model_registry.resolve(
        args.judge_model, args.judge_provider)
    # Same as experience_judge.py: a second vendor with no route on this machine
    # is skipped out loud rather than taking the whole pass down with it.
    if args.judge_b:
        try:
            pipeline.model_registry.resolve(args.judge_b, args.judge_b_provider)
        except SystemExit as exc:
            log(f"skipping experience judge B ({args.judge_b}): {exc}")
            args.judge_b = ""

    paths = []
    for p in sorted(Path(args.results).rglob("result.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        if (rec.get("run") or {}).get("answer") and any(needs(rec, args)):
            paths.append(p)
    log(f"START todo={len(paths)} judge={args.judge_model} judge_b={args.judge_b or '-'} "
        f"workers={args.workers}")
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(judge_one, p, args): p for p in paths}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                log(f"DONE [{i}/{len(paths)}] {f.result()}")
            except Exception as exc:
                log(f"DONE [{i}/{len(paths)}] FAIL {futs[f]}: {type(exc).__name__}: {exc}")
    log("FINISHED")


if __name__ == "__main__":
    main()
