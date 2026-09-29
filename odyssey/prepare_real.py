"""Turn the REAL tasks of the v1 set into run.py tasks, with their state checkers.

REAL (github.com/agi-inc/agisdk) hosts deterministic replicas of real sites
(Omnizon ~ Amazon, GoMail ~ Gmail, ...). Each task has a Python checker that
reads the site's final state and prints SUCCESS or FAILURE. This script

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


def task_id(real_id: str, version: str) -> str:
    # Odysseys ids are 40-hex and results are filed under their first 12 chars;
    # "real-omnizon-13"[:12] would collide across every Omnizon task.
    return hashlib.sha1(f"real/{version}/{real_id}".encode()).hexdigest()


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
        versions.add(version)
        scripts = [e["script"] for e in t["evals"]]
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
                     "site": t["domain"], "eval_scripts": scripts},
            # One item: the site's final state passes REAL's checker. Kept in the
            # rubric shape so the judges and report treat it like any other task.
            "rubrics": {"R1": {"requirement": t["instruction"],
                               "verification": "REAL state checker "
                                               + ", ".join(scripts)
                                               + " prints SUCCESS on the site's final state."}},
        })

    (args.evals_out / "NOTICE").write_text(
        NOTICE.format(eval_dir=EVAL_DIR.format(version="/".join(sorted(versions))), ref=args.ref),
        encoding="utf-8")
    args.tasks_out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(tasks)} REAL tasks -> {args.tasks_out}; checkers -> {args.evals_out}")


if __name__ == "__main__":
    main()
