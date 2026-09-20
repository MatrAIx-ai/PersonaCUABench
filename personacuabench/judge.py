#!/usr/bin/env python3
"""Explicit, post-run judging for one PersonaCUABench run.

This command is intentionally separate from :mod:`personacuabench.run`: browser
artifacts are uploaded only when a user invokes this file without
``--preview``/``--offline``.  A successful invocation atomically adds a
``judgement`` object to the run's ``result.json``.  No partial judge result is
published when an API call, validation step, or final write fails.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import mimetypes
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


if __package__ in {None, ""}:  # Support direct script execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from personacuabench.core import (  # noqa: E402
    DEFAULT_ODYSSEYS_DIR,
    DEFAULT_TASKS_PATH,
    ConfigurationError,
    atomic_write_json,
    load_tasks,
    validate_task,
)
from personacuabench.evaluation import (  # noqa: E402
    compute_availability_adjustment,
    EvaluationError,
    evaluate_adherence,
    evaluate_alignment,
    evaluate_communication,
    merge_task_and_communication,
    persona_contexts,
    task_verdicts_from_standard,
)
from personacuabench.network_preflight import (  # noqa: E402
    PreflightResultError,
    validate_preflight_document,
)


DEFAULT_STANDARD_SCRIPT = (
    DEFAULT_ODYSSEYS_DIR / "scripts" / "python" / "run_full_trajectory_per_rubric.py"
)
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_MAX_COMPLETION_TOKENS = 8192
_TASK_ID = re.compile(r"[0-9a-f]{40}", re.IGNORECASE)


class JudgeConfigurationError(ValueError):
    """Raised when a run or endpoint is not judgeable as configured."""


class StandardJudgeError(RuntimeError):
    """Raised when the Odysseys rubric judge did not finish cleanly."""


@dataclass(frozen=True)
class EndpointConfig:
    """OpenAI-compatible endpoint settings; the credential is never serialized."""

    model: str
    provider: str
    api_key: str = field(repr=False)
    base_url: str | None = None
    timeout_seconds: float = 180.0
    max_retries: int = 5
    max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS
    reasoning_effort: str | None = None

    @property
    def public_meta(self) -> dict[str, Any]:
        # Deliberately whitelist values.  In particular, never serialize the
        # endpoint object or its api_key.
        return {
            "transport": "openai-compatible-chat-completions",
            "provider": self.provider,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "max_completion_tokens": self.max_completion_tokens,
        }


@dataclass(frozen=True)
class RunArtifacts:
    result_path: Path
    result: dict[str, Any]
    source_result_sha256: str
    run_dir: Path
    task: dict[str, Any]
    persona_name: str
    persona_mode: str
    persona_meta: dict[str, Any]
    trajectory_path: Path
    trajectory: list[dict[str, Any]]
    conversation_path: Path
    conversation: list[dict[str, Any]]
    screenshots: list[Path]
    network_preflight_path: Path | None
    network_preflight: dict[str, Any] | None
    network_preflight_integrity_status: str
    source_artifact_sha256: dict[str, str]
    action_history: str
    final_answer: str


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative_run_path(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError as exc:
        raise JudgeConfigurationError(
            f"Artifact path is outside the run directory: {path}"
        ) from exc


def _source_manifest(run_dir: Path, paths: Iterable[Path]) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in paths:
        relative = _relative_run_path(run_dir, path)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise JudgeConfigurationError(f"Cannot read run artifact {path}: {exc}") from exc
        manifest[relative] = _sha256_bytes(raw)
    return dict(sorted(manifest.items()))


def _verify_source_artifacts(artifacts: RunArtifacts) -> None:
    for relative, expected in artifacts.source_artifact_sha256.items():
        candidate = (artifacts.run_dir / relative).resolve()
        _relative_run_path(artifacts.run_dir, candidate)
        try:
            current = candidate.read_bytes()
        except OSError as exc:
            raise JudgeConfigurationError(
                f"Source artifact changed while judging ({relative}): {exc}"
            ) from exc
        if _sha256_bytes(current) != expected:
            raise JudgeConfigurationError(
                f"Source artifact changed while judging: {relative}"
            )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JudgeConfigurationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise JudgeConfigurationError(f"Invalid JSON in {path}: {exc}") from exc


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise JudgeConfigurationError(f"Cannot read {path}: {exc}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JudgeConfigurationError(
                f"Invalid JSON at {path}:{line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise JudgeConfigurationError(
                f"Expected an object at {path}:{line_number}"
            )
        rows.append(row)
    if not rows:
        raise JudgeConfigurationError(f"Artifact is empty: {path}")
    return rows


def _nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _first(value: Any, paths: Iterable[tuple[str, ...]]) -> Any:
    for path in paths:
        candidate = _nested(value, *path)
        if candidate is not None and candidate != "":
            return candidate
    return None


def resolve_result_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path.is_file():
        if path.name != "result.json":
            raise JudgeConfigurationError(
                f"Expected result.json, got a different file: {path}"
            )
        return path
    if not path.is_dir():
        raise JudgeConfigurationError(f"Run path does not exist: {path}")
    direct = path / "result.json"
    if direct.is_file():
        return direct
    nested = list(path.rglob("result.json"))
    if len(nested) == 1:
        return nested[0].resolve()
    if not nested:
        raise JudgeConfigurationError(f"No result.json found in run directory: {path}")
    raise JudgeConfigurationError(
        f"Run directory is ambiguous ({len(nested)} result files): {path}"
    )


def _task_id_from_result(result: Mapping[str, Any], result_path: Path) -> str | None:
    raw = _first(
        result,
        (
            ("task_id",),
            ("task", "task_id"),
            ("run", "task_id"),
            ("metadata", "task_id"),
        ),
    )
    if isinstance(raw, str) and _TASK_ID.fullmatch(raw):
        return raw.lower()
    for part in reversed(result_path.parts):
        match = _TASK_ID.fullmatch(part)
        if match:
            return match.group(0).lower()
    return None


def _load_task(
    result: Mapping[str, Any], result_path: Path, tasks_path: Path
) -> dict[str, Any]:
    embedded = result.get("task")
    if isinstance(embedded, dict) and all(
        key in embedded for key in ("task_id", "confirmed_task", "rubrics")
    ):
        return validate_task(copy.deepcopy(embedded))

    tasks = load_tasks(tasks_path)
    task_id = _task_id_from_result(result, result_path)
    if task_id:
        match = next((task for task in tasks if task["task_id"] == task_id), None)
        if match is not None:
            return copy.deepcopy(match)

    raw_number = _first(
        result,
        (("task_number",), ("task", "number"), ("metadata", "task_number")),
    )
    if isinstance(raw_number, int) and not isinstance(raw_number, bool):
        if 1 <= raw_number <= len(tasks):
            return copy.deepcopy(tasks[raw_number - 1])
    raise JudgeConfigurationError(
        f"Cannot resolve this run to a task in {tasks_path}; record task_id in result.json"
    )


def _resolve_artifact_path(
    run_dir: Path, result: Mapping[str, Any], filename: str, references: Sequence[tuple[str, ...]]
) -> Path:
    run_root = run_dir.resolve()

    def inside_run(path: Path) -> Path | None:
        resolved = path.resolve()
        try:
            resolved.relative_to(run_root)
        except ValueError:
            return None
        return resolved if resolved.is_file() else None

    direct = inside_run(run_root / filename)
    if direct is not None:
        return direct
    raw = _first(result, references)
    if isinstance(raw, str) and raw.strip():
        candidate = Path(raw).expanduser()
        choice = candidate if candidate.is_absolute() else run_root / candidate
        resolved = inside_run(choice)
        if resolved is not None:
            return resolved
        if choice.exists():
            raise JudgeConfigurationError(
                f"Referenced {filename} is outside the run directory"
            )
    raise JudgeConfigurationError(f"Missing required {filename} for run: {run_dir}")


def _load_optional_network_preflight(
    run_dir: Path, result: Mapping[str, Any]
) -> tuple[Path | None, dict[str, Any] | None, str]:
    """Load the optional same-run preflight without risking raw-score judging.

    Availability adjustment is diagnostic and must never make the original
    Odysseys judge unusable.  The runner records a SHA-256 next to the artifact;
    only an exact match is eligible for adjustment.  Missing, malformed, or
    mismatched artifacts are reported to the scorer as unverified instead of
    being trusted or silently repaired.
    """
    raw_reference = _nested(result, "artifacts", "network_preflight")
    filename = raw_reference if isinstance(raw_reference, str) else "network_preflight.json"
    candidate = (run_dir / filename).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError:
        return None, None, "path_outside_run"
    if not candidate.is_file():
        return None, None, "absent"
    try:
        raw_bytes = candidate.read_bytes()
        payload = json.loads(raw_bytes)
    except (OSError, json.JSONDecodeError):
        return candidate, None, "invalid"
    if not isinstance(payload, dict):
        return candidate, None, "invalid"
    expected = _nested(result, "artifacts", "network_preflight_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        return candidate, payload, "missing_hash"
    if _sha256_bytes(raw_bytes) != expected:
        return candidate, payload, "hash_mismatch"
    try:
        validate_preflight_document(payload)
    except PreflightResultError:
        return candidate, payload, "contract_invalid"
    return candidate, payload, "verified"


def _persona_mapping(result: Mapping[str, Any]) -> dict[str, Any]:
    # A runner may keep the human-readable name in ``persona`` and the session
    # metadata in ``persona_meta``.  Select the first *mapping*, not merely the
    # first non-empty value.
    for path in (
        ("persona",),
        ("persona_meta",),
        ("run", "persona"),
        ("metadata", "persona"),
    ):
        raw = _nested(result, *path)
        if isinstance(raw, Mapping):
            return copy.deepcopy(dict(raw))
    return {}


def _persona_scalar(result: Mapping[str, Any], persona: Mapping[str, Any]) -> str | None:
    candidates = [
        result.get("persona_name"),
        persona.get("persona_name"),
        persona.get("name"),
        persona.get("slug"),
        _nested(persona, "persona", "persona_id"),
        persona.get("persona_id"),
    ]
    raw_persona = result.get("persona")
    if isinstance(raw_persona, str):
        candidates.insert(0, raw_persona)
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _find_profile_mapping(persona: Mapping[str, Any]) -> dict[str, Any]:
    current: Mapping[str, Any] = persona
    # Session metadata nests the profile under ``persona``; some runners add a
    # further ``meta`` wrapper.  Only walk these known wrappers.
    for _ in range(4):
        if "evaluation_dimensions" in current or "dimensions" in current:
            return copy.deepcopy(dict(current))
        next_value = current.get("persona")
        if not isinstance(next_value, Mapping):
            next_value = current.get("meta")
        if not isinstance(next_value, Mapping):
            break
        current = next_value
    return copy.deepcopy(dict(current)) if current else {}


def _normalize_persona(
    result: Mapping[str, Any], run_dir: Path
) -> tuple[str, str, dict[str, Any]]:
    persona = _persona_mapping(result)
    name = _persona_scalar(result, persona)
    directory_name = run_dir.name.split("__", 1)[0]
    if name is None and directory_name:
        name = directory_name

    modes = [persona.get("mode"), _nested(persona, "meta", "mode")]
    normalized_modes = {
        str(value).strip().lower() for value in modes if isinstance(value, str)
    }
    if (name or "").lower() == "none" or "none" in normalized_modes:
        return "none", "none", {}

    # Judge only the profile values embedded in the completed run.  Following a
    # recorded persona_path here would let a result file read and upload an
    # arbitrary local YAML file, and would also make historical runs mutable.
    profile = _find_profile_mapping(persona)

    evaluation_values = profile.get("evaluation_values")
    if not isinstance(profile.get("dimensions"), dict) and isinstance(
        evaluation_values, dict
    ):
        profile["dimensions"] = copy.deepcopy(evaluation_values)
    dimensions = profile.get("dimensions")
    targets = profile.get("evaluation_dimensions")
    if not isinstance(targets, list) or not targets:
        raise JudgeConfigurationError(
            "Persona run is missing evaluation_dimensions in result metadata/profile"
        )
    if not isinstance(dimensions, dict):
        raise JudgeConfigurationError(
            "Persona run is missing dimension values in result metadata/profile"
        )
    missing = [target for target in targets if target not in dimensions]
    if missing:
        raise JudgeConfigurationError(
            "Persona evaluation dimensions have no values: " + ", ".join(missing)
        )
    return name or str(profile.get("persona_id") or "persona"), "persona", profile


def _step_number(row: Mapping[str, Any], fallback: int) -> int:
    raw = row.get("step_num", fallback)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _rows_within_limit(
    rows: Sequence[dict[str, Any]], max_steps: int
) -> list[dict[str, Any]]:
    if max_steps <= 0:
        return list(rows)
    return [
        row
        for index, row in enumerate(rows, start=1)
        if _step_number(row, index) <= max_steps
    ]


def _conversation_within_limit(
    turns: Sequence[dict[str, Any]], max_steps: int
) -> list[dict[str, Any]]:
    if max_steps <= 0:
        return list(turns)
    selected: list[dict[str, Any]] = []
    for turn in turns:
        raw = turn.get("turn")
        if raw is None:
            # Older artifacts without turn numbers cannot be truncated safely;
            # the opening is still needed to evaluate communication coverage.
            if str(turn.get("event_type", "")).lower() in {"opening", "opening_request"}:
                selected.append(turn)
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number <= max_steps:
            selected.append(turn)
    return selected


def _natural_screenshot_key(path: Path) -> tuple[int, int, str]:
    match = re.search(r"step_(\d+)(?:_(\d+))?", path.name)
    if match:
        return int(match.group(1)), int(match.group(2) or 0), path.name
    return 10**9, 0, path.name


def _resolve_screenshots(
    run_dir: Path, rows: Sequence[dict[str, Any]], max_images: int
) -> list[Path]:
    run_root = run_dir.resolve()
    resolved: list[Path] = []
    missing: list[str] = []
    for row in rows:
        raw = row.get("screenshot_file") or row.get("screenshot")
        if not isinstance(raw, str) or not raw.strip() or raw.startswith("data:"):
            continue
        path = Path(raw).expanduser()
        choices = [path] if path.is_absolute() else [run_root / path, run_root / path.name]
        match = None
        outside = False
        for choice in choices:
            candidate = choice.resolve()
            try:
                candidate.relative_to(run_root)
            except ValueError:
                if candidate.exists():
                    outside = True
                continue
            if candidate.is_file():
                match = candidate
                break
        if match is None:
            if outside:
                raise JudgeConfigurationError(
                    "Trajectory screenshot reference is outside the run directory"
                )
            missing.append(raw)
        elif match not in resolved:
            resolved.append(match)
    if missing:
        display = ", ".join(missing[:3])
        suffix = " …" if len(missing) > 3 else ""
        raise JudgeConfigurationError(
            f"Trajectory references {len(missing)} missing screenshot(s): {display}{suffix}"
        )
    if not resolved:
        for candidate in sorted(run_root.glob("step_*.png"), key=_natural_screenshot_key):
            match = candidate.resolve()
            try:
                match.relative_to(run_root)
            except ValueError as exc:
                raise JudgeConfigurationError(
                    "Run screenshot symlink points outside the run directory"
                ) from exc
            if match.is_file() and match not in resolved:
                resolved.append(match)
    if not resolved:
        raise JudgeConfigurationError(f"No trajectory screenshots found in {run_dir}")
    return resolved[-max_images:] if max_images > 0 else resolved


def _action_history(rows: Sequence[dict[str, Any]], open_tabs: Any) -> str:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        step = _step_number(row, index)
        fields = []
        for label, key in (
            ("event", "event_type"),
            ("response", "response"),
            ("action", "action"),
            ("question", "question"),
            ("persona_answer", "persona_answer"),
        ):
            value = row.get(key)
            if value not in (None, "", [], {}):
                if isinstance(value, str):
                    rendered = value.strip()
                else:
                    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                fields.append(f"{label}={rendered}")
        if fields:
            lines.append(f"STEP {step}: " + " | ".join(fields))
    if open_tabs not in (None, [], {}):
        lines.append(
            "FINAL OPEN TABS: "
            + json.dumps(open_tabs, ensure_ascii=False, sort_keys=True)
        )
    return "\n".join(lines) or "No recorded actions."


def _final_answer(
    result: Mapping[str, Any],
    conversation: Sequence[dict[str, Any]],
    *,
    allow_result_fallback: bool,
) -> str:
    for turn in reversed(conversation):
        if str(turn.get("event_type", "")).lower() == "final_response":
            content = turn.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    if allow_result_fallback:
        raw = _first(
            result,
            (
                ("answer",),
                ("run", "answer"),
                ("run_outcome", "answer"),
            ),
        )
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


def _verify_none_control(task: Mapping[str, Any], conversation: Sequence[dict[str, Any]]) -> None:
    first_user = next(
        (
            turn.get("content")
            for turn in conversation
            if str(turn.get("role", "")).lower() in {"user", "persona"}
        ),
        None,
    )
    if first_user != task["confirmed_task"]:
        raise JudgeConfigurationError(
            "The none control did not record confirmed_task verbatim; refusing exact communication credit"
        )


def load_run_artifacts(
    raw_path: str | Path,
    *,
    tasks_path: Path = DEFAULT_TASKS_PATH,
    max_images: int = 0,
    max_steps: int = 0,
) -> RunArtifacts:
    if max_images < 0 or max_steps < 0:
        raise JudgeConfigurationError("--max-images and --max-steps must be non-negative")
    result_path = resolve_result_path(raw_path)
    source_bytes = result_path.read_bytes()
    try:
        result = json.loads(source_bytes)
    except json.JSONDecodeError as exc:
        raise JudgeConfigurationError(f"Invalid JSON in {result_path}: {exc}") from exc
    if not isinstance(result, dict):
        raise JudgeConfigurationError(f"result.json must contain an object: {result_path}")
    status = result.get("status")
    if status not in {"agent_complete", "complete"}:
        raise JudgeConfigurationError(
            "Run is not ready for scoring: result.status must be "
            f"'agent_complete' or 'complete', got {status!r}"
        )
    run_dir = result_path.parent
    task = _load_task(result, result_path, tasks_path)
    persona_name, persona_mode, persona_meta = _normalize_persona(result, run_dir)

    trajectory_path = _resolve_artifact_path(
        run_dir,
        result,
        "traj.jsonl",
        (("run", "trajectory_path"), ("run", "trajectory"), ("trajectory_path",)),
    )
    conversation_path = _resolve_artifact_path(
        run_dir,
        result,
        "conversation.jsonl",
        (("run", "conversation_path"), ("conversation_path",)),
    )
    trajectory = _read_jsonl(trajectory_path)
    full_conversation = _read_jsonl(conversation_path)
    limited_rows = _rows_within_limit(trajectory, max_steps)
    if not limited_rows:
        raise JudgeConfigurationError("No trajectory rows remain after --max-steps")
    conversation = _conversation_within_limit(full_conversation, max_steps)
    if not conversation:
        raise JudgeConfigurationError("No conversation turns remain after --max-steps")
    screenshots = _resolve_screenshots(run_dir, limited_rows, max_images)
    (
        network_preflight_path,
        network_preflight,
        network_preflight_integrity_status,
    ) = _load_optional_network_preflight(run_dir, result)

    open_tabs: Any = _first(result, (("run", "open_tabs"), ("open_tabs",)))
    open_tabs_path = (run_dir / "open_tabs.json").resolve()
    open_tabs_manifest_path: Path | None = None
    if open_tabs_path.exists():
        _relative_run_path(run_dir, open_tabs_path)
        if not open_tabs_path.is_file():
            raise JudgeConfigurationError("open_tabs.json is not a regular file")
        open_tabs = _read_json(open_tabs_path)
        open_tabs_manifest_path = open_tabs_path
    trajectory_was_truncated = len(limited_rows) < len(trajectory)
    if trajectory_was_truncated:
        open_tabs = None
    if persona_mode == "none":
        _verify_none_control(task, conversation)

    manifest_paths = [trajectory_path, conversation_path, *screenshots]
    if open_tabs_manifest_path is not None:
        manifest_paths.append(open_tabs_manifest_path)
    if network_preflight_path is not None:
        manifest_paths.append(network_preflight_path)
    source_artifact_sha256 = _source_manifest(run_dir, manifest_paths)

    return RunArtifacts(
        result_path=result_path,
        result=result,
        source_result_sha256=_sha256_bytes(source_bytes),
        run_dir=run_dir,
        task=task,
        persona_name=persona_name,
        persona_mode=persona_mode,
        persona_meta=persona_meta,
        trajectory_path=trajectory_path,
        trajectory=limited_rows,
        conversation_path=conversation_path,
        conversation=conversation,
        screenshots=screenshots,
        network_preflight_path=network_preflight_path,
        network_preflight=network_preflight,
        network_preflight_integrity_status=network_preflight_integrity_status,
        source_artifact_sha256=source_artifact_sha256,
        action_history=_action_history(limited_rows, open_tabs),
        final_answer=_final_answer(
            result,
            conversation,
            allow_result_fallback=not trajectory_was_truncated,
        ),
    )


@contextmanager
def _materialize_judge_snapshot(artifacts: RunArtifacts) -> Iterable[RunArtifacts]:
    """Yield immutable, sanitized evidence paths for all remote judge calls."""
    _verify_source_artifacts(artifacts)
    with tempfile.TemporaryDirectory(prefix="personacua-judge-") as temporary:
        snapshot_dir = Path(temporary) / artifacts.run_dir.name
        snapshot_dir.mkdir()

        screenshot_map: dict[Path, Path] = {}
        snapshot_screenshots: list[Path] = []
        for index, source in enumerate(artifacts.screenshots, start=1):
            relative = _relative_run_path(artifacts.run_dir, source)
            raw = source.read_bytes()
            if _sha256_bytes(raw) != artifacts.source_artifact_sha256.get(relative):
                raise JudgeConfigurationError(
                    f"Source screenshot changed before judge snapshot: {relative}"
                )
            destination = snapshot_dir / f"shot_{index:04d}_{source.name}"
            destination.write_bytes(raw)
            screenshot_map[source.resolve()] = destination
            snapshot_screenshots.append(destination)

        snapshot_rows: list[dict[str, Any]] = []
        run_root = artifacts.run_dir.resolve()
        for raw_row in artifacts.trajectory:
            row = copy.deepcopy(raw_row)
            raw_reference = row.get("screenshot_file") or row.get("screenshot")
            selected: Path | None = None
            if isinstance(raw_reference, str) and raw_reference and not raw_reference.startswith(
                "data:"
            ):
                reference = Path(raw_reference).expanduser()
                choices = (
                    [reference]
                    if reference.is_absolute()
                    else [run_root / reference, run_root / reference.name]
                )
                for choice in choices:
                    selected = screenshot_map.get(choice.resolve())
                    if selected is not None:
                        break
            row.pop("screenshot", None)
            row.pop("screenshot_file", None)
            if selected is not None:
                row["screenshot_file"] = selected.name
            snapshot_rows.append(row)

        trajectory_path = snapshot_dir / "traj.jsonl"
        trajectory_path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, default=str) + "\n"
                for row in snapshot_rows
            ),
            encoding="utf-8",
        )
        conversation_path = snapshot_dir / "conversation.jsonl"
        conversation_path.write_text(
            "".join(
                json.dumps(turn, ensure_ascii=False, default=str) + "\n"
                for turn in artifacts.conversation
            ),
            encoding="utf-8",
        )

        preflight_path: Path | None = None
        if artifacts.network_preflight_path is not None:
            source = artifacts.network_preflight_path
            relative = _relative_run_path(artifacts.run_dir, source)
            raw = source.read_bytes()
            if _sha256_bytes(raw) != artifacts.source_artifact_sha256.get(relative):
                raise JudgeConfigurationError(
                    "network_preflight.json changed before judge snapshot"
                )
            preflight_path = snapshot_dir / "network_preflight.json"
            preflight_path.write_bytes(raw)

        # Detect changes between the initial manifest check and snapshot reads.
        _verify_source_artifacts(artifacts)
        yield dataclass_replace(
            artifacts,
            run_dir=snapshot_dir,
            trajectory_path=trajectory_path,
            trajectory=snapshot_rows,
            conversation_path=conversation_path,
            screenshots=snapshot_screenshots,
            network_preflight_path=preflight_path,
        )


def _env_text(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _env_secret(prefix: str) -> str | None:
    direct = _env_text(f"{prefix}_API_KEY")
    if direct:
        return direct
    raw_path = _env_text(f"{prefix}_API_KEY_FILE")
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise JudgeConfigurationError(
            f"Cannot read {prefix}_API_KEY_FILE ({path}): {exc}"
        ) from exc
    if not secret:
        raise JudgeConfigurationError(f"{prefix}_API_KEY_FILE is empty: {path}")
    return secret


def _env_int(names: Sequence[str], default: int, minimum: int) -> int:
    raw = _env_text(*names)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise JudgeConfigurationError(f"{names[0]} must be an integer") from exc
    if value < minimum:
        raise JudgeConfigurationError(f"{names[0]} must be >= {minimum}")
    return value


def _env_float(names: Sequence[str], default: float) -> float:
    raw = _env_text(*names)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise JudgeConfigurationError(f"{names[0]} must be numeric") from exc
    if value <= 0:
        raise JudgeConfigurationError(f"{names[0]} must be greater than zero")
    return value


def endpoint_from_environment(
    *, model: str | None = None, reasoning_effort: str | None = None
) -> EndpointConfig:
    """Resolve a judge endpoint without accepting credentials on the CLI."""
    judge_key = _env_secret("JUDGE")
    if judge_key:
        judge_base = _env_text("JUDGE_BASE_URL", "JUDGE_API_BASE")
        api_key, base_url, provider = judge_key, judge_base, "judge-compatible"
    elif (azure_key := _env_secret("AZURE_OPENAI")):
        azure_base = _env_text("AZURE_OPENAI_BASE_URL")
        if not azure_base:
            raise JudgeConfigurationError(
                "AZURE_OPENAI_API_KEY is set but AZURE_OPENAI_BASE_URL is missing"
            )
        api_key, base_url, provider = azure_key, azure_base, "azure-openai"
    elif (openai_key := _env_secret("OPENAI")):
        openai_base = _env_text("OPENAI_BASE_URL")
        api_key, base_url, provider = openai_key, openai_base, "openai"
    else:
        raise JudgeConfigurationError(
            "No judge credential found. Set JUDGE_API_KEY[_FILE], "
            "AZURE_OPENAI_API_KEY[_FILE], or OPENAI_API_KEY[_FILE]."
        )

    selected_model = (
        model
        or _env_text("JUDGE_MODEL", "AZURE_OPENAI_JUDGE_MODEL", "OPENAI_MODEL")
        or DEFAULT_MODEL
    ).strip()
    if not selected_model:
        raise JudgeConfigurationError("Judge model must not be empty")
    effort = reasoning_effort or _env_text(
        "JUDGE_REASONING_EFFORT",
        "AZURE_OPENAI_REASONING_EFFORT",
        "OPENAI_REASONING_EFFORT",
    )
    return EndpointConfig(
        model=selected_model,
        provider=provider,
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/" if base_url else None,
        timeout_seconds=_env_float(
            ("JUDGE_TIMEOUT_SECONDS", "AZURE_OPENAI_TIMEOUT_SECONDS"), 180.0
        ),
        max_retries=_env_int(
            ("JUDGE_MAX_RETRIES", "AZURE_OPENAI_MAX_RETRIES"), 5, 0
        ),
        max_completion_tokens=_env_int(
            ("JUDGE_MAX_COMPLETION_TOKENS", "OPENAI_MAX_COMPLETION_TOKENS"),
            DEFAULT_MAX_COMPLETION_TOKENS,
            1,
        ),
        reasoning_effort=effort,
    )


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        value = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if isinstance(value, str):
            parts.append(value)
    return "".join(parts).strip()


class OpenAIJudgeCall:
    """Synchronous multimodal transport matching ``evaluation.JudgeCall``."""

    def __init__(self, config: EndpointConfig) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise JudgeConfigurationError(
                "The openai package is required; install the project dependencies"
            ) from exc
        kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout_seconds,
            "max_retries": config.max_retries,
        }
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = OpenAI(**kwargs)
        self._config = config

    def __call__(self, system: str, user: str, images: list[Path]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for path in images:
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime};base64,{encoded}",
                        "detail": "high",
                    },
                }
            )
        request: dict[str, Any] = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_completion_tokens": self._config.max_completion_tokens,
        }
        if self._config.reasoning_effort:
            request["reasoning_effort"] = self._config.reasoning_effort
        response = self._client.chat.completions.create(**request)
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError("Judge endpoint returned no completion choices")
        text = _response_text(getattr(choices[0].message, "content", None))
        if not text:
            raise RuntimeError("Judge endpoint returned empty content")
        return text


def _load_standard_module(script_path: Path) -> Any:
    if not script_path.is_file():
        raise JudgeConfigurationError(f"Odysseys standard judge not found: {script_path}")
    module_name = "_personacua_odysseys_standard_judge"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise JudgeConfigurationError(f"Cannot import standard judge: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


async def _standard_judge_async(
    artifacts: RunArtifacts,
    config: EndpointConfig,
    *,
    script_path: Path,
    max_images: int,
    max_steps: int,
) -> dict[str, Any]:
    module = _load_standard_module(script_path)
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise JudgeConfigurationError(
            "The openai package is required; install the project dependencies"
        ) from exc
    kwargs: dict[str, Any] = {
        "api_key": config.api_key,
        "timeout": config.timeout_seconds,
        "max_retries": config.max_retries,
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url
    client = AsyncOpenAI(**kwargs)
    task = artifacts.task
    task_index = {
        task["task_id"]: {
            "task": task["confirmed_task"],
            "level": task.get("level", "unknown"),
            "rubrics": [
                {"id": str(rubric_id), **copy.deepcopy(rubric)}
                for rubric_id, rubric in task["rubrics"].items()
            ],
        }
    }
    original_infer = module.infer_task_id
    module.infer_task_id = lambda _run_dir: task["task_id"]
    try:
        result = await module.evaluate_run(
            artifacts.run_dir,
            client,
            "openai",
            config.model,
            task_index,
            max_images,
            max_steps if max_steps > 0 else None,
            config.reasoning_effort,
        )
    finally:
        module.infer_task_id = original_infer
        await client.close()
    return result


def run_standard_judge(
    artifacts: RunArtifacts,
    config: EndpointConfig,
    *,
    script_path: Path = DEFAULT_STANDARD_SCRIPT,
    max_images: int = 0,
    max_steps: int = 0,
) -> dict[str, Any]:
    """Run the repository's current Odysseys full-trajectory rubric judge."""
    result = asyncio.run(
        _standard_judge_async(
            artifacts,
            config,
            script_path=script_path,
            max_images=max_images,
            max_steps=max_steps,
        )
    )
    if not isinstance(result, dict):
        raise StandardJudgeError("Standard judge returned a non-object result")
    if result.get("error"):
        raise StandardJudgeError(str(result["error"]))
    rubric_results = result.get("rubric_results")
    if not isinstance(rubric_results, list):
        raise StandardJudgeError("Standard judge result has no rubric_results")
    expected = {str(key) for key in artifacts.task["rubrics"]}
    seen: set[str] = set()
    for item in rubric_results:
        if not isinstance(item, dict):
            raise StandardJudgeError("Standard judge emitted an invalid rubric record")
        rubric_id = str(item.get("rubric_id", ""))
        seen.add(rubric_id)
        reasoning = str(item.get("final_reasoning", ""))
        if reasoning.startswith("Error judging rubric"):
            raise StandardJudgeError(reasoning)
        if item.get("score") not in (0, 1):
            raise StandardJudgeError(f"Invalid standard score for {rubric_id}")
    if seen != expected:
        raise StandardJudgeError(
            f"Standard judge rubric mismatch: expected {sorted(expected)}, got {sorted(seen)}"
        )
    return result


