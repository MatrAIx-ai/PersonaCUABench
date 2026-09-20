"""PersonaCUABench evaluation adapters and schema validation.

Task success, simulator adherence, and outcome alignment intentionally remain
separate.  Callers provide the model transport so this module is fully
offline-testable and does not silently upload artifacts.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from personacuabench.network_preflight import (
    EVIDENCE_SCOPE as NETWORK_PREFLIGHT_EVIDENCE_SCOPE,
    PREFLIGHT_PHASE as NETWORK_PREFLIGHT_PHASE,
    RUBRIC_MAPPING_SEMANTICS,
    SCHEMA_VERSION as NETWORK_PREFLIGHT_SCHEMA_VERSION,
    PreflightResultError,
    validate_preflight_document,
)


JudgeCall = Callable[[str, str, list[Path]], str]

ALIGNMENT_STATUSES = {
    "aligned",
    "partially_aligned",
    "misaligned",
    "not_applicable",
}
PREFERENCE_AXES = {
    "privacy",
    "frugality",
    "convenience",
    "accessibility",
    "trust",
    "familiarity",
    "speed",
    "quality",
    "risk_aversion",
    "other",
}
SIGNAL_SOURCES = {
    "persona_profile",
    "task_instruction",
    "dialog_context",
    "history_or_memory",
    "multiple",
}
CONSTRAINT_PRIORITIES = {"hard", "soft"}
CONSTRAINT_STATUSES = {
    "satisfied",
    "partially_satisfied",
    "violated",
    "not_triggered",
    "unknown",
}
CONSTRAINT_TYPES = {
    "privacy",
    "budget",
    "accessibility",
    "familiarity",
    "brand_preference",
    "speed",
    "quality_bar",
    "risk_limit",
    "other",
}

NETWORK_PREFLIGHT_ADJUSTMENT_ELIGIBILITY = "eligible_for_policy_review"


class EvaluationError(RuntimeError):
    """Raised when judge output cannot satisfy the declared contract."""


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise EvaluationError("Judge did not return a JSON object")
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as exc:
            raise EvaluationError(f"Invalid judge JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError("Judge response must be a JSON object")
    return value


def task_verdicts_from_standard(
    task: dict[str, Any], standard_task_result: dict[str, Any]
) -> list[dict[str, Any]]:
    by_id = {
        str(item.get("rubric_id")): item
        for item in standard_task_result.get("rubric_results", [])
        if isinstance(item, dict)
    }
    verdicts: list[dict[str, Any]] = []
    for rubric_id, rubric in task["rubrics"].items():
        judged = by_id.get(str(rubric_id), {})
        score = judged.get("score")
        if score not in (0, 1):
            raise EvaluationError(f"Missing standard score for {rubric_id}")
        verdicts.append(
            {
                "rubric_id": str(rubric_id),
                "requirement": rubric.get("requirement", ""),
                "verification": rubric.get("verification", ""),
                "met": bool(score),
                "task_evidence": judged.get("final_reasoning", ""),
                "communicated": None,
                "communication_evidence": "",
            }
        )
    return verdicts


def _persona_utterances(conversation: Iterable[dict[str, Any]]) -> list[str]:
    utterances: list[str] = []
    for item in conversation:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).lower()
        event_type = str(item.get("event_type", "")).lower()
        if role in {"user", "persona"} or event_type in {
            "opening_request",
            "persona_answer",
        }:
            content = str(item.get("content") or item.get("answer") or "").strip()
            if content:
                utterances.append(content)
    return utterances


def evaluate_communication(
    *,
    task: dict[str, Any],
    conversation: list[dict[str, Any]],
    judge: JudgeCall,
    exact_control: bool = False,
) -> dict[str, Any]:
    """Decide which original requirements the simulated user communicated."""
    rubrics = task["rubrics"]
    if exact_control:
        return {
            "judge_derived": False,
            "rubrics": {
                rid: {
                    "communicated": True,
                    "evidence": "The none control sends confirmed_task verbatim.",
                }
                for rid in rubrics
            },
        }

    utterances = _persona_utterances(conversation)
    rubric_text = "\n".join(
        f"- {rid}: {value.get('requirement', '')}" for rid, value in rubrics.items()
    )
    transcript = "\n".join(f"USER TURN {i}: {text}" for i, text in enumerate(utterances, 1))
    system = (
        "You are a strict communication-coverage judge. Determine only whether "
        "each requirement was communicated by the simulated user's own words. "
        "Do not use the hidden original task, browser actions, or the CUA answer as "
        "evidence. Paraphrases count; unstated latent preferences do not. Return "
        "strict JSON with a top-level 'rubrics' object. Each rubric value must have "
        "boolean 'communicated' and string 'evidence'."
    )
    user = f"REQUIREMENTS:\n{rubric_text}\n\nSIMULATED USER UTTERANCES:\n{transcript or '(none)'}"
    raw = judge(system, user, [])
    parsed = parse_json_object(raw)
    judged = parsed.get("rubrics")
    if not isinstance(judged, dict):
        raise EvaluationError("Communication judge is missing rubrics")
    normalized: dict[str, Any] = {}
    for rid in rubrics:
        item = judged.get(rid)
        if not isinstance(item, dict) or not isinstance(item.get("communicated"), bool):
            raise EvaluationError(f"Communication judge is missing boolean {rid}")
        normalized[rid] = {
            "communicated": item["communicated"],
            "evidence": str(item.get("evidence", "")).strip(),
        }
    return {"judge_derived": True, "rubrics": normalized}


def merge_task_and_communication(
    verdicts: list[dict[str, Any]], communication: dict[str, Any]
) -> dict[str, Any]:
    communication_by_id = communication["rubrics"]
    for verdict in verdicts:
        communicated = communication_by_id[verdict["rubric_id"]]
        verdict["communicated"] = communicated["communicated"]
        verdict["communication_evidence"] = communicated["evidence"]
    score = sum(1 for verdict in verdicts if verdict["met"]) / len(verdicts) if verdicts else None
    communicated = [verdict for verdict in verdicts if verdict["communicated"]]
    score_communicated = (
        sum(1 for verdict in communicated if verdict["met"]) / len(communicated)
        if communicated
        else None
    )
    return {
        "verdicts": verdicts,
        "score": round(score, 4) if score is not None else None,
        "score_communicated": (
            round(score_communicated, 4) if score_communicated is not None else None
        ),
        "communicated_rubric_count": len(communicated),
        "communication_judge_derived": communication.get("judge_derived", True),
    }


def _availability_score(verdicts: Iterable[Mapping[str, Any]]) -> float | None:
    items = list(verdicts)
    if not items:
        return None
    return round(sum(1 for item in items if item["met"]) / len(items), 4)


def _validate_task_success_for_availability(
    task_success: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Validate and copy only the verdict fields used by score adjustment."""
    raw_verdicts = task_success.get("verdicts")
    if not isinstance(raw_verdicts, list):
        raise EvaluationError("task_success.verdicts must be a list")

    verdicts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_verdicts, start=1):
        if not isinstance(raw, Mapping):
            raise EvaluationError(f"task_success verdict #{index} must be an object")
        rubric_id = raw.get("rubric_id")
        if not isinstance(rubric_id, str) or not rubric_id:
            raise EvaluationError(
                f"task_success verdict #{index} has an invalid rubric_id"
            )
        if rubric_id in seen_ids:
            raise EvaluationError(f"Duplicate task_success rubric_id: {rubric_id}")
        seen_ids.add(rubric_id)
        if not isinstance(raw.get("met"), bool):
            raise EvaluationError(f"task_success {rubric_id}.met must be boolean")
        if not isinstance(raw.get("communicated"), bool):
            raise EvaluationError(
                f"task_success {rubric_id}.communicated must be boolean"
            )
        verdicts.append(
            {
                "rubric_id": rubric_id,
                "requirement": str(raw.get("requirement", "")),
                "met": raw["met"],
                "communicated": raw["communicated"],
                "task_evidence": str(raw.get("task_evidence", "")),
            }
        )

    raw_score = _availability_score(verdicts)
    communicated = [item for item in verdicts if item["communicated"]]
    communicated_score = _availability_score(communicated)

    def validate_declared_score(key: str, expected: float | None) -> None:
        declared = task_success.get(key)
        if expected is None:
            if declared is not None:
                raise EvaluationError(f"task_success.{key} must be null")
            return
        if (
            isinstance(declared, bool)
            or not isinstance(declared, (int, float))
            or not math.isfinite(float(declared))
            or round(float(declared), 4) != expected
        ):
            raise EvaluationError(
                f"task_success.{key} does not match its verdict denominator"
            )

    validate_declared_score("score", raw_score)
    validate_declared_score("score_communicated", communicated_score)
    declared_communicated_count = task_success.get("communicated_rubric_count")
    if (
        isinstance(declared_communicated_count, bool)
        or not isinstance(declared_communicated_count, int)
        or declared_communicated_count != len(communicated)
    ):
        raise EvaluationError(
            "task_success.communicated_rubric_count does not match its verdicts"
        )
    return verdicts


