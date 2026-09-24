"""Judge whether the simulated user expressed its assigned persona dimensions.

This stage is deliberately independent from task-rubric grading and P1-P5 user
experience grading. It sees only a frozen profile snapshot, the original task
as an inherited-wording baseline, and the simulated user's own utterances.

    python odyssey/persona_fidelity_judge.py --results <run-directory>
    python odyssey/persona_fidelity_judge.py --results <run-directory> \
        --judge-model gpt-5.5 --judge-provider openai
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as odyssey  # noqa: E402

SCHEMA_VERSION = "odyssey.persona-fidelity.v1"
PROMPT = odyssey.prompt("persona_fidelity_judge")


def profile_snapshot(record: dict) -> dict:
    """Return and validate the immutable profile snapshot saved with the run."""
    snapshot = (((record.get("run") or {}).get("user") or {})
                .get("persona_profile"))
    if not isinstance(snapshot, dict):
        raise ValueError("run has no frozen persona_profile snapshot")
    dimensions = snapshot.get("evaluation_dimensions")
    values = snapshot.get("evaluation_values")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("persona snapshot has no evaluation_dimensions")
    if len(dimensions) != len(set(dimensions)):
        raise ValueError("persona snapshot has duplicate evaluation_dimensions")
    if not isinstance(values, dict):
        raise ValueError("persona snapshot has no evaluation_values")
    missing = [dimension for dimension in dimensions if dimension not in values]
    if missing:
        raise ValueError(f"persona snapshot is missing values for {missing}")
    digest = str(snapshot.get("profile_sha256") or "")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
        raise ValueError("persona snapshot has an invalid profile_sha256")
    return snapshot


def requested_targets(snapshot: dict) -> list[dict]:
    targets = [
        {
            "attribute": dimension,
            "expected_value": snapshot["evaluation_values"][dimension],
        }
        for dimension in snapshot["evaluation_dimensions"]
    ]
    matched_pair = snapshot.get("matched_pair")
    if isinstance(matched_pair, dict) and len(targets) == 1:
        rubric = matched_pair.get("adherence_rubric")
        if isinstance(rubric, dict):
            targets[0].update({
                "axis_id": matched_pair.get("axis_id"),
                "axis_label": matched_pair.get("axis_label"),
                "arm": matched_pair.get("arm"),
                "opposite_value": matched_pair.get("opposite_value"),
                "behavioral_definition": rubric.get("behavioral_definition"),
                "generic_observables": rubric.get("generic_observables"),
                "task_observables": rubric.get("task_observables"),
                "opposite_task_observables": rubric.get(
                    "opposite_task_observables"
                ),
                "inherited_task_signals": rubric.get("inherited_task_signals"),
                "contradictions": rubric.get("contradictions"),
                "opposite_behavioral_definition": rubric.get(
                    "opposite_behavioral_definition"
                ),
                "opposite_generic_observables": rubric.get(
                    "opposite_generic_observables"
                ),
            })
    return targets


def persona_utterances(record: dict) -> list[str]:
    """Extract only persona/user turns; CUA text can never become evidence."""
    utterances = []
    for turn in (record.get("run") or {}).get("conversation") or []:
        if turn.get("role") != "user":
            continue
        text = str(turn.get("text") or "").strip()
        if text:
            utterances.append(text)
    return utterances


def communication_guardrail(record: dict, snapshot: dict | None = None) -> dict:
    """Return the formal matched-pair original-rubric coverage status."""
    snapshot = snapshot or profile_snapshot(record)
    if not isinstance(snapshot.get("matched_pair"), dict):
        return {"applicable": False, "status": "not_applicable", "passed": None}
    task, _ = odyssey.task_for_record(record)
    judgement = record.get("judgement")
    expected_total = len(task["rubrics"])
    if not isinstance(judgement, dict):
        return {
            "applicable": True,
            "status": "unavailable",
            "passed": None,
            "reason": "run has no R1–Rn judgement",
            "expected_total": expected_total,
        }
    communicated = judgement.get("communicated")
    total = judgement.get("total")
    if (
        isinstance(communicated, bool)
        or not isinstance(communicated, int)
        or isinstance(total, bool)
        or not isinstance(total, int)
    ):
        return {
            "applicable": True,
            "status": "unavailable",
            "passed": None,
            "reason": "R1–Rn judgement has no complete communication counts",
            "expected_total": expected_total,
        }
    verdicts = judgement.get("verdicts") or {}
    omitted = sorted(
        rubric_id
        for rubric_id, verdict in verdicts.items()
        if isinstance(verdict, dict) and verdict.get("communicated") is not True
    )
    passed = communicated == total == expected_total
    return {
        "applicable": True,
        "status": "complete",
        "passed": passed,
        "communicated": communicated,
        "total": total,
        "expected_total": expected_total,
        "uncommunicated_rubric_ids": omitted,
    }


def build_prompt(record: dict) -> str:
    if record.get("persona") == "none":
        raise ValueError("persona fidelity is not applicable to the control arm")
    snapshot = profile_snapshot(record)
    task, _ = odyssey.task_for_record(record)
    utterances = persona_utterances(record)
    if not utterances:
        raise ValueError("run has no persona utterances")
    coverage = communication_guardrail(record, snapshot)
    if coverage["applicable"]:
        coverage_policy = (
            "This is a controlled matched-pair arm with a 100% original-rubric "
            "communication guardrail. Compare the PERSON utterances with the complete "
            "original task. Omitting or weakening a required component cannot count as "
            "persona expression and any target whose apparent expression depends on "
            "doing so must receive score 0. The separately computed coverage status is: "
            + json.dumps(coverage, ensure_ascii=False, sort_keys=True)
        )
    else:
        coverage_policy = (
            "This is a natural-user profile, not a controlled matched pair. Omission "
            "alone is not a contradiction; judge only whether the declared target was "
            "expressed."
        )
    return PROMPT.format(
        task=task["confirmed_task"],
        targets=json.dumps(requested_targets(snapshot), ensure_ascii=False, indent=2),
        coverage_policy=coverage_policy,
        utterances="\n".join(
            f"PERSON TURN {index}: {text}" for index, text in enumerate(utterances, 1)
        ),
    )


def normalize_verdict(parsed: dict, *, model: str, provider: str,
                      snapshot: dict) -> dict:
    """Fail closed unless the judge returns every frozen target exactly once."""
    expected = requested_targets(snapshot)
    expected_by_id = {item["attribute"]: item for item in expected}
    items = parsed.get("targets")
    if not isinstance(items, list):
        raise ValueError("fidelity judge is missing targets")
    by_id: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("fidelity target must be an object")
        attribute = str(item.get("attribute") or "")
        if attribute in by_id:
            raise ValueError(f"duplicate fidelity target {attribute!r}")
        by_id[attribute] = item
    if set(by_id) != set(expected_by_id):
        raise ValueError(
            "fidelity target mismatch: "
            f"missing={sorted(set(expected_by_id) - set(by_id))}, "
            f"extra={sorted(set(by_id) - set(expected_by_id))}"
        )

    normalized_targets = []
    for attribute, target in expected_by_id.items():
        item = by_id[attribute]
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or score not in {0, 1, 2}:
            raise ValueError(f"invalid fidelity score for {attribute}: {score!r}")
        expressed = item.get("expressed")
        if not isinstance(expressed, bool):
            raise ValueError(f"fidelity expressed must be boolean for {attribute}")
        if expressed != (score == 2):
            raise ValueError(f"fidelity expressed/score mismatch for {attribute}")
        contradicted = item.get("contradicted")
        if not isinstance(contradicted, bool):
            raise ValueError(f"fidelity contradicted must be boolean for {attribute}")
        if contradicted and score != 0:
            raise ValueError(f"contradicted fidelity target must score 0 for {attribute}")
        raw_confidence = item.get("confidence", 0.0)
        if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)):
            raise ValueError(f"invalid fidelity confidence for {attribute}")
        confidence = float(raw_confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"fidelity confidence must be in [0, 1] for {attribute}")
        evidence = item.get("evidence", "")
        note = item.get("note", "")
        if not isinstance(evidence, str) or not isinstance(note, str) or not note.strip():
            raise ValueError(f"fidelity evidence/note must be strings for {attribute}")
        if (score > 0 or contradicted) and not evidence.strip():
            raise ValueError(f"fidelity target {attribute} requires evidence")
        normalized_targets.append({
            **target,
            "score": score,
            "expressed": expressed,
            "contradicted": contradicted,
            "confidence": confidence,
            "evidence": evidence.strip(),
            "note": note.strip(),
            "criterion_source": "declared_profile_dimension",
        })

    issues = parsed.get("fidelity_issues") or []
    if (not isinstance(issues, list)
            or any(not isinstance(issue, str) or not issue.strip() for issue in issues)):
        raise ValueError("fidelity_issues must be a list of non-empty strings")
    raw_judge_confidence = parsed.get("judge_confidence", 0.0)
    if (isinstance(raw_judge_confidence, bool)
            or not isinstance(raw_judge_confidence, (int, float))):
        raise ValueError("judge_confidence must be numeric")
    judge_confidence = float(raw_judge_confidence)
    if not math.isfinite(judge_confidence) or not 0 <= judge_confidence <= 1:
        raise ValueError("judge_confidence must be in [0, 1]")
    return {
        "schema_version": SCHEMA_VERSION,
        "metric": "persona_target_expression_coverage",
        "status": "complete",
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "judge": {"model": model, "provider": provider,
                  "backend": odyssey._provider_backend(provider)},
        "profile_sha256": snapshot["profile_sha256"],
        "profile_integrity": "frozen_snapshot",
        "applicable": True,
        "targets": normalized_targets,
        "expressed_target_count": sum(item["expressed"] for item in normalized_targets),
        "contradicted_target_count": sum(item["contradicted"] for item in normalized_targets),
        "total_target_count": len(normalized_targets),
        "fidelity_issues": [issue.strip() for issue in issues],
        "judge_confidence": judge_confidence,
    }


def apply_communication_guardrail(verdict: dict, coverage: dict) -> dict:
    """Fail a formal arm closed when it did not communicate every base rubric."""
    verdict["communication_guardrail"] = coverage
    if not coverage.get("applicable") or coverage.get("passed") is not False:
        return verdict
    issue = (
        "Matched-pair arm failed the 100% original-rubric communication guardrail; "
        f"communicated {coverage.get('communicated')}/{coverage.get('expected_total')}."
    )
    issues = list(verdict.get("fidelity_issues") or [])
    if issue not in issues:
        issues.append(issue)
    verdict["fidelity_issues"] = issues
    for target in verdict.get("targets") or []:
        target["score_before_coverage_guardrail"] = target.get("score")
        target["expressed_before_coverage_guardrail"] = target.get("expressed")
        target["score"] = 0
        target["expressed"] = False
        target["note"] = f"{issue} {target.get('note', '')}".strip()
    verdict["expressed_target_count"] = 0
    return verdict


def score_once(record: dict, model: str, provider: str = "") -> dict:
    """Call one independent judge, retrying invalid or unparseable responses."""
    snapshot = profile_snapshot(record)
    coverage = communication_guardrail(record, snapshot)
    resolved_provider = odyssey._resolved_provider(model, provider)
    if coverage.get("applicable") and coverage.get("status") != "complete":
        _, task_integrity = odyssey.task_for_record(record)
        return {
            "schema_version": SCHEMA_VERSION,
            "metric": "persona_target_expression_coverage",
            "status": "error",
            "applicable": True,
            "judge": {"model": model, "provider": resolved_provider,
                      "backend": odyssey._provider_backend(resolved_provider)},
            "profile_sha256": snapshot["profile_sha256"],
            "profile_integrity": "frozen_snapshot",
            "task_integrity": task_integrity,
            "communication_guardrail": coverage,
            "error": coverage.get("reason") or "communication coverage unavailable",
        }
    prompt = build_prompt(record)
    client, resolved_provider = odyssey._client(model, provider)
    last = "unparseable judge output"
    for attempt in range(3):
        try:
            response = odyssey._create_with_retry(
                client,
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **odyssey._judge_options(model, 5000),
            )
            parsed = odyssey.extract_json(response.choices[0].message.content or "")
            if parsed:
                verdict = normalize_verdict(
                    parsed,
                    model=model,
                    provider=resolved_provider,
                    snapshot=snapshot,
                )
                verdict = apply_communication_guardrail(verdict, coverage)
                _, verdict["task_integrity"] = odyssey.task_for_record(record)
                return verdict
            last = "unparseable judge output"
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        print(f"    [{model}] attempt {attempt + 1}/3: {last}", flush=True)
    _, task_integrity = odyssey.task_for_record(record)
    return {
        "schema_version": SCHEMA_VERSION,
        "metric": "persona_target_expression_coverage",
        "status": "error",
        "applicable": True,
        "judge": {"model": model, "provider": resolved_provider,
                  "backend": odyssey._provider_backend(resolved_provider)},
        "profile_sha256": snapshot["profile_sha256"],
        "profile_integrity": "frozen_snapshot",
        "task_integrity": task_integrity,
        "error": last,
    }


def _write_record(path: Path, record: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=str(HERE / "results"))
    parser.add_argument("--judge-model", default="gpt-5.5")
    parser.add_argument("--judge-provider", default="")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--print-prompt", action="store_true")
    args = parser.parse_args()
    odyssey.load_dotenv()

    for path in sorted(Path(args.results).rglob("result.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("persona") == "none":
            if args.print_prompt:
                continue
            if not record.get("persona_fidelity") or args.redo:
                record["persona_fidelity"] = {
                    "schema_version": SCHEMA_VERSION,
                    "metric": "persona_target_expression_coverage",
                    "status": "not_applicable",
                    "applicable": False,
                    "reason": "Control arm has no assigned persona.",
                }
                _write_record(path, record)
            print(f"skip {record.get('task_id', '')[:12]} none (control arm)")
            continue
        if args.print_prompt:
            print(build_prompt(record))
            return
        existing = record.get("persona_fidelity") or {}
        if existing.get("status") in {"complete", "not_applicable"} and not args.redo:
            continue
        print(f"{record.get('task_id', '')[:12]} {record.get('persona')}", flush=True)
        try:
            record["persona_fidelity"] = score_once(
                record, args.judge_model, args.judge_provider
            )
        except Exception as exc:
            record["persona_fidelity"] = {
                "schema_version": SCHEMA_VERSION,
                "metric": "persona_target_expression_coverage",
                "status": "error",
                "applicable": True,
                "profile_integrity": "missing_or_invalid_snapshot",
                "error": f"{type(exc).__name__}: {exc}",
            }
        _write_record(path, record)
        fidelity = record["persona_fidelity"]
        if fidelity.get("status") != "complete":
            print(f"  ERROR: {fidelity.get('error')}")
            continue
        for target in fidelity["targets"]:
            print(f"  {target['attribute']:29} {target['score']}  "
                  f"expressed={target['expressed']} contradicted={target['contradicted']}")
        print(f"  expressed {fidelity['expressed_target_count']}/"
              f"{fidelity['total_target_count']}; contradicted "
              f"{fidelity['contradicted_target_count']}")


if __name__ == "__main__":
    main()
