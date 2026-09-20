#!/usr/bin/env python3
"""Summarize PersonaCUABench result files without third-party packages."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "results"
TASKS_FILE = Path(__file__).resolve().parent / "tasks.json"

EXPERIENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("P1_asked_for", "P1 asked for"),
    ("P2_readable_for_them", "P2 readable"),
    ("P3_actionable", "P3 actionable"),
    ("P4_gap_handling", "P4 gap handling"),
    ("P5_overall", "P5 overall"),
)


@dataclass(frozen=True)
class Row:
    task: str
    persona: str
    run: str
    status: str
    environment: str
    task_score: str
    adjusted_task_score: str
    communicated_score: str
    persona_alignment: str
    experience_status: str
    experience_p1: str
    experience_p2: str
    experience_p3: str
    experience_p4: str
    experience_p5: str
    sort_key: tuple[int, str, str]


def nested(payload: object, *path: str) -> object | None:
    current = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def first(payload: object, paths: Iterable[tuple[str, ...]]) -> object | None:
    for path in paths:
        value = nested(payload, *path)
        if value is not None and value != "":
            return value
    return None


def scalar(value: object | None, *, keys: Sequence[str] = ()) -> object | None:
    if isinstance(value, Mapping):
        for key in (*keys, "score", "value", "name", "id", "slug"):
            candidate = value.get(key)
            if candidate is not None and not isinstance(candidate, (dict, list)):
                return candidate
        return None
    if isinstance(value, list):
        return None
    return value


def display(value: object | None) -> str:
    value = scalar(value)
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            return "—"
        return f"{number:.3f}".rstrip("0").rstrip(".")
    return " ".join(str(value).split())


def _experience(payload: object) -> Mapping[str, Any]:
    value = first(payload, (("experience",), ("judgement", "experience")))
    return value if isinstance(value, Mapping) else {}


def _experience_judge(
    experience: Mapping[str, Any], canonical: str, legacy: str
) -> Mapping[str, Any]:
    judges = experience.get("judges")
    judges = judges if isinstance(judges, Mapping) else {}
    value = experience.get(canonical)
    if not isinstance(value, Mapping):
        value = judges.get(canonical)
    if not isinstance(value, Mapping):
        value = experience.get(legacy)
    if not isinstance(value, Mapping):
        value = judges.get(legacy)
    return value if isinstance(value, Mapping) else {}


def _experience_judge_body(judge: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the scored payload across current and early result envelopes."""
    for key in ("verdict", "result", "output", "response", "scores"):
        value = judge.get(key)
        if isinstance(value, Mapping):
            return value
    return judge


def _experience_score(judge: Mapping[str, Any], dimension: str) -> object | None:
    value = _experience_judge_body(judge).get(dimension)
    if isinstance(value, Mapping):
        return value.get("score")
    return value


def _experience_status(payload: object) -> str:
    experience = _experience(payload)
    if not experience:
        return "—"
    explicit = scalar(experience.get("status"))
    if explicit is not None:
        return display(explicit)
    judge_a = _experience_judge(experience, "judge_a", "a")
    judge_b = _experience_judge(experience, "judge_b", "b")
    judges = (judge_a, judge_b)
    score_count = sum(
        _experience_score(judge, dimension) is not None
        for judge in judges
        for dimension, _label in EXPERIENCE_DIMENSIONS
    )
    if score_count == len(EXPERIENCE_DIMENSIONS) * 2:
        return "complete"
    if any(judge.get("error") for judge in judges) and score_count == 0:
        return "failed"
    return "partial" if judge_a or judge_b else "pending"


def _experience_dimension_display(payload: object, dimension: str) -> str:
    experience = _experience(payload)
    if not experience:
        return "—"
    judge_a = _experience_judge(experience, "judge_a", "a")
    judge_b = _experience_judge(experience, "judge_b", "b")
    score_a = _experience_score(judge_a, dimension)
    score_b = _experience_score(judge_b, dimension)
    parts: list[str] = []
    if score_a is not None:
        parts.append(f"A={display(score_a)}")
    if score_b is not None:
        parts.append(f"B={display(score_b)}")
    agreement = experience.get("agreement")
    if isinstance(agreement, Mapping):
        dimension_agreement = agreement.get(dimension)
        dimensions = agreement.get("dimensions")
        if not isinstance(dimension_agreement, Mapping) and isinstance(
            dimensions, Mapping
        ):
            dimension_agreement = dimensions.get(dimension)
    else:
        dimension_agreement = None
    if isinstance(dimension_agreement, Mapping):
        within_one = dimension_agreement.get("within_one")
        if isinstance(within_one, bool):
            parts.append(f"within1={'yes' if within_one else 'no'}")
    return "; ".join(parts) if parts else "—"


def load_task_order() -> tuple[dict[str, int], dict[int, str]]:
    try:
        tasks = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    if not isinstance(tasks, list):
        return {}, {}
    by_id: dict[str, int] = {}
    by_number: dict[int, str] = {}
    for number, task in enumerate(tasks, start=1):
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("task_id")
        if isinstance(task_id, str) and task_id:
            by_id[task_id] = number
            by_number[number] = task_id
    return by_id, by_number


