"""The simulated person's own satisfaction, asked in character.

experience_judge.py has an outside judge rate how well the person was served.
This asks the person. The simulator LLM is rebuilt with the exact chat it had
during the run -- its profile, the need it was given, its opening message and
every answer it gave the assistant -- then told the assistant has finished and
asked how it feels. Two moments:

  handoff   what the person has seen when the assistant hands back: the final
            reply and the tabs left open
  verified  REAL only: the same, plus what actually changed on the site, from
            the site's own records (real_state.json) -- what the person finds
            on checking. Odysseys answers can only be checked by reading the
            pages, which the record does not keep, so they get no verified turn.

Written next to each record as simulator_satisfaction.json; result.json is
never modified. Only the latest scored record of each cell is rated.

    python src/simulator_satisfaction.py --results src/results/s1/gpt-6-astra_real
    python src/simulator_satisfaction.py --results src/results/s1 --workers 8
    python src/simulator_satisfaction.py --results ... --print-prompt   # no calls
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as pipeline  # noqa: E402  (src/run.py: clients, retry, json extraction)

SCHEMA = "simulator-satisfaction.v1"
OUT_NAME = "simulator_satisfaction.json"
PROMPT = pipeline.prompt("simulator_satisfaction")
PROMPT_SHA = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()
RULES_SHA = hashlib.sha256(pipeline.PERSONA_USER_RULES.encode("utf-8")).hexdigest()
BELIEFS = {"yes", "no", "unsure"}
DIFF_CHARS = 12000


def latest_scored(results: Path) -> list[Path]:
    """One result.json per cell: the latest run that carries a score."""
    latest: dict[tuple, tuple[str, Path]] = {}
    for path in results.rglob("result.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        score = (record.get("judgement") or {}).get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue
        agent = ((record.get("run_config") or {}).get("agent") or {}).get("model")
        key = (agent, record.get("suite_id"), record.get("task_id"), record.get("persona"))
        stamp = path.parent.name.rsplit("__", 1)[-1]
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, path)
    return sorted(path for _, path in latest.values())


def simulator_chat(record: dict) -> list[dict]:
    """The persona LLM's chat as PersonaUser held it when the run ended."""
    run_ = record["run"]
    task, _ = pipeline.task_for_record(record)
    rules = pipeline.PERSONA_USER_RULES.format(goal=task["confirmed_task"])
    if record["persona"] == "none":
        system = "You are a person.\n\n" + rules
        ask = "What do you ask the assistant?"
    else:
        snapshot = (run_.get("user") or {}).get("persona_profile") or {}
        if snapshot.get("matched_pair"):
            raise ValueError("matched-pair personas use another rule set; not supported")
        narrative = str(snapshot.get("profile_narrative") or "").strip()
        if not narrative:
            raise ValueError("record has no persona profile snapshot")
        # persona.persona_system_prompt(), built from the run's frozen profile.
        system = (
            "You are role-playing a person with the following profile. Stay fully in "
            "character: let these traits shape your choices and language naturally, "
            "the way a real person with this profile would behave. Do not announce "
            "that you are role-playing.\n\n"
            f"# Your profile\n\n{narrative}"
            "\n\n# Right now\n\n" + rules)
        ask = "Write the message you send the assistant. Only the message itself."
    turns = run_.get("conversation") or []
    if not turns or turns[0].get("role") != "user":
        raise ValueError("conversation does not open with the person's message")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": ask},
                {"role": "assistant", "content": turns[0]["text"]}]
    for question, answer in zip(turns[1::2], turns[2::2]):
        if question.get("role") != "assistant" or answer.get("role") != "user":
            raise ValueError("conversation turns are out of order")
        messages += [
            {"role": "user", "content": f"The assistant asks you: {question['text']}\n\nReply as yourself."},
            {"role": "assistant", "content": answer["text"]}]
    return messages


def _nothing_changed(value) -> bool:
    if isinstance(value, dict):
        return all(_nothing_changed(v) for v in value.values())
    if isinstance(value, list):
        return all(_nothing_changed(v) for v in value)
    return value in (None, "", 0, False)


def site_outcome(record: dict, path: Path) -> str | None:
    """What the person finds on checking the REAL site, or None if unknown."""
    real = (record.get("task_snapshot") or {}).get("real")
    if not real:
        return None
    state_file = path.parent / "real_state.json"
    if not state_file.is_file():
        return None
    state = json.loads(state_file.read_text(encoding="utf-8"))
    # Sites report their change log under one of two names.
    differences = state.get("differences", state.get("initialfinaldiff"))
    site = real.get("site") or "the site"
    if differences is None:
        return None
    if _nothing_changed(differences):
        return (f"\nLater you check for yourself on {site}. According to the site's own "
                f"records, nothing was changed during this session: no booking, message, "
                f"submission or other change was saved.\n")
    shown = json.dumps(differences, ensure_ascii=False, separators=(",", ":"))
    if len(shown) > DIFF_CHARS:
        shown = shown[:DIFF_CHARS] + "\n... (truncated)"
    return (f"\nLater you check for yourself on {site}. According to the site's own "
            f"records, these are all the changes that were actually made during this "
            f"session:\n{shown}\n")


