"""Public availability-preflight API and versioned sidecar-policy loader.

The policy is separate from ``tasks.json`` and the upstream Odysseys configs.
It maps public endpoints to affected rubric IDs without rewriting either source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from personacuabench.core import ConfigurationError, load_json
from personacuabench.network_preflight import (
    EVIDENCE_SCOPE,
    PREFLIGHT_PHASE,
    SCHEMA_VERSION,
    PreflightConfigurationError,
    PreflightEndpoint,
    RUBRIC_MAPPING_SEMANTICS,
    normalize_endpoints,
    parse_controller_result,
    run_network_preflight,
)


POLICY_SCHEMA_VERSION = "persona-cua-availability-policy/v1"
EnvironmentPreflight = Callable[[Any], dict[str, Any]]


def load_task_preflight_endpoints(
    policy_path: Path,
    *,
    task_id: str,
    rubric_ids: Sequence[str],
) -> tuple[PreflightEndpoint, ...] | None:
    """Load one task's immutable probe endpoints from a sidecar policy.

    ``None`` means the policy intentionally has no availability assessment for
    the task.  Unknown affected rubric IDs are rejected rather than silently
    altering a score denominator.
    """
    raw = load_json(Path(policy_path).expanduser().resolve())
    if not isinstance(raw, Mapping):
        raise ConfigurationError("availability policy must be an object")
    if raw.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ConfigurationError("unsupported availability policy schema_version")
    tasks = raw.get("tasks")
    if not isinstance(tasks, Mapping):
        raise ConfigurationError("availability policy tasks must be an object")
    task_policy = tasks.get(task_id)
    if task_policy is None:
        return None
    if not isinstance(task_policy, Mapping):
        raise ConfigurationError(f"availability policy for {task_id} must be an object")
    if task_policy.get("rubric_mapping_semantics") != RUBRIC_MAPPING_SEMANTICS:
        raise ConfigurationError(
            f"availability policy for {task_id} must use "
            f"{RUBRIC_MAPPING_SEMANTICS!r} rubric mapping semantics"
        )
    raw_endpoints = task_policy.get("endpoints")
    if not isinstance(raw_endpoints, list):
        raise ConfigurationError(
            f"availability policy for {task_id} must contain endpoints"
        )

    known_rubrics = set(rubric_ids)
    if len(known_rubrics) != len(rubric_ids):
        raise ConfigurationError("task rubric IDs must be unique")
    endpoints: list[PreflightEndpoint] = []
    try:
        for raw_endpoint in raw_endpoints:
            if not isinstance(raw_endpoint, Mapping):
                raise PreflightConfigurationError("endpoint must be an object")
            affected_value = raw_endpoint.get("affected_rubric_ids", [])
            if not isinstance(affected_value, list):
                raise PreflightConfigurationError(
                    "affected_rubric_ids must be a list"
                )
            affected = tuple(str(value) for value in affected_value)
            unknown = sorted(set(affected) - known_rubrics)
            if unknown:
                raise PreflightConfigurationError(
                    "unknown affected rubric IDs: " + ", ".join(unknown)
                )
            endpoints.append(
                PreflightEndpoint(
                    key=str(raw_endpoint.get("key", "")),
                    role=str(raw_endpoint.get("role", "")),  # type: ignore[arg-type]
                    url=str(raw_endpoint.get("url", "")),
                    label=(
                        str(raw_endpoint["label"])
                        if raw_endpoint.get("label") is not None
                        else None
                    ),
                    affected_rubric_ids=affected,
                )
            )
        return normalize_endpoints(endpoints)
    except PreflightConfigurationError as exc:
        raise ConfigurationError(
            f"invalid availability policy for {task_id}: {exc}"
        ) from exc


def make_environment_preflight(
    *,
    task_id: str,
    run_id: str,
    endpoints: Sequence[PreflightEndpoint],
    timeout_seconds: float = 4.0,
    dns_attempts: int = 2,
) -> EnvironmentPreflight:
    """Return the hook called after reset and before the first agent prediction."""
    frozen_endpoints = tuple(endpoints)

    def preflight(env: Any) -> dict[str, Any]:
        controller = getattr(env, "controller", None)
        if controller is None:
            return parse_controller_result(
                frozen_endpoints,
                None,
                task_id=task_id,
                run_id=run_id,
            )
        try:
            return run_network_preflight(
                controller,
                frozen_endpoints,
                task_id=task_id,
                run_id=run_id,
                timeout_seconds=timeout_seconds,
                dns_attempts=dns_attempts,
            )
        except Exception:
            # The raw benchmark remains valid when diagnostics fail.  Return a
            # schema-valid, fail-closed artifact instead of leaking transport
            # details or letting an optional preflight abort the agent run.
            return parse_controller_result(
                frozen_endpoints,
                None,
                task_id=task_id,
                run_id=run_id,
            )

    return preflight


__all__ = [
    "EVIDENCE_SCOPE",
    "PREFLIGHT_PHASE",
    "POLICY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "PreflightConfigurationError",
    "PreflightEndpoint",
    "load_task_preflight_endpoints",
    "make_environment_preflight",
    "parse_controller_result",
]