def infer_path_fields(path: Path, results_dir: Path) -> tuple[str, str]:
    try:
        parts = path.relative_to(results_dir).parts
    except ValueError:
        parts = path.parts
    task = parts[0] if len(parts) >= 3 else "unknown"
    run_directory = parts[-2] if len(parts) >= 2 else "unknown"
    persona = run_directory.split("__", 1)[0] or "unknown"
    return task, persona


def status_for(payload: object) -> str:
    explicit = scalar(
        first(
            payload,
            (
                ("status",),
                ("run", "status"),
                ("judgement", "status"),
                ("judgment", "status"),
            ),
        )
    )
    if explicit is not None:
        normalized = " ".join(str(explicit).split()).lower()
        aliases = {
            "completed": "complete",
            "done": "complete",
            "success": "complete",
            "succeeded": "complete",
            "in_progress": "pending",
            "in-progress": "pending",
            "running": "pending",
            "queued": "pending",
        }
        return aliases.get(normalized, normalized)

    error = first(payload, (("error",), ("run", "error"), ("judgement", "error")))
    if error:
        return "failed"
    judgement = first(payload, (("judgement",), ("judgment",)))
    if isinstance(judgement, Mapping) and any(
        judgement.get(key) is not None
        for key in ("score", "score_raw", "verdicts", "score_communicated")
    ):
        return "complete"
    return "pending"


def parse_result(
    path: Path,
    results_dir: Path,
    task_order: Mapping[str, int],
    task_ids: Mapping[int, str],
) -> Row:
    fallback_task, fallback_persona = infer_path_fields(path, results_dir)
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Row(
            task=fallback_task,
            persona=fallback_persona,
            run=path.parent.name,
            status="invalid",
            environment="—",
            task_score="—",
            adjusted_task_score="—",
            communicated_score="—",
            persona_alignment="—",
            experience_status="—",
            experience_p1="—",
            experience_p2="—",
            experience_p3="—",
            experience_p4="—",
            experience_p5="—",
            sort_key=(task_order.get(fallback_task, 10**9), fallback_persona, str(path)),
        )
    if not isinstance(payload, Mapping):
        return Row(
            task=fallback_task,
            persona=fallback_persona,
            run=path.parent.name,
            status="invalid",
            environment="—",
            task_score="—",
            adjusted_task_score="—",
            communicated_score="—",
            persona_alignment="—",
            experience_status="—",
            experience_p1="—",
            experience_p2="—",
            experience_p3="—",
            experience_p4="—",
            experience_p5="—",
            sort_key=(task_order.get(fallback_task, 10**9), fallback_persona, str(path)),
        )

    raw_task = scalar(
        first(
            payload,
            (
                ("task_id",),
                ("task", "task_id"),
                ("run", "task_id"),
                ("metadata", "task_id"),
            ),
        )
    )
    task_id = str(raw_task) if raw_task is not None else fallback_task
    if task_id.isdigit() and int(task_id) in task_ids:
        task_id = task_ids[int(task_id)]
    number = task_order.get(task_id)
    task_label = f"{number}: {task_id}" if number is not None else task_id

    raw_persona = scalar(
        first(
            payload,
            (
                ("persona",),
                ("persona_name",),
                ("run", "persona"),
                ("metadata", "persona"),
            ),
        ),
        keys=("persona_name",),
    )
    persona = display(raw_persona) if raw_persona is not None else fallback_persona

    task_score = first(
        payload,
        (
            ("judgement", "score_raw"),
            ("judgement", "score"),
            ("judgment", "score_raw"),
            ("judgment", "score"),
            ("judgement", "task_success", "score_raw"),
            ("judgment", "task_success", "score_raw"),
            ("evaluation", "task_score"),
            ("task_score",),
            ("score",),
        ),
    )
    adjusted_task_score = first(
        payload,
        (
            ("judgement", "score_availability_adjusted"),
            ("judgment", "score_availability_adjusted"),
            ("judgement", "task_success", "score_availability_adjusted"),
            ("judgment", "task_success", "score_availability_adjusted"),
            ("evaluation", "score_availability_adjusted"),
            ("score_availability_adjusted",),
        ),
    )
    communicated = first(
        payload,
        (
            ("judgement", "score_communicated_raw"),
            ("judgement", "score_communicated"),
            ("judgment", "score_communicated_raw"),
            ("judgment", "score_communicated"),
            ("judgement", "task_success", "score_communicated_raw"),
            ("judgment", "task_success", "score_communicated_raw"),
            ("evaluation", "score_communicated"),
            ("score_communicated",),
        ),
    )
    alignment = first(
        payload,
        (
            ("judgement", "persona", "alignment", "persona_alignment_score"),
            ("judgement", "persona_alignment"),
            ("judgement", "persona_alignment_score"),
            ("judgement", "alignment", "persona_alignment_score"),
            ("judgment", "persona", "alignment", "persona_alignment_score"),
            ("judgment", "persona_alignment"),
            ("judgment", "alignment", "persona_alignment_score"),
            ("evaluation", "persona_alignment"),
            ("evaluation", "alignment", "persona_alignment_score"),
            ("run", "persona_alignment"),
            ("persona_alignment",),
            ("alignment", "persona_alignment_score"),
        ),
    )
    alignment = scalar(
        alignment,
        keys=("persona_alignment_score", "alignment", "alignment_score"),
    )
    alignment_status = scalar(
        first(
            payload,
            (
                ("judgement", "persona", "alignment", "persona_alignment_status"),
                ("judgement", "persona_alignment_status"),
                ("judgement", "alignment", "persona_alignment_status"),
                ("judgment", "persona", "alignment", "persona_alignment_status"),
                ("judgment", "persona_alignment_status"),
                ("judgment", "alignment", "persona_alignment_status"),
                ("evaluation", "alignment", "persona_alignment_status"),
                ("persona_alignment_status",),
                ("alignment", "persona_alignment_status"),
            ),
        )
    )
    alignment_score_display = display(alignment)
    alignment_status_display = display(alignment_status)
    if alignment_status_display != "—" and alignment_score_display != "—":
        alignment_display = f"{alignment_status_display} ({alignment_score_display})"
    elif alignment_status_display != "—":
        alignment_display = alignment_status_display
    else:
        alignment_display = alignment_score_display

    environment = first(
        payload,
        (
            ("judgement", "environment_feasibility", "status"),
            ("judgment", "environment_feasibility", "status"),
            ("run", "environment", "status"),
        ),
    )

    return Row(
        task=task_label,
        persona=persona,
        run=path.parent.name,
        status=status_for(payload),
        environment=display(environment),
        task_score=display(task_score),
        adjusted_task_score=display(adjusted_task_score),
        communicated_score=display(communicated),
        persona_alignment=alignment_display,
        experience_status=_experience_status(payload),
        experience_p1=_experience_dimension_display(payload, "P1_asked_for"),
        experience_p2=_experience_dimension_display(payload, "P2_readable_for_them"),
        experience_p3=_experience_dimension_display(payload, "P3_actionable"),
        experience_p4=_experience_dimension_display(payload, "P4_gap_handling"),
        experience_p5=_experience_dimension_display(payload, "P5_overall"),
        sort_key=(number if number is not None else 10**9, persona, str(path)),
    )


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def print_markdown(rows: Sequence[Row]) -> None:
    headers = (
        "Task",
        "Persona",
        "Run",
        "Status",
        "Environment",
        "Task score (raw)",
        "Adjusted task score (diagnostic)",
        "Communicated score",
        "Persona alignment",
        "Experience status",
        "P1 asked for (A/B)",
        "P2 readable (A/B)",
        "P3 actionable (A/B)",
        "P4 gap handling (A/B)",
        "P5 overall (A/B)",
    )
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        values = (
            row.task,
            row.persona,
            row.run,
            row.status,
            row.environment,
            row.task_score,
            row.adjusted_task_score,
            row.communicated_score,
            row.persona_alignment,
            row.experience_status,
            row.experience_p1,
            row.experience_p2,
            row.experience_p3,
            row.experience_p4,
            row.experience_p5,
        )
        print("| " + " | ".join(markdown_cell(value) for value in values) + " |")


