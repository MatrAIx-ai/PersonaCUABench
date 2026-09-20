#!/usr/bin/env python3
"""Run the optional two-judge P1--P5 person-experience evaluation.

This phase is deliberately separate from task-success judging. It sends the
persona profile, task, transcript, action history, final answer, and final tab
state to two independent OpenAI-compatible judge calls. It never sends the
trajectory screenshots, never averages the two judges, and writes nothing in
``--preview``/``--print-prompt`` mode.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


if __package__ in {None, ""}:  # Support direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personacuabench.core import (  # noqa: E402
    DEFAULT_RESULTS_DIR,
    DEFAULT_TASKS_PATH,
    ConfigurationError,
    atomic_write_json,
)
from personacuabench.evaluation import EvaluationError, parse_json_object  # noqa: E402
from personacuabench.judge import (  # noqa: E402
    DEFAULT_MODEL,
    EndpointConfig,
    JudgeConfigurationError,
    OpenAIJudgeCall,
    RunArtifacts,
    _verify_source_artifacts,
    endpoint_from_environment,
    load_run_artifacts,
)
from personacuabench.prompting import load_prompt  # noqa: E402


DIMENSIONS = (
    "P1_asked_for",
    "P2_readable_for_them",
    "P3_actionable",
    "P4_gap_handling",
    "P5_overall",
)
_OUTPUT_KEYS = frozenset(
    (*DIMENSIONS, "unmet_requests", "missed_gaps", "judge_confidence")
)
_SYSTEM_PROMPT = (
    "You are a strict evaluation judge. Follow the supplied scoring protocol "
    "and return only the requested JSON object."
)
DEFAULT_VALIDATION_ATTEMPTS = 3


class ExperienceJudgeError(RuntimeError):
    """Raised when an experience judge response violates the protocol."""


JudgeCall = Callable[[str, str, list[Path]], str]


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _persona_description(artifacts: RunArtifacts) -> str:
    if artifacts.persona_mode == "none":
        return (
            "Control arm: no persona. This person sent the expert brief "
            "verbatim, so treat them as a demanding expert who asked for "
            "every item in it."
        )
    # Upload only the semantic identity needed by this judge.  Runner metadata
    # also contains local paths, hashes, renderer names, and experiment/audit
    # fields that are irrelevant to the person's experience.
    meta = artifacts.persona_meta
    profile = {
        key: copy.deepcopy(meta[key])
        for key in ("persona_id", "display_name", "dimensions")
        if meta.get(key) is not None
    }
    return json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True)


def _turn_content(turn: Mapping[str, Any]) -> str:
    for key in ("content", "answer", "persona_answer", "question", "response"):
        value = turn.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _conversation_text(turns: Sequence[Mapping[str, Any]]) -> str:
    rendered: list[str] = []
    for turn in turns:
        content = _turn_content(turn)
        if not content:
            continue
        role = str(turn.get("role", "")).strip().lower()
        event = str(turn.get("event_type", "")).strip().lower()
        if role in {"user", "persona"} or event in {
            "opening",
            "opening_request",
            "persona_answer",
        }:
            label = "PERSON"
        elif role == "system":
            label = "SYSTEM"
        else:
            label = "ASSISTANT"
        rendered.append(f"{label}: {content}")
    return "\n".join(rendered) or "(none)"


def _open_tabs(artifacts: RunArtifacts) -> Any:
    """Return the final tab state already validated by ``load_run_artifacts``."""
    candidate = artifacts.run_dir / "open_tabs.json"
    if candidate.is_file():
        try:
            resolved = candidate.resolve()
            relative = str(resolved.relative_to(artifacts.run_dir.resolve()))
            raw = resolved.read_bytes()
            expected = artifacts.source_artifact_sha256.get(relative)
            if expected is None or _sha256_bytes(raw) != expected:
                raise ExperienceJudgeError(
                    "Final tab state changed after run artifacts were loaded"
                )
            return json.loads(raw)
        except ValueError as exc:
            raise ExperienceJudgeError(
                "Final tab state resolves outside the run directory"
            ) from exc
        except ExperienceJudgeError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperienceJudgeError(f"Cannot read final tab state: {exc}") from exc
    raw = _nested(artifacts.result, "run", "open_tabs")
    if raw is None:
        raw = artifacts.result.get("open_tabs")
    return raw if raw is not None else []


def build_prompt(artifacts: RunArtifacts, *, template: str | None = None) -> str:
    """Render the versioned experience prompt from one immutable run snapshot."""
    prompt_template = template if template is not None else load_prompt("experience_judge")
    return prompt_template.format(
        persona=_persona_description(artifacts),
        task=artifacts.task["confirmed_task"],
        conversation=_conversation_text(artifacts.conversation),
        actions=artifacts.action_history,
        answer=artifacts.final_answer or "(the assistant produced no answer)",
        tabs=json.dumps(_open_tabs(artifacts), ensure_ascii=False, indent=2),
    )


def valid_score(value: Any) -> int | None:
    """Return a valid numeric dimension score; ``n/a`` remains non-comparable."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or not numeric.is_integer():
        return None
    score = int(numeric)
    return score if 1 <= score <= 5 else None


