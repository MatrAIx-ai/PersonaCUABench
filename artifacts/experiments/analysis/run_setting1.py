#!/usr/bin/env python3
"""Run one Setting 1 replicate for the science-education tasks on unmodified main.

Follows the maintainers' Shopping main plan (codex/shopping-main-2026-09-26):
6 tasks x (4 personas + none) per execution backbone, persona simulator and judges on
gpt-5.6-terra, one fresh persistent Chrome profile per cell, results in a dated block:

    artifacts/experiments/<LA date>/science-education-main-setting1-<rep>/
        RUN_MANIFEST.json  RUN_MANIFEST.md  inputs/  results/  logs/

Every cell is invoked through odyssey/run.py exactly as run_grid.sh would, plus the
experiment-level model overrides; the runner logic, prompts, rubrics and judges are main's.

Two local choices, both recorded in the manifest:
- each cell's profile is seeded from one identical warm cookie template (five files,
  work/chrome-seed/) because Google walls automated search, and a wall counts against the
  8 of 32 rubric items that require a Google search. Same seed for every cell, so no
  persona or executor starts from a different browser state.
- order is task-major with the persona order rotated per task, and the executor order
  rotated per (task, persona) block, so no persona or executor always runs first or last.

Resumable: run.py's --skip-existing skips any cell that already has a scored result.

    python3 work/run_setting1.py --rep r1 --executors terra
    python3 work/run_setting1.py --rep r1 --executors terra,opus --tasks 3
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "repo"
ODY = REPO / "odyssey"
SEED = ROOT / "work" / "chrome-seed"
VENVPY = ROOT / "work" / "venvpy"
SEED_FILES = ["Local State", "Default/Cookies", "Default/Preferences",
              "Default/Secure Preferences", "Default/Network Persistent State"]

EXECUTORS = {  # short name -> (provider, model id); ids verified in the dated preflight
    "terra":   ("openrouter", "openai/gpt-5.6-terra"),
    "astra":   ("openrouter", "openai/gpt-6-astra"),
    "opus":    ("openrouter", "anthropic/claude-opus-5.5"),
    "kimi":    ("openrouter", "moonshotai/kimi-k3"),
    "grok":    ("openrouter", "x-ai/grok-4.7"),
    "minimax": ("openrouter", "minimax/minimax-m3"),
    "glm":     ("openrouter", "z-ai/glm-5.3"),
    "qwen":    ("openrouter", "qwen/qwen3.8-27b"),
}
PERSONAS = ["none", "education-faculty-advisor", "education-k12-teacher",
            "education-first-gen-applicant", "education-parent-helper"]
FIXED = ["--persona-model", "gpt-5.6-terra", "--persona-provider", "openai",
         "--judge-model", "gpt-5.6-terra", "--judge-provider", "openai",
         "--temperature", "1", "--max-steps", "50", "--headless", "--skip-existing"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True).stdout.strip()


def rotated(seq: list, k: int) -> list:
    k %= len(seq)
    return seq[k:] + seq[:k]


def snapshot_inputs(block: Path) -> dict:
    inp = block / "inputs"
    (inp / "personas").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ODY / "tasks.json", inp / "tasks.json")
    shutil.copy2(ODY / "make_personas.py", inp / "make_personas.py")
    for p in PERSONAS[1:]:
        shutil.copy2(ODY / "personas" / f"{p}.yaml", inp / "personas" / f"{p}.yaml")
    if (inp / "prompts").exists():
        shutil.rmtree(inp / "prompts")
    shutil.copytree(ODY / "prompts", inp / "prompts")
    return {
        "tasks.json": sha(ODY / "tasks.json"),
        "personas": {p: sha(ODY / "personas" / f"{p}.yaml") for p in PERSONAS[1:]},
        "prompts": {f.name: sha(f) for f in sorted((ODY / "prompts").glob("*.md"))},
    }


def seed_profile(profile: Path) -> None:
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    for rel in SEED_FILES:
        src = SEED / rel
        if src.is_file() and not (profile / rel).exists():
            shutil.copy2(src, profile / rel)


def openrouter_remaining() -> float | None:
    """Dollars left on the OpenRouter key, or None if it cannot be read."""
    import urllib.request
    try:
        env = dict(l.strip().split("=", 1) for l in (REPO / ".env").read_text().splitlines() if "=" in l)
        req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                     headers={"Authorization": "Bearer " + env["OPENROUTER_API_KEY"]})
        d = json.load(urllib.request.urlopen(req, timeout=60))["data"]
        return None if d.get("limit") is None else float(d["limit"]) - float(d["usage"])
    except Exception:
        return None


def kill_chrome_for(profile: Path) -> None:
    subprocess.run(["pkill", "-f", str(profile)], capture_output=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rep", required=True)
    ap.add_argument("--executors", default="terra")
    ap.add_argument("--tasks", default="1,2,3,4,5,6")
    ap.add_argument("--personas", default=",".join(PERSONAS))
    ap.add_argument("--date", help="LA date of the block; default = today in America/Los_Angeles")
    ap.add_argument("--min-remaining", type=float, default=10.0,
                    help="stop before a cell if the OpenRouter key has less than this many dollars left")
    args = ap.parse_args()

    execs = [e.strip() for e in args.executors.split(",") if e.strip()]
    tasks = [int(t) for t in args.tasks.split(",")]
    personas = [p.strip() for p in args.personas.split(",") if p.strip()]
    date = args.date or dt.datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")
    block = REPO / "artifacts" / "experiments" / date / f"science-education-main-setting1-{args.rep}"
    for d in ("results", "logs"):
        (block / d).mkdir(parents=True, exist_ok=True)
    # Profiles hold real session cookies, so they live outside the repo, never under
    # artifacts/ (which main does not gitignore).
    prof_root = ROOT / "work" / "setting1" / "profiles" / date / args.rep

    hashes = snapshot_inputs(block)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cells = []
    k = 0
    for ti, t in enumerate(tasks):
        for p in rotated(personas, ti):
            for e in rotated(execs, k):
                cells.append((t, p, e))
            k += 1

    print(f"block {block.relative_to(REPO)}: {len(cells)} cells "
          f"({len(tasks)} tasks x {len(personas)} arms x {len(execs)} executors)", flush=True)
    log = []
    stopped = None
    for i, (t, p, e) in enumerate(cells, 1):
        prov, mid = EXECUTORS[e]
        left = openrouter_remaining() if prov == "openrouter" else None
        if left is not None and left < args.min_remaining:
            stopped = f"budget guard: ${left:.2f} left on OpenRouter before cell {i}"
            print(stopped, flush=True)
            break
        profile = prof_root / f"t{t}" / p / e
        seed_profile(profile)
        cmd = [str(VENVPY), str(ODY / "run.py"), "--task", str(t), "--persona", p,
               "--model", mid, "--provider", prov, *FIXED,
               "--profile", str(profile), "--out", str(block / "results")]
        t0 = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with open(block / "logs" / f"t{t}__{p}__{e}.log", "a") as fh:
            rc = subprocess.run(cmd, cwd=str(REPO), stdout=fh, stderr=subprocess.STDOUT).returncode
        t1 = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        kill_chrome_for(profile)
        log.append({"cell": i, "task": t, "persona": p, "executor": e, "provider": prov,
                    "model": mid, "exit": rc, "utc_start": t0, "utc_end": t1})
        print(f"[{i}/{len(cells)}] task {t} {p:<30} {e:<8} exit={rc}  {t0} -> {t1}", flush=True)

    manifest = {
        "experiment": "science-education main Setting 1", "replicate": args.rep,
        "date_block_la": date, "utc_start": started,
        "utc_end": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "git_sha": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--", "odyssey")),
        "roles": {
            "persona_simulator": "openai gpt-5.6-terra (direct OpenAI API), temperature 1",
            "rubric_judge": "openai gpt-5.6-terra (direct OpenAI API)",
            "executors": {e: {"provider": EXECUTORS[e][0], "model": EXECUTORS[e][1]} for e in execs},
        },
        "runtime": {"temperature": 1, "max_steps": 50, "max_tabs": 8, "headless": True,
                    "profile_mode": "fresh persistent profile per cell, seeded from one identical "
                                    "5-file warm cookie template"},
        "input_sha256": hashes, "planned_cells": len(cells), "cells": log,
        "protocol_deviations_vs_shopping_main": [
            "execution routed through OpenRouter; persona and judges on the direct OpenAI API "
            "(Shopping used one Azure gpt-5.6-terra deployment for every role)",
            "per-cell profiles pre-seeded from a warm cookie template",
        ],
    }
    manifest["stopped_early"] = stopped
    mpath = block / "RUN_MANIFEST.json"
    if mpath.exists():  # a later invocation into the same block: merge, never overwrite
        old = json.loads(mpath.read_text())
        invs = old.get("invocations") or [{k: old[k] for k in ("utc_start", "utc_end", "planned_cells") if k in old}
                                          | {"executors": sorted(old.get("roles", {}).get("executors", {}))}]
        invs.append({"utc_start": started, "utc_end": manifest["utc_end"], "planned_cells": len(cells),
                     "executors": execs, "stopped_early": stopped})
        old["cells"] = (old.get("cells") or []) + log
        old.setdefault("roles", {}).setdefault("executors", {}).update(manifest["roles"]["executors"])
        old["utc_end"] = manifest["utc_end"]
        old["planned_cells"] = sum(v.get("planned_cells", 0) for v in invs)
        old["invocations"] = invs
        old["git_sha"], old["dirty"] = manifest["git_sha"], manifest["dirty"]
        manifest = old
    mpath.write_text(json.dumps(manifest, indent=1))
    print(f"manifest -> {(block / 'RUN_MANIFEST.json').relative_to(REPO)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
