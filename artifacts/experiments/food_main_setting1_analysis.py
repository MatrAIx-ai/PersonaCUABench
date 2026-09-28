#!/usr/bin/env python3
"""Deterministic post-hoc analysis for Food & Drink main-style / Setting 1.

The script uses only the Python standard library.  It treats each replicate
root independently, keeps the latest *numeric scored* result for each
(task, persona, execution model) cell within that replicate, and reports all
other attempts as execution-integrity exclusions.  This selection says only
that an execution produced a numeric score; it is explicitly not a claim of
environment validity.  In particular, an attempt containing only an
``error.txt`` file is never treated as a selected numeric scored cell.

When an environment-validity audit is available at
``<replicate>/analysis/ENVIRONMENT_VALIDITY_AUDIT.json`` (or is supplied with
the repeatable ``--validity-json`` option), the report also contains a
separate KEEP-only overlay.  The all-numeric results remain unchanged.

Example:

    python artifacts/experiments/food_main_setting1_analysis.py \
      artifacts/experiments/2026-09-28/food-main-setting1-r1 \
      --output-prefix \
      artifacts/experiments/2026-09-28/food-main-setting1-r1/analysis/formal-posthoc

The command writes ``<prefix>.json`` and ``<prefix>.md``.  Passing a prefix
that already ends in ``.json`` or ``.md`` is also accepted; that suffix is
removed before both output names are formed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "1.1"
EXPERIENCE_DIMENSIONS = (
    "P1_asked_for",
    "P2_readable_for_them",
    "P3_actionable",
    "P4_gap_handling",
    "P5_overall",
)

# These categories are descriptive signals, not causal attributions.  An
# attempt can match more than one category, so category counts overlap.
NOISE_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "403_or_access_denied",
        "HTTP 403 / forbidden / access-denied evidence",
        re.compile(r"(?:\b403\b|access[ _-]?denied|\bforbidden\b)", re.I),
    ),
    (
        "verification_captcha_cloudflare",
        "verification, CAPTCHA, bot challenge, or Cloudflare evidence",
        re.compile(
            r"(?:captcha|cloudflare|verify\s+(?:that\s+)?you(?:'re|\s+are)?\s+human|"
            r"human\s+verification|security\s+verification|unusual\s+traffic|"
            r"attention\s+required|bot\s+(?:challenge|detection)|/sorry/(?:index)?)",
            re.I,
        ),
    ),
    (
        "timeout_or_dns",
        "timeout, DNS, or name-resolution evidence",
        re.compile(
            r"(?:time(?:d)?\s*out|timeout|dns|err_name_not_resolved|"
            r"name\s+not\s+resolved|temporary\s+failure\s+in\s+name\s+resolution)",
            re.I,
        ),
    ),
    (
        "max_tab",
        "maximum-tab / tab-limit evidence",
        re.compile(
            r"(?:tab\s+limit|max(?:imum)?[_\s-]*tabs?|too\s+many\s+tabs?)",
            re.I,
        ),
    ),
)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def round_number(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None


def median(values: Iterable[float]) -> float | None:
    items = list(values)
    return statistics.median(items) if items else None


def rate(numerator: int | float, denominator: int | float) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def metric_distribution(values: Iterable[float]) -> dict[str, Any]:
    items = [float(value) for value in values]
    if not items:
        return {"n": 0, "total": 0.0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "n": len(items),
        "total": round_number(sum(items)),
        "mean": round_number(mean(items)),
        "median": round_number(median(items)),
        "min": round_number(min(items)),
        "max": round_number(max(items)),
    }


def proportion_distribution(values: Iterable[float], threshold: float = 4.0) -> dict[str, Any]:
    items = [float(value) for value in values]
    above = sum(value >= threshold for value in items)
    return {
        "n": len(items),
        "mean": round_number(mean(items)),
        "median": round_number(median(items)),
        "score_gte_4": above,
        "score_gte_4_denominator": len(items),
        "score_gte_4_rate": round_number(rate(above, len(items))),
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_prefix(path: Path) -> Path:
    if path.suffix.lower() in {".json", ".md"}:
        return path.with_suffix("")
    return path


def short_text(text: str, width: int = 92) -> str:
    clean = " ".join(text.split())
    if len(clean) <= width:
        return clean
    clipped = clean[: width - 1].rsplit(" ", 1)[0]
    return (clipped or clean[: width - 1]) + "…"


def markdown_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def format_number(value: Any, digits: int = 3) -> str:
    if not is_number(value):
        return "—"
    return f"{float(value):.{digits}f}"


def format_percent(value: Any, digits: int = 1) -> str:
    if not is_number(value):
        return "—"
    return f"{float(value):.{digits}%}"


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(markdown_escape(item) for item in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(markdown_escape(item) for item in row) + " |" for row in rows
    )
    return lines


@dataclass
class Replicate:
    root: Path
    root_key: str
    experiment_id: str
    manifest: dict[str, Any]
    runtime_config: dict[str, Any]
    tasks: list[dict[str, Any]]

    @property
    def results_root(self) -> Path:
        return self.root / "results"


@dataclass
class Attempt:
    replicate: Replicate
    directory: Path
    relative_path: str
    result_path: Path | None = None
    error_paths: list[Path] = field(default_factory=list)
    record: dict[str, Any] | None = None
    parse_error: str | None = None
    task_id: str | None = None
    persona: str | None = None
    model: str | None = None
    provider: str | None = None
    score: float | None = None
    explicit_exclusion: bool = False
    selected: bool = False
    exclusion_reason: str | None = None

    @property
    def timestamp_key(self) -> str:
        name = self.directory.name
        return name.rsplit("__", 1)[-1] if "__" in name else name

    @property
    def cell_key(self) -> tuple[str, str, str, str] | None:
        if not (self.task_id and self.persona and self.model):
            return None
        return (self.replicate.root_key, self.task_id, self.persona, self.model)

    @property
    def arm_key(self) -> tuple[str, str]:
        return (self.persona or "<missing>", self.model or "<missing>")

    @property
    def arm_label(self) -> str:
        return f"{self.persona or '<missing>'} / {self.model or '<missing>'}"

    @property
    def is_scored(self) -> bool:
        return self.score is not None and self.cell_key is not None

    @property
    def has_error_file(self) -> bool:
        return bool(self.error_paths)


@dataclass
class ValidityAudit:
    """One environment-validity overlay associated with one replicate."""

    path: Path
    replicate: Replicate
    record: dict[str, Any]


def load_replicate(root: Path) -> Replicate:
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"replicate root is not a directory: {root}")
    results_root = resolved / "results"
    if not results_root.is_dir():
        raise ValueError(f"replicate root has no results/ directory: {resolved}")

    manifest_path = resolved / "RUN_MANIFEST.json"
    runtime_path = resolved / "inputs" / "runtime-config.json"
    tasks_path = resolved / "inputs" / "tasks.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    runtime = read_json(runtime_path) if runtime_path.is_file() else {}
    tasks = read_json(tasks_path) if tasks_path.is_file() else []
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(runtime, dict):
        runtime = {}
    if not isinstance(tasks, list):
        tasks = []
    experiment_id = str(manifest.get("experiment_id") or runtime.get("experiment_id") or resolved.name)
    return Replicate(
        root=resolved,
        root_key=resolved.as_posix(),
        experiment_id=experiment_id,
        manifest=manifest,
        runtime_config=runtime,
        tasks=tasks,
    )


def discover_attempts(replicate: Replicate) -> list[Attempt]:
    files = sorted(
        path
        for path in replicate.results_root.rglob("*")
        if path.is_file() and path.name in {"result.json", "error.txt"}
    )
    by_directory: dict[Path, Attempt] = {}
    for path in files:
        directory = path.parent
        attempt = by_directory.setdefault(
            directory,
            Attempt(
                replicate=replicate,
                directory=directory,
                relative_path=directory.relative_to(replicate.root).as_posix(),
            ),
        )
        if path.name == "result.json":
            attempt.result_path = path
        else:
            attempt.error_paths.append(path)

    attempts = [by_directory[key] for key in sorted(by_directory, key=lambda item: item.as_posix())]
    for attempt in attempts:
        relative_parts = attempt.directory.relative_to(replicate.results_root).parts
        attempt.explicit_exclusion = any(part.startswith("_") for part in relative_parts)
        if attempt.result_path:
            try:
                raw = read_json(attempt.result_path)
                if not isinstance(raw, dict):
                    raise ValueError("top-level JSON value is not an object")
                attempt.record = raw
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                attempt.parse_error = f"{type(exc).__name__}: {exc}"
                continue

            run = raw.get("run") if isinstance(raw.get("run"), dict) else {}
            arm = run.get("arm") if isinstance(run.get("arm"), dict) else {}
            judgement = raw.get("judgement") if isinstance(raw.get("judgement"), dict) else {}
            attempt.task_id = str(raw.get("task_id")) if raw.get("task_id") else None
            attempt.persona = str(raw.get("persona")) if raw.get("persona") is not None else None
            attempt.model = str(arm.get("model")) if arm.get("model") else None
            attempt.provider = str(arm.get("provider")) if arm.get("provider") else None
            raw_score = judgement.get("score")
            attempt.score = float(raw_score) if is_number(raw_score) else None
    return attempts


def select_latest_scored(attempts: list[Attempt]) -> list[Attempt]:
    candidates: dict[tuple[str, str, str, str], list[Attempt]] = defaultdict(list)
    for attempt in attempts:
        if attempt.explicit_exclusion:
            attempt.exclusion_reason = "explicitly_excluded_path"
        elif attempt.parse_error:
            attempt.exclusion_reason = "malformed_result_json"
        elif attempt.is_scored and attempt.cell_key is not None:
            candidates[attempt.cell_key].append(attempt)
        elif attempt.result_path:
            attempt.exclusion_reason = "result_without_numeric_score_or_cell_key"
        elif attempt.has_error_file:
            attempt.exclusion_reason = "error_only_attempt"
        else:
            attempt.exclusion_reason = "unrecognized_attempt"

    selected: list[Attempt] = []
    for key in sorted(candidates):
        group = candidates[key]
        winner = max(group, key=lambda item: (item.timestamp_key, item.relative_path))
        winner.selected = True
        selected.append(winner)
        for attempt in group:
            if attempt is not winner:
                attempt.exclusion_reason = "older_duplicate_scored_attempt"
    return sorted(
        selected,
        key=lambda item: (
            item.replicate.root_key,
            item.task_id or "",
            item.persona or "",
            item.model or "",
        ),
    )


def task_catalog(replicates: Sequence[Replicate], selected: Sequence[Attempt]) -> list[dict[str, Any]]:
    tasks_by_id: dict[str, dict[str, Any]] = {}
    position: dict[str, tuple[str, int]] = {}
    for replicate in sorted(replicates, key=lambda item: item.root_key):
        for index, task in enumerate(replicate.tasks, start=1):
            if not isinstance(task, dict) or not task.get("task_id"):
                continue
            task_id = str(task["task_id"])
            tasks_by_id.setdefault(task_id, task)
            position.setdefault(task_id, (replicate.root_key, index))
    for attempt in selected:
        if attempt.task_id and attempt.task_id not in tasks_by_id:
            tasks_by_id[attempt.task_id] = {"task_id": attempt.task_id}
            position[attempt.task_id] = (attempt.replicate.root_key, 10**9)

    ordered_ids = sorted(tasks_by_id, key=lambda task_id: (position[task_id], task_id))
    catalog: list[dict[str, Any]] = []
    for index, task_id in enumerate(ordered_ids, start=1):
        task = tasks_by_id[task_id]
        prompt = str(task.get("confirmed_task") or "")
        rubrics = task.get("rubrics") if isinstance(task.get("rubrics"), dict) else {}
        catalog.append(
            {
                "order": index,
                "label": f"T{index}",
                "task_id": task_id,
                "task_id_short": task_id[:12],
                "level": task.get("level"),
                "prompt_preview": short_text(prompt),
                "rubric_count": len(rubrics),
            }
        )
    return catalog


def planned_cells(replicate: Replicate) -> tuple[int | None, str]:
    manifest_value = replicate.manifest.get("planned_cells")
    if is_number(manifest_value):
        return int(manifest_value), "RUN_MANIFEST.json:planned_cells"
    runtime_value = replicate.runtime_config.get("planned_cells")
    if is_number(runtime_value):
        return int(runtime_value), "inputs/runtime-config.json:planned_cells"
    personas = replicate.runtime_config.get("personas")
    if isinstance(personas, list) and replicate.tasks:
        return len(personas) * len(replicate.tasks), "derived:len(personas)*len(tasks)"
    return None, "unavailable"


def judgement_counts(attempt: Attempt) -> tuple[int | None, int | None]:
    judgement = (attempt.record or {}).get("judgement")
    if not isinstance(judgement, dict):
        return None, None
    met = judgement.get("met")
    total = judgement.get("total")
    return (int(met) if is_number(met) else None, int(total) if is_number(total) else None)


def communication_counts(attempt: Attempt) -> tuple[int | None, int | None, int | None]:
    """Return (met_and_communicated, communicated, total rubrics)."""
    judgement = (attempt.record or {}).get("judgement")
    if not isinstance(judgement, dict):
        return None, None, None
    total_raw = judgement.get("total")
    total = int(total_raw) if is_number(total_raw) else None
    verdicts = judgement.get("verdicts")
    if isinstance(verdicts, dict) and verdicts:
        values = [value for value in verdicts.values() if isinstance(value, dict)]
        communicated_values = [value for value in values if bool(value.get("communicated"))]
        met_communicated = sum(bool(value.get("met")) for value in communicated_values)
        communicated = len(communicated_values)
        if total is None:
            total = len(values)
        return met_communicated, communicated, total

    communicated_raw = judgement.get("communicated")
    communicated = int(communicated_raw) if is_number(communicated_raw) else None
    communicated_score = judgement.get("score_communicated")
    met_communicated: int | None = None
    if communicated is not None and is_number(communicated_score):
        met_communicated = int(round(communicated * float(communicated_score)))
    return met_communicated, communicated, total


def cell_score(attempt: Attempt) -> float:
    assert attempt.score is not None
    return float(attempt.score)


def cell_communicated_score(attempt: Attempt) -> float | None:
    judgement = (attempt.record or {}).get("judgement")
    if not isinstance(judgement, dict):
        return None
    value = judgement.get("score_communicated")
    return float(value) if is_number(value) else None


def cell_communication_coverage(attempt: Attempt) -> float | None:
    _, communicated, total = communication_counts(attempt)
    return rate(communicated or 0, total) if communicated is not None and total is not None else None


def completion_stats(items: Sequence[Attempt]) -> dict[str, Any]:
    scores = [cell_score(item) for item in items]
    met_total = [judgement_counts(item) for item in items]
    rubric_met = sum(met for met, _ in met_total if met is not None)
    rubric_total = sum(total for _, total in met_total if total is not None)
    return {
        "cells": len(items),
        "score_mean": round_number(mean(scores)),
        "score_median": round_number(median(scores)),
        "rubric_met": rubric_met,
        "rubric_total": rubric_total,
        "rubric_micro_completion": round_number(rate(rubric_met, rubric_total)),
    }


def communication_stats(items: Sequence[Attempt]) -> dict[str, Any]:
    counts = [communication_counts(item) for item in items]
    communicated = sum(value for _, value, _ in counts if value is not None)
    total = sum(value for _, _, value in counts if value is not None)
    met_communicated = sum(value for value, _, _ in counts if value is not None)
    coverage_values = [
        value for value in (cell_communication_coverage(item) for item in items) if value is not None
    ]
    communicated_scores = [
        value for value in (cell_communicated_score(item) for item in items) if value is not None
    ]
    zero_communicated = sum(
        1 for _, communicated_count, _ in counts if communicated_count == 0
    )
    return {
        "cells": len(items),
        "coverage": {
            "communicated_rubrics": communicated,
            "all_rubrics": total,
            "micro_rate": round_number(rate(communicated, total)),
            "cell_macro_rate": round_number(mean(coverage_values)),
            "cell_macro_denominator": len(coverage_values),
        },
        "communicated_only_completion": {
            "met_communicated_rubrics": met_communicated,
            "communicated_rubrics": communicated,
            "micro_rate": round_number(rate(met_communicated, communicated)),
            "cell_macro_rate": round_number(mean(communicated_scores)),
            "cell_macro_denominator": len(communicated_scores),
            "cells_with_zero_communicated_rubrics": zero_communicated,
        },
    }


def group_rows(
    selected: Sequence[Attempt],
    key_function: Any,
    row_function: Any,
) -> list[dict[str, Any]]:
    groups: dict[Any, list[Attempt]] = defaultdict(list)
    for attempt in selected:
        groups[key_function(attempt)].append(attempt)
    return [row_function(key, groups[key]) for key in sorted(groups)]


def completion_analysis(
    selected: Sequence[Attempt],
    catalog: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    label_by_task = {item["task_id"]: item["label"] for item in catalog}
    task_groups: dict[str, list[Attempt]] = defaultdict(list)
    for attempt in selected:
        assert attempt.task_id is not None
        task_groups[attempt.task_id].append(attempt)
    per_task = []
    for task_id in (item["task_id"] for item in catalog):
        group = task_groups.get(task_id, [])
        if group:
            per_task.append(
                {"task_id": task_id, "task_label": label_by_task[task_id], **completion_stats(group)}
            )

    per_arm = group_rows(
        selected,
        lambda item: item.arm_key,
        lambda key, group: {
            "persona": key[0],
            "model": key[1],
            "arm": f"{key[0]} / {key[1]}",
            **completion_stats(group),
        },
    )
    per_arm_per_task = group_rows(
        selected,
        lambda item: (item.persona or "", item.model or "", item.task_id or ""),
        lambda key, group: {
            "persona": key[0],
            "model": key[1],
            "arm": f"{key[0]} / {key[1]}",
            "task_id": key[2],
            "task_label": label_by_task.get(key[2], key[2][:12]),
            **completion_stats(group),
        },
    )

    all_stats = completion_stats(selected)
    task_means = [row["score_mean"] for row in per_task if is_number(row["score_mean"])]
    return {
        "cell_macro_completion": all_stats["score_mean"],
        "task_macro_completion": round_number(mean(float(value) for value in task_means)),
        "task_macro_denominator": len(task_means),
        "rubric_micro_completion": {
            "met": all_stats["rubric_met"],
            "total": all_stats["rubric_total"],
            "rate": all_stats["rubric_micro_completion"],
        },
        "per_arm": per_arm,
        "per_task": per_task,
        "per_arm_per_task": per_arm_per_task,
    }


def communication_analysis(selected: Sequence[Attempt]) -> dict[str, Any]:
    per_arm = group_rows(
        selected,
        lambda item: item.arm_key,
        lambda key, group: {
            "persona": key[0],
            "model": key[1],
            "arm": f"{key[0]} / {key[1]}",
            **communication_stats(group),
        },
    )
    return {"overall": communication_stats(selected), "per_arm": per_arm}


def question_count(attempt: Attempt) -> int:
    run = (attempt.record or {}).get("run")
    if not isinstance(run, dict):
        return 0
    trajectory = run.get("trajectory")
    if not isinstance(trajectory, list):
        return 0
    return sum(
        1
        for entry in trajectory
        if isinstance(entry, dict) and str(entry.get("tool") or "") == "ask_user"
    )


def step_count(attempt: Attempt) -> float | None:
    run = (attempt.record or {}).get("run")
    if not isinstance(run, dict):
        return None
    value = run.get("steps")
    return float(value) if is_number(value) else None


def run_behavior_analysis(selected: Sequence[Attempt]) -> dict[str, Any]:
    stop_reasons: Counter[str] = Counter()
    budgets: Counter[str] = Counter()
    for attempt in selected:
        run = (attempt.record or {}).get("run")
        run = run if isinstance(run, dict) else {}
        stop_reasons[str(run.get("stop_reason") or "<missing>")] += 1
        budget = run.get("max_steps")
        budgets[str(int(budget)) if is_number(budget) else "<missing>"] += 1

    def behavior(group: Sequence[Attempt]) -> dict[str, Any]:
        steps = [value for value in (step_count(item) for item in group) if value is not None]
        questions = [float(question_count(item)) for item in group]
        return {
            "cells": len(group),
            "steps": metric_distribution(steps),
            "questions": metric_distribution(questions),
        }

    per_arm = group_rows(
        selected,
        lambda item: item.arm_key,
        lambda key, group: {
            "persona": key[0],
            "model": key[1],
            "arm": f"{key[0]} / {key[1]}",
            **behavior(group),
        },
    )
    return {
        "stop_reasons": [
            {"reason": reason, "count": stop_reasons[reason]} for reason in sorted(stop_reasons)
        ],
        "max_step_budgets": [
            {"max_steps": budget, "count": budgets[budget]} for budget in sorted(budgets)
        ],
        "overall": behavior(selected),
        "per_arm": per_arm,
        "question_definition": "count of run.trajectory entries whose tool is ask_user",
    }


def experience_score(attempt: Attempt, judge: str, dimension: str) -> float | None:
    experience = (attempt.record or {}).get("experience")
    if not isinstance(experience, dict):
        return None
    verdict = experience.get(judge)
    if not isinstance(verdict, dict):
        return None
    dimension_value = verdict.get(dimension)
    if not isinstance(dimension_value, dict):
        return None
    value = dimension_value.get("score")
    if is_number(value) and 1 <= float(value) <= 5:
        return float(value)
    return None


def experience_dimension_row(items: Sequence[Attempt], dimension: str) -> dict[str, Any]:
    a_values = [
        value for value in (experience_score(item, "a", dimension) for item in items) if value is not None
    ]
    b_values = [
        value for value in (experience_score(item, "b", dimension) for item in items) if value is not None
    ]
    pairs = [
        (a, b)
        for item in items
        for a, b in [(experience_score(item, "a", dimension), experience_score(item, "b", dimension))]
        if a is not None and b is not None
    ]
    exact = sum(a == b for a, b in pairs)
    within_one = sum(abs(a - b) <= 1 for a, b in pairs)
    a_stats = proportion_distribution(a_values)
    b_stats = proportion_distribution(b_values)
    a_stats.update({"n_a": len(items) - len(a_values), "expected": len(items)})
    b_stats.update({"n_a": len(items) - len(b_values), "expected": len(items)})
    return {
        "dimension": dimension,
        "judge_a": a_stats,
        "judge_b": b_stats,
        "agreement": {
            "paired": len(pairs),
            "expected": len(items),
            "n_a": len(items) - len(pairs),
            "exact": exact,
            "exact_rate": round_number(rate(exact, len(pairs))),
            "within_one": within_one,
            "within_one_rate": round_number(rate(within_one, len(pairs))),
        },
    }


def experience_analysis(selected: Sequence[Attempt]) -> dict[str, Any]:
    dimensions = [experience_dimension_row(selected, dimension) for dimension in EXPERIENCE_DIMENSIONS]
    all_pairs: list[tuple[float, float]] = []
    expected = len(selected) * len(EXPERIENCE_DIMENSIONS)
    for item in selected:
        for dimension in EXPERIENCE_DIMENSIONS:
            a = experience_score(item, "a", dimension)
            b = experience_score(item, "b", dimension)
            if a is not None and b is not None:
                all_pairs.append((a, b))
    exact = sum(a == b for a, b in all_pairs)
    within_one = sum(abs(a - b) <= 1 for a, b in all_pairs)
    return {
        "note": "Judge A and Judge B are reported separately and are never averaged.",
        "dimensions": dimensions,
        "overall_agreement": {
            "paired_dimension_scores": len(all_pairs),
            "expected_dimension_scores": expected,
            "n_a": expected - len(all_pairs),
            "exact": exact,
            "exact_rate": round_number(rate(exact, len(all_pairs))),
            "within_one": within_one,
            "within_one_rate": round_number(rate(within_one, len(all_pairs))),
        },
    }


def slice_analysis(items: Sequence[Attempt], all_selected_count: int) -> dict[str, Any]:
    per_arm_counter: Counter[tuple[str, str]] = Counter(item.arm_key for item in items)
    dimensions = [experience_dimension_row(items, dimension) for dimension in EXPERIENCE_DIMENSIONS]
    return {
        "cells": len(items),
        "all_selected_numeric_scored_cells": all_selected_count,
        # Deprecated compatibility alias; no environment-validity claim.
        "all_valid_cells": all_selected_count,
        "rate_of_selected_numeric_scored_cells": round_number(
            rate(len(items), all_selected_count)
        ),
        "rate_of_valid_cells": round_number(rate(len(items), all_selected_count)),
        "terminology_compatibility": {
            "all_valid_cells": (
                "Deprecated alias of all_selected_numeric_scored_cells; no environment-validity claim."
            ),
            "rate_of_valid_cells": (
                "Deprecated alias of rate_of_selected_numeric_scored_cells."
            ),
        },
        "per_arm": [
            {
                "persona": key[0],
                "model": key[1],
                "arm": f"{key[0]} / {key[1]}",
                "cells": per_arm_counter[key],
            }
            for key in sorted(per_arm_counter)
        ],
        "experience_dimensions": dimensions,
    }


def perfect_slices(selected: Sequence[Attempt]) -> dict[str, Any]:
    full = [item for item in selected if item.score is not None and item.score == 1.0]
    communicated = [
        item for item in selected if cell_communicated_score(item) == 1.0
    ]
    return {
        "full_task_perfect": {
            "definition": "judgement.score == 1.0",
            **slice_analysis(full, len(selected)),
        },
        "communicated_perfect": {
            "definition": "judgement.score_communicated == 1.0",
            **slice_analysis(communicated, len(selected)),
        },
    }


def paired_delta_analysis(
    selected: Sequence[Attempt], baseline_persona: str
) -> dict[str, Any]:
    baseline: dict[tuple[str, str, str], Attempt] = {}
    for item in selected:
        if item.persona == baseline_persona and item.task_id and item.model:
            baseline[(item.replicate.root_key, item.task_id, item.model)] = item

    pairs: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for item in selected:
        if item.persona == baseline_persona or not item.task_id or not item.model:
            continue
        key = (item.replicate.root_key, item.task_id, item.model)
        base = baseline.get(key)
        if base is None:
            missing.append(
                {
                    "replicate": item.replicate.experiment_id,
                    "task_id": item.task_id,
                    "persona": item.persona,
                    "model": item.model,
                }
            )
            continue
        persona_coverage = cell_communication_coverage(item)
        baseline_coverage = cell_communication_coverage(base)
        persona_comm = cell_communicated_score(item)
        baseline_comm = cell_communicated_score(base)
        pairs.append(
            {
                "replicate": item.replicate.experiment_id,
                "task_id": item.task_id,
                "persona": item.persona,
                "model": item.model,
                "persona_completion": round_number(item.score),
                "baseline_completion": round_number(base.score),
                "completion_delta": round_number(float(item.score) - float(base.score)),
                "persona_communication_coverage": round_number(persona_coverage),
                "baseline_communication_coverage": round_number(baseline_coverage),
                "communication_coverage_delta": round_number(
                    persona_coverage - baseline_coverage
                    if persona_coverage is not None and baseline_coverage is not None
                    else None
                ),
                "persona_communicated_only_completion": round_number(persona_comm),
                "baseline_communicated_only_completion": round_number(baseline_comm),
                "communicated_only_completion_delta": round_number(
                    persona_comm - baseline_comm
                    if persona_comm is not None and baseline_comm is not None
                    else None
                ),
            }
        )
    pairs.sort(key=lambda row: (row["persona"], row["model"], row["replicate"], row["task_id"]))
    missing.sort(key=lambda row: (row["persona"], row["model"], row["replicate"], row["task_id"]))

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        groups[(str(pair["persona"]), str(pair["model"]))].append(pair)
    aggregate: list[dict[str, Any]] = []
    for key in sorted(groups):
        rows = groups[key]
        completion_deltas = [float(row["completion_delta"]) for row in rows]
        coverage_deltas = [
            float(row["communication_coverage_delta"])
            for row in rows
            if is_number(row["communication_coverage_delta"])
        ]
        communicated_deltas = [
            float(row["communicated_only_completion_delta"])
            for row in rows
            if is_number(row["communicated_only_completion_delta"])
        ]
        aggregate.append(
            {
                "persona": key[0],
                "model": key[1],
                "arm": f"{key[0]} / {key[1]}",
                "paired_cells": len(rows),
                "completion_delta_mean": round_number(mean(completion_deltas)),
                "completion_delta_median": round_number(median(completion_deltas)),
                "completion_wins": sum(value > 0 for value in completion_deltas),
                "completion_ties": sum(value == 0 for value in completion_deltas),
                "completion_losses": sum(value < 0 for value in completion_deltas),
                "communication_coverage_delta_mean": round_number(mean(coverage_deltas)),
                "communication_coverage_delta_n": len(coverage_deltas),
                "communicated_only_completion_delta_mean": round_number(mean(communicated_deltas)),
                "communicated_only_completion_delta_n": len(communicated_deltas),
            }
        )
    return {
        "baseline_persona": baseline_persona,
        "definition": "Within-replicate, within-task, same-execution-model persona score minus baseline score.",
        "pairs": pairs,
        "aggregate_by_persona_and_model": aggregate,
        "missing_baseline_pairs": missing,
    }


def noise_text(attempt: Attempt) -> str:
    chunks: list[str] = []
    record = attempt.record or {}
    run = record.get("run") if isinstance(record.get("run"), dict) else {}
    answer = run.get("answer")
    if isinstance(answer, str):
        chunks.append(answer)
    trajectory = run.get("trajectory")
    if isinstance(trajectory, list):
        for entry in trajectory:
            if not isinstance(entry, dict):
                continue
            preview = entry.get("result_preview")
            if isinstance(preview, str):
                chunks.append(preview)
    for error_path in attempt.error_paths:
        try:
            chunks.append(error_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return "\n".join(chunks)


def external_noise_analysis(attempts: Sequence[Attempt]) -> dict[str, Any]:
    categories: list[dict[str, Any]] = []
    for key, label, pattern in NOISE_PATTERNS:
        affected: list[Attempt] = []
        occurrences = 0
        for attempt in attempts:
            matches = list(pattern.finditer(noise_text(attempt)))
            if matches:
                affected.append(attempt)
                occurrences += len(matches)
        categories.append(
            {
                "category": key,
                "description": label,
                "regex": pattern.pattern,
                "attempts_with_evidence": len(affected),
                "all_attempts_denominator": len(attempts),
                "occurrences": occurrences,
                "selected_numeric_scored_attempts_with_evidence": sum(
                    item.selected for item in affected
                ),
                "execution_integrity_excluded_attempts_with_evidence": sum(
                    not item.selected for item in affected
                ),
                # Deprecated compatibility aliases.
                "selected_scored_attempts_with_evidence": sum(item.selected for item in affected),
                "excluded_attempts_with_evidence": sum(not item.selected for item in affected),
                "attempt_paths": [
                    {
                        "replicate": item.replicate.experiment_id,
                        "path": item.relative_path,
                        "selected_numeric_scored_cell": item.selected,
                        "selected_scored_cell": item.selected,
                    }
                    for item in sorted(
                        affected,
                        key=lambda value: (value.replicate.root_key, value.relative_path),
                    )
                ],
            }
        )
    return {
        "label": "descriptive external-noise keyword evidence",
        "scope": (
            "run.answer, run.trajectory[*].result_preview, and error.txt across all discovered "
            "attempts (selected and excluded); prompts and judge rationales are not searched"
        ),
        "overlap_warning": (
            "Categories are descriptive and overlapping: one attempt may contribute to multiple "
            "categories, and keyword evidence does not establish causal impact on score."
        ),
        "categories": categories,
    }


def load_validity_audits(
    replicates: Sequence[Replicate], explicit_paths: Sequence[Path]
) -> list[ValidityAudit]:
    """Load at most one environment-validity audit per replicate.

    Explicit ``--validity-json`` files take precedence.  A file is associated
    with a replicate by being inside that replicate root, or (when unique) by
    its top-level ``experiment_id``.  Replicates without an explicit file are
    auto-discovered at analysis/ENVIRONMENT_VALIDITY_AUDIT.json.
    """

    assigned: dict[str, ValidityAudit] = {}
    seen_paths: set[Path] = set()

    def load_one(path: Path, explicit: bool) -> None:
        resolved = path.expanduser().resolve()
        if resolved in seen_paths:
            raise ValueError(f"environment-validity audit supplied more than once: {resolved}")
        seen_paths.add(resolved)
        if not resolved.is_file():
            raise ValueError(f"environment-validity audit is not a file: {resolved}")
        raw = read_json(resolved)
        if not isinstance(raw, dict):
            raise ValueError(f"environment-validity audit is not a JSON object: {resolved}")

        contained = []
        for replicate in replicates:
            try:
                resolved.relative_to(replicate.root)
            except ValueError:
                continue
            contained.append(replicate)
        if len(contained) > 1:
            raise ValueError(f"audit path is inside multiple replicate roots: {resolved}")
        if contained:
            replicate = contained[0]
        else:
            experiment_id = str(raw.get("experiment_id") or "")
            candidates = [item for item in replicates if item.experiment_id == experiment_id]
            if len(candidates) != 1:
                mode = "explicit" if explicit else "auto-discovered"
                raise ValueError(
                    f"cannot associate {mode} audit {resolved} with exactly one replicate "
                    f"(experiment_id={experiment_id!r})"
                )
            replicate = candidates[0]

        if replicate.root_key in assigned:
            previous = assigned[replicate.root_key].path
            raise ValueError(
                f"more than one environment-validity audit for {replicate.experiment_id}: "
                f"{previous} and {resolved}"
            )
        assigned[replicate.root_key] = ValidityAudit(resolved, replicate, raw)

    for path in sorted((item.expanduser().resolve() for item in explicit_paths), key=lambda item: item.as_posix()):
        load_one(path, explicit=True)

    for replicate in sorted(replicates, key=lambda item: item.root_key):
        if replicate.root_key in assigned:
            continue
        candidate = replicate.root / "analysis" / "ENVIRONMENT_VALIDITY_AUDIT.json"
        if candidate.is_file():
            load_one(candidate, explicit=False)

    return [assigned[key] for key in sorted(assigned)]


def environment_validity_analysis(
    replicates: Sequence[Replicate],
    audits: Sequence[ValidityAudit],
    selected: Sequence[Attempt],
    catalog: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Build a separate KEEP-only overlay without mutating all-numeric data."""

    selected_by_replicate: dict[str, list[Attempt]] = defaultdict(list)
    for attempt in selected:
        selected_by_replicate[attempt.replicate.root_key].append(attempt)

    if not audits:
        return {
            "status": "not_available",
            "population_note": (
                "No environment-validity audit was supplied or auto-discovered. All other "
                "sections describe selected numeric scored execution cells only and must not be "
                "interpreted as environment-valid."
            ),
            "auto_discovery_filename": "analysis/ENVIRONMENT_VALIDITY_AUDIT.json",
            "counts": {
                "selected_numeric_scored_cells": len(selected),
                "audited_selected_numeric_scored_cells": 0,
                "environment_keep_cells": 0,
                "environment_exclude_rerun_cells": 0,
                "environment_unclassified_selected_numeric_cells": len(selected),
            },
            "audits": [],
            "decisions": [],
            "keep_only": None,
        }

    keep: list[Attempt] = []
    environment_excluded: list[Attempt] = []
    matched_attempt_paths: set[tuple[str, str]] = set()
    audit_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    for audit in sorted(audits, key=lambda item: item.replicate.root_key):
        raw_cells = audit.record.get("cells")
        if not isinstance(raw_cells, list):
            raise ValueError(f"environment-validity audit has no cells list: {audit.path}")
        status_counter: Counter[str] = Counter()
        matched_for_audit = 0
        local_seen: set[str] = set()

        for index, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, dict):
                raise ValueError(f"audit cell {index} is not an object: {audit.path}")
            task_ref = str(raw_cell.get("task_id") or "")
            persona = str(raw_cell.get("persona") or "")
            model_ref = raw_cell.get("model")
            status = str(raw_cell.get("status") or "")
            if status not in {"KEEP", "EXCLUDE_RERUN"}:
                raise ValueError(
                    f"unsupported environment-validity status {status!r} in {audit.path} cell {index}"
                )
            if not task_ref or not persona:
                raise ValueError(f"audit cell {index} lacks task_id/persona: {audit.path}")

            matches = [
                attempt
                for attempt in selected_by_replicate.get(audit.replicate.root_key, [])
                if attempt.task_id
                and (attempt.task_id == task_ref or attempt.task_id.startswith(task_ref))
                and attempt.persona == persona
                and (model_ref is None or attempt.model == str(model_ref))
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"audit cell {index} in {audit.path} maps to {len(matches)} selected numeric "
                    f"cells (task_id={task_ref!r}, persona={persona!r}, model={model_ref!r})"
                )
            attempt = matches[0]
            match_key = f"{attempt.task_id}|{attempt.persona}|{attempt.model}"
            if match_key in local_seen:
                raise ValueError(f"duplicate audit decision for {match_key}: {audit.path}")
            local_seen.add(match_key)
            global_key = (audit.replicate.root_key, attempt.relative_path)
            if global_key in matched_attempt_paths:
                raise ValueError(f"selected numeric cell matched by multiple audits: {attempt.relative_path}")
            matched_attempt_paths.add(global_key)
            matched_for_audit += 1
            status_counter[status] += 1
            if status == "KEEP":
                keep.append(attempt)
            else:
                environment_excluded.append(attempt)

            decision_rows.append(
                {
                    "replicate": audit.replicate.experiment_id,
                    "audit_path": audit.path.as_posix(),
                    "task_id": attempt.task_id,
                    "task_id_in_audit": task_ref,
                    "persona": attempt.persona,
                    "model": attempt.model,
                    "selected_result_path": attempt.relative_path,
                    "status": status,
                    "communicated_rubrics": raw_cell.get("communicated_rubrics", []),
                    "impacted_rubrics": raw_cell.get("impacted_rubrics", []),
                    "blocking_causes": raw_cell.get("blocking_causes", []),
                    "evidence": raw_cell.get("evidence"),
                    "decision_basis": raw_cell.get("decision_basis"),
                }
            )

        declared = audit.record.get("counts")
        declared = declared if isinstance(declared, dict) else {}
        for status in ("KEEP", "EXCLUDE_RERUN"):
            declared_value = declared.get(status)
            if is_number(declared_value) and int(declared_value) != status_counter[status]:
                raise ValueError(
                    f"audit count mismatch for {audit.replicate.experiment_id} {status}: "
                    f"declared {int(declared_value)}, mapped {status_counter[status]}"
                )
        replicate_selected_count = len(selected_by_replicate.get(audit.replicate.root_key, []))
        audit_rows.append(
            {
                "experiment_id": audit.replicate.experiment_id,
                "replicate_root": audit.replicate.root.as_posix(),
                "audit_path": audit.path.as_posix(),
                "audit_version": audit.record.get("audit_version"),
                "audited_at": audit.record.get("audited_at"),
                "selected_numeric_scored_cells": replicate_selected_count,
                "audit_cells": len(raw_cells),
                "matched_selected_numeric_cells": matched_for_audit,
                "environment_keep_cells": status_counter["KEEP"],
                "environment_exclude_rerun_cells": status_counter["EXCLUDE_RERUN"],
                "environment_unclassified_selected_numeric_cells": (
                    replicate_selected_count - matched_for_audit
                ),
                "decision_rule": audit.record.get("decision_rule"),
                "retained_subset_descriptive_only_from_audit": audit.record.get(
                    "retained_subset_descriptive_only"
                ),
                "structural_limit": audit.record.get("structural_limit"),
            }
        )

    decision_rows.sort(
        key=lambda row: (
            str(row["replicate"]),
            str(row["task_id"]),
            str(row["persona"]),
            str(row["model"]),
        )
    )
    keep.sort(
        key=lambda item: (
            item.replicate.root_key,
            item.task_id or "",
            item.persona or "",
            item.model or "",
        )
    )
    audited_root_keys = {audit.replicate.root_key for audit in audits}
    unclassified = [
        attempt
        for attempt in selected
        if (attempt.replicate.root_key, attempt.relative_path) not in matched_attempt_paths
    ]
    unaudited_replicates = [
        replicate.experiment_id
        for replicate in sorted(replicates, key=lambda item: item.root_key)
        if replicate.root_key not in audited_root_keys
    ]

    keep_counts = completion_stats(keep)
    return {
        "status": "applied",
        "population_note": (
            "Environment validity is an overlay on selected numeric scored execution cells. "
            "KEEP-only aggregates are descriptive and do not replace or mutate the all-numeric "
            "completion, communication, run, experience, or perfect-slice sections."
        ),
        "auto_discovery_filename": "analysis/ENVIRONMENT_VALIDITY_AUDIT.json",
        "counts": {
            "selected_numeric_scored_cells": len(selected),
            "audited_selected_numeric_scored_cells": len(matched_attempt_paths),
            "environment_keep_cells": len(keep),
            "environment_exclude_rerun_cells": len(environment_excluded),
            "environment_unclassified_selected_numeric_cells": len(unclassified),
            "replicates_with_audit": len(audits),
            "replicates_without_audit": len(unaudited_replicates),
        },
        "unaudited_replicates": unaudited_replicates,
        "audits": audit_rows,
        "decisions": decision_rows,
        "keep_only": {
            "population": "selected numeric scored cells classified KEEP by environment audit",
            "warning": (
                "This subset can be imbalanced by task/persona and is not automatically an "
                "overall Food & Drink performance estimate."
            ),
            "counts": {
                "cells": len(keep),
                "rubric_met": keep_counts["rubric_met"],
                "rubric_total": keep_counts["rubric_total"],
            },
            "completion": completion_analysis(keep, catalog),
            "communication": communication_analysis(keep),
            "run_behavior": run_behavior_analysis(keep),
            "experience": experience_analysis(keep),
            "perfect_slices": perfect_slices(keep),
        },
    }