def rating_turn(record: dict, outcome: str | None) -> str:
    run_ = record["run"]
    tabs = "\n".join(f"- {t.get('title') or '(untitled)'} ({t.get('url')})"
                     for t in run_.get("open_tabs") or []) or "(none)"
    return PROMPT.format(
        answer=run_.get("answer") or "(the assistant sent no final reply)",
        tabs=tabs,
        outcome=outcome or "",
        basis=("everything you have seen, including what you found when you checked"
               if outcome else "everything you have seen so far"))


def valid(parsed: dict | None) -> dict | None:
    if not isinstance(parsed, dict):
        return None
    score = parsed.get("satisfaction")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 1 <= score <= 5:
        return None
    belief = str(parsed.get("believes_done", "")).strip().lower()
    if belief not in BELIEFS:
        return None
    return {"satisfaction": int(score), "believes_done": belief,
            "why": str(parsed.get("why") or "")}


def ask(messages: list[dict], model: str, provider: str, temperature: float) -> dict:
    """One in-character rating, retried while the reply is unusable."""
    client, resolved = pipeline._client(model, provider)
    meter = pipeline.Meter()
    last = ""
    for attempt in range(pipeline.MAX_RETRIES):
        try:
            resp, _ = pipeline.metered(client, meter, "simulator_satisfaction",
                                       provider=resolved, model=model,
                                       messages=messages, temperature=temperature)
            parsed = valid(pipeline.extract_json(resp.choices[0].message.content or ""))
        except (NameError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"simulator satisfaction call is broken: {exc}") from exc
        except Exception as exc:  # provider weather: retried
            parsed, last = None, f"{type(exc).__name__}: {exc}"
        else:
            last = "unusable reply"
        if parsed:
            return {**parsed, "accounting": meter.totals()}
        print(f"    attempt {attempt + 1}/{pipeline.MAX_RETRIES}: {last}", flush=True)
    return {"error": last, "accounting": meter.totals()}


def _usable(rating: dict | None) -> bool:
    return isinstance(rating, dict) and not rating.get("error") and "satisfaction" in rating


def rate(path: Path, model: str, provider: str, redo: bool) -> str:
    out = path.parent / OUT_NAME
    record = json.loads(path.read_text(encoding="utf-8"))
    outcome = site_outcome(record, path)
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() and not redo else {}
    # Each moment is asked only while it lacks a usable answer, so a resume
    # never re-asks a rating it already has.
    need_handoff = not _usable(done.get("handoff"))
    need_verified = outcome is not None and not _usable(done.get("verified"))
    if not need_handoff and not need_verified:
        return "skip"
    chat = simulator_chat(record)
    temperature = float(((record["run"].get("user") or {}).get("temperature")) or 1.0)
    handoff = (ask(chat + [{"role": "user", "content": rating_turn(record, None)}],
                   model, provider, temperature) if need_handoff else done["handoff"])
    verified = (ask(chat + [{"role": "user", "content": rating_turn(record, outcome)}],
                    model, provider, temperature) if need_verified
                else done.get("verified") if outcome is not None else None)
    recorded_rules = (((record.get("run_config") or {}).get("prompt_sha256") or {})
                      .get("persona_user"))
    payload = {
        "schema_version": SCHEMA,
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "temperature": temperature,
        "prompt_sha256": PROMPT_SHA,
        "persona_rules_sha256": RULES_SHA,
        "persona_rules_match_run": recorded_rules == RULES_SHA if recorded_rules else None,
        "task_score": record["judgement"]["score"],
        "handoff": handoff,
        "verified": verified,
    }
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(out)
    return "error" if handoff.get("error") or (verified or {}).get("error") else "ok"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", default=str(HERE / "results"))
    ap.add_argument("--model", default="gpt-5.6-terra",
                    help="the simulator model; the runs' persona user is gpt-5.6-terra")
    ap.add_argument("--provider", default="")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--print-prompt", action="store_true",
                    help="print one cell's messages (both moments) and exit")
    args = ap.parse_args()

    pipeline.load_dotenv()
    paths = latest_scored(Path(args.results))
    if args.print_prompt:
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["persona"] != "none" and site_outcome(record, path):
                chat = simulator_chat(record)
                print(f"# {path}\n")
                for m in chat + [{"role": "user", "content": rating_turn(record, site_outcome(record, path))}]:
                    print(f"[{m['role']}]\n{m['content']}\n")
                return
        sys.exit("no persona REAL cell found to print")
    model, provider = pipeline.model_registry.resolve(args.model, args.provider)
    print(f"{len(paths)} cells", flush=True)

    def one(path: Path) -> str:
        try:
            return rate(path, model, provider, args.redo)
        except ValueError as exc:
            print(f"  skip {path.parent.name}: {exc}", flush=True)
            return "invalid"

    with ThreadPoolExecutor(args.workers) as ex:
        outcomes = list(ex.map(one, paths))
    counts = {k: outcomes.count(k) for k in sorted(set(outcomes))}
    print("done", counts)


if __name__ == "__main__":
    main()