def validate_judge_output(raw: str | Mapping[str, Any]) -> dict[str, Any]:
    """Parse and strictly validate one judge's exact P1--P5 response shape."""
    if isinstance(raw, str):
        try:
            parsed = parse_json_object(raw)
        except EvaluationError as exc:
            raise ExperienceJudgeError(str(exc)) from exc
    elif isinstance(raw, Mapping):
        parsed = copy.deepcopy(dict(raw))
    else:
        raise ExperienceJudgeError("Judge response must be JSON text or an object")

    actual_keys = frozenset(parsed)
    if actual_keys != _OUTPUT_KEYS:
        missing = sorted(_OUTPUT_KEYS - actual_keys)
        extra = sorted(actual_keys - _OUTPUT_KEYS)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ExperienceJudgeError(
            "Experience judge returned the wrong top-level keys ("
            + "; ".join(details)
            + ")"
        )

    for dimension in DIMENSIONS:
        item = parsed[dimension]
        if not isinstance(item, Mapping) or frozenset(item) != {"score", "reason"}:
            raise ExperienceJudgeError(
                f"{dimension} must contain exactly 'score' and 'reason'"
            )
        score = item["score"]
        if score != "n/a" and valid_score(score) is None:
            raise ExperienceJudgeError(
                f"{dimension}.score must be an integer 1-5 or 'n/a'"
            )
        reason = item["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ExperienceJudgeError(f"{dimension}.reason must be non-empty text")
        parsed[dimension] = {
            "score": "n/a" if score == "n/a" else valid_score(score),
            "reason": reason.strip(),
        }

    for key in ("unmet_requests", "missed_gaps"):
        values = parsed[key]
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() for value in values
        ):
            raise ExperienceJudgeError(f"{key} must be a list of non-empty strings")
        parsed[key] = [value.strip() for value in values]

    confidence = parsed["judge_confidence"]
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0 <= float(confidence) <= 1
    ):
        raise ExperienceJudgeError("judge_confidence must be a finite number from 0 to 1")
    parsed["judge_confidence"] = float(confidence)
    return parsed


