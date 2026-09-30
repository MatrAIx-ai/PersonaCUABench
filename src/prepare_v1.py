"""Turn benchmark/v1_tasks.json into the task suites the runner reads.

The v1 manifest is the single source of truth for the full experiment: 75 tasks
from three sources that need three different runtimes.

    Odysseys   38  live web,     rubrics judged by an LLM
    REAL       36  sandbox site, its own checkers on the site's final state

Anything from a source this repo has no runtime for is reported as not prepared
rather than silently dropped. As of the 2026-09-29 manifest there is none: the
four ClawBench entries were replaced with one Odysseys and two REAL tasks and
now sit in the manifest's `dropped` list with their reasons.

    python src/prepare_v1.py            # rewrite the suites
    python src/prepare_v1.py --check    # verify they match the manifest
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = REPO / "benchmark" / "v1_tasks.json"
SUITES = HERE / "task_suites"
REAL_TASKS = HERE / "tasks_real.json"

# Which manifest source becomes which suite. ClawBench is absent on purpose.
SOURCES = {"Odysseys": "odysseys", "REAL": "real"}
# The manifest check types judge_real() implements, mirrored from prepare_real.py
# so a --check run fails on an unknown one even without the network.
CHECK_TYPES = ("jmespath", "llm_boolean")
# Carried through so a report can group by them; the runner ignores them.
METADATA = ("domain", "scenario", "level", "action", "platform", "source",
            "source_id", "title")


class PrepareError(RuntimeError):
    """Something in the manifest cannot be turned into a runnable task."""


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        raise PrepareError(
            f"{MANIFEST} is missing. It lives on the main line; restore it with\n"
            f"  git checkout origin/main -- benchmark/v1_tasks.json")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for field in ("version", "tasks"):
        if field not in manifest:
            raise PrepareError(f"{MANIFEST} has no {field!r}")
    return manifest


def odysseys_task(entry: dict) -> dict:
    """One live-web task, rubrics carried over verbatim."""
    task_id = entry.get("source_id") or ""
    if len(task_id) != 40:
        raise PrepareError(f"Odysseys source_id is not a 40-hex id: {task_id!r}")
    rubrics = entry.get("rubrics")
    if not isinstance(rubrics, dict) or not rubrics:
        raise PrepareError(f"{task_id[:12]} has no rubrics")
    for rid, rubric in rubrics.items():
        missing = [f for f in ("requirement", "verification")
                   if not str((rubric or {}).get(f) or "").strip()]
        if missing:
            raise PrepareError(f"{task_id[:12]} rubric {rid} is missing {missing}")
    instruction = str(entry.get("instruction") or "").strip()
    if not instruction:
        raise PrepareError(f"{task_id[:12]} has no instruction")
    return {"task_id": task_id, "confirmed_task": instruction,
            "rubrics": rubrics,
            **{k: entry[k] for k in METADATA if k in entry}}


def real_tasks() -> list[dict]:
    """The REAL tasks as prepare_real.py wrote them, checked against the manifest."""
    if not REAL_TASKS.is_file():
        raise PrepareError(
            f"{REAL_TASKS} is missing. Build it and download the checkers with\n"
            f"  python src/prepare_real.py")
    tasks = json.loads(REAL_TASKS.read_text(encoding="utf-8"))
    for task in tasks:
        real = task.get("real") or {}
        scripts = real.get("eval_scripts") or []
        checks = real.get("checks") or []
        # A REAL task with neither would be scored by nothing and would look
        # like a pass, so it is refused here.
        if not scripts and not checks:
            raise PrepareError(
                f"{task.get('task_id', '?')[:12]} has neither an eval script nor a "
                f"manifest check; rerun python src/prepare_real.py")
        for check in checks:
            if check.get("type") not in CHECK_TYPES:
                raise PrepareError(
                    f"{task.get('task_id', '?')[:12]} has check type "
                    f"{check.get('type')!r}, which judge_real() cannot run")
        for script in scripts:
            if not (HERE / "real_evals" / script).is_file():
                raise PrepareError(
                    f"{script} is missing from src/real_evals; run "
                    f"python src/prepare_real.py")
        if not str(real.get("url") or "").startswith("http"):
            raise PrepareError(f"{task.get('task_id', '?')[:12]} has no sandbox url")
    return tasks


def build() -> tuple[dict[str, list[dict]], list[dict]]:
    """(suite id -> tasks, tasks we cannot run)."""
    manifest = load_manifest()
    entries = manifest["tasks"]
    suites: dict[str, list[dict]] = {name: [] for name in SOURCES.values()}
    unrunnable: list[dict] = []

    for entry in entries:
        source = entry.get("source")
        if source == "Odysseys":
            suites["odysseys"].append(odysseys_task(entry))
        elif source == "REAL":
            continue                      # taken from tasks_real.json below
        else:
            unrunnable.append(entry)      # ClawBench, and anything new

    suites["real"] = real_tasks()
    prepared_real = {t["real"]["id"] for t in suites["real"]}
    manifest_real = {e["source_id"] for e in entries if e.get("source") == "REAL"}
    if prepared_real != manifest_real:
        raise PrepareError(
            "tasks_real.json does not match the manifest; rerun "
            "python src/prepare_real.py. "
            f"missing={sorted(manifest_real - prepared_real)} "
            f"extra={sorted(prepared_real - manifest_real)}")

    # A level is required by the router and by every report that splits on it.
    for suite_id, tasks in suites.items():
        for task in tasks:
            if not str(task.get("level") or "").strip():
                raise PrepareError(
                    f"{suite_id}/{task['task_id'][:12]} has no level; the manifest "
                    f"leaves it null and a report cannot group without it")
    seen: dict[str, str] = {}
    for suite_id, tasks in suites.items():
        for task in tasks:
            if task["task_id"] in seen:
                raise PrepareError(
                    f"task_id {task['task_id'][:12]} is in both "
                    f"{seen[task['task_id']]} and {suite_id}")
            seen[task["task_id"]] = suite_id
    return suites, unrunnable


def write(suites: dict[str, list[dict]]) -> list[Path]:
    written = []
    for suite_id, tasks in suites.items():
        path = SUITES / suite_id / "000-core.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="fail if the suites on disk differ from the manifest")
    args = ap.parse_args()

    try:
        suites, unrunnable = build()
    except PrepareError as exc:
        raise SystemExit(f"v1 preparation failed: {exc}")

    if args.check:
        for suite_id, tasks in suites.items():
            path = SUITES / suite_id / "000-core.json"
            if not path.is_file():
                raise SystemExit(f"{path} is missing; run python src/prepare_v1.py")
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            if on_disk != tasks:
                raise SystemExit(
                    f"{path} is stale: it differs from benchmark/v1_tasks.json. "
                    f"Regenerate it with python src/prepare_v1.py")
        print(f"suites match the manifest: "
              + ", ".join(f"{k} {len(v)}" for k, v in sorted(suites.items())))
    else:
        for path in write(suites):
            print(f"wrote {path.relative_to(REPO)} "
                  f"({len(json.loads(path.read_text(encoding='utf-8')))} tasks)")

    rubrics = sum(len(t["rubrics"]) for t in suites["odysseys"])
    print(f"odysseys: {len(suites['odysseys'])} tasks / {rubrics} rubric items")
    scripts = sum(len(t["real"]["eval_scripts"]) for t in suites["real"])
    checks = sum(len(t["real"].get("checks") or []) for t in suites["real"])
    print(f"real:     {len(suites['real'])} tasks / {scripts} state checkers "
          f"/ {checks} manifest checks")
    if unrunnable:
        print(f"\nNOT PREPARED -- {len(unrunnable)} task(s) this repo cannot run:")
        for entry in unrunnable:
            print(f"  {entry.get('source')} {entry.get('source_id')}: "
                  f"{(entry.get('title') or '')[:60]}"
                  f"  [{entry.get('requires') or entry.get('platform')}]")
        print("  They stay in benchmark/v1_tasks.json; nothing here pretends to score them.")


if __name__ == "__main__":
    main()