def build_counts(
    replicates: Sequence[Replicate], attempts: Sequence[Attempt], selected: Sequence[Attempt]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    replicate_rows: list[dict[str, Any]] = []
    total_planned = 0
    planned_known = True
    for replicate in replicates:
        planned, source = planned_cells(replicate)
        replicate_attempts = [item for item in attempts if item.replicate.root_key == replicate.root_key]
        replicate_selected = [item for item in selected if item.replicate.root_key == replicate.root_key]
        if planned is None:
            planned_known = False
        else:
            total_planned += planned
        replicate_rows.append(
            {
                "experiment_id": replicate.experiment_id,
                "root": replicate.root.as_posix(),
                "date_block": replicate.manifest.get("date_block"),
                "replicate": replicate.manifest.get("replicate", replicate.runtime_config.get("replicate")),
                "planned_cells": planned,
                "planned_cells_source": source,
                "discovered_attempts": len(replicate_attempts),
                "selected_numeric_scored_cells": len(replicate_selected),
                "execution_integrity_excluded_attempts": sum(
                    not item.selected for item in replicate_attempts
                ),
                # Deprecated compatibility aliases.  These never meant that a
                # web environment was valid; they pre-date the validity overlay.
                "valid_scored_cells": len(replicate_selected),
                "excluded_attempts": sum(not item.selected for item in replicate_attempts),
                "error_attempts": sum(item.has_error_file for item in replicate_attempts),
            }
        )

    exclusions = [item for item in attempts if not item.selected]
    exclusion_counter = Counter(item.exclusion_reason or "unknown" for item in exclusions)
    exclusion_details = [
        {
            "replicate": item.replicate.experiment_id,
            "path": item.relative_path,
            "reason": item.exclusion_reason or "unknown",
            "has_result_json": item.result_path is not None,
            "has_error_txt": item.has_error_file,
            "parse_error": item.parse_error,
        }
        for item in sorted(exclusions, key=lambda value: (value.replicate.root_key, value.relative_path))
    ]
    counts = {
        "replicates": len(replicates),
        "planned_cells": total_planned if planned_known else None,
        "planned_cells_all_replicates_known": planned_known,
        "discovered_attempts": len(attempts),
        "selected_numeric_scored_cells": len(selected),
        "execution_integrity_excluded_attempts": len(exclusions),
        # Deprecated aliases retained so existing consumers do not silently
        # break.  See terminology_compatibility below.
        "valid_scored_cells": len(selected),
        "excluded_attempts": len(exclusions),
        "error_attempts": sum(item.has_error_file for item in attempts),
        "error_only_attempts": sum(
            item.has_error_file and item.result_path is None for item in attempts
        ),
        "malformed_result_attempts": sum(item.parse_error is not None for item in attempts),
        "unfilled_planned_cells": (
            max(total_planned - len(selected), 0) if planned_known else None
        ),
        "exclusion_reasons": [
            {"reason": reason, "count": exclusion_counter[reason]}
            for reason in sorted(exclusion_counter)
        ],
        "terminology_compatibility": {
            "valid_scored_cells": (
                "Deprecated alias of selected_numeric_scored_cells; it denotes execution-integrity "
                "selection only, not environment validity."
            ),
            "excluded_attempts": "Deprecated alias of execution_integrity_excluded_attempts.",
        },
    }
    return counts, replicate_rows, exclusion_details


def analyze(
    replicates: Sequence[Replicate],
    baseline_persona: str,
    validity_audits: Sequence[ValidityAudit],
) -> dict[str, Any]:
    attempts: list[Attempt] = []
    for replicate in replicates:
        attempts.extend(discover_attempts(replicate))
    selected = select_latest_scored(attempts)
    catalog = task_catalog(replicates, selected)
    counts, replicate_rows, exclusion_details = build_counts(replicates, attempts, selected)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis": "Food & Drink main-style Setting 1 formal post-hoc summary",
        "primary_population": (
            "all selected numeric scored execution cells; not filtered for environment validity"
        ),
        "definitions": {
            "selected_numeric_scored_cell": (
                "Latest execution-integrity-eligible result with a finite numeric "
                "judgement.score for each (replicate root, task_id, persona, execution model). "
                "This does not assert environment validity."
            ),
            "execution_integrity_excluded_attempt": (
                "Any discovered result/error attempt not selected as the numeric scored cell, "
                "including error-only, unscored, explicitly excluded, malformed, and older duplicate attempts."
            ),
            "environment_validity": (
                "A separate optional audit overlay. EXCLUDE_RERUN cells remain in the raw/all-numeric "
                "aggregates; KEEP-only aggregates are reported separately."
            ),
            "task_macro_completion": "Mean of task-level means of judgement.score; each task has equal weight.",
            "rubric_micro_completion": (
                "Sum(judgement.met) / sum(judgement.total) over selected numeric scored cells."
            ),
            "communication_coverage": "Communicated rubric items / all rubric items.",
            "communicated_only_completion": (
                "Met-and-communicated rubric items / communicated rubric items; cells with zero "
                "communicated items are excluded only from the cell-macro rate and are counted explicitly."
            ),
        },
        "inputs": replicate_rows,
        "task_catalog": catalog,
        "counts": counts,
        "exclusions": exclusion_details,
        "completion": completion_analysis(selected, catalog),
        "communication": communication_analysis(selected),
        "run_behavior": run_behavior_analysis(selected),
        "experience": experience_analysis(selected),
        "perfect_slices": perfect_slices(selected),
        "paired_persona_minus_none": paired_delta_analysis(selected, baseline_persona),
        "external_noise": external_noise_analysis(attempts),
        "environment_validity": environment_validity_analysis(
            replicates, validity_audits, selected, catalog
        ),
    }