def print_csv(rows: Sequence[Row]) -> None:
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(
        (
            "task",
            "persona",
            "run",
            "status",
            "environment",
            "task_score",
            "adjusted_task_score",
            "communicated_score",
            "persona_alignment",
            "experience_status",
            "experience_p1",
            "experience_p2",
            "experience_p3",
            "experience_p4",
            "experience_p5",
        )
    )
    for row in rows:
        writer.writerow(
            (
                row.task,
                row.persona,
                row.run,
                row.status,
                row.environment,
                row.task_score,
                row.adjusted_task_score,
                row.communicated_score,
                row.persona_alignment,
                row.experience_status,
                row.experience_p1,
                row.experience_p2,
                row.experience_p3,
                row.experience_p4,
                row.experience_p5,
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"results directory (default: {DEFAULT_RESULTS_DIR})",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "csv"),
        default="markdown",
        help="output format (default: markdown)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    results_dir = args.results.expanduser().resolve()
    task_order, task_ids = load_task_order()
    paths = sorted(results_dir.glob("**/result.json")) if results_dir.is_dir() else []
    rows = sorted(
        (
            parse_result(path, results_dir, task_order, task_ids)
            for path in paths
        ),
        key=lambda row: row.sort_key,
    )

    if args.format == "csv":
        print_csv(rows)
    else:
        print_markdown(rows)
        counts = Counter(row.status for row in rows)
        status_summary = ", ".join(
            f"{status}={count}" for status, count in sorted(counts.items())
        )
        print()
        print(f"Runs: {len(rows)}" + (f" ({status_summary})" if status_summary else ""))
        if not rows:
            print(f"No result.json files found under {results_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
