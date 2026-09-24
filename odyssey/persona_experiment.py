"""Validation and generation helpers for controlled persona experiments.

The task suite owns the experiment protocol.  A protocol selects three to six
observable MatrAIx dimensions and creates one matched pair per dimension.  The
two arms of a pair are generated from the same baseline and therefore differ
in exactly one value.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_SCHEMA_PATH = HERE / "dimensions.json"
PROTOCOL_SCHEMA = "personacuabench.matched-pair.v1"
MIN_PAIRS = 3
MAX_PAIRS = 6
ARMS = ("positive", "negative")


class ExperimentDefinitionError(ValueError):
    """The experiment protocol or its generated profiles are inconsistent."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExperimentDefinitionError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExperimentDefinitionError(f"invalid JSON {path}: {exc}") from exc


def file_sha256(path: Path) -> str:
    # Git may check out text protocols with CRLF on Windows. Hash their
    # repository-standard LF content so generated profiles remain portable.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dimension_catalog(path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, dict[str, Any]]:
    payload = load_json(path)
    rows = payload.get("dimensions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ExperimentDefinitionError(f"schema has no dimensions list: {path}")
    catalog: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        values = row.get("values")
        if not isinstance(values, list) or not values:
            continue
        catalog[row["id"]] = row
    return catalog


def _nonempty_strings(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ExperimentDefinitionError(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ExperimentDefinitionError(f"{field} entries must be non-empty strings")
    return [item.strip() for item in value]


def validate_protocol(
    protocol: Any,
    *,
    catalog: dict[str, dict[str, Any]],
    task_ids: list[str],
    expected_suite_id: str | None = None,
) -> dict[str, Any]:
    """Validate the generic 6–12-persona contract and its task matrix."""
    if not isinstance(protocol, dict):
        raise ExperimentDefinitionError("protocol must contain an object")
    if protocol.get("schema_version") != PROTOCOL_SCHEMA:
        raise ExperimentDefinitionError(
            f"schema_version must be {PROTOCOL_SCHEMA!r}"
        )
    experiment_id = protocol.get("experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ExperimentDefinitionError("experiment_id must be non-empty")
    suite_id = protocol.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id.strip():
        raise ExperimentDefinitionError("suite_id must be non-empty")
    if expected_suite_id is not None and suite_id != expected_suite_id:
        raise ExperimentDefinitionError(
            f"protocol suite_id {suite_id!r} does not match {expected_suite_id!r}"
        )
    display_name = protocol.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ExperimentDefinitionError("display_name must be non-empty")

    baseline = protocol.get("baseline_dimensions")
    if not isinstance(baseline, dict) or not baseline:
        raise ExperimentDefinitionError("baseline_dimensions must be a non-empty object")
    for dimension, value in baseline.items():
        if dimension not in catalog:
            raise ExperimentDefinitionError(f"unknown baseline dimension: {dimension}")
        allowed = catalog[dimension].get("values") or []
        if value not in allowed:
            raise ExperimentDefinitionError(
                f"invalid baseline {dimension}={value!r}"
            )

    scoring = protocol.get("scoring")
    if not isinstance(scoring, dict):
        raise ExperimentDefinitionError("scoring must be an object")
    score_scale = scoring.get("per_arm_scale")
    if not isinstance(score_scale, dict) or set(score_scale) != {"0", "1", "2"}:
        raise ExperimentDefinitionError("per_arm_scale must define 0, 1, and 2")

    axes = protocol.get("axes")
    if not isinstance(axes, list) or not MIN_PAIRS <= len(axes) <= MAX_PAIRS:
        raise ExperimentDefinitionError(
            f"axes must contain {MIN_PAIRS}–{MAX_PAIRS} entries "
            f"({MIN_PAIRS * 2}–{MAX_PAIRS * 2} personas)"
        )
    design = protocol.get("design")
    if not isinstance(design, dict):
        raise ExperimentDefinitionError("design must be an object")
    if design.get("selected_axis_count") != len(axes):
        raise ExperimentDefinitionError("selected_axis_count differs from axes length")
    if design.get("expected_persona_count") != len(axes) * 2:
        raise ExperimentDefinitionError(
            "expected_persona_count must be twice the selected axis count"
        )
    replicates = design.get("recommended_replicates")
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates < 1:
        raise ExperimentDefinitionError("recommended_replicates must be a positive integer")
    for field in ("pairing_controls", "invalid_pair_conditions"):
        _nonempty_strings(design.get(field), field=f"design/{field}")

    for field in (
        "binary_adherence_rule",
        "pair_separation_rule",
        "coverage_guardrail",
    ):
        if not isinstance(scoring.get(field), str) or not scoring[field].strip():
            raise ExperimentDefinitionError(f"scoring/{field} must be non-empty")
    _nonempty_strings(scoring.get("reporting"), field="scoring/reporting")

    known_tasks = set(task_ids)
    seen_axis_ids: set[str] = set()
    seen_dimensions: set[str] = set()
    task_axis_counts: Counter[str] = Counter()
    for index, axis in enumerate(axes, start=1):
        if not isinstance(axis, dict):
            raise ExperimentDefinitionError(f"axis #{index} must be an object")
        axis_id = axis.get("axis_id")
        if not isinstance(axis_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", axis_id):
            raise ExperimentDefinitionError(f"axis #{index} has invalid axis_id")
        if axis_id in seen_axis_ids:
            raise ExperimentDefinitionError(f"duplicate axis_id: {axis_id}")
        seen_axis_ids.add(axis_id)
        if not isinstance(axis.get("label"), str) or not axis["label"].strip():
            raise ExperimentDefinitionError(f"{axis_id}: label must be non-empty")

        dimension = axis.get("dimension")
        if dimension not in baseline:
            raise ExperimentDefinitionError(
                f"{axis_id}: target dimension must be in baseline_dimensions"
            )
        if dimension in seen_dimensions:
            raise ExperimentDefinitionError(f"duplicate target dimension: {dimension}")
        seen_dimensions.add(str(dimension))

        values: list[str] = []
        for arm_name in ARMS:
            arm = axis.get(arm_name)
            if not isinstance(arm, dict):
                raise ExperimentDefinitionError(f"{axis_id}/{arm_name} must be an object")
            value = arm.get("value")
            allowed = catalog[str(dimension)].get("values") or []
            if value not in allowed:
                raise ExperimentDefinitionError(
                    f"{axis_id}/{arm_name}: invalid {dimension}={value!r}"
                )
            values.append(str(value))
            if not str(arm.get("behavioral_definition") or "").strip():
                raise ExperimentDefinitionError(
                    f"{axis_id}/{arm_name} has no behavioral_definition"
                )
            _nonempty_strings(
                arm.get("generic_observables"),
                field=f"{axis_id}/{arm_name}/generic_observables",
            )
            _nonempty_strings(
                arm.get("contradictions"),
                field=f"{axis_id}/{arm_name}/contradictions",
            )
        if values[0] == values[1]:
            raise ExperimentDefinitionError(f"{axis_id}: arm values must differ")

        criteria = axis.get("tasks")
        if not isinstance(criteria, dict) or not criteria:
            raise ExperimentDefinitionError(f"{axis_id}: tasks must be non-empty")
        unknown = set(criteria) - known_tasks
        if unknown:
            raise ExperimentDefinitionError(
                f"{axis_id}: unknown task IDs: {sorted(unknown)}"
            )
        for task_id, criterion in criteria.items():
            if not isinstance(criterion, dict):
                raise ExperimentDefinitionError(
                    f"{axis_id}/{task_id}: criterion must be an object"
                )
            for field in ("task_label", "rationale"):
                if not isinstance(criterion.get(field), str) or not criterion[field].strip():
                    raise ExperimentDefinitionError(
                        f"{axis_id}/{task_id}/{field} must be non-empty"
                    )
            for field in (
                "inherited_task_signals",
                "positive_observables",
                "negative_observables",
            ):
                _nonempty_strings(
                    criterion.get(field), field=f"{axis_id}/{task_id}/{field}"
                )
            task_axis_counts[task_id] += 1

    uncovered = known_tasks - set(task_axis_counts)
    if uncovered:
        raise ExperimentDefinitionError(
            f"tasks without persona axes: {sorted(uncovered)}"
        )
    task_axis_total = sum(task_axis_counts.values())
    if design.get("expected_task_axis_pairs_per_replicate") != task_axis_total:
        raise ExperimentDefinitionError(
            "expected_task_axis_pairs_per_replicate differs from the protocol matrix"
        )
    if design.get("expected_run_cells_per_replicate") != task_axis_total * 2:
        raise ExperimentDefinitionError(
            "expected_run_cells_per_replicate must be twice the task-axis count"
        )
    return protocol


def profile_name(axis_id: str, arm: str) -> str:
    return f"mp_{axis_id}_{arm}"


def expected_profiles(
    protocol: dict[str, Any],
    *,
    catalog: dict[str, dict[str, Any]],
    suite_id: str,
    protocol_path: Path,
) -> dict[str, dict[str, Any]]:
    """Render protocol arms into the current runner's ``attributes`` schema."""
    digest = file_sha256(protocol_path)
    try:
        relative_protocol = protocol_path.resolve().relative_to(HERE.resolve()).as_posix()
    except ValueError:
        relative_protocol = str(protocol_path.resolve())
    profiles: dict[str, dict[str, Any]] = {}
    baseline = protocol["baseline_dimensions"]
    for axis in protocol["axes"]:
        axis_id = axis["axis_id"]
        dimension = axis["dimension"]
        for arm_name in ARMS:
            opposite_name = "negative" if arm_name == "positive" else "positive"
            arm = axis[arm_name]
            opposite = axis[opposite_name]
            name = profile_name(axis_id, arm_name)
            counterpart_name = profile_name(axis_id, opposite_name)
            values = dict(baseline)
            values[dimension] = arm["value"]
            attributes = {
                key: {
                    "value": value,
                    "label": catalog[key].get("label") or key.replace("_", " ").title(),
                    "category": catalog[key].get("category") or "Other attributes",
                }
                for key, value in values.items()
            }
            profiles[name] = {
                "persona_id": f"{suite_id}-{name.replace('_', '-')}",
                "version": "1.0",
                "source": "synthetic:controlled-matched-pair",
                "display_name": protocol["display_name"],
                "experimental_profile": True,
                "interaction_protocol": "matched_pair_full_coverage.v1",
                "matched_pair": {
                    "schema_version": protocol["schema_version"],
                    "experiment_id": protocol["experiment_id"],
                    "protocol_path": relative_protocol,
                    "protocol_sha256": digest,
                    "pair_id": f"pair-{axis_id.replace('_', '-')}",
                    "axis_id": axis_id,
                    "axis_label": axis["label"],
                    "arm": arm_name,
                    "profile_name": name,
                    "counterpart_profile_name": counterpart_name,
                    "changed_dimension": dimension,
                    "target_value": arm["value"],
                    "opposite_value": opposite["value"],
                    "behavioral_definition": arm["behavioral_definition"],
                    "generic_observables": arm["generic_observables"],
                    "contradictions": arm["contradictions"],
                    "opposite_behavioral_definition": opposite["behavioral_definition"],
                    "opposite_generic_observables": opposite["generic_observables"],
                    "applicable_task_ids": list(axis["tasks"]),
                    "task_criteria": axis["tasks"],
                },
                "evaluation_dimensions": [dimension],
                "attributes": attributes,
            }
    _validate_generated_pair_deltas(profiles)
    return profiles


def _attribute_values(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (spec.get("value") if isinstance(spec, dict) else spec)
        for key, spec in (profile.get("attributes") or {}).items()
    }


def _validate_generated_pair_deltas(profiles: dict[str, dict[str, Any]]) -> None:
    """Assert that every generated pair differs on exactly its target field."""
    seen: set[str] = set()
    for profile in profiles.values():
        meta = profile["matched_pair"]
        pair_id = meta["pair_id"]
        if pair_id in seen:
            continue
        seen.add(pair_id)
        counterpart = profiles.get(meta["counterpart_profile_name"])
        if counterpart is None:
            raise ExperimentDefinitionError(f"{pair_id}: counterpart is missing")
        left = _attribute_values(profile)
        right = _attribute_values(counterpart)
        changed = {key for key in set(left) | set(right) if left.get(key) != right.get(key)}
        expected = {meta["changed_dimension"]}
        if changed != expected:
            raise ExperimentDefinitionError(
                f"{pair_id}: pair differs on {sorted(changed)}, expected {sorted(expected)}"
            )


def _render(payload: dict[str, Any]) -> str:
    header = (
        "# CONTROLLED MATCHED-PAIR PROFILE — synthetic experiment fixture.\n"
        "# Generated by odyssey/make_matched_personas.py; edit the protocol, not this file.\n"
    )
    return header + yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), 0o644)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def materialize_profiles(
    profiles: dict[str, dict[str, Any]],
    *,
    output_dir: Path,
    check: bool,
) -> list[Path]:
    """Write profiles, or check that checked-in generated files are current."""
    paths: list[Path] = []
    mismatches: list[Path] = []
    expected_names = {f"{name}.yaml" for name in profiles}
    for name, expected in profiles.items():
        path = output_dir / f"{name}.yaml"
        paths.append(path)
        if check:
            try:
                actual = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, yaml.YAMLError):
                mismatches.append(path)
                continue
            if actual != expected:
                mismatches.append(path)
        else:
            _atomic_write(path, _render(expected))

    if output_dir.is_dir():
        mismatches.extend(
            sorted(
                path
                for path in output_dir.glob("*.yaml")
                if path.name not in expected_names
            )
        )
    if mismatches:
        joined = "\n  ".join(str(path) for path in mismatches)
        raise ExperimentDefinitionError(
            "generated matched-pair profiles are missing, stale, or unexpected:\n  "
            + joined
        )
    return paths


def build_cells(
    protocol: dict[str, Any],
    tasks: list[dict[str, Any]],
    *,
    selected_task_ids: set[str] | None = None,
    selected_axes: set[str] | None = None,
    replicate_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return only protocol-approved task × axis × arm cells."""
    selected_task_ids = selected_task_ids or set()
    selected_axes = selected_axes or set()
    task_order = {str(task["task_id"]): index for index, task in enumerate(tasks)}
    cells: list[dict[str, Any]] = []
    for axis in protocol["axes"]:
        axis_id = axis["axis_id"]
        if selected_axes and axis_id not in selected_axes:
            continue
        for task_id in axis["tasks"]:
            if selected_task_ids and task_id not in selected_task_ids:
                continue
            arm_order = ARMS
            if replicate_id is not None:
                base = int.from_bytes(
                    hashlib.sha256(
                        f"{protocol['experiment_id']}|{task_id}|{axis_id}".encode("utf-8")
                    ).digest()[:2],
                    "big",
                ) % 2
                match = re.search(r"(\d+)$", replicate_id)
                replicate_phase = (
                    (int(match.group(1)) - 1) % 2
                    if match
                    else int.from_bytes(
                        hashlib.sha256(replicate_id.encode("utf-8")).digest()[:2],
                        "big",
                    ) % 2
                )
                if base ^ replicate_phase:
                    arm_order = tuple(reversed(ARMS))
            order_label = "-".join(arm_order)
            for position, arm in enumerate(arm_order, start=1):
                cells.append(
                    {
                        "task_id": task_id,
                        "task_number": task_order[task_id] + 1,
                        "axis_id": axis_id,
                        "arm": arm,
                        "persona": profile_name(axis_id, arm),
                        "pair_order": order_label,
                        "pair_position": position,
                    }
                )
    cells.sort(
        key=lambda cell: (
            task_order[cell["task_id"]],
            cell["axis_id"],
            cell["pair_position"],
        )
    )
    return cells


__all__ = [
    "ARMS",
    "DEFAULT_SCHEMA_PATH",
    "ExperimentDefinitionError",
    "build_cells",
    "dimension_catalog",
    "expected_profiles",
    "file_sha256",
    "load_json",
    "materialize_profiles",
    "profile_name",
    "validate_protocol",
]
