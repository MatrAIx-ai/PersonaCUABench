#!/usr/bin/env python3
"""Run the PersonaCUABench user-simulator -> CUA phase.

Judging is deliberately not performed here.  A run publishes the browser
artifacts and an atomic ``result.json`` with ``judgement.status=not_run``;
``python -m personacuabench.judge`` is the explicit, separately consented
upload phase.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


# Support direct execution as well as ``python -m personacuabench.run``.
PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from personacuabench.core import (  # noqa: E402
    DEFAULT_ODYSSEYS_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_OSWORLD_DIR,
    DEFAULT_PERSONA8B_DIR,
    DEFAULT_PERSONA_DIR,
    DEFAULT_RESULTS_DIR,
    DEFAULT_TASKS_PATH,
    ConfigurationError,
    atomic_write_json,
    build_fingerprint,
    complete_result,
    file_sha256,
    git_head,
    iter_result_files,
    load_json,
    load_task_config,
    load_tasks,
    safe_slug,
    select_tasks,
    stable_sha256,
)
from personacuabench.availability import (  # noqa: E402
    load_task_preflight_endpoints,
    make_environment_preflight,
)
from personacuabench.network_preflight import RUBRIC_MAPPING_SEMANTICS  # noqa: E402
from personacuabench.osworld_runner import create_osworld_runtime, run_interaction_loop  # noqa: E402
from personacuabench.persona import (  # noqa: E402
    OpenAICompatibleChat,
    PersonaProfile,
    PersonaSession,
    load_profile,
)


DEFAULT_AZURE_BASE_URL = (
    "https://matraixwild.services.ai.azure.com/api/projects/"
    "MatrAIxWild/openai/v1"
)
DEFAULT_AVAILABILITY_POLICY = PACKAGE_DIR / "availability_policies.json"
SCHEMA_VERSION = "persona-cua-bench.run.v2"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def configure_local_azure_defaults() -> None:
    """Reuse the already-proven local Azure setup without copying its secret."""
    local_key = REPO_ROOT / "azure_api_key.txt"
    if (
        not os.environ.get("AZURE_OPENAI_API_KEY")
        and not os.environ.get("AZURE_OPENAI_API_KEY_FILE")
        and local_key.is_file()
    ):
        os.environ["AZURE_OPENAI_API_KEY_FILE"] = str(local_key)
    if os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get(
        "AZURE_OPENAI_API_KEY_FILE"
    ):
        os.environ.setdefault("AZURE_OPENAI_BASE_URL", DEFAULT_AZURE_BASE_URL)


def resolve_profile(
    persona: str, *, persona_dir: Path, persona_repo: Path
) -> tuple[PersonaProfile | None, str]:
    if persona == "none":
        return None, "none"
    supplied = Path(persona).expanduser()
    if supplied.suffix in {".yaml", ".yml", ".json"} or supplied.is_absolute():
        profile_path = supplied if supplied.is_absolute() else (REPO_ROOT / supplied)
    else:
        candidates = [
            persona_dir / f"{persona}.yaml",
            persona_dir / "matched_pairs" / f"{persona}.yaml",
        ]
        existing = [candidate for candidate in candidates if candidate.is_file()]
        if len(existing) > 1:
            raise ConfigurationError(
                f"Persona name {persona!r} is ambiguous: "
                + ", ".join(str(path) for path in existing)
            )
        profile_path = existing[0] if existing else candidates[0]
    profile = load_profile(profile_path, persona_repo)
    name = profile.path.stem
    return profile, name


def _matched_pair_rubric(
    profile: PersonaProfile, task: dict[str, Any]
) -> dict[str, Any] | None:
    pair = profile.matched_pair
    if pair is None:
        return None
    raw_protocol_path = pair.get("protocol_path")
    if not isinstance(raw_protocol_path, str) or not raw_protocol_path.strip():
        raise ConfigurationError("Matched-pair profile has no protocol_path")
    protocol_path = (REPO_ROOT / raw_protocol_path).resolve()
    try:
        protocol_path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ConfigurationError(
            f"Matched-pair protocol must stay inside the repository: {protocol_path}"
        ) from exc
    expected_hash = pair.get("protocol_sha256")
    if not isinstance(expected_hash, str) or file_sha256(protocol_path) != expected_hash:
        raise ConfigurationError(
            "Matched-pair profile is stale: regenerate it from "
            f"{raw_protocol_path}"
        )
    protocol = load_json(protocol_path)
    if not isinstance(protocol, dict):
        raise ConfigurationError("Matched-pair protocol must contain an object")
    if protocol.get("schema_version") != pair.get("schema_version"):
        raise ConfigurationError("Matched-pair protocol schema does not match profile")
    if protocol.get("experiment_id") != pair.get("experiment_id"):
        raise ConfigurationError("Matched-pair experiment_id does not match profile")

    axes = protocol.get("axes")
    if not isinstance(axes, list):
        raise ConfigurationError("Matched-pair protocol has no axes")
    matches = [
        axis
        for axis in axes
        if isinstance(axis, dict) and axis.get("axis_id") == pair.get("axis_id")
    ]
    if len(matches) != 1:
        raise ConfigurationError("Matched-pair axis is missing or duplicated")
    axis = matches[0]
    dimension = axis.get("dimension")
    arm_name = pair.get("arm")
    arm = (
        axis.get(arm_name)
        if isinstance(arm_name, str) and arm_name in {"positive", "negative"}
        else None
    )
    if not isinstance(dimension, str) or not isinstance(arm, dict):
        raise ConfigurationError("Matched-pair axis or arm is malformed")
    if dimension != pair.get("changed_dimension"):
        raise ConfigurationError("Matched-pair changed_dimension disagrees with protocol")

    baseline = protocol.get("baseline_dimensions")
    if not isinstance(baseline, dict):
        raise ConfigurationError("Matched-pair protocol has no baseline_dimensions")
    expected_dimensions = dict(baseline)
    expected_dimensions[dimension] = arm.get("value")
    if profile.dimensions != expected_dimensions:
        raise ConfigurationError(
            "Matched-pair dimensions differ from the one-variable protocol"
        )

    criteria = axis.get("tasks")
    if not isinstance(criteria, dict):
        raise ConfigurationError("Matched-pair axis has no task criteria")
    if list(criteria) != pair.get("applicable_task_ids"):
        raise ConfigurationError(
            "Matched-pair applicable_task_ids disagree with the protocol"
        )
    task_id = task["task_id"]
    criterion = criteria.get(task_id)
    if not isinstance(criterion, dict):
        raise ConfigurationError(
            f"Axis {pair.get('axis_id')} is not assigned to task {task_id}"
        )
    scoring = protocol.get("scoring")
    if not isinstance(scoring, dict):
        raise ConfigurationError("Matched-pair protocol has no scoring definition")
    opposite = "negative" if arm_name == "positive" else "positive"
    opposite_arm = axis.get(opposite)
    if not isinstance(opposite_arm, dict):
        raise ConfigurationError("Matched-pair opposite arm is malformed")
    return {
        "protocol_schema_version": protocol["schema_version"],
        "protocol_sha256": expected_hash,
        "experiment_id": protocol["experiment_id"],
        "axis_id": pair["axis_id"],
        "arm": arm_name,
        "task_id": task_id,
        "dimension": dimension,
        "expected_value": arm.get("value"),
        "behavioral_definition": arm.get("behavioral_definition"),
        "generic_observables": copy.deepcopy(arm.get("generic_observables", [])),
        "contradictions": copy.deepcopy(arm.get("contradictions", [])),
        "score_scale": copy.deepcopy(scoring.get("per_arm_scale", {})),
        "binary_adherence_rule": scoring.get("binary_adherence_rule"),
        "task_criterion": {
            "task_label": criterion.get("task_label"),
            "rationale": criterion.get("rationale"),
            "inherited_task_signals": copy.deepcopy(
                criterion.get("inherited_task_signals", [])
            ),
            "expected_observables": copy.deepcopy(
                criterion.get(f"{arm_name}_observables", [])
            ),
            "opposite_observables": copy.deepcopy(
                criterion.get(f"{opposite}_observables", [])
            ),
        },
    }


def persona_metadata(
    profile: PersonaProfile | None, *, task: dict[str, Any]
) -> dict[str, Any]:
    if profile is None:
        return {
            "mode": "none",
            "persona_id": "none",
            "display_name": "No persona (verbatim task control)",
            "profile_sha256": None,
            "evaluation_dimensions": [],
            "dimensions": {},
        }
    result = {
        "mode": "persona",
        **profile.meta,
        # Judges need the assigned values, while the CUA never receives this map.
        "dimensions": profile.dimensions,
    }
    rubric = _matched_pair_rubric(profile, task)
    if rubric is not None:
        result["adherence_rubric"] = rubric
    return result


def source_revisions(
    *,
    osworld_root: Path,
    odysseys_dir: Path,
    persona_repo: Path,
    availability_policy_task_sha256: str | None = None,
    task_config_sha256: str | None = None,
) -> dict[str, Any]:
    adapter = REPO_ROOT / "integrations" / "osworld" / "azure_foundry_agent.py"
    persona_experiment = PACKAGE_DIR / "persona_experiment.json"
    pipeline_files = [
        Path(__file__).resolve(),
        PACKAGE_DIR / "core.py",
        PACKAGE_DIR / "osworld_runner.py",
        PACKAGE_DIR / "persona.py",
        PACKAGE_DIR / "protocol.py",
        PACKAGE_DIR / "availability.py",
        PACKAGE_DIR / "network_preflight.py",
        PACKAGE_DIR / "schemas" / "network_preflight.schema.json",
        PACKAGE_DIR / "availability_policies.json",
    ]
    required_files = [adapter, persona_experiment, *pipeline_files]
    missing_files = [path for path in required_files if not path.is_file()]
    if missing_files:
        raise ConfigurationError(
            "Required pipeline source files are missing: "
            + ", ".join(str(path) for path in missing_files)
        )
    runtime_files = sorted(
        {
            *(
                path
                for root in (
                    osworld_root / "desktop_env",
                    osworld_root / "mm_agents",
                )
                if root.is_dir()
                for path in root.rglob("*.py")
            ),
            osworld_root / "pyproject.toml",
            osworld_root / "uv.lock",
        },
        key=lambda path: str(path),
    )
    return {
        "benchmark": git_head(REPO_ROOT),
        "osworld": git_head(osworld_root),
        "odysseys": git_head(odysseys_dir),
        "persona8b": git_head(persona_repo),
        "persona_experiment_sha256": file_sha256(persona_experiment),
        "azure_adapter_sha256": file_sha256(adapter),
        "osworld_runtime_sha256": stable_sha256(
            {
                str(path.relative_to(osworld_root)): file_sha256(path)
                for path in runtime_files
                if path.is_file()
            }
        ),
        "agent_pipeline_sha256": stable_sha256(
            {
                str(path.relative_to(PACKAGE_DIR)): file_sha256(path)
                for path in pipeline_files
            }
        ),
        "availability_policy_task_sha256": availability_policy_task_sha256,
        "task_config_sha256": task_config_sha256,
    }


def find_cached_result(
    results_dir: Path, task_id: str, fingerprint: str
) -> Path | None:
    task_root = results_dir / task_id
    if not task_root.exists():
        return None
    candidates: list[tuple[int, str, str, Path]] = []
    for result_path in iter_result_files(task_root):
        if not complete_result(result_path, fingerprint) or not _cache_artifacts_valid(
            result_path
        ):
            continue
        try:
            result = load_json(result_path)
        except ConfigurationError:
            continue
        if not isinstance(result, Mapping):
            continue
        candidates.append(
            (
                1 if result.get("status") == "complete" else 0,
                str(result.get("updated_at") or result.get("created_at") or ""),
                str(result_path),
                result_path,
            )
        )
    return max(candidates, default=(0, "", "", None))[-1]


def _cache_artifacts_valid(result_path: Path) -> bool:
    """Require every recorded cache artifact to exist with its published hash."""
    try:
        result = load_json(result_path)
    except ConfigurationError:
        return False
    if not isinstance(result, Mapping):
        return False
    artifacts = result.get("artifacts")
    run = result.get("run")
    if not isinstance(artifacts, Mapping) or not isinstance(run, Mapping):
        return False
    manifest = artifacts.get("sha256")
    if not isinstance(manifest, Mapping) or not manifest:
        return False

    required: set[str] = set()
    for key in ("trajectory", "conversation", "open_tabs", "run_outcome", "result_marker"):
        value = artifacts.get(key)
        if not isinstance(value, str) or not value:
            return False
        required.add(value)
    screenshots = run.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots or any(
        not isinstance(value, str) or not value for value in screenshots
    ):
        return False
    required.update(screenshots)
    network_preflight = artifacts.get("network_preflight")
    if isinstance(network_preflight, str) and network_preflight:
        required.add(network_preflight)

    run_dir = result_path.parent.resolve()
    for relative, expected in manifest.items():
        if (
            not isinstance(relative, str)
            or not isinstance(expected, str)
            or len(expected) != 64
        ):
            return False
        candidate = (run_dir / relative).resolve()
        try:
            candidate.relative_to(run_dir)
        except ValueError:
            return False
        if (
            not candidate.is_file()
            or candidate.stat().st_size == 0
            or file_sha256(candidate) != expected
        ):
            return False
    return required.issubset(set(manifest))


def jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number} is not a JSON object")
            rows.append(value)
    return rows


def environment_status_for_run(
    task: Mapping[str, Any], preflight: Mapping[str, Any] | None
) -> str:
    """Summarize pre-judge feasibility without changing any rubric verdict."""
    if preflight is None:
        return "not_assessed"
    feasibility = preflight.get("feasibility")
    if not isinstance(feasibility, Mapping):
        return "indeterminate"
    status = feasibility.get("status")
    if status == "feasible":
        return "feasible"
    if status != "infeasible_candidate":
        return "indeterminate"
    affected = feasibility.get("affected_rubric_ids")
    rubrics = task.get("rubrics")
    if not isinstance(affected, list) or not isinstance(rubrics, Mapping):
        return "indeterminate"
    affected_ids = {value for value in affected if isinstance(value, str)}
    rubric_ids = {str(value) for value in rubrics}
    if not affected_ids or not affected_ids.issubset(rubric_ids):
        return "indeterminate"
    return "infeasible" if affected_ids == rubric_ids else "partially_infeasible"


def opening_cache_path(
    *,
    cache_dir: Path,
    task: dict[str, Any],
    profile: PersonaProfile | None,
    persona_model: str | None,
    provider: str | None,
    generation_meta: Mapping[str, Any] | None = None,
    max_questions: int,
    replicate_id: str = "0",
) -> Path:
    key = stable_sha256(
        {
            "task_id": task["task_id"],
            "task": task["confirmed_task"],
            "profile_sha256": profile.sha256 if profile else None,
            "persona_system_sha256": (
                stable_sha256(profile.persona_system) if profile else None
            ),
            "persona_model": persona_model,
            "provider": provider,
            "generation_meta": dict(generation_meta or {}),
            "max_questions": max_questions,
            "replicate_id": replicate_id,
            "schema": "persona-opening.v2",
            "persona_session_sha256": file_sha256(
                PACKAGE_DIR / "persona.py"
            ),
        }
    )
    return cache_dir / "openings" / f"{key}.json"


def cached_opening_session(
    *,
    task: dict[str, Any],
    profile: PersonaProfile | None,
    client: OpenAICompatibleChat | None,
    persona_model: str | None,
    max_questions: int,
    cache_dir: Path,
    replicate_id: str = "0",
) -> tuple[PersonaSession, Path, str]:
    state_path = opening_cache_path(
        cache_dir=cache_dir,
        task=task,
        profile=profile,
        persona_model=persona_model,
        provider=client.provider if client else None,
        generation_meta=(
            {
                key: value
                for key, value in getattr(client, "meta", {}).items()
                if key
                in {
                    "type",
                    "role",
                    "model",
                    "provider",
                    "reasoning_effort",
                    "max_completion_tokens",
                    "endpoint_sha256",
                }
            }
            if client is not None and isinstance(getattr(client, "meta", None), Mapping)
            else None
        ),
        max_questions=max_questions,
        replicate_id=replicate_id,
    )
    session = PersonaSession(
        task=task["confirmed_task"],
        profile=profile,
        client=client,
        max_questions=max_questions,
        state_path=state_path,
    )
    opening = session.start()
    # This cache is an opening cache, never shared mutable dialogue state.
    if len(session.exchanges) != 1 or session.exchanges[0].get("type") != "opening":
        raise RuntimeError(f"Opening cache contains dialogue state: {state_path}")
    return session, state_path, opening


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PersonaCUABench's persona/CUA phase (judging is separate)."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task", type=int, help="1-based task number")
    selection.add_argument("--all", action="store_true", help="run every task")
    parser.add_argument("--persona", required=True, help="none, profile name, or profile path")
    parser.add_argument("--preview", action="store_true", help="generate opening only; no VM/CUA")
    parser.add_argument("--force", action="store_true", help="rerun an already completed fingerprint")
    parser.add_argument(
        "--replicate-id",
        default=os.environ.get("REPLICATE_ID", "0"),
        help="controlled replicate label; changes the run and persona-opening cache",
    )
    parser.add_argument("--tasks-file", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--persona-dir", type=Path, default=DEFAULT_PERSONA_DIR)
    parser.add_argument("--persona-repo", type=Path, default=DEFAULT_PERSONA8B_DIR)
    parser.add_argument("--osworld-root", type=Path, default=DEFAULT_OSWORLD_DIR)
    parser.add_argument("--odysseys-dir", type=Path, default=DEFAULT_ODYSSEYS_DIR)
    parser.add_argument(
        "--availability-policy",
        type=Path,
        default=DEFAULT_AVAILABILITY_POLICY,
        help="versioned sidecar policy for read-only availability diagnostics",
    )
    parser.add_argument(
        "--network-preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run the guest-side read-only network preflight (default: enabled)",
    )
    parser.add_argument("--model", default=os.environ.get("CUA_MODEL", "gpt-5.6-terra"))
    parser.add_argument(
        "--persona-model",
        default=os.environ.get("PERSONA_MODEL", "gpt-5.6-terra"),
    )
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--max-questions", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--max-trajectory-length", type=int, default=3)
    parser.add_argument("--provider", default="vmware")
    parser.add_argument("--path-to-vm", default=None)
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--screen-width", type=int, default=1920)
    parser.add_argument("--screen-height", type=int, default=1080)
    parser.add_argument("--sleep-after-execution", type=float, default=1.0)
    parser.add_argument("--ready-wait-seconds", type=float, default=60.0)
    parser.add_argument("--settle-seconds", type=float, default=20.0)
    parser.add_argument(
        "--prediction-retries",
        type=int,
        default=1,
        help="additional attempts for a thrown/empty CUA prediction",
    )
    parser.add_argument(
        "--prediction-retry-seconds",
        type=float,
        default=2.0,
        help="delay between CUA prediction attempts",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if not isinstance(args.replicate_id, str) or not args.replicate_id.strip():
        raise ConfigurationError("--replicate-id must be non-empty")
    if len(args.replicate_id) > 80:
        raise ConfigurationError("--replicate-id must be at most 80 characters")
    if args.max_steps <= 0:
        raise ConfigurationError("--max-steps must be positive")
    if args.max_questions < 0:
        raise ConfigurationError("--max-questions must be non-negative")
    if args.max_tokens <= 0 or args.max_trajectory_length <= 0:
        raise ConfigurationError("token and trajectory limits must be positive")
    if args.screen_width <= 0 or args.screen_height <= 0:
        raise ConfigurationError("screen dimensions must be positive")
    if args.prediction_retries < 0:
        raise ConfigurationError("--prediction-retries must be non-negative")
    for name in (
        "sleep_after_execution",
        "ready_wait_seconds",
        "settle_seconds",
        "prediction_retry_seconds",
    ):
        if getattr(args, name) < 0:
            raise ConfigurationError(f"--{name.replace('_', '-')} must be non-negative")


def preview_task(
    *,
    number: int,
    task: dict[str, Any],
    persona_name: str,
    profile: PersonaProfile | None,
    client: OpenAICompatibleChat | None,
    args: argparse.Namespace,
) -> None:
    # Resolve and validate task-specific matched-pair metadata before spending a
    # model call on an inapplicable or stale profile.
    persona_metadata(profile, task=task)
    _, cache_path, opening = cached_opening_session(
        task=task,
        profile=profile,
        client=client,
        persona_model=args.persona_model if client else None,
        max_questions=args.max_questions,
        cache_dir=args.cache_dir.resolve(),
        replicate_id=args.replicate_id,
    )
    print(f"Task {number}: {task['task_id']}")
    print(f"Persona: {persona_name}")
    print(f"Opening cache: {cache_path}")
    print("Opening:")
    print(opening)
    print()


def run_task(
    *,
    number: int,
    task: dict[str, Any],
    persona_name: str,
    profile: PersonaProfile | None,
    client: OpenAICompatibleChat | None,
    args: argparse.Namespace,
) -> Path:
    osworld_root = args.osworld_root.resolve()
    odysseys_dir = args.odysseys_dir.resolve()
    persona_repo = args.persona_repo.resolve()
    results_dir = args.results_dir.resolve()
    availability_policy = Path(
        getattr(args, "availability_policy", DEFAULT_AVAILABILITY_POLICY)
    ).resolve()
    network_preflight_enabled = bool(getattr(args, "network_preflight", True))
    preflight_endpoints = (
        load_task_preflight_endpoints(
            availability_policy,
            task_id=task["task_id"],
            rubric_ids=list(task["rubrics"]),
        )
        if network_preflight_enabled
        else None
    )
    policy_task_sha256 = (
        stable_sha256(
            {
                "schema_version": "persona-cua-availability-policy/v1",
                "rubric_mapping_semantics": RUBRIC_MAPPING_SEMANTICS,
                "task_id": task["task_id"],
                "endpoints": [endpoint.to_dict() for endpoint in preflight_endpoints],
            }
        )
        if preflight_endpoints is not None
        else None
    )
    task_config = load_task_config(task, odysseys_dir)
    task_config_sha256 = stable_sha256(task_config)
    _, cached_state, opening = cached_opening_session(
        task=task,
        profile=profile,
        client=client,
        persona_model=args.persona_model if client else None,
        max_questions=args.max_questions,
        cache_dir=args.cache_dir.resolve(),
        replicate_id=args.replicate_id,
    )
    persona_meta = persona_metadata(profile, task=task)
    models = {
        "cua": args.model,
        "persona": args.persona_model if client else None,
        "persona_transport": (
            {
                key: value
                for key, value in getattr(client, "meta", {}).items()
                if key
                in {
                    "type",
                    "role",
                    "model",
                    "provider",
                    "reasoning_effort",
                    "max_completion_tokens",
                    "endpoint_sha256",
                }
            }
            if client is not None and isinstance(getattr(client, "meta", None), Mapping)
            else None
        ),
    }
    limits = {
        "max_steps": args.max_steps,
        "max_questions": args.max_questions,
        "max_tokens": args.max_tokens,
        "max_trajectory_length": args.max_trajectory_length,
        "prediction_retries": args.prediction_retries,
        "prediction_retry_seconds": args.prediction_retry_seconds,
        "network_preflight": network_preflight_enabled,
        "opening_sha256": stable_sha256(opening),
        "provider": args.provider,
        "path_to_vm": (
            str(Path(args.path_to_vm).expanduser().resolve())
            if args.path_to_vm
            else None
        ),
        "headless": bool(args.headless),
        "screen_width": args.screen_width,
        "screen_height": args.screen_height,
        "sleep_after_execution": args.sleep_after_execution,
        "ready_wait_seconds": args.ready_wait_seconds,
        "settle_seconds": args.settle_seconds,
        "cua_reasoning_effort": os.environ.get(
            "AZURE_OPENAI_REASONING_EFFORT", "low"
        ).strip(),
        "cua_timeout_seconds": os.environ.get(
            "AZURE_OPENAI_TIMEOUT_SECONDS", "180"
        ).strip(),
        "cua_max_retries": os.environ.get("AZURE_OPENAI_MAX_RETRIES", "5").strip(),
        "vision_width": os.environ.get("AZURE_VISION_COORD_WIDTH", "1365").strip(),
        "vision_height": os.environ.get("AZURE_VISION_COORD_HEIGHT", "768").strip(),
        "cua_endpoint_sha256": (
            stable_sha256(
                os.environ.get("OSWORLD_OPENAI_BASE_URL", "").strip()
                or os.environ.get("AZURE_OPENAI_BASE_URL", "").strip()
            )
            if (
                os.environ.get("OSWORLD_OPENAI_BASE_URL", "").strip()
                or os.environ.get("AZURE_OPENAI_BASE_URL", "").strip()
            )
            else None
        ),
    }
    run_control = {"replicate_id": args.replicate_id}
    revisions = source_revisions(
        osworld_root=osworld_root,
        odysseys_dir=odysseys_dir,
        persona_repo=persona_repo,
        availability_policy_task_sha256=policy_task_sha256,
        task_config_sha256=task_config_sha256,
    )
    fingerprint = build_fingerprint(
        task=task,
        persona_meta=persona_meta,
        models=models,
        limits=limits,
        source_revisions=revisions,
        run_control=run_control,
    )
    existing = find_cached_result(results_dir, task["task_id"], fingerprint)
    if existing is not None and not args.force:
        print(f"SKIP task {number} / {persona_name}: {existing}")
        return existing

    # Ending the leaf directory with task_id keeps the artifacts directly
    # compatible with Odysseys' existing task-id inference.
    cell_name = "__".join(
        (
            safe_slug(persona_name),
            safe_slug(args.model),
            f"replicate-{safe_slug(args.replicate_id)}",
            run_stamp(),
            task["task_id"],
        )
    )
    result_dir = results_dir / task["task_id"] / cell_name
    # A same-second forced rerun remains unambiguous.
    if result_dir.exists():
        suffix = 2
        while result_dir.with_name(f"{cell_name}_{suffix}").exists():
            suffix += 1
        result_dir = result_dir.with_name(f"{cell_name}_{suffix}")
    result_dir.mkdir(parents=True)
    result_path = result_dir / "result.json"
    created_at = utc_now()
    base_result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "running",
        "fingerprint": fingerprint,
        "task_number": number,
        "task_id": task["task_id"],
        "task": copy.deepcopy(task),
        "persona": persona_name,
        "persona_meta": persona_meta,
        "models": models,
        "limits": limits,
        "run_control": run_control,
        "source_revisions": revisions,
        "created_at": created_at,
        "updated_at": created_at,
        "run": None,
        "judgement": {"status": "not_run"},
    }
    atomic_write_json(result_path, base_result)

    try:
        session_state = result_dir / "persona_session.json"
        shutil.copyfile(cached_state, session_state)
        os.chmod(session_state, 0o600)
        session = PersonaSession(
            task=task["confirmed_task"],
            profile=profile,
            client=client,
            max_questions=args.max_questions,
            state_path=session_state,
        )

        # The VM setup data is unchanged, but no hidden original wording remains
        # in the environment config visible to this run.
        task_config = copy.deepcopy(task_config)
        task_config["instruction"] = opening
        environment_preflight = (
            make_environment_preflight(
                task_id=task["task_id"],
                run_id=result_dir.name,
                endpoints=preflight_endpoints,
            )
            if preflight_endpoints is not None
            else None
        )

        print(f"RUN task {number} / {persona_name}: {result_dir}")
        os.environ["OSWORLD_SCREEN_WIDTH"] = str(args.screen_width)
        os.environ["OSWORLD_SCREEN_HEIGHT"] = str(args.screen_height)
        with create_osworld_runtime(
            model=args.model,
            osworld_root=osworld_root,
            provider_name=args.provider,
            path_to_vm=args.path_to_vm,
            headless=args.headless,
            screen_width=args.screen_width,
            screen_height=args.screen_height,
            max_tokens=args.max_tokens,
            max_trajectory_length=args.max_trajectory_length,
            allow_ask_user=args.max_questions > 0,
            max_questions=args.max_questions,
        ) as runtime:
            outcome = run_interaction_loop(
                agent=runtime.agent,
                env=runtime.env,
                opening_request=opening,
                answer_user=lambda question, _conversation: session.reply(question),
                result_dir=result_dir,
                task_config=task_config,
                max_steps=args.max_steps,
                max_questions=args.max_questions,
                sleep_after_execution=args.sleep_after_execution,
                ready_wait_seconds=args.ready_wait_seconds,
                settle_seconds=args.settle_seconds,
                prediction_retries=args.prediction_retries,
                prediction_retry_seconds=args.prediction_retry_seconds,
                environment_preflight=environment_preflight,
            )

        trajectory = jsonl_rows(result_dir / "traj.jsonl")
        if not trajectory or not outcome.screenshot_files:
            raise RuntimeError(
                "completed CUA run has no judgeable trajectory screenshots"
            )
        network_preflight_path = result_dir / "network_preflight.json"
        network_preflight_sha256 = (
            file_sha256(network_preflight_path)
            if network_preflight_path.is_file()
            else None
        )
        artifact_paths = [
            result_dir / "traj.jsonl",
            result_dir / "conversation.jsonl",
            result_dir / "open_tabs.json",
            result_dir / "run_outcome.json",
            result_dir / "persona_session.json",
            result_dir / "result.txt",
            *(result_dir / name for name in outcome.screenshot_files),
        ]
        if network_preflight_path.is_file():
            artifact_paths.append(network_preflight_path)
        artifact_manifest: dict[str, str] = {}
        for artifact_path in artifact_paths:
            resolved_artifact = artifact_path.resolve()
            try:
                relative_artifact = resolved_artifact.relative_to(result_dir.resolve())
            except ValueError as exc:
                raise RuntimeError(
                    f"run artifact escaped its result directory: {resolved_artifact}"
                ) from exc
            if not resolved_artifact.is_file():
                raise RuntimeError(f"required run artifact is missing: {relative_artifact}")
            artifact_manifest[str(relative_artifact)] = file_sha256(resolved_artifact)
        preflight_summary = outcome.environment_preflight or {}
        completed = {
            **base_result,
            "status": "agent_complete",
            "updated_at": utc_now(),
            "run": {
                "opening": opening,
                "conversation": outcome.conversation,
                "trajectory": trajectory,
                "answer": outcome.answer,
                "open_tabs": outcome.open_tabs,
                "stop_reason": outcome.stop_reason,
                "agent_turns": outcome.agent_turns,
                "env_actions": outcome.env_actions,
                "questions_asked": outcome.questions_asked,
                "questions_answered": outcome.questions_answered,
                "osworld_result_marker": outcome.osworld_result_marker,
                "warnings": outcome.warnings,
                "screenshots": outcome.screenshot_files,
                "recording": outcome.recording_path,
                "started_at": outcome.started_at,
                "finished_at": outcome.finished_at,
                "environment": {
                    "network_preflight_enabled": network_preflight_enabled,
                    "network_preflight_configured": preflight_endpoints is not None,
                    "status": environment_status_for_run(
                        task,
                        outcome.environment_preflight,
                    ),
                    "classification": preflight_summary.get("classification"),
                    "feasibility": preflight_summary.get("feasibility"),
                },
            },
            "artifacts": {
                "trajectory": "traj.jsonl",
                "conversation": "conversation.jsonl",
                "open_tabs": "open_tabs.json",
                "run_outcome": "run_outcome.json",
                "persona_session": "persona_session.json",
                "result_marker": "result.txt",
                "sha256": dict(sorted(artifact_manifest.items())),
                **(
                    {
                        "network_preflight": "network_preflight.json",
                        "network_preflight_sha256": network_preflight_sha256,
                    }
                    if network_preflight_sha256 is not None
                    else {}
                ),
            },
        }
        atomic_write_json(result_path, completed)
        print(f"DONE task {number} / {persona_name}: {result_path}")
        print(
            "Judge separately: "
            f"{sys.executable} -m personacuabench.judge {result_dir}"
        )
        return result_path
    except BaseException as exc:
        failed = {
            **base_result,
            "status": "failed",
            "updated_at": utc_now(),
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        atomic_write_json(result_path, failed)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        configure_local_azure_defaults()
        tasks = load_tasks(args.tasks_file.resolve())
        chosen = select_tasks(tasks, task_number=args.task, select_all=args.all)
        profile, persona_name = resolve_profile(
            args.persona,
            persona_dir=args.persona_dir.resolve(),
            persona_repo=args.persona_repo.resolve(),
        )

        needs_client = profile is not None or (not args.preview and args.max_questions > 0)
        client = (
            OpenAICompatibleChat.from_environment("persona", args.persona_model)
            if needs_client
            else None
        )
        number_by_id = {task["task_id"]: i for i, task in enumerate(tasks, start=1)}
        for task in chosen:
            number = number_by_id[task["task_id"]]
            if args.preview:
                preview_task(
                    number=number,
                    task=task,
                    persona_name=persona_name,
                    profile=profile,
                    client=client,
                    args=args,
                )
            else:
                run_task(
                    number=number,
                    task=task,
                    persona_name=persona_name,
                    profile=profile,
                    client=client,
                    args=args,
                )
        return 0
    except (ConfigurationError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