def environment_validity_markdown(summary: dict[str, Any]) -> list[str]:
    overlay = summary["environment_validity"]
    lines = [
        "## Environment-validity overlay",
        "",
        "This section is separate from the all-numeric execution results. Environment-excluded "
        "cells remain preserved in every all-numeric section below.",
        "",
    ]
    if overlay["status"] != "applied":
        lines.extend(
            [
                "No environment-validity audit was supplied or auto-discovered. No KEEP-only "
                "performance estimate is available.",
                "",
            ]
        )
        return lines

    counts = overlay["counts"]
    lines.extend(
        [
            f"Audited selected numeric cells: **{counts['audited_selected_numeric_scored_cells']}**; "
            f"**KEEP {counts['environment_keep_cells']}**; "
            f"**EXCLUDE_RERUN {counts['environment_exclude_rerun_cells']}**; "
            f"unclassified selected numeric cells: "
            f"**{counts['environment_unclassified_selected_numeric_cells']}**.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "Replicate",
                "Audit version",
                "Selected numeric",
                "Audited/matched",
                "KEEP",
                "EXCLUDE_RERUN",
                "Unclassified",
            ],
            [
                [
                    row["experiment_id"],
                    row.get("audit_version") or "—",
                    row["selected_numeric_scored_cells"],
                    row["matched_selected_numeric_cells"],
                    row["environment_keep_cells"],
                    row["environment_exclude_rerun_cells"],
                    row["environment_unclassified_selected_numeric_cells"],
                ]
                for row in overlay["audits"]
            ],
        )
    )

    keep = overlay["keep_only"]
    assert isinstance(keep, dict)
    completion = keep["completion"]
    micro = completion["rubric_micro_completion"]
    communication = keep["communication"]["overall"]
    coverage = communication["coverage"]
    communicated = communication["communicated_only_completion"]
    lines.extend(
        [
            "",
            "### KEEP-only completion and communication",
            "",
            keep["warning"],
            "",
            f"- Cells: **{keep['counts']['cells']}**.",
            f"- Task-macro completion: **{format_number(completion['task_macro_completion'])}** "
            f"across {completion['task_macro_denominator']} represented tasks.",
            f"- Cell-macro completion: **{format_number(completion['cell_macro_completion'])}**.",
            f"- Rubric-micro completion: **{micro['met']}/{micro['total']} = "
            f"{format_number(micro['rate'])}**.",
            f"- Communication coverage: **{coverage['communicated_rubrics']}/"
            f"{coverage['all_rubrics']} = {format_number(coverage['micro_rate'])}**.",
            f"- Communicated-only completion: **{communicated['met_communicated_rubrics']}/"
            f"{communicated['communicated_rubrics']} = "
            f"{format_number(communicated['micro_rate'])}**.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["Arm", "KEEP cells", "Score mean", "Rubric met / total", "Rubric micro"],
            [
                [
                    row["arm"],
                    row["cells"],
                    format_number(row["score_mean"]),
                    f"{row['rubric_met']} / {row['rubric_total']}",
                    format_number(row["rubric_micro_completion"]),
                ]
                for row in completion["per_arm"]
            ],
        )
    )

    behavior = keep["run_behavior"]
    steps = behavior["overall"]["steps"]
    questions = behavior["overall"]["questions"]
    stop_text = ", ".join(
        f"{row['reason']}={row['count']}" for row in behavior["stop_reasons"]
    ) or "none"
    lines.extend(
        [
            "",
            "### KEEP-only run behavior",
            "",
            f"Stop reasons: {stop_text}. Steps: mean **{format_number(steps['mean'], 2)}**, "
            f"median **{format_number(steps['median'], 2)}**, range "
            f"{format_number(steps['min'], 0)}–{format_number(steps['max'], 0)}. "
            f"Questions (`ask_user` calls): **{format_number(questions['total'], 0)} total**.",
            "",
            "### KEEP-only experience",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "Dimension",
                "A mean / median / n",
                "A ≥4 / n",
                "B mean / median / n",
                "B ≥4 / n",
                "Exact / paired",
                "Within 1 / paired",
            ],
            [
                [
                    row["dimension"],
                    f"{format_number(row['judge_a']['mean'], 2)} / "
                    f"{format_number(row['judge_a']['median'], 2)} / {row['judge_a']['n']}",
                    f"{row['judge_a']['score_gte_4']} / "
                    f"{row['judge_a']['score_gte_4_denominator']}",
                    f"{format_number(row['judge_b']['mean'], 2)} / "
                    f"{format_number(row['judge_b']['median'], 2)} / {row['judge_b']['n']}",
                    f"{row['judge_b']['score_gte_4']} / "
                    f"{row['judge_b']['score_gte_4_denominator']}",
                    f"{row['agreement']['exact']} / {row['agreement']['paired']}",
                    f"{row['agreement']['within_one']} / {row['agreement']['paired']}",
                ]
                for row in keep["experience"]["dimensions"]
            ],
        )
    )
    full = keep["perfect_slices"]["full_task_perfect"]
    communicated_slice = keep["perfect_slices"]["communicated_perfect"]
    lines.extend(
        [
            "",
            "### KEEP-only perfect slices",
            "",
            f"Full-task perfect (`judgement.score == 1.0`): **{full['cells']}/"
            f"{full['all_selected_numeric_scored_cells']}**. Communicated-perfect "
            f"(`judgement.score_communicated == 1.0`): **{communicated_slice['cells']}/"
            f"{communicated_slice['all_selected_numeric_scored_cells']}**.",
            "",
        ]
    )
    return lines


