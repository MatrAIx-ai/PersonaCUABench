"""Break each REAL task into the requirements its own checker actually tests.

A REAL task arrives as one instruction and one SUCCESS/FAILURE checker, so
prepare_real.py gives it a single rubric item. That is fine for `met` -- the
checker is the authority and stays untouched -- but it collapses the subjective
half: "which parts of this did the person raise, and did the agent take them
up" has nothing to range over, so half the benchmark has no intent data.

The requirements are recoverable. The two FlyUnified tasks name theirs in the
manifest (`correct departure city`, `correct fare type`...). The other 34 hide
theirs in the vendored checker, which is readable: eval_dashdish_3.py ANDs
"a cart item named pizza" with "total under $30".

This reads both, once, and writes them into tasks_real.json as data that can be
reviewed and corrected by hand. `met` is unaffected.

    python src/derive_real_requirements.py --dry-run   # print, change nothing
    python src/derive_real_requirements.py             # write tasks_real.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as pipeline  # noqa: E402

TASKS_REAL = HERE / "tasks_real.json"
EVALS = HERE / "real_evals"

PROMPT = """\
A benchmark task gives a web agent one instruction, and a checker decides
afterwards whether the work passed. Your job is to list the separate things the
task actually requires, so that each can be judged independently.

Use the checker as the authority on what counts: it is the thing that will
decide pass or fail. The instruction tells you what the user was told to ask
for. Where they disagree, follow the checker.

Rules:
- One requirement per line, each a single checkable thing. Two to six of them.
- Split conjunctions: "order a pizza and keep it under $30" is two.
- Include constraints that are easy to miss: a price cap, a star rating, a
  date, a named passenger, a "cheapest" or "before noon" qualifier.
- Do not include the site name, or the mechanics of using the site.
- Do not invent anything neither the instruction nor the checker asks for.

Phrase each one as **the thing the person wants**, in their terms, not as the
checker's test. Another judge will hold these up against what the person
actually said, so implementation detail makes them useless:

    good:  The order includes a pizza.
    bad:   A cart item name contains "pizza" (case-insensitive).
    good:  The order costs less than $30.
    bad:   checkoutDetails.charges.totalAmount is under 30.

Use the checker to decide *what* is required and the instruction to decide
*how to say it*.

## The instruction the user was given
{instruction}

## The checker that decides pass or fail
{checker}

Return ONLY a JSON object:

{{"requirements": ["...", "..."]}}
"""


def checker_text(task: dict) -> str:
    """What decides this task: the vendored script, or the manifest's checks."""
    real = task["real"]
    parts = []
    for script in real.get("eval_scripts") or []:
        path = EVALS / script
        if path.is_file():
            parts.append(f"# {script}\n{path.read_text(encoding='utf-8')}")
    for check in real.get("checks") or []:
        if check.get("type") == "jmespath":
            parts.append(f"- {check.get('description') or check['query']}: "
                         f"must equal {json.dumps(check.get('expected_value'))}")
        elif check.get("type") == "llm_boolean":
            parts.append(f"- a judge must answer "
                         f"{json.dumps(check.get('expected_value'))} to: {check['rubric']}")
    return "\n\n".join(parts) or "(no checker available)"


def derive(task: dict, model: str, provider: str) -> list[str]:
    client, resolved = pipeline._client(model, provider)
    text = PROMPT.format(instruction=task["confirmed_task"],
                         checker=checker_text(task)[:12000])
    parsed, err = pipeline._ask_judge(client, pipeline.Meter(), "derive_requirements",
                                      provider=resolved, model=model, text=text,
                                      budget=2000)
    if not parsed or not isinstance(parsed.get("requirements"), list):
        raise SystemExit(f"{task['real']['id']}: no requirements came back ({err})")
    out = [str(r).strip() for r in parsed["requirements"] if str(r).strip()]
    if not 1 <= len(out) <= 8:
        raise SystemExit(f"{task['real']['id']}: {len(out)} requirements, expected 2-6")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="terra")
    ap.add_argument("--provider", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="one REAL id, for checking the prompt")
    args = ap.parse_args()
    pipeline.load_dotenv()
    model, provider = pipeline.model_registry.resolve(args.model, args.provider)

    tasks = json.loads(TASKS_REAL.read_text(encoding="utf-8"))
    todo = [t for t in tasks
            if not args.only or t["real"]["id"] == args.only]
    for i, task in enumerate(todo, 1):
        reqs = derive(task, model, provider)
        print(f"\n[{i}/{len(todo)}] {task['real']['id']}  ({len(reqs)})")
        print(f"    {task['confirmed_task'][:110]}")
        for r in reqs:
            print(f"      - {r}")
        task["real"]["requirements"] = reqs
        task["real"]["requirements_source"] = f"derived from instruction + checker by {model}"

    if args.dry_run or args.only:
        print("\n(dry run: tasks_real.json not written)")
        return
    TASKS_REAL.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"\nwrote {len(todo)} tasks -> {TASKS_REAL.relative_to(HERE.parent)}")
    print("Review them by hand; they are data now, and corrections stick.")


if __name__ == "__main__":
    main()
