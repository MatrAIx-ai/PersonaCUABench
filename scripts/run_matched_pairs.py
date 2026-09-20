#!/usr/bin/env python3
"""Plan or serially run only the applicable matched-pair experiment cells."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "personacuabench" / "persona_experiment.json"
DEFAULT_TASKS = ROOT / "personacuabench" / "tasks.json"
DEFAULT_RUNTIME_PYTHON = ROOT / ".osworld" / "OSWorld" / ".venv" / "bin" / "python"


class PlanError(ValueError):
    """Raised when the checked-in experiment cannot produce a run plan."""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"Cannot read {path}: {exc}") from exc


def build_cells(
    protocol: dict[str, Any],
    tasks: list[dict[str, Any]],
    *,
    selected_tasks: set[int],
    selected_axes: set[str],
) -> list[dict[str, Any]]:
    task_number_by_id = {
        str(task["task_id"]): number for number, task in enumerate(tasks, start=1)
    }
    cells: list[dict[str, Any]] = []
    for axis in protocol.get("axes", []):
        if not isinstance(axis, dict):
            raise PlanError("Every protocol axis must be an object")
        axis_id = str(axis.get("axis_id") or "")
        if selected_axes and axis_id not in selected_axes:
            continue
        criteria = axis.get("tasks")
        if not isinstance(criteria, dict):
            raise PlanError(f"{axis_id} has no task mapping")
        for task_id in criteria:
            task_number = task_number_by_id.get(task_id)
            if task_number is None:
                raise PlanError(f"{axis_id} references unknown task {task_id}")
            if selected_tasks and task_number not in selected_tasks:
                continue
            for arm in ("positive", "negative"):
                cells.append(
                    {
                        "task_number": task_number,
                        "task_id": task_id,
                        "axis_id": axis_id,
                        "arm": arm,
                        "persona": f"mp_{axis_id}_{arm}",
                    }
                )
    cells.sort(
        key=lambda cell: (
            cell["task_number"],
            cell["axis_id"],
            0 if cell["arm"] == "positive" else 1,
        )
    )
    return cells


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--tasks-file", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--replicate-id", required=True)
    parser.add_argument(
        "--task",
        type=int,
        action="append",
        default=[],
        help="limit to a 1-based task number; repeat to select multiple tasks",
    )
    parser.add_argument(
        "--axis",
        action="append",
        default=[],
        help="limit to an axis_id; repeat to select multiple axes",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=DEFAULT_RUNTIME_PYTHON if DEFAULT_RUNTIME_PYTHON.is_file() else Path(sys.executable),
        help="Python executable used for personacuabench.run",
    )
    parser.add_argument(
        "--run-arg",
        action="append",
        default=[],
        help="one additional argument for personacuabench.run; repeat as needed",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="execute serially; without this flag the command only prints the plan",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.replicate_id.strip():
        parser.error("--replicate-id must be non-empty")
    protocol = _json(args.protocol.expanduser().resolve())
    tasks = _json(args.tasks_file.expanduser().resolve())
    if not isinstance(protocol, dict) or not isinstance(tasks, list):
        parser.error("protocol must be an object and tasks-file must be an array")
    task_numbers = set(args.task)
    if task_numbers and (
        min(task_numbers) < 1 or max(task_numbers) > len(tasks)
    ):
        parser.error(f"--task must be between 1 and {len(tasks)}")
    available_axes = {
        str(axis.get("axis_id"))
        for axis in protocol.get("axes", [])
        if isinstance(axis, dict)
    }
    requested_axes = set(args.axis)
    unknown_axes = requested_axes - available_axes
    if unknown_axes:
        parser.error(f"unknown --axis values: {sorted(unknown_axes)}")

    try:
        cells = build_cells(
            protocol,
            tasks,
            selected_tasks=task_numbers,
            selected_axes=requested_axes,
        )
    except PlanError as exc:
        parser.error(str(exc))
    if not cells:
        parser.error("selection produced no matched-pair cells")

    python = args.python.expanduser().resolve()
    commands: list[list[str]] = []
    for cell in cells:
        commands.append(
            [
                str(python),
                "-m",
                "personacuabench.run",
                "--task",
                str(cell["task_number"]),
                "--persona",
                cell["persona"],
                "--replicate-id",
                args.replicate_id,
                "--headless",
                *args.run_arg,
            ]
        )

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(
        f"{mode}: {len(cells)} cells, replicate={args.replicate_id}, "
        f"tasks={sorted({cell['task_number'] for cell in cells})}"
    )
    for index, (cell, command) in enumerate(zip(cells, commands), start=1):
        print(
            f"[{index}/{len(cells)}] task={cell['task_number']} "
            f"axis={cell['axis_id']} arm={cell['arm']} persona={cell['persona']}"
        )
        print("  " + shlex.join(command))

    if not args.execute:
        print("No model, VM, or browser call was made. Add --execute to run this plan.")
        return 0

    environment = dict(os.environ)
    current_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + current_pythonpath if current_pythonpath else ""
    )
    for index, command in enumerate(commands, start=1):
        print(f"running cell {index}/{len(commands)}", flush=True)
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    print(f"matched-pair replicate complete: {len(commands)}/{len(commands)} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
