#!/usr/bin/env python3
"""Plan, cache persona openings, or execute applicable matched-pair cells.

The default is a free dry run. ``--materialize-openings`` makes paid persona
model calls but launches no browser/CUA/judge; ``--execute`` runs complete
cells. Extra arguments after ``--`` are forwarded to ``odyssey/run.py``.
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import persona_experiment as experiment  # noqa: E402
import task_router  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", default="shopping")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--replicate-id", required=True)
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help="task ordinal, full ID, or unique ID prefix; repeat as needed",
    )
    parser.add_argument(
        "--axis", action="append", default=[], help="axis_id; repeat as needed"
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--profile-root",
        type=Path,
        default=REPO / "artifacts" / "chrome-profiles" / "matched-pairs",
        help="root for isolated per-cell Chrome profiles",
    )
    parser.add_argument("--headless", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true")
    mode.add_argument(
        "--materialize-openings",
        action="store_true",
        help="call only the persona model, print and cache every selected opening",
    )
    parser.add_argument(
        "run_args",
        nargs=argparse.REMAINDER,
        help="arguments after -- are forwarded to odyssey/run.py",
    )
    return parser


def _strip_separator(values: list[str]) -> list[str]:
    return values[1:] if values and values[0] == "--" else values


def _reject_owned_run_args(values: list[str]) -> None:
    owned = (
        "--suite", "--tasks-file", "--task", "--all", "--persona",
        "--replicate-id", "--profile", "--pair-order", "--pair-position",
        "--preview", "--list-suites", "--list-tasks", "--help",
    )
    for value in values:
        if any(value == flag or value.startswith(f"{flag}=") for flag in owned):
            raise experiment.ExperimentDefinitionError(
                f"{value!r} is owned by run_matched_pairs.py and cannot be forwarded"
            )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not task_router.PERSONA_ID_RE.fullmatch(args.replicate_id):
        raise SystemExit("--replicate-id must be one path-safe token")
    try:
        suite = task_router.TaskCatalog.load().get_suite(args.suite)
        protocol_path = (
            args.protocol.expanduser().resolve()
            if args.protocol
            else suite.persona_experiment
        )
        if protocol_path is None:
            raise experiment.ExperimentDefinitionError(
                f"suite {suite.suite_id!r} has no persona_experiment"
            )
        catalog = experiment.dimension_catalog()
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
        experiment.materialize_profiles(
            profiles,
            output_dir=HERE / "personas" / suite.suite_id / "matched_pairs",
            check=True,
        )

        selected_task_ids: set[str] = set()
        for selector in args.task:
            selected_task_ids.update(
                task["task_id"] for task in suite.resolve(selector, False)
            )
        selected_axes = set(args.axis)
        known_axes = {axis["axis_id"] for axis in protocol["axes"]}
        unknown_axes = selected_axes - known_axes
        if unknown_axes:
            raise experiment.ExperimentDefinitionError(
                f"unknown --axis values: {sorted(unknown_axes)}"
            )
        cells = experiment.build_cells(
            protocol,
            suite.tasks,
            selected_task_ids=selected_task_ids,
            selected_axes=selected_axes,
            replicate_id=args.replicate_id,
        )
        if not cells:
            raise experiment.ExperimentDefinitionError("selection produced no cells")
        run_args = _strip_separator(list(args.run_args))
        _reject_owned_run_args(run_args)
    except (experiment.ExperimentDefinitionError, task_router.TaskRoutingError) as exc:
        raise SystemExit(f"matched-pair plan error: {exc}") from exc

    commands: list[list[str]] = []
    profile_root = args.profile_root.expanduser().resolve()
    for cell in cells:
        profile = (
            profile_root
            / suite.suite_id
            / args.replicate_id
            / cell["task_id"]
            / cell["axis_id"]
            / cell["arm"]
        )
        command = [
            # Keep a virtualenv's interpreter path intact.  Resolving the
            # symlink here can turn ``.venv/bin/python`` into the base Python
            # executable, which makes the child lose the venv's site-packages.
            str(args.python.expanduser().absolute()),
            str(HERE / "run.py"),
            "--suite",
            suite.suite_id,
            "--task",
            cell["task_id"],
            "--persona",
            cell["persona"],
            "--replicate-id",
            args.replicate_id,
            "--pair-order",
            cell["pair_order"],
            "--pair-position",
            str(cell["pair_position"]),
            "--profile",
            str(profile),
            "--skip-existing",
        ]
        if args.headless:
            command.append("--headless")
        if args.materialize_openings:
            command.append("--preview")
        command.extend(run_args)
        commands.append(command)

    mode = (
        "EXECUTE"
        if args.execute
        else "MATERIALIZE OPENINGS"
        if args.materialize_openings
        else "DRY RUN"
    )
    print(
        f"{mode}: suite={suite.suite_id} replicate={args.replicate_id} "
        f"cells={len(cells)} tasks={len({cell['task_id'] for cell in cells})} "
        f"axes={len({cell['axis_id'] for cell in cells})}"
    )
    for index, (cell, command) in enumerate(zip(cells, commands), start=1):
        print(
            f"[{index}/{len(cells)}] task={cell['task_number']} "
            f"axis={cell['axis_id']} arm={cell['arm']} "
            f"order={cell['pair_order']}:{cell['pair_position']} "
            f"persona={cell['persona']}"
        )
        print("  " + shlex.join(command))

    if not args.execute and not args.materialize_openings:
        print("No model or browser call was made. Add --execute to run this plan.")
        return 0

    environment = dict(os.environ)
    for index, command in enumerate(commands, start=1):
        print(f"running cell {index}/{len(commands)}", flush=True)
        completed = subprocess.run(command, cwd=REPO, env=environment, check=False)
        if completed.returncode:
            print(
                f"cell {index}/{len(commands)} failed with exit "
                f"{completed.returncode}; stop and resume with the same command",
                file=sys.stderr,
            )
            return completed.returncode
    if args.materialize_openings:
        print(f"persona openings materialized: {len(commands)}/{len(commands)} cells")
    else:
        print(f"matched-pair replicate complete: {len(commands)}/{len(commands)} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