def agreement(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Compare judge scores without combining or averaging them."""
    comparison: dict[str, Any] = {}
    comparable = 0
    within_one = 0
    for dimension in DIMENSIONS:
        raw_a = (a.get(dimension) or {}).get("score")
        raw_b = (b.get(dimension) or {}).get("score")
        score_a = valid_score(raw_a)
        score_b = valid_score(raw_b)
        if score_a is None or score_b is None:
            comparison[dimension] = {
                "judge_a": raw_a,
                "judge_b": raw_b,
                "delta": None,
                "absolute_delta": None,
                "within_one": None,
            }
            continue
        delta = score_a - score_b
        is_within_one = abs(delta) <= 1
        comparable += 1
        within_one += int(is_within_one)
        comparison[dimension] = {
            "judge_a": score_a,
            "judge_b": score_b,
            "delta": delta,
            "absolute_delta": abs(delta),
            "within_one": is_within_one,
        }
    comparison.update(
        {
            "comparable_dimensions": comparable,
            "within_one_dimensions": within_one,
            "within_one_rate": (within_one / comparable if comparable else None),
            "scores_averaged": False,
        }
    )
    return comparison


def _score_once(
    *,
    prompt: str,
    judge_call: JudgeCall,
    endpoint_meta: Mapping[str, Any],
    slot: str,
    validation_attempts: int,
) -> dict[str, Any]:
    failures: list[str] = []
    for attempt in range(1, validation_attempts + 1):
        try:
            raw = judge_call(_SYSTEM_PROMPT, prompt, [])
            parsed = validate_judge_output(raw)
        except Exception as exc:
            failures.append(f"{type(exc).__name__}: {exc}")
            continue
        return {
            "slot": slot,
            **dict(endpoint_meta),
            "validation_attempts": attempt,
            **parsed,
        }
    last = failures[-1] if failures else "judge returned no result"
    raise ExperienceJudgeError(
        f"Judge {slot} failed validation after {validation_attempts} attempt(s): {last}"
    )


def assemble_experience(
    *,
    artifacts: RunArtifacts,
    judge_a: JudgeCall,
    judge_b: JudgeCall,
    endpoint_a: Mapping[str, Any],
    endpoint_b: Mapping[str, Any],
    validation_attempts: int = DEFAULT_VALIDATION_ATTEMPTS,
) -> dict[str, Any]:
    """Run two judges and assemble one auditable, non-aggregated result."""
    if validation_attempts < 1:
        raise ExperienceJudgeError("validation_attempts must be at least 1")
    template = load_prompt("experience_judge")
    prompt = build_prompt(artifacts, template=template)
    result_a = _score_once(
        prompt=prompt,
        judge_call=judge_a,
        endpoint_meta=endpoint_a,
        slot="a",
        validation_attempts=validation_attempts,
    )
    result_b = _score_once(
        prompt=prompt,
        judge_call=judge_b,
        endpoint_meta=endpoint_b,
        slot="b",
        validation_attempts=validation_attempts,
    )
    manifest_hash = _sha256_text(
        json.dumps(
            artifacts.source_artifact_sha256,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return {
        "schema_version": "persona-cua-experience.v1",
        "status": "complete",
        "judged_at": _utc_now(),
        "protocol": {
            "dimensions": list(DIMENSIONS),
            "judge_slots": 2,
            "independent_calls": True,
            "scores_averaged": False,
            "screenshots_sent": 0,
            "application_call_attempts": (
                result_a["validation_attempts"] + result_b["validation_attempts"]
            ),
        },
        "prompt": {
            "name": "experience_judge",
            "template_sha256": _sha256_text(template),
            "rendered_sha256": _sha256_text(prompt),
        },
        "scope": {
            "source_result_sha256": artifacts.source_result_sha256,
            "source_artifact_manifest_sha256": manifest_hash,
            "trajectory_events": len(artifacts.trajectory),
            "conversation_turns": len(artifacts.conversation),
        },
        "judge_a": result_a,
        "judge_b": result_b,
        "agreement": agreement(result_a, result_b),
    }


def _commit_experience(artifacts: RunArtifacts, experience: Mapping[str, Any]) -> None:
    """Atomically merge experience scores if no source evidence has changed."""
    _verify_source_artifacts(artifacts)
    try:
        current_bytes = artifacts.result_path.read_bytes()
    except OSError as exc:
        raise ExperienceJudgeError(f"Cannot re-read result before merge: {exc}") from exc
    if _sha256_bytes(current_bytes) != artifacts.source_result_sha256:
        raise ExperienceJudgeError(
            "result.json changed while experience judging; refusing to overwrite newer state"
        )
    try:
        current = json.loads(current_bytes)
    except json.JSONDecodeError as exc:
        raise ExperienceJudgeError(f"result.json became invalid JSON: {exc}") from exc
    if not isinstance(current, dict):
        raise ExperienceJudgeError("result.json stopped being an object")
    merged = copy.deepcopy(current)
    merged["experience"] = copy.deepcopy(dict(experience))
    # Experience scoring is additive. It must not promote an agent-only run to
    # the standard judge's terminal ``complete`` status.
    atomic_write_json(artifacts.result_path, merged)


def _selected_models(args: argparse.Namespace) -> tuple[str, str]:
    common = (
        os.environ.get("JUDGE_MODEL", "").strip()
        or os.environ.get("AZURE_OPENAI_JUDGE_MODEL", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
        or DEFAULT_MODEL
    )
    model_a = (
        args.judge_a
        or os.environ.get("EXPERIENCE_JUDGE_A_MODEL", "").strip()
        or common
    )
    model_b = (
        args.judge_b
        or os.environ.get("EXPERIENCE_JUDGE_B_MODEL", "").strip()
        or model_a
    )
    return model_a, model_b


def _preview_payload(
    artifacts: RunArtifacts, *, model_a: str, model_b: str
) -> dict[str, Any]:
    template = load_prompt("experience_judge")
    prompt = build_prompt(artifacts, template=template)
    return {
        "status": "preview",
        "offline": True,
        "api_calls_made": 0,
        "result_writes": 0,
        "result_path": str(artifacts.result_path),
        "task_id": artifacts.task["task_id"],
        "persona": {
            "name": artifacts.persona_name,
            "mode": artifacts.persona_mode,
        },
        "evidence": {
            "trajectory_events": len(artifacts.trajectory),
            "conversation_turns": len(artifacts.conversation),
            "has_final_answer": bool(artifacts.final_answer),
            "screenshots_sent": 0,
        },
        "planned_judges": [
            {"slot": "a", "model": model_a},
            {"slot": "b", "model": model_b},
        ],
        "prompt": {
            "name": "experience_judge",
            "template_sha256": _sha256_text(template),
            "rendered_sha256": _sha256_text(prompt),
            "characters": len(prompt),
        },
        "scores_averaged": False,
    }


def _result_paths(runs: Sequence[Path], results_dir: Path) -> list[Path]:
    if runs:
        raw_paths = list(runs)
    else:
        root = results_dir.expanduser().resolve()
        raw_paths = sorted(root.rglob("result.json")) if root.is_dir() else []
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        path = raw.expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
    if not paths:
        raise ExperienceJudgeError(
            "No runs selected and no result.json files found under "
            f"{results_dir.expanduser().resolve()}"
        )
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly score person experience for one or more completed "
            "PersonaCUABench runs with two independent text-only judge calls."
        )
    )
    parser.add_argument(
        "runs",
        nargs="*",
        type=Path,
        help=(
            "Run directories or result.json files. If omitted, recursively "
            "scan --results."
        ),
    )
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--judge-a", default=None, help="Model for judge A")
    parser.add_argument("--judge-b", default=None, help="Model for judge B")
    parser.add_argument("--judge-a-reasoning-effort", default=None)
    parser.add_argument("--judge-b-reasoning-effort", default=None)
    parser.add_argument(
        "--validation-attempts",
        type=int,
        default=DEFAULT_VALIDATION_ATTEMPTS,
        help=(
            "Maximum calls per judge when output is invalid or a request fails "
            f"(default: {DEFAULT_VALIDATION_ATTEMPTS})"
        ),
    )
    parser.add_argument(
        "--force",
        "--redo",
        dest="force",
        action="store_true",
        help="Replace an existing complete experience evaluation",
    )
    parser.add_argument(
        "--preview",
        "--offline",
        dest="preview",
        action="store_true",
        help="Validate and print manifests without API calls or writes",
    )
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="Print the rendered prompt for exactly one run; no API calls or writes",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.validation_attempts < 1:
        raise ExperienceJudgeError("--validation-attempts must be at least 1")
    paths = _result_paths(args.runs, args.results)
    artifacts: list[RunArtifacts] = []
    for path in paths:
        try:
            artifacts.append(
                load_run_artifacts(
                    path,
                    tasks_path=args.tasks.expanduser().resolve(),
                )
            )
        except (ConfigurationError, JudgeConfigurationError) as exc:
            if args.runs:
                raise
            print(f"Skipping ineligible result {path}: {exc}", file=sys.stderr)
    if not artifacts:
        raise ExperienceJudgeError(
            f"No eligible completed runs found under {args.results.expanduser().resolve()}"
        )
    model_a, model_b = _selected_models(args)

    if args.print_prompt:
        if len(artifacts) != 1:
            raise ExperienceJudgeError("--print-prompt requires exactly one run")
        print(build_prompt(artifacts[0]))
        return 0

    if args.preview:
        payloads = [
            _preview_payload(item, model_a=model_a, model_b=model_b)
            for item in artifacts
        ]
        print(json.dumps(payloads[0] if len(payloads) == 1 else payloads, indent=2))
        return 0

    pending: list[RunArtifacts] = []
    for item in artifacts:
        existing = item.result.get("experience")
        if (
            not args.force
            and isinstance(existing, Mapping)
            and existing.get("status") == "complete"
        ):
            print(f"Already experience-judged; unchanged: {item.result_path}")
        else:
            pending.append(item)
    if not pending:
        return 0

    effort_a = (
        args.judge_a_reasoning_effort
        or os.environ.get("EXPERIENCE_JUDGE_A_REASONING_EFFORT", "").strip()
        or None
    )
    effort_b = (
        args.judge_b_reasoning_effort
        or os.environ.get("EXPERIENCE_JUDGE_B_REASONING_EFFORT", "").strip()
        or None
    )
    config_a: EndpointConfig = endpoint_from_environment(
        model=model_a, reasoning_effort=effort_a
    )
    config_b: EndpointConfig = endpoint_from_environment(
        model=model_b, reasoning_effort=effort_b
    )
    # Separate transport instances make A and B independent calls even when a
    # single Azure deployment/model is intentionally used for both slots.
    call_a = OpenAIJudgeCall(config_a)
    call_b = OpenAIJudgeCall(config_b)

    for item in pending:
        print(
            f"Experience-judging {item.task['task_id']} ({item.persona_name}) with "
            f"A={config_a.model}, B={config_b.model}. Sending text evidence twice; "
            "sending no screenshots."
        )
        experience = assemble_experience(
            artifacts=item,
            judge_a=call_a,
            judge_b=call_b,
            endpoint_a=config_a.public_meta,
            endpoint_b=config_b.public_meta,
            validation_attempts=args.validation_attempts,
        )
        _commit_experience(item, experience)
        print(f"Experience evaluation written atomically: {item.result_path}")
        for dimension in DIMENSIONS:
            score_a = experience["judge_a"][dimension]["score"]
            score_b = experience["judge_b"][dimension]["score"]
            print(f"  {dimension:22} A={score_a!s:>3} B={score_b!s:>3}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ConfigurationError,
        EvaluationError,
        ExperienceJudgeError,
        JudgeConfigurationError,
    ) as exc:
        print(f"experience judge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        # Provider/network failures happen before the atomic merge. Leave the
        # existing result untouched and report a concise automation error.
        print(
            f"experience judge failed: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        raise SystemExit(1) from None
