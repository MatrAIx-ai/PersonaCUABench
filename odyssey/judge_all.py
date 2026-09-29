"""Re-judge every saved run with both judges: rubric (task completion) and
experience (satisfaction). Resumable: a record already judged by the current
models is skipped, so re-running the same command picks up where it stopped.

    python odyssey/judge_all.py                   # judge model = $AZURE_OPENAI_DEPLOYMENT
    python odyssey/judge_all.py --workers 8
    python odyssey/judge_all.py --judge-b anthropic/claude-opus-4.8   # needs OPENROUTER_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as odyssey  # noqa: E402
import experience_judge as exp  # noqa: E402

# Results from the first task set (the one pushed to GitHub) reference tasks
# that tasks.json no longer holds; tasks_v1.json keeps them judgeable.
_known = {t["task_id"] for t in odyssey.TASKS}
odyssey.TASKS.extend(t for t in json.loads((HERE / "tasks_v1.json").read_text(encoding="utf-8"))
                     if t["task_id"] not in _known)

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def needs(record: dict, args) -> tuple[bool, bool]:
    j = record.get("judgement") or {}
    need_rubric = args.redo or j.get("score") is None or j.get("judge_model") != args.judge_model
    e = record.get("experience") or {}
    a_ok = "error" not in (e.get("a") or {"error": 1}) and (e.get("a") or {}).get("model") == args.judge_model
    b_ok = not args.judge_b or ("error" not in (e.get("b") or {"error": 1}))
    need_exp = args.redo or not (a_ok and b_ok)
    return need_rubric, need_exp


def judge_one(path: Path, args) -> str:
    record = json.loads(path.read_text(encoding="utf-8"))
    run_ = record.get("run") or {}
    need_rubric, need_exp = needs(record, args)
    task = next(t for t in odyssey.TASKS if t["task_id"] == record["task_id"])

    if need_rubric and task.get("real"):
        # REAL tasks are scored by their deterministic state checkers, not an LLM.
        record["judgement"] = odyssey.judge_real(task, run_)
    elif need_rubric:
        old = record.get("judgement")
        if old and old.get("judge_model") != args.judge_model:
            record.setdefault("judgement_history", []).append(old)
        record["judgement"] = odyssey.judge_run(task, run_, judge_model=args.judge_model,
                                                judge_provider=args.judge_provider)
    if need_exp:
        prompt = exp.build_prompt(record)
        a = exp.score_once(prompt, args.judge_model, args.judge_provider)
        b = exp.score_once(prompt, args.judge_b, args.judge_b_provider) if args.judge_b else None
        record["experience"] = {"a": a, "b": b,
                                "agreement": exp.agreement(a, b) if b else None}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    j, a = record["judgement"], (record.get("experience") or {}).get("a") or {}
    p5 = (a.get("P5_overall") or {}).get("score")
    err = j.get("error") or a.get("error")
    return (f"{record['task_id'][:12]} {record['persona']:28} "
            f"rubric={j.get('met')}/{j.get('total')} comm={j.get('score_communicated')} "
            f"P5={p5}" + (f"  ERROR: {err}" if err else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--judge-model", default=None,
                    help="default: $AZURE_OPENAI_DEPLOYMENT")
    ap.add_argument("--judge-provider", default="azure")
    ap.add_argument("--judge-b", default="", help="second experience judge; empty = skip")
    ap.add_argument("--judge-b-provider", default="openrouter")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    odyssey.load_dotenv()
    args.judge_model = args.judge_model or os.environ["AZURE_OPENAI_DEPLOYMENT"]

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
