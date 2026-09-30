"""Turn the REAL tasks of the v1 set into run.py tasks, with their state checkers.

REAL (github.com/agi-inc/agisdk) hosts deterministic replicas of real sites
(Omnizon ~ Amazon, GoMail ~ Gmail, ...). A task is checked one of two ways, and
some tasks use both:

  - a Python checker vendored from agisdk, which reads the site's final state
    and prints SUCCESS or FAILURE;
  - checks written into the manifest itself: a `jmespath` query on the final
    state compared with an expected value, or an `llm_boolean` rubric put to the
    judge about the agent's own answer.

This script

  - reads the REAL entries of benchmark/v1_tasks.json,
  - downloads their checkers from agisdk at a pinned commit into odyssey/real_evals/,
  - writes odyssey/tasks_real.json, which run.py loads next to tasks.json.

    python odyssey/prepare_real.py
    python odyssey/prepare_real.py --ref <agisdk commit or tag>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
EVAL_DIR = "src/agisdk/REAL/browsergym/webclones/{version}/eval_scripts"
RAW = "https://raw.githubusercontent.com/agi-inc/agisdk/{ref}/{path}"
NOTICE = """The eval_*.py files in this directory are copied unchanged from
https://github.com/agi-inc/agisdk ({eval_dir}, commit {ref}),
licensed under the Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0
"""


# The declarative check types judge_real() implements. A manifest asking for
# anything else is refused here rather than silently scored as a pass.
CHECK_TYPES = ("jmespath", "llm_boolean")


def task_id(real_id: str, version: str) -> str:
    # Odysseys ids are 40-hex and results are filed under their first 12 chars;
    # "real-omnizon-13"[:12] would collide across every Omnizon task.
    return hashlib.sha1(f"real/{version}/{real_id}".encode()).hexdigest()


def verification(scripts: list[str], checks: list[dict]) -> str:
    """How this task is decided, in the rubric's own words."""
    parts = []
    if scripts:
        parts.append("REAL state checker " + ", ".join(scripts)
                     + " prints SUCCESS on the site's final state")
    for check in checks:
        if check["type"] == "jmespath":
            parts.append(f"the site's final state has {check['query']} == "
                         f"{json.dumps(check['expected_value'], ensure_ascii=False)}")
        else:
            parts.append(f"the judge answers {json.dumps(check['expected_value'])} to: "
                         f"{check['rubric']}")
    return "; and ".join(parts) + "."


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=REPO / "benchmark" / "v1_tasks.json")
    ap.add_argument("--ref", default="97a245dcbccd3e1cf4d5ee00d5b1707942258518",
                    help="agisdk commit the checkers are pinned to")
    ap.add_argument("--evals-out", type=Path, default=HERE / "real_evals")
    ap.add_argument("--tasks-out", type=Path, default=HERE / "tasks_real.json")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    real = [t for t in manifest["tasks"] if t["source"] == "REAL"]
    args.evals_out.mkdir(parents=True, exist_ok=True)

    tasks, versions = [], set()
    for t in real:
        version = t["version"]
        scripts = [e["script"] for e in t["evals"] if e.get("script")]
        # Only a version we actually vendored a script from belongs in the
        # NOTICE; the v1 FlyUnified tasks are checked from the manifest alone.
        if scripts:
            versions.add(version)
        checks = [e for e in t["evals"] if not e.get("script")]
        if not scripts and not checks:
            raise SystemExit(f"{t['source_id']} has no evals at all")
        for check in checks:
            if check.get("type") not in CHECK_TYPES:
                raise SystemExit(
                    f"{t['source_id']} wants check type {check.get('type')!r}, which "
                    f"judge_real() does not implement; known: {CHECK_TYPES}")
            if check["type"] == "jmespath" and not check.get("query"):
                raise SystemExit(f"{t['source_id']} has a jmespath check with no query")
            if check["type"] == "llm_boolean" and not check.get("rubric"):
                raise SystemExit(f"{t['source_id']} has an llm_boolean check with no rubric")
        for script in scripts:
            dest = args.evals_out / script
            if not dest.is_file():
                url = RAW.format(ref=args.ref, path=f"{EVAL_DIR.format(version=version)}/{script}")
                with urllib.request.urlopen(url, timeout=30) as resp:
                    dest.write_bytes(resp.read())
        tasks.append({
            "task_id": task_id(t["source_id"], version),
            "confirmed_task": t["instruction"],
            "level": t["level"],
            "domain": t["domain"],
            "scenario": t["scenario"],
            "real": {"id": t["source_id"], "version": version, "url": t["url"].rstrip("/"),
                     "site": t["domain"], "eval_scripts": scripts, "checks": checks},
            # One item: the site's final state passes REAL's checks. Kept in the
            # rubric shape so the judges and report treat it like any other task.
            "rubrics": {"R1": {"requirement": t["instruction"],
                               "verification": verification(scripts, checks)}},
        })

    (args.evals_out / "NOTICE").write_text(
        NOTICE.format(eval_dir=EVAL_DIR.format(version="/".join(sorted(versions))), ref=args.ref),
        encoding="utf-8")
    args.tasks_out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    scripted = sum(1 for t in tasks if t["real"]["eval_scripts"])
    declared = sum(1 for t in tasks if t["real"]["checks"])
    print(f"{len(tasks)} REAL tasks -> {args.tasks_out} "
          f"({scripted} with vendored checkers, {declared} with manifest checks); "
          f"checkers -> {args.evals_out}")


if __name__ == "__main__":
    main()
