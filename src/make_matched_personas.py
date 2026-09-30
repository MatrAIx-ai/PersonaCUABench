#!/usr/bin/env python3
"""Generate or validate a suite's controlled matched-pair personas.

Examples:

    python src/make_matched_personas.py --suite shopping
    python src/make_matched_personas.py --suite shopping --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import persona_experiment as experiment  # noqa: E402
import task_router  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        default="shopping",
        help="registered suite with a persona_experiment entry (default: shopping)",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        help="override the suite's registered protocol (advanced use)",
    )
    parser.add_argument("--schema", type=Path, default=experiment.DEFAULT_SCHEMA_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="default: src/personas/<suite>/matched_pairs",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the protocol and confirm generated YAML is current",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        suite = task_router.TaskCatalog.load().get_suite(args.suite)
        protocol_path = (
            args.protocol.expanduser().resolve()
            if args.protocol
            else suite.persona_experiment
        )
        if protocol_path is None:
            raise experiment.ExperimentDefinitionError(
                f"suite {suite.suite_id!r} has no persona_experiment in task_suites.json"
            )
        catalog = experiment.dimension_catalog(args.schema.expanduser().resolve())
        protocol = experiment.validate_protocol(
            experiment.load_json(protocol_path),
            catalog=catalog,
            task_ids=[task["task_id"] for task in suite.tasks],
            expected_suite_id=suite.suite_id,
        )
        profiles = experiment.expected_profiles(
            protocol,
            catalog=catalog,
            suite_id=suite.suite_id,
            protocol_path=protocol_path,
        )
        output_dir = (
            args.output_dir.expanduser().resolve()
            if args.output_dir
            else HERE / "personas" / suite.suite_id / "matched_pairs"
        )
        paths = experiment.materialize_profiles(
            profiles, output_dir=output_dir, check=args.check
        )
    except (experiment.ExperimentDefinitionError, task_router.TaskRoutingError) as exc:
        raise SystemExit(f"persona experiment error: {exc}") from exc

    verb = "checked" if args.check else "wrote"
    print(
        f"{verb} {len(paths)} personas across {len(protocol['axes'])} matched pairs "
        f"for suite {suite.suite_id!r}"
    )
    print(
        f"matrix: {protocol['design']['expected_task_axis_pairs_per_replicate']} "
        "task-axis pairs / "
        f"{protocol['design']['expected_run_cells_per_replicate']} cells per replicate"
    )
    for path in paths:
        print(f"{verb}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