def assemble_judgement(
    *,
    artifacts: RunArtifacts,
    standard_result: dict[str, Any],
    judge_call: Callable[[str, str, list[Path]], str],
    endpoint_meta: Mapping[str, Any],
    max_images: int,
    max_steps: int,
) -> dict[str, Any]:
    """Build a strict, three-axis judgement entirely in memory."""
    verdicts = task_verdicts_from_standard(artifacts.task, standard_result)
    communication = evaluate_communication(
        task=artifacts.task,
        conversation=artifacts.conversation,
        judge=judge_call,
        exact_control=artifacts.persona_mode == "none",
    )
    task_success = merge_task_and_communication(verdicts, communication)
    availability_adjustment = compute_availability_adjustment(
        task_success,
        artifacts.network_preflight,
        expected_task_id=artifacts.task["task_id"],
        expected_run_id=artifacts.result_path.parent.name,
        artifact_integrity_verified=(
            artifacts.network_preflight_integrity_status == "verified"
        ),
    )
    task_success = {
        **task_success,
        "score_raw": availability_adjustment["score_raw"],
        "score_availability_adjusted": availability_adjustment[
            "score_availability_adjusted"
        ],
        "score_communicated_raw": availability_adjustment[
            "score_communicated_raw"
        ],
        "score_communicated_availability_adjusted": availability_adjustment[
            "score_communicated_availability_adjusted"
        ],
        "availability_adjustment": availability_adjustment,
    }
    if artifacts.persona_mode == "none":
        # The control has no simulated identity to adhere or align to.  Keeping
        # both axes explicitly N/A avoids spending an extra model call and,
        # more importantly, avoids turning ordinary task behavior into a
        # fabricated persona score.  There are no persona contexts to emit.
        adherence = {
            "applicable": False,
            "reason": "The none control has no persona profile.",
            "targets": [],
        }
        alignment = {
            "persona_alignment_status": "not_applicable",
            "persona_alignment_score": None,
            "persona_preference_axis_primary": "",
            "persona_signal_source": "",
            "persona_alignment_explanation": (
                "The none control sends the original task verbatim and has no "
                "persona preferences or constraints to evaluate."
            ),
            "persona_constraints": [],
        }
        contexts: list[dict[str, Any]] = []
    else:
        adherence = evaluate_adherence(
            persona_meta=artifacts.persona_meta,
            conversation=artifacts.conversation,
            judge=judge_call,
            task=artifacts.task,
        )
        alignment = evaluate_alignment(
            task=artifacts.task,
            persona_meta=artifacts.persona_meta,
            conversation=artifacts.conversation,
            action_history=artifacts.action_history,
            final_answer=artifacts.final_answer,
            communication=communication,
            screenshots=artifacts.screenshots,
            judge=judge_call,
        )
        contexts = persona_contexts(alignment)
    return {
        "schema_version": "persona-cua-judgement.v2",
        "status": "complete",
        "judged_at": _utc_now(),
        "judge": dict(endpoint_meta),
        "scope": {
            "max_images": max_images,
            "screenshots_sent": len(artifacts.screenshots),
            "max_steps": max_steps,
            "trajectory_events": len(artifacts.trajectory),
            "source_result_sha256": artifacts.source_result_sha256,
            "source_artifact_manifest_sha256": _sha256_bytes(
                json.dumps(
                    artifacts.source_artifact_sha256,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
            "network_preflight_integrity": (
                artifacts.network_preflight_integrity_status
            ),
        },
        # These aliases preserve the root README/report contract.
        "verdicts": task_success["verdicts"],
        "score": task_success["score"],
        "score_raw": task_success["score_raw"],
        "score_availability_adjusted": task_success[
            "score_availability_adjusted"
        ],
        "score_communicated": task_success["score_communicated"],
        "score_communicated_raw": task_success["score_communicated_raw"],
        "score_communicated_availability_adjusted": task_success[
            "score_communicated_availability_adjusted"
        ],
        "environment_feasibility": availability_adjustment[
            "environment_feasibility"
        ],
        "communication": communication,
        "task_success": {
            **task_success,
            "standard": standard_result,
        },
        # Do not average adherence/alignment into task success.
        "persona": {
            "name": artifacts.persona_name,
            "mode": artifacts.persona_mode,
            "adherence": adherence,
            "alignment": alignment,
            "contexts": contexts,
        },
    }


def _commit_judgement(artifacts: RunArtifacts, judgement: dict[str, Any]) -> None:
    _verify_source_artifacts(artifacts)
    try:
        current_bytes = artifacts.result_path.read_bytes()
    except OSError as exc:
        raise JudgeConfigurationError(
            f"Cannot re-read result before atomic merge: {exc}"
        ) from exc
    if _sha256_bytes(current_bytes) != artifacts.source_result_sha256:
        raise JudgeConfigurationError(
            "result.json changed while judging; refusing to overwrite newer state"
        )
    if (
        artifacts.network_preflight_integrity_status == "verified"
        and artifacts.network_preflight_path is not None
    ):
        expected_preflight_hash = _nested(
            artifacts.result, "artifacts", "network_preflight_sha256"
        )
        try:
            current_preflight_bytes = artifacts.network_preflight_path.read_bytes()
        except OSError as exc:
            raise JudgeConfigurationError(
                "network_preflight.json changed while judging; refusing to publish "
                f"an availability-adjusted score: {exc}"
            ) from exc
        if _sha256_bytes(current_preflight_bytes) != expected_preflight_hash:
            raise JudgeConfigurationError(
                "network_preflight.json changed while judging; refusing to publish "
                "an availability-adjusted score"
            )
    current = json.loads(current_bytes)
    if not isinstance(current, dict):
        raise JudgeConfigurationError("result.json stopped being an object")
    merged = copy.deepcopy(current)
    merged["judgement"] = judgement
    if merged.get("status") == "agent_complete":
        merged["agent_status"] = "agent_complete"
        merged["status"] = "complete"
    atomic_write_json(artifacts.result_path, merged)


def _preview_payload(
    artifacts: RunArtifacts,
    *,
    model: str,
    max_images: int,
    max_steps: int,
    standard_script: Path,
) -> dict[str, Any]:
    rubric_requests = len(artifacts.task["rubrics"])
    persona_requests = 0 if artifacts.persona_mode == "none" else 3
    return {
        "status": "preview",
        "offline": True,
        "api_calls_made": 0,
        "result_writes": 0,
        "result_path": str(artifacts.result_path),
        "task_id": artifacts.task["task_id"],
        "rubric_ids": list(artifacts.task["rubrics"]),
        "persona": {
            "name": artifacts.persona_name,
            "mode": artifacts.persona_mode,
            "communication": (
                "exact-verbatim-control"
                if artifacts.persona_mode == "none"
                else "judge-derived"
            ),
            "evaluation_dimensions": artifacts.persona_meta.get(
                "evaluation_dimensions", []
            ),
        },
        "artifacts": {
            "trajectory": str(artifacts.trajectory_path),
            "trajectory_events": len(artifacts.trajectory),
            "conversation": str(artifacts.conversation_path),
            "conversation_turns": len(artifacts.conversation),
            "screenshots_selected": len(artifacts.screenshots),
            "screenshot_files": [path.name for path in artifacts.screenshots],
            "has_final_answer": bool(artifacts.final_answer),
            "network_preflight": (
                str(artifacts.network_preflight_path)
                if artifacts.network_preflight_path is not None
                else None
            ),
            "network_preflight_integrity": (
                artifacts.network_preflight_integrity_status
            ),
        },
        "planned_judge": {
            "model": model,
            "standard_script": str(standard_script),
            "max_images": max_images,
            "max_steps": max_steps,
            "axes": [
                "task_success_raw",
                "task_success_availability_adjusted",
                "environment_feasibility",
                "persona_adherence",
                "persona_alignment",
            ],
            "api_requests": rubric_requests + persona_requests,
            "screenshot_bearing_requests": rubric_requests
            + (1 if artifacts.persona_mode != "none" else 0),
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly judge one completed PersonaCUABench run. Normal mode uploads "
            "the selected screenshots and textual artifacts; --preview/--offline does not."
        )
    )
    parser.add_argument("run", type=Path, help="A run directory or its result.json")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--model", default=None, help=f"Judge model (default: env or {DEFAULT_MODEL})")
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Send the last N trajectory screenshots; 0 sends all (default: 0)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="Judge trajectory steps <= N; 0 uses all (default: 0)",
    )
    parser.add_argument(
        "--standard-script", type=Path, default=DEFAULT_STANDARD_SCRIPT, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--preview",
        "--offline",
        dest="preview",
        action="store_true",
        help="Validate and print the upload manifest without API calls or writes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing complete judgement",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.max_images < 0 or args.max_steps < 0:
        raise JudgeConfigurationError("--max-images and --max-steps must be non-negative")
    artifacts = load_run_artifacts(
        args.run,
        tasks_path=args.tasks.expanduser().resolve(),
        max_images=args.max_images,
        max_steps=args.max_steps,
    )
    model = (
        args.model
        or _env_text("JUDGE_MODEL", "AZURE_OPENAI_JUDGE_MODEL", "OPENAI_MODEL")
        or DEFAULT_MODEL
    )
    standard_script = args.standard_script.expanduser().resolve()
    if not standard_script.is_file():
        raise JudgeConfigurationError(f"Odysseys standard judge not found: {standard_script}")

    if args.preview:
        print(
            json.dumps(
                _preview_payload(
                    artifacts,
                    model=model,
                    max_images=args.max_images,
                    max_steps=args.max_steps,
                    standard_script=standard_script,
                ),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    existing = artifacts.result.get("judgement")
    if (
        not args.force
        and isinstance(existing, Mapping)
        and existing.get("status") == "complete"
    ):
        print(f"Already judged; leaving result unchanged: {artifacts.result_path}")
        return 0

    config = endpoint_from_environment(
        model=args.model, reasoning_effort=args.reasoning_effort
    )
    rubric_requests = len(artifacts.task["rubrics"])
    screenshot_requests = rubric_requests + (
        1 if artifacts.persona_mode != "none" else 0
    )
    print(
        f"Judging task {artifacts.task['task_id']} ({artifacts.persona_name}) with "
        f"{config.model}. This sends {len(artifacts.screenshots)} selected "
        f"screenshot(s) in each of {screenshot_requests} judge request(s), plus "
        "trajectory/task/conversation text and the final answer."
    )
    with _materialize_judge_snapshot(artifacts) as judge_artifacts:
        standard = run_standard_judge(
            judge_artifacts,
            config,
            script_path=standard_script,
            max_images=0,
            max_steps=0,
        )
        # The upstream adapter saw only the immutable temporary snapshot; keep
        # the durable source run path in the published audit record.
        standard["run_dir"] = str(artifacts.run_dir)
        if artifacts.persona_mode == "none":
            def judge_call(_system: str, _user: str, _images: list[Path]) -> str:
                raise AssertionError("none control must not invoke a persona judge")
        else:
            judge_call = OpenAIJudgeCall(config)
        judgement = assemble_judgement(
            artifacts=judge_artifacts,
            standard_result=standard,
            judge_call=judge_call,
            endpoint_meta={
                **config.public_meta,
                "judge_adapter_sha256": _sha256_bytes(Path(__file__).read_bytes()),
                "evaluation_adapter_sha256": _sha256_bytes(
                    (Path(__file__).parent / "evaluation.py").read_bytes()
                ),
                "standard_judge_sha256": _sha256_bytes(standard_script.read_bytes()),
            },
            max_images=args.max_images,
            max_steps=args.max_steps,
        )
    _commit_judgement(artifacts, judgement)
    print(f"Judgement written atomically: {artifacts.result_path}")
    print(
        "Scores: task_raw="
        f"{judgement['score']}, task_adjusted="
        f"{judgement['score_availability_adjusted']}, "
        f"communicated_raw={judgement['score_communicated']}, "
        "communicated_adjusted="
        f"{judgement['score_communicated_availability_adjusted']}, "
        "persona_alignment="
        f"{judgement['persona']['alignment']['persona_alignment_score']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ConfigurationError,
        EvaluationError,
        JudgeConfigurationError,
        StandardJudgeError,
    ) as exc:
        print(f"judge failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        # Network/provider exceptions are intentionally handled before any
        # result mutation; keep the existing run valid and report one concise
        # failure to automation callers.
        print(f"judge failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