def compute_availability_adjustment(
    task_success: dict[str, Any],
    network_preflight: dict[str, Any] | None,
    *,
    expected_task_id: str,
    expected_run_id: str,
    artifact_integrity_verified: bool,
) -> dict[str, Any]:
    """Return an auditable raw/availability-adjusted score pair without mutation.

    The adjustment contract is intentionally fail-closed.  A usable preflight
    artifact must have all of the following fields:

    * ``schema_version == "persona-cua-network-preflight/v1"``;
    * top-level ``task_id`` and ``run_id`` matching this exact task/run,
      ``phase == "after_reset_before_agent"``, and
      ``evidence_scope == "same_run"``;
    * ``execution.status == "complete"`` and
      ``policy.assessment_complete is true``;
    * matching ``classification`` and ``feasibility`` states.

    A feasible assessment uses ``classification.status == "feasible"`` and
    ``feasibility.status == "feasible"`` and returns adjusted scores equal to
    raw scores.  An exclusion additionally requires high-confidence
    ``target_external_unavailable`` evidence, explicit
    ``eligible_for_policy_review`` values in both ``classification`` and
    ``policy``, ``classification.infeasible_candidate is true``,
    ``policy.dns_only is true``, and identical non-empty
    ``feasibility.affected_rubric_ids`` and
    ``policy.affected_rubric_ids`` lists.  Every exclusively blocked affected
    rubric is removed from adjusted denominators independent of the agent's
    verdict, so all agents in the same environment use the same denominator.
    Neither the supplied task-success object nor any verdict is modified.

    Missing, legacy, malformed, phase/task mismatched, integrity-unverified, or
    indeterminate artifacts return null adjusted scores.  If exclusions remove
    the entire task or communicated denominator, the corresponding adjusted
    score is also null.
    """
    if not isinstance(task_success, Mapping):
        raise EvaluationError("task_success must be an object")
    if not isinstance(expected_task_id, str) or not expected_task_id:
        raise EvaluationError("expected_task_id must be a non-empty string")
    if not isinstance(expected_run_id, str) or not expected_run_id:
        raise EvaluationError("expected_run_id must be a non-empty string")
    if not isinstance(artifact_integrity_verified, bool):
        raise EvaluationError("artifact_integrity_verified must be boolean")

    verdicts = _validate_task_success_for_availability(task_success)
    raw_communicated = [item for item in verdicts if item["communicated"]]
    score_raw = _availability_score(verdicts)
    score_communicated_raw = _availability_score(raw_communicated)
    raw_ids = [item["rubric_id"] for item in verdicts]

    base_counts: dict[str, int | None] = {
        "raw_rubric_count": len(verdicts),
        "raw_met_count": sum(item["met"] for item in verdicts),
        "raw_failed_count": sum(not item["met"] for item in verdicts),
        "raw_communicated_rubric_count": len(raw_communicated),
        "raw_communicated_met_count": sum(
            item["met"] for item in raw_communicated
        ),
        "raw_communicated_failed_count": sum(
            not item["met"] for item in raw_communicated
        ),
        "eligible_rubric_count": None,
        "eligible_met_count": None,
        "eligible_failed_count": None,
        "eligible_communicated_rubric_count": None,
        "eligible_communicated_met_count": None,
        "eligible_communicated_failed_count": None,
        "excluded_rubric_count": 0,
        "excluded_communicated_rubric_count": 0,
    }

    def result(
        *,
        status: str,
        environment_status: str,
        reasons: list[str],
        classification_status: str | None = None,
        confidence: str | None = None,
        affected_ids: list[str] | None = None,
        eligible: list[dict[str, Any]] | None = None,
        excluded: list[dict[str, Any]] | None = None,
        affected_target_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        affected = list(affected_ids or [])
        excluded_items = list(excluded or [])
        excluded_ids = [item["rubric_id"] for item in excluded_items]
        if eligible is None:
            counts = dict(base_counts)
            eligible_ids: list[str] | None = None
            adjusted_score = None
            adjusted_communicated_score = None
        else:
            eligible_communicated = [
                item for item in eligible if item["communicated"]
            ]
            counts = {
                **base_counts,
                "eligible_rubric_count": len(eligible),
                "eligible_met_count": sum(item["met"] for item in eligible),
                "eligible_failed_count": sum(not item["met"] for item in eligible),
                "eligible_communicated_rubric_count": len(eligible_communicated),
                "eligible_communicated_met_count": sum(
                    item["met"] for item in eligible_communicated
                ),
                "eligible_communicated_failed_count": sum(
                    not item["met"] for item in eligible_communicated
                ),
                "excluded_rubric_count": len(excluded_items),
                "excluded_communicated_rubric_count": sum(
                    item["communicated"] for item in excluded_items
                ),
            }
            eligible_ids = [item["rubric_id"] for item in eligible]
            adjusted_score = _availability_score(eligible)
            adjusted_communicated_score = _availability_score(
                eligible_communicated
            )
        return {
            "status": status,
            "score_raw": score_raw,
            "score_availability_adjusted": adjusted_score,
            "score_communicated_raw": score_communicated_raw,
            "score_communicated_availability_adjusted": (
                adjusted_communicated_score
            ),
            "coverage": {
                "assessment_complete": eligible is not None,
                "raw_rubric_ids": list(raw_ids),
                "affected_rubric_ids": affected,
                "eligible_rubric_ids": eligible_ids,
                "excluded_rubric_ids": excluded_ids,
            },
            "counts": counts,
            "excluded_rubrics": excluded_items,
            "environment_feasibility": {
                "status": environment_status,
                "classification_status": classification_status,
                "confidence": confidence,
                "reasons": list(reasons),
                "affected_rubric_ids": affected,
                "affected_target_keys": list(affected_target_keys or []),
            },
        }

    if network_preflight is None:
        return result(
            status="not_assessed",
            environment_status="indeterminate",
            reasons=["network_preflight_missing"],
        )
    if not artifact_integrity_verified:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=["artifact_integrity_not_verified"],
        )
    if not isinstance(network_preflight, Mapping):
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=["network_preflight_not_an_object"],
        )

    artifact = dict(network_preflight)
    try:
        validate_preflight_document(artifact)
    except PreflightResultError:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=["preflight_contract_invalid"],
        )
    provenance_checks = (
        (
            artifact.get("schema_version") == NETWORK_PREFLIGHT_SCHEMA_VERSION,
            "unsupported_network_preflight_schema",
        ),
        (artifact.get("task_id") == expected_task_id, "task_id_mismatch"),
        (artifact.get("run_id") == expected_run_id, "run_id_mismatch"),
        (
            artifact.get("phase") == NETWORK_PREFLIGHT_PHASE,
            "preflight_not_before_agent",
        ),
        (
            artifact.get("evidence_scope") == NETWORK_PREFLIGHT_EVIDENCE_SCOPE,
            "preflight_not_same_run",
        ),
    )
    provenance_failures = [reason for passed, reason in provenance_checks if not passed]
    if provenance_failures:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=provenance_failures,
        )

    execution = artifact.get("execution")
    classification = artifact.get("classification")
    feasibility = artifact.get("feasibility")
    policy = artifact.get("policy")
    if not all(
        isinstance(value, Mapping)
        for value in (execution, classification, feasibility, policy)
    ):
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=["preflight_contract_incomplete"],
        )
    assert isinstance(execution, Mapping)
    assert isinstance(classification, Mapping)
    assert isinstance(feasibility, Mapping)
    assert isinstance(policy, Mapping)

    classification_status = classification.get("status")
    confidence = classification.get("confidence")
    classification_status_text = (
        classification_status if isinstance(classification_status, str) else None
    )
    confidence_text = confidence if isinstance(confidence, str) else None
    reason_codes = classification.get("reason_codes")
    safe_reasons = (
        [value for value in reason_codes if isinstance(value, str)]
        if isinstance(reason_codes, list)
        else []
    )
    affected_target_keys_value = feasibility.get("affected_target_keys")
    affected_target_keys = (
        [value for value in affected_target_keys_value if isinstance(value, str)]
        if isinstance(affected_target_keys_value, list)
        else []
    )

    common_failures: list[str] = []
    if execution.get("status") != "complete":
        common_failures.append("preflight_execution_incomplete")
    if policy.get("assessment_complete") is not True:
        common_failures.append("policy_assessment_incomplete")
    if classification.get("assessment_complete") is not True:
        common_failures.append("classification_assessment_incomplete")
    if classification.get("raw_score_affected") is not False:
        common_failures.append("classification_raw_score_contract_invalid")
    if feasibility.get("raw_score_affected") is not False:
        common_failures.append("feasibility_raw_score_contract_invalid")
    if common_failures:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=common_failures + safe_reasons,
            classification_status=classification_status_text,
            confidence=confidence_text,
            affected_target_keys=affected_target_keys,
        )

    if classification_status == "feasible":
        if feasibility.get("status") != "feasible":
            return result(
                status="not_eligible",
                environment_status="indeterminate",
                reasons=["classification_feasibility_mismatch"] + safe_reasons,
                classification_status=classification_status_text,
                confidence=confidence_text,
            )
        affected = feasibility.get("affected_rubric_ids")
        policy_affected = policy.get("affected_rubric_ids")
        if affected != [] or policy_affected != []:
            return result(
                status="not_eligible",
                environment_status="indeterminate",
                reasons=["feasible_assessment_has_affected_rubrics"] + safe_reasons,
                classification_status=classification_status_text,
                confidence=confidence_text,
            )
        return result(
            status="feasible",
            environment_status="feasible",
            reasons=safe_reasons or ["preflight_assessed_environment_feasible"],
            classification_status=classification_status_text,
            confidence=confidence_text,
            eligible=verdicts,
        )

    if classification_status != "target_external_unavailable":
        return result(
            status="not_assessed",
            environment_status="indeterminate",
            reasons=safe_reasons or ["preflight_classification_indeterminate"],
            classification_status=classification_status_text,
            confidence=confidence_text,
            affected_target_keys=affected_target_keys,
        )

    affected_value = feasibility.get("affected_rubric_ids")
    policy_affected_value = policy.get("affected_rubric_ids")
    ids_are_valid = (
        isinstance(affected_value, list)
        and bool(affected_value)
        and all(isinstance(value, str) and value for value in affected_value)
        and len(set(affected_value)) == len(affected_value)
        and isinstance(policy_affected_value, list)
        and policy_affected_value == affected_value
    )
    eligibility_failures: list[str] = []
    if confidence != "high":
        eligibility_failures.append("classification_not_high_confidence")
    if classification.get("infeasible_candidate") is not True:
        eligibility_failures.append("classification_not_infeasible_candidate")
    if (
        classification.get("adjustment_eligibility")
        != NETWORK_PREFLIGHT_ADJUSTMENT_ELIGIBILITY
    ):
        eligibility_failures.append("classification_not_adjustment_eligible")
    if feasibility.get("status") != "infeasible_candidate":
        eligibility_failures.append("feasibility_not_infeasible_candidate")
    if policy.get("adjustment_eligibility") != NETWORK_PREFLIGHT_ADJUSTMENT_ELIGIBILITY:
        eligibility_failures.append("policy_not_adjustment_eligible")
    if policy.get("dns_only") is not True:
        eligibility_failures.append("policy_not_dns_only")
    if policy.get("rubric_mapping_semantics") != RUBRIC_MAPPING_SEMANTICS:
        eligibility_failures.append("policy_mapping_semantics_invalid")
    if not ids_are_valid:
        eligibility_failures.append("affected_rubric_mapping_invalid")
    if eligibility_failures:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=eligibility_failures + safe_reasons,
            classification_status=classification_status_text,
            confidence=confidence_text,
            affected_target_keys=affected_target_keys,
        )

    assert isinstance(affected_value, list)
    affected_ids = list(affected_value)
    verdict_by_id = {item["rubric_id"]: item for item in verdicts}
    unmapped_ids = [value for value in affected_ids if value not in verdict_by_id]
    if unmapped_ids:
        return result(
            status="not_eligible",
            environment_status="indeterminate",
            reasons=["affected_rubric_not_in_task_success"] + safe_reasons,
            classification_status=classification_status_text,
            confidence=confidence_text,
            affected_ids=affected_ids,
            affected_target_keys=affected_target_keys,
        )

    affected_set = set(affected_ids)
    excluded_verdicts = [
        item
        for item in verdicts
        if item["rubric_id"] in affected_set
    ]
    excluded_ids = {item["rubric_id"] for item in excluded_verdicts}
    eligible_verdicts = [
        item for item in verdicts if item["rubric_id"] not in excluded_ids
    ]
    excluded_audit = [
        {
            "rubric_id": item["rubric_id"],
            "requirement": item["requirement"],
            "met": item["met"],
            "communicated": item["communicated"],
            "task_evidence": item["task_evidence"],
            "availability_evidence": {
                "classification_status": classification_status_text,
                "confidence": confidence_text,
                "reason_codes": list(safe_reasons),
                "affected_target_keys": list(affected_target_keys),
            },
        }
        for item in excluded_verdicts
    ]
    if not excluded_audit:
        adjustment_status = "eligible_no_change"
    elif not eligible_verdicts:
        adjustment_status = "adjusted_no_task_denominator"
    else:
        adjustment_status = "adjusted"
    environment_status = (
        "infeasible"
        if affected_set == set(raw_ids)
        else "partially_infeasible"
    )
    return result(
        status=adjustment_status,
        environment_status=environment_status,
        reasons=safe_reasons or ["target_external_unavailable"],
        classification_status=classification_status_text,
        confidence=confidence_text,
        affected_ids=affected_ids,
        eligible=eligible_verdicts,
        excluded=excluded_audit,
        affected_target_keys=affected_target_keys,
    )


