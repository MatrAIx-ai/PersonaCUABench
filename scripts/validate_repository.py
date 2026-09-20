#!/usr/bin/env python3
"""Validate the benchmark subset and reproducibility metadata offline."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = ROOT / "personacuabench"
TASKS_PATH = BENCHMARK_DIR / "tasks.json"
DIMENSIONS_PATH = BENCHMARK_DIR / "dimensions.json"
METADATA_PATH = BENCHMARK_DIR / "metadata.json"
MANIFEST_PATH = BENCHMARK_DIR / "osworld_manifest.json"
EXPERIMENT_PATH = BENCHMARK_DIR / "persona_experiment.json"
AVAILABILITY_POLICY_PATH = BENCHMARK_DIR / "availability_policies.json"
PREFLIGHT_SCHEMA_PATH = BENCHMARK_DIR / "schemas" / "network_preflight.schema.json"
PROMPTS_DIR = BENCHMARK_DIR / "prompts"
OSWORLD_INTEGRATION_DIR = ROOT / "integrations" / "osworld"
REPRODUCIBILITY_DIR = ROOT / "reproducibility"


def validate_repository_layout() -> None:
    expected_prompts = {
        "README.md",
        "agent.md",
        "experience_judge.md",
        "persona_user.md",
        "rubric_judge.md",
    }
    actual_prompts = {
        path.name for path in PROMPTS_DIR.iterdir() if path.is_file()
    } if PROMPTS_DIR.is_dir() else set()
    if actual_prompts != expected_prompts:
        fail(
            "personacuabench/prompts must contain exactly the documented prompt "
            f"assets: expected {sorted(expected_prompts)}, found {sorted(actual_prompts)}"
        )
    for name in expected_prompts - {"README.md"}:
        text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
        if not re.match(r"\A<!--.*?-->\s*\S", text, flags=re.DOTALL):
            fail(f"personacuabench/prompts/{name} lacks prompt metadata or body")

    expected_integration = {
        "README.md",
        "azure_foundry_agent.py",
        "install_osworld.sh",
    }
    actual_integration = {
        path.name for path in OSWORLD_INTEGRATION_DIR.iterdir() if path.is_file()
    } if OSWORLD_INTEGRATION_DIR.is_dir() else set()
    if actual_integration != expected_integration:
        fail(
            "integrations/osworld must contain only its adapter, installer, and "
            f"README: found {sorted(actual_integration)}"
        )

    legacy_files = [
        path for path in (ROOT / "odyssey").rglob("*") if path.is_file()
    ] if (ROOT / "odyssey").is_dir() else []
    if legacy_files:
        fail("legacy odyssey/ implementation files remain after the package rename")
    package_tests = sorted(BENCHMARK_DIR.glob("test*.py"))
    if package_tests:
        fail(
            "tests belong under tests/, not personacuabench/: "
            + ", ".join(path.name for path in package_tests)
        )


def fail(message: str) -> None:
    raise SystemExit(f"repository validation failed: {message}")


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read {path.relative_to(ROOT)}: {exc}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_persona_experiment(task_ids: list[str]) -> tuple[int, int]:
    protocol = load_json(EXPERIMENT_PATH)
    if not isinstance(protocol, dict):
        fail("personacuabench/persona_experiment.json must contain an object")
    if protocol.get("schema_version") != "personacuabench.matched-pair.v1":
        fail("persona experiment has an unsupported schema_version")
    axes = protocol.get("axes")
    if not isinstance(axes, list) or not 4 <= len(axes) <= 6:
        fail("persona experiment must define between four and six axes")
    design = protocol.get("design")
    if not isinstance(design, dict) or design.get("selected_axis_count") != len(axes):
        fail("persona experiment selected_axis_count differs from axes length")
    baseline = protocol.get("baseline_dimensions")
    if not isinstance(baseline, dict) or not baseline:
        fail("persona experiment has no baseline_dimensions")

    axis_ids: set[str] = set()
    dimensions: set[str] = set()
    task_axis_counts: Counter[str] = Counter()
    for axis in axes:
        if not isinstance(axis, dict):
            fail("persona experiment axis must be an object")
        axis_id = axis.get("axis_id")
        dimension = axis.get("dimension")
        if not isinstance(axis_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", axis_id
        ):
            fail(f"persona experiment has invalid axis_id: {axis_id!r}")
        if axis_id in axis_ids:
            fail(f"persona experiment has duplicate axis_id: {axis_id}")
        axis_ids.add(axis_id)
        if not isinstance(dimension, str) or dimension not in baseline:
            fail(f"{axis_id} target dimension is absent from baseline_dimensions")
        if dimension in dimensions:
            fail(f"persona experiment repeats target dimension: {dimension}")
        dimensions.add(dimension)
        values: list[str] = []
        for arm_name in ("positive", "negative"):
            arm = axis.get(arm_name)
            if not isinstance(arm, dict) or not str(arm.get("value", "")).strip():
                fail(f"{axis_id}/{arm_name} has no value")
            values.append(str(arm["value"]))
        if values[0] == values[1]:
            fail(f"{axis_id} arm values must differ")

        criteria = axis.get("tasks")
        if not isinstance(criteria, dict) or not criteria:
            fail(f"{axis_id} has no task criteria")
        unknown = set(criteria) - set(task_ids)
        if unknown:
            fail(f"{axis_id} references unknown tasks: {sorted(unknown)}")
        for task_id, criterion in criteria.items():
            if not isinstance(criterion, dict):
                fail(f"{axis_id}/{task_id} criterion must be an object")
            for field in (
                "inherited_task_signals",
                "positive_observables",
                "negative_observables",
            ):
                value = criterion.get(field)
                if not isinstance(value, list) or not value or not all(
                    isinstance(item, str) and item.strip() for item in value
                ):
                    fail(f"{axis_id}/{task_id}/{field} must be non-empty strings")
            task_axis_counts[task_id] += 1

    if set(task_axis_counts) != set(task_ids):
        fail("persona experiment does not cover every benchmark task")
    if any(count != 3 for count in task_axis_counts.values()):
        fail(f"each task must have exactly three axes: {dict(task_axis_counts)}")
    task_axis_pairs = sum(task_axis_counts.values())
    if design.get("expected_task_axis_pairs_per_replicate") != task_axis_pairs:
        fail("persona experiment task-axis total differs from design metadata")
    run_cells = task_axis_pairs * 2
    if design.get("expected_run_cells_per_replicate") != run_cells:
        fail("persona experiment run-cell total differs from design metadata")
    return len(axes), run_cells


def validate_availability_policy(tasks: list[dict[str, object]]) -> int:
    policy = load_json(AVAILABILITY_POLICY_PATH)
    if not isinstance(policy, dict):
        fail("personacuabench/availability_policies.json must contain an object")
    if policy.get("schema_version") != "persona-cua-availability-policy/v1":
        fail("availability policy has an unsupported schema_version")
    task_policies = policy.get("tasks")
    if not isinstance(task_policies, dict):
        fail("availability policy tasks must be an object")

    rubrics_by_task = {
        str(task["task_id"]): set(task["rubrics"])
        for task in tasks
        if isinstance(task.get("rubrics"), dict)
    }
    unknown_tasks = set(task_policies) - set(rubrics_by_task)
    if unknown_tasks:
        fail(f"availability policy references unknown tasks: {sorted(unknown_tasks)}")

    for task_id, task_policy in task_policies.items():
        if not isinstance(task_policy, dict):
            fail(f"availability policy for {task_id} must be an object")
        if task_policy.get("rubric_mapping_semantics") != "exclusive_blocking_dependency":
            fail(f"availability policy for {task_id} has invalid mapping semantics")
        endpoints = task_policy.get("endpoints")
        if not isinstance(endpoints, list) or not endpoints:
            fail(f"availability policy for {task_id} has no endpoints")

        keys: set[str] = set()
        target_count = 0
        control_hosts: set[str] = set()
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                fail(f"availability policy for {task_id} has a non-object endpoint")
            key = endpoint.get("key")
            role = endpoint.get("role")
            url = endpoint.get("url")
            affected = endpoint.get("affected_rubric_ids")
            if not isinstance(key, str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", key
            ):
                fail(f"availability policy for {task_id} has invalid endpoint key")
            if key in keys:
                fail(f"availability policy for {task_id} repeats endpoint {key}")
            keys.add(key)
            if role not in {"target", "control"}:
                fail(f"availability endpoint {task_id}/{key} has invalid role")
            if not isinstance(url, str):
                fail(f"availability endpoint {task_id}/{key} has no URL")
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                fail(f"availability endpoint {task_id}/{key} has invalid URL")
            if not isinstance(affected, list) or not all(
                isinstance(item, str) for item in affected
            ):
                fail(f"availability endpoint {task_id}/{key} has invalid rubric IDs")
            unknown_rubrics = set(affected) - rubrics_by_task[task_id]
            if unknown_rubrics:
                fail(
                    f"availability endpoint {task_id}/{key} references unknown rubrics: "
                    f"{sorted(unknown_rubrics)}"
                )
            if role == "target":
                target_count += 1
                if not affected:
                    fail(f"availability target {task_id}/{key} affects no rubric")
            else:
                if affected:
                    fail(f"availability control {task_id}/{key} affects a rubric")
                control_hosts.add(parsed.hostname.lower())
        if target_count == 0 or len(control_hosts) < 2:
            fail(
                f"availability policy for {task_id} needs a target and two controls"
            )

    schema = load_json(PREFLIGHT_SCHEMA_PATH)
    if not isinstance(schema, dict):
        fail("personacuabench/schemas/network_preflight.schema.json must contain an object")
    properties = schema.get("properties")
    schema_version = (
        properties.get("schema_version")
        if isinstance(properties, dict)
        else None
    )
    if not isinstance(schema_version, dict) or schema_version.get("const") != (
        "persona-cua-network-preflight/v1"
    ):
        fail("network preflight schema does not pin the v1 artifact contract")
    return len(task_policies)


def main() -> int:
    validate_repository_layout()
    metadata = load_json(METADATA_PATH)
    tasks = load_json(TASKS_PATH)
    manifest = load_json(MANIFEST_PATH)
    if not isinstance(metadata, dict):
        fail("personacuabench/metadata.json must contain an object")
    if metadata.get("schema_version") != "personacuabench.subset.v1":
        fail("personacuabench/metadata.json has an unsupported schema_version")
    if not isinstance(tasks, list):
        fail("personacuabench/tasks.json must contain an array")
    if not isinstance(manifest, dict) or not isinstance(
        manifest.get("mind2web_chrome"), list
    ):
        fail("personacuabench/osworld_manifest.json has an invalid schema")

    duplicate_sources = [
        ROOT / "benchmark" / "tasks.json",
        ROOT / "configs" / "personas",
        ROOT / "odyssey" / "tasks.json",
    ]
    for duplicate in duplicate_sources:
        if duplicate.exists():
            fail(
                f"duplicate canonical source exists at {duplicate.relative_to(ROOT)}; "
                "personacuabench/ is the single source of truth"
            )

    expected_task_count = metadata.get("task_count")
    expected_rubric_count = metadata.get("rubric_count")
    if len(tasks) != expected_task_count:
        fail(f"expected {expected_task_count} tasks, found {len(tasks)}")

    task_ids: list[str] = []
    rubric_count = 0
    levels: Counter[str] = Counter()
    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            fail(f"task #{index} is not an object")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{40}", task_id):
            fail(f"task #{index} has an invalid task_id")
        if not str(task.get("confirmed_task", "")).strip():
            fail(f"{task_id} has no confirmed_task")
        rubrics = task.get("rubrics")
        if not isinstance(rubrics, dict) or not rubrics:
            fail(f"{task_id} has no rubrics")
        expected_ids = [f"R{i}" for i in range(1, len(rubrics) + 1)]
        if list(rubrics) != expected_ids:
            fail(f"{task_id} rubric IDs must be sequential: {expected_ids}")
        for rubric_id, rubric in rubrics.items():
            if not isinstance(rubric, dict):
                fail(f"{task_id}/{rubric_id} is not an object")
            for field in ("requirement", "verification"):
                if not str(rubric.get(field, "")).strip():
                    fail(f"{task_id}/{rubric_id} has no {field}")
        task_ids.append(task_id)
        rubric_count += len(rubrics)
        levels[str(task.get("level"))] += 1

    if len(task_ids) != len(set(task_ids)):
        fail("task IDs are not unique")
    if rubric_count != expected_rubric_count:
        fail(f"expected {expected_rubric_count} rubrics, found {rubric_count}")
    if dict(levels) != metadata.get("levels"):
        fail(f"level counts differ: {dict(levels)}")
    if manifest["mind2web_chrome"] != task_ids:
        fail("OSWorld manifest IDs/order differ from personacuabench/tasks.json")

    axis_count, matched_pair_cells = validate_persona_experiment(task_ids)
    availability_task_count = validate_availability_policy(tasks)

    hash_specs = (
        (TASKS_PATH, "tasks_sha256"),
        (DIMENSIONS_PATH, "dimensions_sha256"),
        (EXPERIMENT_PATH, "persona_experiment_sha256"),
        (AVAILABILITY_POLICY_PATH, "availability_policy_sha256"),
        (PREFLIGHT_SCHEMA_PATH, "network_preflight_schema_sha256"),
    )
    hashes: dict[str, str] = {}
    for path, metadata_key in hash_specs:
        actual = sha256(path)
        hashes[metadata_key] = actual
        if actual != metadata.get(metadata_key):
            fail(
                f"{path.relative_to(ROOT)} differs from its recorded checksum: "
                f"{actual}"
            )

    for name in ("OSWORLD_COMMIT", "ODYSSEYS_COMMIT", "PERSONA8B_COMMIT"):
        value = (REPRODUCIBILITY_DIR / name).read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", value):
            fail(f"{name} must contain one full git commit SHA")

    artifact_hashes = {
        "OSWORLD_UV_LOCK_SHA256": "uv.lock",
        "UBUNTU_ARM_SHA256": "Ubuntu-arm.zip",
    }
    for name, artifact_name in artifact_hashes.items():
        value = (REPRODUCIBILITY_DIR / name).read_text(encoding="utf-8").strip()
        if not re.fullmatch(
            rf"[0-9a-f]{{64}}  {re.escape(artifact_name)}", value
        ):
            fail(f"{name} must contain one sha256sum line for {artifact_name}")

    upstream_dimensions = (
        ROOT / "MatrAIx-Persona-8B" / "persona" / "schema" / "dimensions.json"
    )
    if upstream_dimensions.is_file() and (
        upstream_dimensions.read_bytes() != DIMENSIONS_PATH.read_bytes()
    ):
        fail("personacuabench/dimensions.json differs from the pinned Persona-8B schema")

    print("repository validation: ok")
    print(f"tasks: {len(tasks)} ({dict(levels)})")
    print(f"rubrics: {rubric_count}")
    print(f"persona axes: {axis_count}")
    print(f"matched-pair cells per replicate: {matched_pair_cells}")
    print(f"availability-configured tasks: {availability_task_count}")
    print(f"tasks sha256: {hashes['tasks_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
