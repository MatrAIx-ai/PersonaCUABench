"""Offline integrity checks for the Health pilot's redacted evidence bundle.

Run: python docs/reports/health-pilot-2026-09-22/verify_audit.py
This verifies provenance and accounting, not the correctness of subjective audit
judgments. It makes no browser requests or model calls.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def resolve(document, path):
    for part in path.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


def main():
    audit = load("health-evaluation-audit.json")
    manifest = load("redaction-manifest.json")
    originals = {}
    for name, digests in manifest["files"].items():
        assert sha((HERE / name).read_bytes()) == digests["review_copy_sha256"], name
        assert audit["input_sha256"][name] == digests["review_copy_sha256"]
        originals[name] = load(name)
    data = originals["health-pilot-results.json"]
    statuses = ("supported", "not_met", "insufficient_evidence")
    counts, transitions = Counter(), Counter()
    seen, event_count, original_met = set(), 0, 0
    for run in audit["runs"]:
        assert run["audit_run_id"] not in seen
        seen.add(run["audit_run_id"])
        record = resolve(data, run["source"]["json_pointer"])
        assert record["run"]["answer"] and record["task_id"] == run["task_id"]
        assert (HERE / run["evidence_report"]).is_file()
        assert record["persona"] == run["persona"]
        assert run["final_tab_count"] == len(record["run"]["open_tabs"])
        event_count += len(record["run"]["trajectory"])
        assert len(record["run"]["trajectory"]) == run["trajectory_event_count"]
        assert record["run"]["conversation"][0]["text"].startswith(record["task_snapshot"]["confirmed_task"])
        assert not any(t["tool"] == "ask_user" for t in record["run"]["trajectory"])
        assert set(run["rubrics"]) == set(record["task_snapshot"]["rubrics"])
        run_counts = Counter()
        for rid, review in run["rubrics"].items():
            assert review["status"] in statuses
            assert review["original_rubric"] == record["task_snapshot"]["rubrics"][rid]
            assert review["original_automatic_verdict"] == record["judgement"]["verdicts"][rid]
            for ref in review["event_refs"]:
                event = resolve(data, ref["json_pointer"])
                assert event["step"] == ref["step_label"] and event["tool"] == ref["tool"]
                assert event == record["run"]["trajectory"][ref["event_index"]]
            for ref in review["field_refs"]:
                resolve(data, ref["json_pointer"])
            run_counts[review["status"]] += 1
            old = "original_met" if review["original_automatic_verdict"]["met"] else "original_not_met"
            transitions[(old, review["status"])] += 1
        assert {s: run_counts[s] for s in statuses} == run["audit_counts"]
        counts.update(run_counts)
        original_met += record["judgement"]["met"]
        for excerpt in run["excerpts"]:
            text = resolve(data, excerpt["source"]["json_pointer"])
            assert sha(text) == excerpt["result_sha256"]
            assert text[excerpt["start_char"]:excerpt["end_char"]] == excerpt["text"]
        for kind in ("experience_review", "persona_expression_review"):
            ref = run[kind]["source"]
            resolve(originals[ref["file"]], ref["json_pointer"])
    summary = audit["summary"]
    assert len(seen) == summary["answered_runs"] == 12
    assert sum(counts.values()) == summary["reviewed_rubric_decisions"] == 66
    assert dict(counts) == summary["audit_counts"]
    assert event_count == summary["answered_trajectory_events"] == 134
    assert original_met == summary["original_automatic_met"] == 31
    for row in summary["transitions"]:
        assert transitions[(row["original"], row["audit_status"])] == row["count"]
    assert len(audit["unscored_attempts"]) == 5
    for failure in audit["unscored_attempts"]:
        record = resolve(data, failure["source"]["json_pointer"])
        assert failure["score"] is None
        assert not record.get("run", {}).get("answer")
    assert len(seen) + len(audit["unscored_attempts"]) == summary["attempts_total"] == 17
    # The published task snapshots must also match the checked-in Health suite.
    suite = {t["task_id"]: t for t in json.loads(
        (HERE.parents[2] / "odyssey/task_suites/health/000-core.json").read_text()
    )}
    for group in ("records", "recovery_records", "api_retry_records", "failed_attempts"):
        for record in data[group]:
            assert record["task_snapshot"] == suite[record["task_id"]]
    print("Health audit OK: 12 answers, 66 rubric decisions, 134 events, 5 unscored attempts; "
          "source hashes, task snapshots, pointers and excerpts match.")


if __name__ == "__main__":
    main()