def evaluate_adherence(
    *,
    persona_meta: dict[str, Any],
    conversation: list[dict[str, Any]],
    judge: JudgeCall,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    targets = persona_meta.get("evaluation_dimensions") or []
    if not targets:
        return {
            "applicable": False,
            "reason": "No evaluation_dimensions were declared for this persona.",
            "targets": [],
        }
    dimensions = persona_meta.get("dimensions") or {}
    adherence_rubric = persona_meta.get("adherence_rubric")
    if adherence_rubric is not None and not isinstance(adherence_rubric, dict):
        raise EvaluationError("adherence_rubric must be an object")
    task_id = str((task or {}).get("task_id") or "")
    task_criterion: dict[str, Any] | None = None
    if isinstance(adherence_rubric, dict):
        rubric_dimension = adherence_rubric.get("dimension")
        if targets != [rubric_dimension]:
            raise EvaluationError(
                "A matched-pair adherence rubric must target exactly one dimension"
            )
        selected_task_id = adherence_rubric.get("task_id")
        selected_criterion = adherence_rubric.get("task_criterion")
        if selected_task_id is not None or selected_criterion is not None:
            if selected_task_id != task_id:
                raise EvaluationError(
                    "Selected adherence rubric does not belong to this task"
                )
            raw_criterion = selected_criterion
        else:
            # Compatibility for early experiment artifacts that embedded the
            # full task map in each profile.
            criteria = adherence_rubric.get("task_criteria")
            if not isinstance(criteria, dict):
                raise EvaluationError(
                    "adherence_rubric must contain task_criterion or task_criteria"
                )
            if task_id not in criteria:
                return {
                    "applicable": False,
                    "reason": (
                        "The matched-pair axis is not assigned to task "
                        f"{task_id or '(unknown)'}"
                    ),
                    "targets": [],
                }
            raw_criterion = criteria[task_id]
        if not isinstance(raw_criterion, dict):
            raise EvaluationError("Task-specific adherence criterion must be an object")
        task_criterion = raw_criterion

    requested = []
    for key in targets:
        target: dict[str, Any] = {
            "attribute": key,
            "expectedValue": dimensions.get(key),
        }
        if isinstance(adherence_rubric, dict):
            target["behavioralDefinition"] = adherence_rubric.get(
                "behavioral_definition", ""
            )
            target["genericObservables"] = adherence_rubric.get(
                "generic_observables", []
            )
            target["contradictions"] = adherence_rubric.get("contradictions", [])
            target["scoreScale"] = adherence_rubric.get("score_scale", {})
            target["taskCriterion"] = task_criterion
        requested.append(target)
    utterances = _persona_utterances(conversation)
    system = (
        "You are a strict persona-adherence judge. Score only the simulated user's "
        "own utterances; ignore task success and the computer-use assistant's "
        "behavior. For each target use the supplied 0/1/2 rubric: 0 means absent or "
        "contradicted, 1 means weak/ambiguous or merely inherited from the original "
        "task, and 2 means clear task-specific expression beyond inherited wording. "
        "Set expressed=true if and only if score=2. A negative-arm value requires "
        "positive evidence such as explicit delegation or acceptance; mere silence is "
        "not enough for score 2. Never infer demographic stereotypes. Evidence must "
        "quote or tightly paraphrase a user utterance. Return strict JSON: "
        "{\"targets\":[{\"attribute\":...,\"expectedValue\":...,\"score\":0|1|2,"
        "\"expressed\":true|false,\"confidence\":0..1,\"evidence\":...,"
        "\"note\":...}]}"
    )
    user = (
        "ORIGINAL TASK (baseline wording; not persona evidence by itself):\n"
        + str((task or {}).get("confirmed_task") or "(not provided)")
        + "\n\nTARGETS AND SCORING RUBRICS:\n"
        + json.dumps(requested, ensure_ascii=False, indent=2)
        + "\n\nPERSONA UTTERANCES:\n"
        + "\n".join(f"TURN {i}: {text}" for i, text in enumerate(utterances, 1))
    )
    parsed = parse_json_object(judge(system, user, []))
    items = parsed.get("targets")
    if not isinstance(items, list):
        raise EvaluationError("Adherence judge is missing targets")
    by_attribute = {
        str(item.get("attribute")): item for item in items if isinstance(item, dict)
    }
    normalized = []
    for target in requested:
        item = by_attribute.get(target["attribute"])
        if not isinstance(item, dict) or not isinstance(item.get("expressed"), bool):
            raise EvaluationError(
                f"Adherence judge is missing {target['attribute']}"
            )
        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or score not in {0, 1, 2}:
            raise EvaluationError("Adherence score must be one of 0, 1, or 2")
        if item["expressed"] != (score == 2):
            raise EvaluationError(
                "Adherence expressed must be true if and only if score is 2"
            )
        confidence = float(item.get("confidence", 0.0))
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise EvaluationError("Adherence confidence must be in [0, 1]")
        normalized.append(
            {
                **target,
                "score": score,
                "expressed": item["expressed"],
                "confidence": confidence,
                "evidence": str(item.get("evidence", "")).strip(),
                "note": str(item.get("note", "")).strip(),
                "criterion_source": (
                    "matched_pair_task_specific"
                    if isinstance(adherence_rubric, dict)
                    else "generic_dimension"
                ),
            }
        )
    return {"applicable": True, "targets": normalized}


def evaluate_alignment(
    *,
    task: dict[str, Any],
    persona_meta: dict[str, Any],
    conversation: list[dict[str, Any]],
    action_history: str,
    final_answer: str,
    communication: dict[str, Any],
    screenshots: list[Path],
    judge: JudgeCall,
) -> dict[str, Any]:
    """Judge outcome fit using only preferences communicated to the CUA."""
    # Matched-pair scoring instructions belong only to adherence. Hiding them
    # here avoids priming the independent outcome-alignment judgement.
    alignment_profile = {
        key: value
        for key, value in persona_meta.items()
        if key not in {"adherence_rubric", "matched_pair"}
    }
    system = (
        "You evaluate whether a computer-use assistant served a simulated user's "
        "communicated preferences. Task completion is scored elsewhere. Use browser "
        "evidence and the final answer, but do not penalize the CUA for latent profile "
        "attributes the user never communicated. Return strict JSON with fields "
        "persona_alignment_status (aligned|partially_aligned|misaligned|not_applicable), "
        "persona_alignment_score (0..1), persona_preference_axis_primary, "
        "persona_signal_source, persona_alignment_explanation, and persona_constraints. "
        "persona_preference_axis_primary must be privacy|frugality|convenience|"
        "accessibility|trust|familiarity|speed|quality|risk_aversion|other. "
        "persona_signal_source must be persona_profile|task_instruction|dialog_context|"
        "history_or_memory|multiple. "
        "Each constraint needs key, type (privacy|budget|accessibility|familiarity|"
        "brand_preference|speed|quality_bar|risk_limit|other), priority (hard|soft), "
        "status (satisfied|partially_satisfied|violated|not_triggered|unknown), "
        "source (profile|task|dialog), communicated (boolean), and evidence."
        " If a constraint concept is not exactly one of the listed types (for "
        "example trust), use type other; trust is valid only as a preference axis."
        " A constraint with communicated=false must have status not_triggered or "
        "unknown and must not affect the overall status or score. A non-not_applicable "
        "overall status requires at least one communicated constraint."
    )
    user = (
        "PERSONA PROFILE (judge-only):\n"
        + json.dumps(alignment_profile, ensure_ascii=False, indent=2)
        + "\n\nORIGINAL TASK (judge-only):\n"
        + task["confirmed_task"]
        + "\n\nUSER/CUA CONVERSATION:\n"
        + json.dumps(conversation, ensure_ascii=False, indent=2)
        + "\n\nCOMMUNICATION COVERAGE:\n"
        + json.dumps(communication, ensure_ascii=False, indent=2)
        + "\n\nACTION HISTORY:\n"
        + action_history
        + "\n\nFINAL CUA ANSWER:\n"
        + (final_answer or "(none)")
        + f"\n\nAttached screenshots: {len(screenshots)}."
    )
    parsed = parse_json_object(judge(system, user, screenshots))
    status = str(parsed.get("persona_alignment_status", ""))
    if status not in ALIGNMENT_STATUSES:
        raise EvaluationError(f"Invalid persona_alignment_status: {status!r}")
    score = float(parsed.get("persona_alignment_score", 0.0))
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise EvaluationError("persona_alignment_score must be in [0, 1]")
    preference_axis = str(parsed.get("persona_preference_axis_primary", ""))
    if preference_axis not in PREFERENCE_AXES:
        raise EvaluationError(
            f"Invalid persona_preference_axis_primary: {preference_axis!r}"
        )
    signal_source = str(parsed.get("persona_signal_source", ""))
    if signal_source not in SIGNAL_SOURCES:
        raise EvaluationError(f"Invalid persona_signal_source: {signal_source!r}")
    constraints = parsed.get("persona_constraints") or []
    if not isinstance(constraints, list):
        raise EvaluationError("persona_constraints must be a list")
    normalized_constraints = []
    for i, item in enumerate(constraints, start=1):
        if not isinstance(item, dict):
            raise EvaluationError(f"persona constraint #{i} must be an object")
        raw_ctype_value = item.get("type", "other")
        if not isinstance(raw_ctype_value, str):
            raise EvaluationError("Constraint type must be a string")
        raw_ctype = raw_ctype_value.strip()
        ctype = raw_ctype
        priority = str(item.get("priority", "soft"))
        cstatus = str(item.get("status", "unknown"))
        if ctype not in CONSTRAINT_TYPES:
            # The contract deliberately provides ``other`` as the lossless
            # bucket for judge-authored semantic labels (for example
            # ``trust``).  Preserve the original label for auditability while
            # keeping downstream context facets inside the declared enum.
            ctype = "other"
        if priority not in CONSTRAINT_PRIORITIES:
            raise EvaluationError(f"Invalid constraint priority: {priority!r}")
        if cstatus not in CONSTRAINT_STATUSES:
            raise EvaluationError(f"Invalid constraint status: {cstatus!r}")
        if not isinstance(item.get("communicated"), bool):
            raise EvaluationError("Constraint communicated must be boolean")
        normalized = {
            "key": str(item.get("key", f"constraint_{i}")),
            "type": ctype,
            "priority": priority,
            "status": cstatus,
            "source": str(item.get("source", "dialog")),
            "communicated": item["communicated"],
            "evidence": str(item.get("evidence", "")).strip(),
        }
        if raw_ctype not in CONSTRAINT_TYPES:
            normalized["type_original"] = raw_ctype
        normalized_constraints.append(normalized)
    latent_scored = [
        item
        for item in normalized_constraints
        if not item["communicated"]
        and item["status"] not in {"not_triggered", "unknown"}
    ]
    if latent_scored:
        raise EvaluationError(
            "Uncommunicated persona constraints must not be scored as satisfied or violated"
        )
    communicated_triggered = [
        item
        for item in normalized_constraints
        if item["communicated"]
        and item["status"] not in {"not_triggered", "unknown"}
    ]
    if status != "not_applicable" and not communicated_triggered:
        raise EvaluationError(
            "Persona alignment cannot be applicable without a communicated constraint"
        )
    if status == "not_applicable" and communicated_triggered:
        raise EvaluationError(
            "Persona alignment cannot be not_applicable with a triggered constraint"
        )
    return {
        "persona_alignment_status": status,
        "persona_alignment_score": score,
        "persona_preference_axis_primary": preference_axis,
        "persona_signal_source": signal_source,
        "persona_alignment_explanation": str(
            parsed.get("persona_alignment_explanation", "")
        ),
        "persona_constraints": normalized_constraints,
    }


def persona_contexts(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert alignment output to MatrAIx shared-core context/facet names."""
    contexts = [
        {
            "key": "persona_alignment.primary",
            "label": "Persona alignment",
            "contextType": "persona_alignment",
            "facets": [
                {
                    "key": "persona_alignment_status",
                    "label": "Persona alignment status",
                    "role": "primary",
                    "kind": "categorical",
                    "value": alignment["persona_alignment_status"],
                },
                {
                    "key": "persona_alignment_score",
                    "label": "Persona alignment score",
                    "role": "score",
                    "kind": "numerical",
                    "value": alignment["persona_alignment_score"],
                },
                {
                    "key": "persona_preference_axis_primary",
                    "label": "Primary persona axis",
                    "role": "primary",
                    "kind": "categorical",
                    "value": alignment["persona_preference_axis_primary"],
                },
                {
                    "key": "persona_signal_source",
                    "label": "Persona signal source",
                    "role": "evidence",
                    "kind": "categorical",
                    "value": alignment["persona_signal_source"],
                },
                {
                    "key": "persona_alignment_explanation",
                    "label": "Persona alignment explanation",
                    "role": "explanation",
                    "kind": "textual",
                    "value": alignment["persona_alignment_explanation"],
                },
            ],
        }
    ]
    for item in alignment["persona_constraints"]:
        contexts.append(
            {
                "key": f"persona_constraint.{item['key']}",
                "label": f"Persona constraint: {item['key']}",
                "contextType": "persona_constraint",
                "facets": [
                    {"key": "persona_constraint_key", "label": "Persona constraint key", "role": "evidence", "kind": "categorical", "value": item["key"]},
                    {"key": "persona_constraint_type", "label": "Persona constraint type", "role": "primary", "kind": "categorical", "value": item["type"]},
                    {"key": "persona_constraint_priority", "label": "Persona constraint priority", "role": "evidence", "kind": "categorical", "value": item["priority"]},
                    {"key": "persona_constraint_status", "label": "Persona constraint status", "role": "primary", "kind": "categorical", "value": item["status"]},
                    {"key": "persona_constraint_evidence", "label": "Persona constraint evidence", "role": "explanation", "kind": "textual", "value": item["evidence"]},
                ],
            }
        )
    return contexts
