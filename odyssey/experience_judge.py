"""Judge a finished run from the PERSON's side, not just the rubric's.

The rubric judge in run.py asks "was the requirement satisfied". That is the
task's view. This one asks what the person who actually spoke would say: they
described their situation in their own words, left things out, and cannot be
held to requirements they never voiced -- but they can be failed by an answer
they cannot read, cannot act on, or that ignores what they did say.

Two judges (default GPT-5.5 and Claude Opus 4.8) score the same prompt
independently. Their scores are never averaged: both are kept, and we report
how often they land within one point, the way the MatrAIx paper does.

    python odyssey/experience_judge.py                 # every result missing one
    python odyssey/experience_judge.py --redo          # rescore everything
    python odyssey/experience_judge.py --results odyssey/results/_v1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as odyssey  # noqa: E402  (odyssey/run.py: clients, retry, json extraction)

DIMENSIONS = ("P1_asked_for", "P2_readable_for_them", "P3_actionable",
              "P4_gap_handling", "P5_overall")

PROMPT = odyssey.prompt("experience_judge")


def build_prompt(record: dict) -> str:
    run_ = record["run"]
    task, _ = odyssey.task_for_record(record)
    persona = record["persona"]
    if persona == "none":
        profile = ("Control arm: no persona. This person sent the expert brief "
                   "verbatim, so treat them as a demanding expert who asked for "
                   "every item in it.")
    else:
        # Prefer the immutable profile used by this exact run. Legacy results
        # predate snapshots and fall back to the local YAML for compatibility.
        snapshot = ((run_.get("user") or {}).get("persona_profile") or {})
        profile = str(snapshot.get("profile_narrative") or "").strip()
        if not profile:
            # The profile alone -- persona_system_prompt() wraps it in role-play
            # instructions, which would tell the judge to become this person.
            doc = odyssey.persona_lib.load_persona(HERE / "personas" / f"{persona}.yaml")
            profile = "\n\n".join(odyssey.persona_lib.build_dimension_narrative(doc))
    conversation = "\n".join(
        f"{'PERSON' if t['role'] == 'user' else 'ASSISTANT'}: {t['text']}"
        for t in run_.get("conversation") or []) or "(none)"
    actions = "\n".join(
        f"{t['step']}. {t['tool']}({json.dumps(t['args'], ensure_ascii=False)[:200]}) -> "
        f"{t['result_preview'][:160]}" for t in run_["trajectory"]) or "(no actions)"
    return PROMPT.format(
        persona=profile, task=task["confirmed_task"], conversation=conversation,
        actions=actions, answer=run_["answer"] or "(the assistant produced no answer)",
        tabs=json.dumps(run_["open_tabs"], indent=2))


def score_once(prompt: str, model: str, provider: str = "") -> dict:
    """One judge's verdict, retried while it returns nothing parseable."""
    client, resolved_provider = odyssey._client(model, provider)
    for attempt in range(3):
        try:
            resp = odyssey._create_with_retry(
                client, model=model, messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=4000)
            parsed = odyssey.extract_json(resp.choices[0].message.content or "")
        except Exception as exc:
            parsed, last = None, f"{type(exc).__name__}: {exc}"
        else:
            last = "unparseable judge output"
        if parsed:
            return {"model": model, "provider": resolved_provider,
                    "backend": odyssey._provider_backend(resolved_provider), **parsed}
        print(f"    [{model}] attempt {attempt + 1}/3: {last}", flush=True)
    return {"model": model, "provider": resolved_provider,
            "backend": odyssey._provider_backend(resolved_provider), "error": last}


def valid_score(value) -> int | None:
    """A dimension's score as an int 1-5, or None for 'n/a' and anything odd."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if 1 <= value <= 5 else None


def agreement(a: dict, b: dict) -> dict:
    """Per-dimension gap between the two judges; never an average of them."""
    out = {}
    for dim in DIMENSIONS:
        sa = valid_score((a.get(dim) or {}).get("score"))
        sb = valid_score((b.get(dim) or {}).get("score"))
        out[dim] = None if sa is None or sb is None else {
            "delta": sa - sb, "within_one": abs(sa - sb) <= 1}
    return out


def experience_complete(value: object) -> bool:
    """Only successful dual-judge output is resumable as complete."""
    if not isinstance(value, dict):
        return False
    for slot in ("a", "b"):
        judge = value.get(slot)
        if not isinstance(judge, dict) or judge.get("error"):
            return False
        if any(not isinstance(judge.get(dimension), dict) for dimension in DIMENSIONS):
            return False
    return True


def _write_record(path: Path, record: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--judge-a", default="gpt-5.5")
    ap.add_argument("--judge-b", default="anthropic/claude-opus-4.8")
    ap.add_argument("--redo", action="store_true", help="rescore results that already have one")
    ap.add_argument("--print-prompt", action="store_true",
                    help="print the prompt for the first result and exit, no API calls")
    args = ap.parse_args()
    odyssey.load_dotenv()

    paths = sorted(Path(args.results).rglob("result.json"))
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not (record.get("run") or {}).get("answer"):
            continue                      # nothing to judge
        if args.print_prompt:
            print(build_prompt(record))
            return
        if experience_complete(record.get("experience")) and not args.redo:
            continue
        print(f"{record['task_id'][:12]} {record['persona']}", flush=True)
        prompt = build_prompt(record)
        a = score_once(prompt, args.judge_a)
        b = score_once(prompt, args.judge_b)
        profile_snapshot = (((record.get("run") or {}).get("user") or {})
                            .get("persona_profile") or {})
        profile_integrity = (
            "frozen_snapshot"
            if profile_snapshot.get("profile_narrative")
            else "unverified_legacy"
        )
        _, task_integrity = odyssey.task_for_record(record)
        record["experience"] = {
            "a": a,
            "b": b,
            "agreement": agreement(a, b),
            "profile_integrity": profile_integrity,
            "task_integrity": task_integrity,
        }
        _write_record(path, record)
        for dim in DIMENSIONS:
            print(f"  {dim:22} {(a.get(dim) or {}).get('score')!s:>4} "
                  f"{(b.get(dim) or {}).get('score')!s:>4}")


if __name__ == "__main__":
    main()