def markdown_report(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Food & Drink main-style Setting 1 — formal post-hoc analysis",
        "",
        "This report is generated deterministically from the replicate roots listed below. "
        "Judge A and Judge B experience scores are always shown separately. Unless a section "
        "is explicitly labeled KEEP-only, metrics use all selected numeric scored execution "
        "cells and do not assert environment validity.",
        "",
        "## Inputs and attempt accounting",
        "",
    ]
    input_rows = []
    for item in summary["inputs"]:
        input_rows.append(
            [
                item["experiment_id"],
                item.get("date_block") or "—",
                item.get("planned_cells") if item.get("planned_cells") is not None else "—",
                item["discovered_attempts"],
                item["selected_numeric_scored_cells"],
                item["execution_integrity_excluded_attempts"],
                item["error_attempts"],
            ]
        )
    lines.extend(
        markdown_table(
            [
                "Replicate",
                "Date block",
                "Planned",
                "Attempts",
                "Selected numeric scored",
                "Execution-integrity excluded",
                "Errors",
            ],
            input_rows,
        )
    )
    counts = summary["counts"]
    lines.extend(
        [
            "",
            f"Across all roots: **{counts['planned_cells'] if counts['planned_cells'] is not None else 'unknown'} planned cells**, "
            f"**{counts['selected_numeric_scored_cells']} selected numeric scored cells**, "
            f"**{counts['execution_integrity_excluded_attempts']} execution-integrity excluded attempts**, "
            f"and **{counts['error_attempts']} attempts containing `error.txt`**. "
            "Error counts overlap the execution-selected/excluded partition if an attempt ever "
            "contains both a scored result and an error file.",
            "",
            "A selected numeric scored cell is the latest execution-integrity-eligible finite "
            "numeric `judgement.score` for one (replicate, task, persona, execution model). "
            "This is **not** an environment-validity claim. Error-only attempts are never scored.",
            "",
        ]
    )
    if counts["exclusion_reasons"]:
        lines.extend(
            markdown_table(
                ["Exclusion reason", "Attempts"],
                [[row["reason"], row["count"]] for row in counts["exclusion_reasons"]],
            )
        )

    lines.extend(["", *environment_validity_markdown(summary)])

    completion = summary["completion"]
    micro = completion["rubric_micro_completion"]
    lines.extend(
        [
            "",
            "## All selected numeric scored cells — task completion",
            "",
            f"- Task-macro completion: **{format_number(completion['task_macro_completion'])}** "
            f"across {completion['task_macro_denominator']} tasks.",
            f"- Cell-macro completion: **{format_number(completion['cell_macro_completion'])}**.",
            f"- Rubric-micro completion: **{micro['met']}/{micro['total']} = "
            f"{format_number(micro['rate'])}**.",
            "",
            "### Completion by arm",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["Arm", "Cells", "Score mean", "Score median", "Rubric met / total", "Rubric micro"],
            [
                [
                    row["arm"],
                    row["cells"],
                    format_number(row["score_mean"]),
                    format_number(row["score_median"]),
                    f"{row['rubric_met']} / {row['rubric_total']}",
                    format_number(row["rubric_micro_completion"]),
                ]
                for row in completion["per_arm"]
            ],
        )
    )
    lines.extend(["", "### Completion by task", ""])
    lines.extend(
        markdown_table(
            ["Task", "Cells", "Score mean", "Rubric met / total", "Rubric micro"],
            [
                [
                    row["task_label"],
                    row["cells"],
                    format_number(row["score_mean"]),
                    f"{row['rubric_met']} / {row['rubric_total']}",
                    format_number(row["rubric_micro_completion"]),
                ]
                for row in completion["per_task"]
            ],
        )
    )

    task_labels = [item["label"] for item in summary["task_catalog"]]
    matrix: dict[tuple[str, str], dict[str, Any]] = {
        (row["arm"], row["task_label"]): row for row in completion["per_arm_per_task"]
    }
    arms = [row["arm"] for row in completion["per_arm"]]
    matrix_rows = []
    for arm in arms:
        row: list[Any] = [arm]
        for task_label in task_labels:
            value = matrix.get((arm, task_label))
            row.append(
                f"{format_number(value['score_mean'])} (n={value['cells']})" if value else "—"
            )
        matrix_rows.append(row)
    lines.extend(["", "### Arm × task completion", ""])
    lines.extend(markdown_table(["Arm", *task_labels], matrix_rows))

    communication = summary["communication"]
    overall_comm = communication["overall"]
    coverage = overall_comm["coverage"]
    communicated_completion = overall_comm["communicated_only_completion"]
    lines.extend(
        [
            "",
            "## All selected numeric scored cells — communication-conditioned metrics",
            "",
            f"Overall communication coverage is **{coverage['communicated_rubrics']}/{coverage['all_rubrics']} = "
            f"{format_number(coverage['micro_rate'])}** (micro); the cell-macro rate is "
            f"**{format_number(coverage['cell_macro_rate'])}** over {coverage['cell_macro_denominator']} cells.",
            "",
            f"Communicated-only completion is **{communicated_completion['met_communicated_rubrics']}/"
            f"{communicated_completion['communicated_rubrics']} = "
            f"{format_number(communicated_completion['micro_rate'])}** (micro); the cell-macro rate is "
            f"**{format_number(communicated_completion['cell_macro_rate'])}** over "
            f"{communicated_completion['cell_macro_denominator']} cells. "
            f"Cells with zero communicated rubric items: {communicated_completion['cells_with_zero_communicated_rubrics']}.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["Arm", "Coverage numerator / denominator", "Coverage", "Communicated met / denominator", "Communicated completion"],
            [
                [
                    row["arm"],
                    f"{row['coverage']['communicated_rubrics']} / {row['coverage']['all_rubrics']}",
                    format_number(row["coverage"]["micro_rate"]),
                    f"{row['communicated_only_completion']['met_communicated_rubrics']} / "
                    f"{row['communicated_only_completion']['communicated_rubrics']}",
                    format_number(row["communicated_only_completion"]["micro_rate"]),
                ]
                for row in communication["per_arm"]
            ],
        )
    )

    behavior = summary["run_behavior"]
    lines.extend(["", "## All selected numeric scored cells — run behavior", ""])
    lines.extend(
        markdown_table(
            ["Stop reason", "Cells"],
            [[row["reason"], row["count"]] for row in behavior["stop_reasons"]],
        )
    )
    overall_steps = behavior["overall"]["steps"]
    overall_questions = behavior["overall"]["questions"]
    lines.extend(
        [
            "",
            f"Steps: mean **{format_number(overall_steps['mean'], 2)}**, median "
            f"**{format_number(overall_steps['median'], 2)}**, range "
            f"{format_number(overall_steps['min'], 0)}–{format_number(overall_steps['max'], 0)} "
            f"over {overall_steps['n']} cells. Questions are reconstructed as `ask_user` trajectory calls: "
            f"**{format_number(overall_questions['total'], 0)} total**, mean "
            f"**{format_number(overall_questions['mean'], 2)}** per cell.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["Arm", "Cells", "Step mean", "Step median", "Questions total", "Questions mean"],
            [
                [
                    row["arm"],
                    row["cells"],
                    format_number(row["steps"]["mean"], 2),
                    format_number(row["steps"]["median"], 2),
                    format_number(row["questions"]["total"], 0),
                    format_number(row["questions"]["mean"], 2),
                ]
                for row in behavior["per_arm"]
            ],
        )
    )

    experience = summary["experience"]
    lines.extend(
        [
            "",
            "## All selected numeric scored cells — experience judges",
            "",
            "Scores are 1–5. `n/a` is missing or invalid at the relevant judge/dimension; "
            "A/B values are not averaged together.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "Dimension",
                "A mean / median",
                "A ≥4 / n",
                "A n/a",
                "B mean / median",
                "B ≥4 / n",
                "B n/a",
                "Exact / paired",
                "Within 1 / paired",
            ],
            [
                [
                    row["dimension"],
                    f"{format_number(row['judge_a']['mean'], 2)} / {format_number(row['judge_a']['median'], 2)}",
                    f"{row['judge_a']['score_gte_4']} / {row['judge_a']['score_gte_4_denominator']} "
                    f"({format_percent(row['judge_a']['score_gte_4_rate'])})",
                    row["judge_a"]["n_a"],
                    f"{format_number(row['judge_b']['mean'], 2)} / {format_number(row['judge_b']['median'], 2)}",
                    f"{row['judge_b']['score_gte_4']} / {row['judge_b']['score_gte_4_denominator']} "
                    f"({format_percent(row['judge_b']['score_gte_4_rate'])})",
                    row["judge_b"]["n_a"],
                    f"{row['agreement']['exact']} / {row['agreement']['paired']} "
                    f"({format_percent(row['agreement']['exact_rate'])})",
                    f"{row['agreement']['within_one']} / {row['agreement']['paired']} "
                    f"({format_percent(row['agreement']['within_one_rate'])})",
                ]
                for row in experience["dimensions"]
            ],
        )
    )
    agreement = experience["overall_agreement"]
    lines.extend(
        [
            "",
            f"Across dimensions, exact agreement is **{agreement['exact']}/"
            f"{agreement['paired_dimension_scores']} = {format_percent(agreement['exact_rate'])}**; "
            f"within-one agreement is **{agreement['within_one']}/"
            f"{agreement['paired_dimension_scores']} = {format_percent(agreement['within_one_rate'])}**; "
            f"paired-score n/a count is {agreement['n_a']}.",
            "",
            "## All selected numeric scored cells — perfect-task slices",
            "",
            "These slices are separate: full-task perfect uses all original rubrics, while "
            "communicated-perfect uses only rubric items the persona communicated.",
            "",
        ]
    )
    for slice_key, title in (
        ("full_task_perfect", "Full-task perfect (`judgement.score == 1.0`)"),
        ("communicated_perfect", "Communicated-perfect (`judgement.score_communicated == 1.0`)"),
    ):
        slice_value = summary["perfect_slices"][slice_key]
        lines.extend(
            [
                f"### {title}",
                "",
                f"{slice_value['cells']} / {slice_value['all_selected_numeric_scored_cells']} "
                "selected numeric scored cells "
                f"({format_percent(slice_value['rate_of_selected_numeric_scored_cells'])}).",
                "",
            ]
        )
        lines.extend(
            markdown_table(
                ["Dimension", "A mean / median / n", "B mean / median / n", "Within 1 / paired"],
                [
                    [
                        row["dimension"],
                        f"{format_number(row['judge_a']['mean'], 2)} / "
                        f"{format_number(row['judge_a']['median'], 2)} / {row['judge_a']['n']}",
                        f"{format_number(row['judge_b']['mean'], 2)} / "
                        f"{format_number(row['judge_b']['median'], 2)} / {row['judge_b']['n']}",
                        f"{row['agreement']['within_one']} / {row['agreement']['paired']} "
                        f"({format_percent(row['agreement']['within_one_rate'])})",
                    ]
                    for row in slice_value["experience_dimensions"]
                ],
            )
        )
        lines.append("")

    paired = summary["paired_persona_minus_none"]
    lines.extend(
        [
            "## All selected numeric scored cells — paired persona-minus-none deltas",
            "",
            f"Baseline persona: `{paired['baseline_persona']}`. Pairing is within replicate, "
            "task, and execution model. Positive completion delta favors the persona arm.",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            ["Persona / model", "Pairs", "Completion Δ mean", "Median", "W / T / L", "Coverage Δ mean", "Communicated completion Δ mean (n)"],
            [
                [
                    row["arm"],
                    row["paired_cells"],
                    format_number(row["completion_delta_mean"]),
                    format_number(row["completion_delta_median"]),
                    f"{row['completion_wins']} / {row['completion_ties']} / {row['completion_losses']}",
                    format_number(row["communication_coverage_delta_mean"]),
                    f"{format_number(row['communicated_only_completion_delta_mean'])} "
                    f"(n={row['communicated_only_completion_delta_n']})",
                ]
                for row in paired["aggregate_by_persona_and_model"]
            ],
        )
    )
    if paired["missing_baseline_pairs"]:
        lines.extend(
            [
                "",
                f"Unpaired persona cells with no matching baseline: {len(paired['missing_baseline_pairs'])}.",
            ]
        )

    noise = summary["external_noise"]
    lines.extend(
        [
            "",
            "## Descriptive external-noise keyword evidence",
            "",
            noise["overlap_warning"],
            "",
        ]
    )
    lines.extend(
        markdown_table(
            [
                "Category",
                "Attempts / all",
                "Occurrences",
                "Selected numeric scored",
                "Execution-integrity excluded",
            ],
            [
                [
                    row["description"],
                    f"{row['attempts_with_evidence']} / {row['all_attempts_denominator']}",
                    row["occurrences"],
                    row["selected_numeric_scored_attempts_with_evidence"],
                    row["execution_integrity_excluded_attempts_with_evidence"],
                ]
                for row in noise["categories"]
            ],
        )
    )
    lines.extend(["", f"Scope: {noise['scope']}.", "", "## Task catalog", ""])
    lines.extend(
        markdown_table(
            ["Task", "ID", "Level", "Rubrics", "Prompt preview"],
            [
                [
                    row["label"],
                    row["task_id_short"],
                    row.get("level") or "—",
                    row["rubric_count"],
                    row["prompt_preview"],
                ]
                for row in summary["task_catalog"]
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Excluded attempts",
            "",
        ]
    )
    if summary["exclusions"]:
        lines.extend(
            markdown_table(
                ["Replicate", "Path", "Reason", "result.json", "error.txt"],
                [
                    [
                        row["replicate"],
                        row["path"],
                        row["reason"],
                        "yes" if row["has_result_json"] else "no",
                        "yes" if row["has_error_txt"] else "no",
                    ]
                    for row in summary["exclusions"]
                ],
            )
        )
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one or more Food & Drink main-style Setting 1 replicate roots and write deterministic "
            "JSON plus Markdown summaries."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Each replicate root must contain results/. The tool keeps the latest numeric scored "
            "result per task/persona/model within each replicate and reports other attempts as "
            "execution-integrity exclusions. Environment validity is a separate optional overlay."
        ),
    )
    parser.add_argument(
        "replicate_roots",
        nargs="+",
        type=Path,
        help="replicate root directories (for example .../food-main-setting1-r1)",
    )
    parser.add_argument(
        "--output-prefix",
        required=True,
        type=Path,
        help="output prefix; writes PREFIX.json and PREFIX.md",
    )
    parser.add_argument(
        "--baseline-persona",
        default="none",
        help="baseline persona for paired deltas (default: none)",
    )
    parser.add_argument(
        "--validity-json",
        action="append",
        default=[],
        type=Path,
        help=(
            "environment-validity audit JSON; repeat once per replicate. Replicates without an "
            "explicit path auto-discover analysis/ENVIRONMENT_VALIDITY_AUDIT.json"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        roots = sorted({path.expanduser().resolve() for path in args.replicate_roots})
        replicates = [load_replicate(root) for root in roots]
        validity_audits = load_validity_audits(replicates, args.validity_json)
        summary = analyze(replicates, args.baseline_persona, validity_audits)
        prefix = normalize_prefix(args.output_prefix.expanduser())
        prefix.parent.mkdir(parents=True, exist_ok=True)
        json_path = prefix.with_suffix(".json")
        markdown_path = prefix.with_suffix(".md")
        json_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        markdown_path.write_text(markdown_report(summary), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    print(
        "selected_numeric_scored_cells={selected} execution_integrity_excluded_attempts={excluded} "
        "error_attempts={errors}".format(
            selected=summary["counts"]["selected_numeric_scored_cells"],
            excluded=summary["counts"]["execution_integrity_excluded_attempts"],
            errors=summary["counts"]["error_attempts"],
        )
    )
    validity = summary["environment_validity"]
    if validity["status"] == "applied":
        validity_counts = validity["counts"]
        print(
            "environment_keep_cells={keep} environment_exclude_rerun_cells={exclude} "
            "environment_unclassified_selected_numeric_cells={unclassified}".format(
                keep=validity_counts["environment_keep_cells"],
                exclude=validity_counts["environment_exclude_rerun_cells"],
                unclassified=validity_counts[
                    "environment_unclassified_selected_numeric_cells"
                ],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
