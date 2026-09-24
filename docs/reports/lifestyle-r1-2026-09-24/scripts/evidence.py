"""Export or verify the first Lifestyle replicate. No network or model calls.

python docs/reports/lifestyle-r1-2026-09-24/verify_audit.py
python docs/reports/lifestyle-r1-2026-09-24/scripts/evidence.py export --archive /path/to/artifacts
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
SUITE = REPO / "odyssey/task_suites/lifestyle"
LABELS = ("Father's Day gifts", "All-black outfit", "Men's outfit",
          "Shared journaling", "Christmas gifts", "Budget outfit")


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8"))


def redact(value):
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"(?i)[a-z]:[\\/]+Users[\\/]+[^\\/\s\"'<>]+",
                   "<LOCAL_USER>", value)
    value = re.sub(r"(?i)/(?:home|Users)/[^/\s\"'<>]+", "<LOCAL_USER>", value)
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP_ADDRESS>", value)
    value = re.sub(r"https?://(?:www\.)?google\.[^/\s]+/sorry/[^\s\"<>]+",
                   "https://www.google.com/sorry/<REDACTED>", value)
    return value.replace("default-yingtaoluo", "<GCP_PROJECT>")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def rows_and_summary(entries):
    tasks = load(SUITE / "000-core.json")
    labels = {task["task_id"]: label for task, label in zip(tasks, LABELS)}
    records = [(entry, load(HERE / entry["file"])) for entry in entries]
    summary = []
    for task in tasks:
        group = [record for _, record in records if record["task_id"] == task["task_id"]]
        scored = [r for r in group if isinstance(r["judgement"].get("score"), (int, float))]
        summary.append({
            "task_id": task["task_id"], "task": labels[task["task_id"]],
            "cells": len(group), "scored": len(scored), "unscored": len(group) - len(scored),
            "scored_with_empty_answer": sum(not r["run"].get("answer", "").strip() for r in scored),
            "raw_mean_score": round(sum(r["judgement"]["score"] for r in scored) / len(scored), 4)
            if scored else None,
            "raw_met": sum(r["judgement"]["met"] for r in scored),
            "rubric_decisions_scored": sum(r["judgement"]["total"] for r in scored),
        })
    lines = ["# First replicate: saved results", "",
             "Raw automatic scores; not independently verified completion. Unscored cells are not zeroes.", "",
             "| Task | Cells | Scored | Unscored | Mean raw score |",
             "|---|---:|---:|---:|---:|"]
    for row in summary:
        score = "n/a" if row["raw_mean_score"] is None else f'{row["raw_mean_score"]:.3f}'
        lines.append(f'| {row["task"]} | {row["cells"]} | {row["scored"]} | {row["unscored"]} | {score} |')
    lines += ["", "## Every cell", "",
              "Each JSON retains the task, configuration, original judgement, final answer,",
              "conversation, saved action previews and final tabs when available.", "",
              "| Task | Persona | Raw score | Outcome | Evidence |",
              "|---|---|---:|---|---|"]
    for entry, record in records:
        judgement = record["judgement"]
        score = (f'{judgement["met"]}/{judgement["total"]}'
                 if judgement.get("score") is not None else "unscored")
        outcome = "scored" if score != "unscored" else "403: JJ's House verification"
        if score != "unscored" and not record["run"].get("answer", "").strip():
            outcome = "raw score retained; empty final answer at step limit"
        lines.append(f'| {labels[record["task_id"]]} | {record["persona"]} | {score} | {outcome} | '
                     f'[JSON]({entry["file"]}) |')
    return summary, "\n".join(lines) + "\n"


def export(archive):
    # Only the first replicate from the final collection; no smoke/other batches.
    source_root = archive.resolve() / "lifestyle-final-results"
    entries = []
    for path in sorted(source_root.rglob("result.json")):
        original = path.read_bytes()
        record = json.loads(original)
        if record.get("suite_id") != "lifestyle" or record.get("replicate_id") != "r1":
            continue
        name = f'evidence/{record["task_id"][:8]}--{record["persona"]}.json'
        if any(entry["file"] == name for entry in entries):
            raise ValueError("Multiple attempts for one r1 cell; do not silently choose one")
        copy = redact(record)
        write_json(HERE / name, copy)
        entries.append({"file": name, "source": path.relative_to(archive.resolve()).as_posix(),
                        "original_sha256": sha(original),
                        "review_copy_sha256": sha((HERE / name).read_bytes()),
                        "redacted": copy != record})
    if len(entries) != 30:
        raise ValueError(f"Expected 30 persisted r1 cells, found {len(entries)}")
    summary, markdown = rows_and_summary(entries)
    write_json(HERE / "lifestyle-score-results.json", summary)
    (HERE / "lifestyle-score-results.md").write_text(markdown, encoding="utf-8", newline="\n")
    write_json(HERE / "redaction-manifest.json", {
        "schema_version": "lifestyle.r1-evidence.v1", "replicate_id": "r1",
        "selection": "lifestyle-final-results, suite=lifestyle, replicate_id=r1",
        "redactions": ["local user paths", "IP addresses", "GCP project ID",
                       "Google challenge URLs"],
        "files": entries,
    })
    verify()


def verify():
    manifest = load(HERE / "redaction-manifest.json")
    tasks = {task["task_id"]: task for task in load(SUITE / "000-core.json")}
    protocol = load(SUITE / "personas/persona_experiment.json")
    expected = {(task_id, f'mp_{axis["axis_id"]}_{arm}')
                for axis in protocol["axes"] for task_id in axis["tasks"]
                for arm in ("positive", "negative")}
    seen, outcomes = set(), Counter()
    entries = manifest["files"]
    assert len(entries) == len(expected) == 30
    assert {p.relative_to(HERE).as_posix() for p in (HERE / "evidence").glob("*--mp_*.json")} == {
        entry["file"] for entry in entries}
    for entry in entries:
        path = HERE / entry["file"]
        assert path.resolve().is_relative_to((HERE / "evidence").resolve())
        assert sha(path.read_bytes()) == entry["review_copy_sha256"], entry["file"]
        record = load(path)
        assert redact(record) == record, "unredacted data"
        assert record["replicate_id"] == record["run_config"]["replicate_id"] == "r1"
        assert record["suite_id"] == "lifestyle"
        cell = (record["task_id"], record["persona"])
        assert cell in expected and cell not in seen
        seen.add(cell)
        assert record["task_snapshot"] == tasks[record["task_id"]]
        assert canonical(record["task_snapshot"]) == record["task_sha256"]
        # Redactions may change display evidence; the configuration objects here
        # contain hashed endpoints, not the redacted addresses or user paths.
        assert canonical(record["run_config"]) == record["run_config_sha256"]
        assert canonical(record["resume_config"]) == record["resume_config_sha256"]
        judgement = record["judgement"]
        if judgement.get("score") is None:
            outcomes["unscored"] += 1
            assert record["environment"]["status"] == "blocked"
            assert any(check.get("http_status") == 403 for check in record["environment"]["checks"])
        else:
            outcomes["scored"] += 1
            assert record["environment"]["status"] == "valid"
            if not record["run"].get("answer", "").strip():
                assert record["run"]["stop_reason"] == "max_steps_summarised"
            verdicts = judgement["verdicts"]
            assert set(verdicts) == set(record["task_snapshot"]["rubrics"])
            assert judgement["total"] == len(verdicts)
            assert judgement["met"] == sum(v.get("met") is True for v in verdicts.values())
            assert judgement["score"] == round(judgement["met"] / judgement["total"], 3)
        assert "persona_fidelity" not in record and "experience" not in record
    assert seen == expected and outcomes == {"scored": 26, "unscored": 4}
    summary, markdown = rows_and_summary(entries)
    assert sum(row["scored_with_empty_answer"] for row in summary) == 2
    assert load(HERE / "lifestyle-score-results.json") == summary
    assert (HERE / "lifestyle-score-results.md").read_text(encoding="utf-8") == markdown
    print("r1 evidence verified: 30 cells, 26 raw scores, 4 unscored 403 outcomes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("export", "verify"))
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.mode == "export":
        if args.archive is None:
            parser.error("export requires --archive (the local artifacts directory)")
        export(args.archive)
    else:
        verify()
