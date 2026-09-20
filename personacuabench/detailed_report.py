#!/usr/bin/env python3
"""Render one PersonaCUABench ``result.json`` as a detailed Markdown report.

The command is deliberately read-only with respect to the benchmark run.  It
does not import the runner, contact an API, or upload browser artifacts.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPERIENCE_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("P1_asked_for", "Asked for"),
    ("P2_readable_for_them", "Readable for this person"),
    ("P3_actionable", "Actionable"),
    ("P4_gap_handling", "Gap handling"),
    ("P5_overall", "Overall experience"),
)


class ReportError(ValueError):
    """Raised when a report cannot be produced from the supplied path."""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _first(root: Any, *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current = root
        for key in path:
            if not isinstance(current, Mapping) or key not in current:
                current = None
                break
            current = current[key]
        if current is not None and current != "":
            return current
    return None


def _compact(value: Any) -> str:
    """Convert an arbitrary JSON value to a compact, deterministic string."""
    if value is None or value == "":
        return "N/A"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "N/A"
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (Mapping, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(", ", ": "))
    return " ".join(str(value).split()) or "N/A"


def _md(value: Any) -> str:
    """Escape untrusted result data for a single Markdown paragraph/list item."""
    text = html.escape(_compact(value), quote=False)
    text = text.replace("\\", "\\\\")
    # CommonMark permits a backslash escape for every ASCII punctuation mark
    # below.  Escaping them even in prose prevents result-controlled headings,
    # lists, links, emphasis, and tables without relying on raw HTML.
    for character in (
        "`",
        "*",
        "_",
        "{",
        "}",
        "[",
        "]",
        "(",
        ")",
        "#",
        "+",
        "-",
        ".",
        "!",
        "|",
    ):
        text = text.replace(character, f"\\{character}")
    return text


def _score(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _compact(value)
    if not math.isfinite(number):
        return "N/A"
    return f"{number:.4f} ({number * 100:.1f}%)"


def _tri_state(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "N/A"


def _experience(result: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _first(result, ("experience",), ("judgement", "experience"))
    return _mapping(value)


def _experience_judge(
    experience: Mapping[str, Any], canonical: str, legacy: str
) -> Mapping[str, Any]:
    judges = _mapping(experience.get("judges"))
    value = experience.get(canonical)
    if not isinstance(value, Mapping):
        value = judges.get(canonical)
    if not isinstance(value, Mapping):
        value = experience.get(legacy)
    if not isinstance(value, Mapping):
        value = judges.get(legacy)
    return _mapping(value)


def _experience_judge_body(judge: Mapping[str, Any]) -> Mapping[str, Any]:
    """Unwrap known judge envelopes while retaining old main-branch results."""
    for key in ("verdict", "result", "output", "response", "scores"):
        value = judge.get(key)
        if isinstance(value, Mapping):
            return value
    return judge


def _experience_dimension(
    judge: Mapping[str, Any], dimension: str
) -> tuple[Any, Any]:
    value = _experience_judge_body(judge).get(dimension)
    if isinstance(value, Mapping):
        return value.get("score"), value.get("reason")
    return value, None


def _experience_agreement(
    experience: Mapping[str, Any], dimension: str
) -> Mapping[str, Any]:
    agreement = _mapping(experience.get("agreement"))
    dimensions = _mapping(agreement.get("dimensions"))
    value = agreement.get(dimension)
    if not isinstance(value, Mapping):
        value = dimensions.get(dimension)
    return _mapping(value)


def _experience_status(
    experience: Mapping[str, Any],
    judge_a: Mapping[str, Any],
    judge_b: Mapping[str, Any],
) -> Any:
    if experience.get("status") is not None:
        return experience.get("status")
    judges = (judge_a, judge_b)
    score_count = sum(
        _experience_dimension(judge, dimension)[0] is not None
        for judge in judges
        for dimension, _title in EXPERIENCE_DIMENSIONS
    )
    if score_count == len(EXPERIENCE_DIMENSIONS) * 2:
        return "complete"
    if any(judge.get("error") for judge in judges) and score_count == 0:
        return "failed"
    return "partial" if judge_a or judge_b else "pending"


def resolve_result_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if path.is_file():
        if path.name != "result.json":
            raise ReportError(f"Expected result.json, got: {path}")
        return path
    if not path.is_dir():
        raise ReportError(f"Run path does not exist: {path}")
    direct = path / "result.json"
    if direct.is_file():
        return direct.resolve()
    matches = sorted(path.rglob("result.json"))
    if not matches:
        raise ReportError(f"No result.json found under: {path}")
    if len(matches) > 1:
        raise ReportError(
            f"Run path is ambiguous: found {len(matches)} result.json files under {path}"
        )
    return matches[0].resolve()


def load_result(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReportError(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReportError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReportError(f"Expected a JSON object in {path}")
    return payload


def _persona_identity(result: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    judgement_persona = _mapping(_first(result, ("judgement", "persona")))
    meta = _mapping(result.get("persona_meta"))
    raw_persona = result.get("persona")
    name = _first(
        judgement_persona,
        ("name",),
    )
    if name is None and isinstance(raw_persona, str):
        name = raw_persona
    if name is None:
        name = _first(meta, ("persona_name",), ("name",), ("slug",), ("persona_id",))
    name_text = _compact(name if name is not None else "unknown")
    mode = _first(judgement_persona, ("mode",)) or meta.get("mode")
    if mode is None:
        mode = "none" if name_text.strip().lower() == "none" else "persona"
    return name_text, _compact(mode), meta


def _rubric_items(task: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rubrics = task.get("rubrics")
    if isinstance(rubrics, Mapping):
        return [(str(key), _mapping(value)) for key, value in rubrics.items()]
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for index, value in enumerate(_sequence(rubrics), start=1):
        item = _mapping(value)
        rubric_id = str(item.get("rubric_id") or item.get("id") or f"R{index}")
        rows.append((rubric_id, item))
    return rows


def _verdict_map(judgement: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = _first(judgement, ("verdicts",), ("task_success", "verdicts"))
    result: dict[str, Mapping[str, Any]] = {}
    for index, item_value in enumerate(_sequence(raw), start=1):
        item = _mapping(item_value)
        rubric_id = str(item.get("rubric_id") or item.get("id") or f"R{index}")
        result[rubric_id] = item
    return result


def _standard_rubric_map(judgement: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = _first(judgement, ("task_success", "standard", "rubric_results"))
    result: dict[str, Mapping[str, Any]] = {}
    for item_value in _sequence(raw):
        item = _mapping(item_value)
        if item.get("rubric_id") is not None:
            result[str(item["rubric_id"])] = item
    return result


def _add_field(lines: list[str], label: str, value: Any) -> None:
    lines.append(f"- **{label}:** {_md(value)}")


def _render_header(
    lines: list[str], result: Mapping[str, Any], result_path: Path
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], str, str]:
    task = _mapping(result.get("task"))
    run = _mapping(result.get("run"))
    judgement = _mapping(result.get("judgement"))
    persona_name, persona_mode, persona_meta = _persona_identity(result)
    models = _mapping(result.get("models"))

    lines.extend(
        [
            "# PersonaCUABench Detailed Run Report",
            "",
            "> Task success, persona adherence, and persona alignment are independent axes. "
            "They are **not averaged into one aggregate score**.",
            "",
            "## Run identity",
            "",
        ]
    )
    _add_field(lines, "Result file", result_path)
    _add_field(lines, "Schema", result.get("schema_version"))
    _add_field(lines, "Overall status", result.get("status"))
    _add_field(lines, "Created", result.get("created_at"))
    _add_field(lines, "Updated", result.get("updated_at"))
    _add_field(lines, "Task number", result.get("task_number"))
    _add_field(lines, "Task ID", result.get("task_id") or task.get("task_id"))
    _add_field(lines, "Assignment", task.get("assignment"))
    _add_field(lines, "Task level", task.get("level"))
    _add_field(lines, "Persona", persona_name)
    _add_field(lines, "Persona mode", persona_mode)
    _add_field(lines, "CUA model", models.get("cua"))
    _add_field(lines, "Persona model", models.get("persona"))

    error = _mapping(result.get("error"))
    if error:
        lines.extend(["", "### Run failure", ""])
        _add_field(lines, "Error type", error.get("type"))
        _add_field(lines, "Error message", error.get("message"))

    lines.extend(["", "## Task", ""])
    _add_field(lines, "Starting website", task.get("website"))
    _add_field(lines, "Categories", task.get("categories"))
    lines.extend(["", "### Confirmed task", "", _md(task.get("confirmed_task")), ""])

    dimensions = _first(
        persona_meta,
        ("evaluation_dimensions",),
        ("persona", "evaluation_dimensions"),
    )
    if dimensions is not None:
        lines.extend(["### Persona evaluation dimensions", ""])
        _add_field(lines, "Profile ID", persona_meta.get("persona_id"))
        _add_field(lines, "Display name", persona_meta.get("display_name"))
        _add_field(lines, "Dimensions", dimensions)
        _add_field(
            lines,
            "Assigned values",
            persona_meta.get("evaluation_values") or persona_meta.get("dimensions"),
        )

    return task, run, judgement, persona_name, persona_mode


def _render_run_statistics(
    lines: list[str], result: Mapping[str, Any], run: Mapping[str, Any]
) -> None:
    limits = _mapping(result.get("limits"))
    screenshots = _sequence(run.get("screenshots"))
    trajectory = _sequence(run.get("trajectory"))
    lines.extend(["## Execution details", ""])
    _add_field(lines, "Stop reason", run.get("stop_reason"))
    _add_field(lines, "Started", run.get("started_at"))
    _add_field(lines, "Finished", run.get("finished_at"))
    _add_field(lines, "Agent turns", run.get("agent_turns"))
    _add_field(lines, "Environment actions", run.get("env_actions"))
    _add_field(lines, "Trajectory events", len(trajectory) if "trajectory" in run else None)
    _add_field(lines, "Screenshots", len(screenshots) if "screenshots" in run else None)
    _add_field(lines, "OSWorld result marker", run.get("osworld_result_marker"))
    _add_field(lines, "Questions asked", run.get("questions_asked"))
    _add_field(lines, "Questions answered", run.get("questions_answered"))
    _add_field(lines, "Question budget", limits.get("max_questions"))
    _add_field(lines, "Step budget", limits.get("max_steps"))

    environment = _mapping(run.get("environment"))
    if environment:
        lines.extend(["", "### Run-time environment preflight", ""])
        _add_field(
            lines,
            "Enabled",
            environment.get("network_preflight_enabled"),
        )
        _add_field(
            lines,
            "Configured for task",
            environment.get("network_preflight_configured"),
        )
        _add_field(lines, "Environment status", environment.get("status"))
        _add_field(lines, "Classification", environment.get("classification"))
        _add_field(lines, "Feasibility evidence", environment.get("feasibility"))
        artifacts = _mapping(result.get("artifacts"))
        revisions = _mapping(result.get("source_revisions"))
        _add_field(lines, "Preflight artifact", artifacts.get("network_preflight"))
        _add_field(
            lines,
            "Preflight SHA-256",
            artifacts.get("network_preflight_sha256"),
        )
        _add_field(
            lines,
            "Task-specific availability policy SHA-256",
            revisions.get("availability_policy_task_sha256")
            or revisions.get("availability_policy_sha256"),
        )

    opening = run.get("opening")
    answer = run.get("answer")
    if opening is not None:
        lines.extend(["", "### Persona opening request", "", _md(opening)])
    if answer is not None:
        lines.extend(["", "### Final CUA answer", "", _md(answer)])

    lines.extend(["", "### Warnings", ""])
    warnings = _sequence(run.get("warnings"))
    if warnings:
        lines.extend(f"- {_md(warning)}" for warning in warnings)
    elif run.get("warnings"):
        lines.append(f"- {_md(run.get('warnings'))}")
    else:
        lines.append("- None recorded.")

    lines.extend(["", "### Open browser tabs", ""])
    tabs = _sequence(run.get("open_tabs"))
    if not tabs:
        lines.append("- None recorded or tab collection was unavailable.")
    for index, tab_value in enumerate(tabs, start=1):
        tab = _mapping(tab_value)
        if tab:
            title = tab.get("title") or tab.get("name") or f"Tab {index}"
            url = tab.get("url") or tab.get("href") or "N/A"
            lines.append(f"- **{index}. {_md(title)}** — {_md(url)}")
        else:
            lines.append(f"- **{index}.** {_md(tab_value)}")
    lines.append("")


def _render_task_scoring(
    lines: list[str], task: Mapping[str, Any], judgement: Mapping[str, Any]
) -> None:
    verdicts = _verdict_map(judgement)
    standard = _standard_rubric_map(judgement)
    rubric_items = _rubric_items(task)
    # Preserve judge-only rubrics even when an older result omitted embedded task rubrics.
    known_ids = {rubric_id for rubric_id, _ in rubric_items}
    rubric_items.extend(
        (rubric_id, {}) for rubric_id in verdicts if rubric_id not in known_ids
    )

    lines.extend(
        [
            "## Ordinary task-rubric scoring",
            "",
            "Each `met` decision measures task execution against that rubric's requirement "
            "and verification evidence. `communicated` separately measures whether the "
            "simulated user actually told the CUA that requirement. The communicated score "
            "therefore uses only communicated rubrics as its denominator.",
            "",
        ]
    )
    score_raw = _first(
        judgement,
        ("score_raw",),
        ("score",),
        ("task_success", "score_raw"),
        ("task_success", "score"),
    )
    score_adjusted = _first(
        judgement,
        ("score_availability_adjusted",),
        ("task_success", "score_availability_adjusted"),
    )
    score_communicated_raw = _first(
        judgement,
        ("score_communicated_raw",),
        ("score_communicated",),
        ("task_success", "score_communicated_raw"),
        ("task_success", "score_communicated"),
    )
    score_communicated_adjusted = _first(
        judgement,
        ("score_communicated_availability_adjusted",),
        ("task_success", "score_communicated_availability_adjusted"),
    )
    communicated_count = _first(
        judgement, ("task_success", "communicated_rubric_count")
    )
    _add_field(lines, "Task score (raw / official)", _score(score_raw))
    _add_field(
        lines,
        "Availability-adjusted task score (diagnostic)",
        _score(score_adjusted),
    )
    _add_field(
        lines,
        "Communicated-only score (raw / official)",
        _score(score_communicated_raw),
    )
    _add_field(
        lines,
        "Availability-adjusted communicated-only score (diagnostic)",
        _score(score_communicated_adjusted),
    )
    _add_field(lines, "Communicated rubric count", communicated_count)
    _add_field(
        lines,
        "Communication classification",
        (
            "judge-derived"
            if _first(judgement, ("task_success", "communication_judge_derived")) is True
            else "exact none-control or not recorded"
        ),
    )
    lines.extend(
        [
            "",
            "> The availability-adjusted scores are diagnostic. The raw scores and "
            "original per-rubric verdicts remain unchanged; adjustment does not rewrite "
            "the task or its official result.",
            "",
        ]
    )

    environment = _mapping(judgement.get("environment_feasibility"))
    adjustment = _mapping(
        _first(judgement, ("task_success", "availability_adjustment"))
    )
    lines.extend(["### Environment feasibility", ""])
    _add_field(lines, "Status", environment.get("status"))
    _add_field(lines, "Reasons", environment.get("reasons"))
    if not environment:
        lines.append("- No environment-feasibility diagnosis was recorded.")

    lines.extend(["", "### Availability adjustment", ""])
    _add_field(lines, "Status", adjustment.get("status"))
    _add_field(lines, "Coverage", adjustment.get("coverage"))
    _add_field(lines, "Excluded rubrics", adjustment.get("excluded_rubrics"))
    if adjustment.get("counts") is not None:
        _add_field(lines, "Counts", adjustment.get("counts"))
    _add_field(
        lines,
        "Raw rubric count",
        _first(
            adjustment,
            ("raw_rubric_count",),
            ("raw_count",),
            ("counts", "raw_rubric_count"),
            ("counts", "raw"),
            ("raw", "count"),
        ),
    )
    _add_field(
        lines,
        "Eligible rubric count",
        _first(
            adjustment,
            ("eligible_rubric_count",),
            ("eligible_count",),
            ("counts", "eligible_rubric_count"),
            ("counts", "eligible"),
            ("eligible", "count"),
        ),
    )
    raw_met_count = _first(
        adjustment,
        ("raw_met_count",),
        ("counts", "raw_met_count"),
        ("counts", "raw_met"),
        ("raw", "met_count"),
    )
    eligible_met_count = _first(
        adjustment,
        ("eligible_met_count",),
        ("counts", "eligible_met_count"),
        ("counts", "eligible_met"),
        ("eligible", "met_count"),
    )
    if raw_met_count is not None or eligible_met_count is not None:
        _add_field(lines, "Raw met count", raw_met_count)
        _add_field(lines, "Eligible met count", eligible_met_count)
    if not adjustment:
        lines.append("- No availability adjustment was recorded.")
    lines.append("")

    if not rubric_items:
        lines.extend(
            [
                "No rubric definitions or verdicts were recorded. The run may have failed "
                "before task metadata was written.",
                "",
            ]
        )
        return

    excluded_ids = {
        str(item.get("rubric_id"))
        for item in _sequence(adjustment.get("excluded_rubrics"))
        if isinstance(item, Mapping) and item.get("rubric_id") is not None
    }
    for rubric_id, rubric in rubric_items:
        verdict = verdicts.get(rubric_id, {})
        standard_item = standard.get(rubric_id, {})
        requirement = verdict.get("requirement") or rubric.get("requirement")
        verification = verdict.get("verification") or rubric.get("verification")
        met = verdict.get("met")
        if not isinstance(met, bool) and standard_item.get("score") in (0, 1):
            met = bool(standard_item["score"])
        task_evidence = (
            verdict.get("task_evidence")
            or standard_item.get("final_reasoning")
            or standard_item.get("reasoning")
        )
        communicated = verdict.get("communicated")
        communication_evidence = verdict.get("communication_evidence")
        lines.extend([f"### {_md(rubric_id)}", ""])
        _add_field(lines, "Requirement", requirement)
        _add_field(lines, "Verification standard", verification)
        _add_field(lines, "Met", _tri_state(met))
        _add_field(lines, "Communicated", _tri_state(communicated))
        _add_field(lines, "Task evidence", task_evidence)
        _add_field(lines, "Communication evidence", communication_evidence)
        if rubric_id in excluded_ids:
            _add_field(
                lines,
                "Adjusted-score handling",
                "Excluded from the diagnostic adjusted denominator because the "
                "required external target was unavailable; raw verdict remains unchanged.",
            )
        if not verdict and not standard_item:
            _add_field(lines, "Scoring state", "Pending / not scored")
        lines.append("")


def _render_adherence(
    lines: list[str], judgement: Mapping[str, Any], persona_mode: str
) -> None:
    persona = _mapping(judgement.get("persona"))
    adherence = _mapping(persona.get("adherence"))
    lines.extend(
        [
            "## Persona adherence",
            "",
            "Adherence evaluates whether the persona simulator expressed its assigned "
            "attributes. It does not measure whether the browser task succeeded.",
            "",
        ]
    )
    if not adherence:
        if persona_mode.lower() == "none":
            lines.append("**N/A:** the `none` control has no persona profile to adhere to.")
        else:
            lines.append("**Pending / not scored:** no adherence judgement is recorded.")
        lines.append("")
        return

    applicable = adherence.get("applicable")
    _add_field(lines, "Applicable", _tri_state(applicable))
    _add_field(lines, "Reason", adherence.get("reason"))
    targets = _sequence(adherence.get("targets"))
    if not targets:
        if applicable is False:
            lines.append("- No targets: N/A.")
        else:
            lines.append("- No target-level results were recorded.")
        lines.append("")
        return
    lines.append("")
    for index, target_value in enumerate(targets, start=1):
        target = _mapping(target_value)
        attribute = target.get("attribute") or f"target_{index}"
        lines.extend([f"### Target {index}: {_md(attribute)}", ""])
        _add_field(lines, "Expected value", target.get("expectedValue"))
        _add_field(lines, "Expressed", _tri_state(target.get("expressed")))
        _add_field(lines, "Confidence", _score(target.get("confidence")))
        _add_field(lines, "Evidence", target.get("evidence"))
        _add_field(lines, "Judge note", target.get("note"))
        lines.append("")


def _render_alignment(
    lines: list[str], judgement: Mapping[str, Any], persona_mode: str
) -> None:
    persona = _mapping(judgement.get("persona"))
    alignment = _mapping(persona.get("alignment"))
    lines.extend(
        [
            "## Persona outcome alignment",
            "",
            "Alignment evaluates whether the CUA served preferences and constraints that "
            "were communicated to it. Latent, uncommunicated profile attributes must not "
            "reduce this score.",
            "",
        ]
    )
    if not alignment:
        if persona_mode.lower() == "none":
            lines.append("**N/A:** the `none` control has no persona outcome to align with.")
        else:
            lines.append("**Pending / not scored:** no alignment judgement is recorded.")
        lines.append("")
        return

    _add_field(lines, "Status", alignment.get("persona_alignment_status"))
    _add_field(lines, "Score", _score(alignment.get("persona_alignment_score")))
    _add_field(
        lines,
        "Primary preference axis",
        alignment.get("persona_preference_axis_primary"),
    )
    _add_field(lines, "Signal source", alignment.get("persona_signal_source"))
    _add_field(lines, "Explanation", alignment.get("persona_alignment_explanation"))
    lines.extend(["", "### Persona constraints", ""])
    constraints = _sequence(alignment.get("persona_constraints"))
    if not constraints:
        lines.append("- None recorded / N/A.")
    for index, constraint_value in enumerate(constraints, start=1):
        constraint = _mapping(constraint_value)
        key = constraint.get("key") or f"constraint_{index}"
        lines.extend([f"#### Constraint {index}: {_md(key)}", ""])
        _add_field(lines, "Type", constraint.get("type"))
        if constraint.get("type_original") is not None:
            _add_field(lines, "Original judge type", constraint.get("type_original"))
        _add_field(lines, "Priority", constraint.get("priority"))
        _add_field(lines, "Status", constraint.get("status"))
        _add_field(lines, "Source", constraint.get("source"))
        _add_field(lines, "Communicated", _tri_state(constraint.get("communicated")))
        _add_field(lines, "Evidence", constraint.get("evidence"))
        lines.append("")

    contexts = _sequence(persona.get("contexts"))
    if contexts:
        lines.extend(["### Emitted persona contexts", ""])
        for index, context in enumerate(contexts, start=1):
            lines.append(f"- **Context {index}:** {_md(context)}")
        lines.append("")


def _render_experience(lines: list[str], result: Mapping[str, Any]) -> None:
    experience = _experience(result)
    lines.extend(
        [
            "## Persona experience (P1–P5)",
            "",
            "Two independent judges assess the encounter from the particular person's "
            "perspective. Their P1–P5 scores are retained separately and are **not "
            "averaged with each other or with task success, availability, adherence, "
            "or alignment**.",
            "",
        ]
    )
    if not experience:
        lines.extend(
            [
                "**Not run:** no persona-experience judgement is recorded. Ordinary "
                "task and persona scores above are unaffected.",
                "",
            ]
        )
        return

    judge_a = _experience_judge(experience, "judge_a", "a")
    judge_b = _experience_judge(experience, "judge_b", "b")
    body_a = _experience_judge_body(judge_a)
    body_b = _experience_judge_body(judge_b)

    _add_field(
        lines,
        "Experience status",
        _experience_status(experience, judge_a, judge_b),
    )
    _add_field(lines, "Experience schema", experience.get("schema_version"))
    _add_field(
        lines,
        "Judged at",
        experience.get("judged_at") or experience.get("created_at"),
    )
    _add_field(
        lines,
        "Prompt SHA-256",
        experience.get("prompt_sha256")
        or _first(
            experience,
            ("prompt", "template_sha256"),
            ("scope", "prompt_sha256"),
        ),
    )
    for label, judge in (("Judge A", judge_a), ("Judge B", judge_b)):
        _add_field(
            lines,
            f"{label} model",
            _first(judge, ("model",), ("judge", "model"), ("config", "model")),
        )
        provider = _first(
            judge,
            ("provider",),
            ("transport",),
            ("judge", "provider"),
            ("config", "provider"),
        )
        if provider is not None:
            _add_field(lines, f"{label} provider/transport", provider)
        if judge.get("status") is not None:
            _add_field(lines, f"{label} status", judge.get("status"))
        if judge.get("error") is not None:
            _add_field(lines, f"{label} error", judge.get("error"))
    lines.append("")

    for dimension, title in EXPERIENCE_DIMENSIONS:
        score_a, reason_a = _experience_dimension(judge_a, dimension)
        score_b, reason_b = _experience_dimension(judge_b, dimension)
        agreement = _experience_agreement(experience, dimension)
        lines.extend([f"### {_md(dimension)} — {title}", ""])
        _add_field(lines, "Judge A score", score_a)
        _add_field(lines, "Judge A reason", reason_a)
        _add_field(lines, "Judge B score", score_b)
        _add_field(lines, "Judge B reason", reason_b)
        _add_field(lines, "Score delta (A minus B)", agreement.get("delta"))
        _add_field(lines, "Within one point", _tri_state(agreement.get("within_one")))
        lines.append("")

    lines.extend(["### Explicit requests and unspoken gaps", ""])
    _add_field(lines, "Judge A unmet requests", body_a.get("unmet_requests"))
    _add_field(lines, "Judge B unmet requests", body_b.get("unmet_requests"))
    _add_field(lines, "Judge A missed gaps", body_a.get("missed_gaps"))
    _add_field(lines, "Judge B missed gaps", body_b.get("missed_gaps"))
    _add_field(lines, "Judge A confidence", body_a.get("judge_confidence"))
    _add_field(lines, "Judge B confidence", body_b.get("judge_confidence"))

    agreement = _mapping(experience.get("agreement"))
    for keys, label in (
        (("comparable_count", "comparable_dimensions"), "Comparable dimensions"),
        (("within_one_count", "within_one_dimensions"), "Dimensions within one point"),
        (("within_one_rate",), "Within-one agreement rate"),
    ):
        value = next(
            (agreement.get(key) for key in keys if agreement.get(key) is not None),
            None,
        )
        if value is not None:
            _add_field(lines, label, value)
    lines.append("")


def _render_judge(lines: list[str], judgement: Mapping[str, Any]) -> None:
    judge = _mapping(judgement.get("judge"))
    scope = _mapping(judgement.get("scope"))
    lines.extend(
        [
            "## Judge provenance and scope",
            "",
        ]
    )
    _add_field(lines, "Judgement status", judgement.get("status"))
    _add_field(lines, "Judged at", judgement.get("judged_at"))
    _add_field(lines, "API/transport", judge.get("transport"))
    _add_field(lines, "Provider", judge.get("provider"))
    _add_field(lines, "API model", judge.get("model"))
    _add_field(lines, "Reasoning effort", judge.get("reasoning_effort"))
    _add_field(lines, "Max completion tokens", judge.get("max_completion_tokens"))
    _add_field(lines, "Screenshot limit", scope.get("max_images"))
    _add_field(lines, "Screenshots sent", scope.get("screenshots_sent"))
    _add_field(lines, "Trajectory step limit", scope.get("max_steps"))
    _add_field(lines, "Trajectory events judged", scope.get("trajectory_events"))
    _add_field(lines, "Source result SHA-256", scope.get("source_result_sha256"))
    _add_field(
        lines,
        "Source artifact manifest SHA-256",
        scope.get("source_artifact_manifest_sha256"),
    )
    _add_field(
        lines,
        "Network preflight integrity",
        scope.get("network_preflight_integrity"),
    )
    if not judgement or judgement.get("status") in {None, "not_run", "pending"}:
        lines.extend(
            [
                "",
                "No API judging has been recorded. All scoring fields shown as N/A or "
                "pending are intentionally not inferred by this offline report.",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- **Task success** measures completion of the ordinary R1–Rn requirements.",
            "- **Persona adherence** measures the simulator's expression of "
            "assigned traits.",
            "- **Persona alignment** measures whether the CUA respected "
            "communicated persona constraints.",
            "- **Persona experience P1–P5** records two independent judges' "
            "user-side assessments.",
            "- These axes answer different questions and **must not be averaged** into a single score.",
            "",
        ]
    )


def render_report(result: Mapping[str, Any], result_path: Path) -> str:
    lines: list[str] = []
    task, run, judgement, _persona_name, persona_mode = _render_header(
        lines, result, result_path
    )
    _render_run_statistics(lines, result, run)
    _render_task_scoring(lines, task, judgement)
    _render_adherence(lines, judgement, persona_mode)
    _render_alignment(lines, judgement, persona_mode)
    _render_experience(lines, result)
    _render_judge(lines, judgement)
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_name = stream.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="Run directory or result.json")
    parser.add_argument(
        "--output",
        default="-",
        help="Markdown output path (default: stdout; use - for stdout)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result_path = resolve_result_path(args.run)
        result = load_result(result_path)
        report = render_report(result, result_path)
        if args.output == "-":
            sys.stdout.write(report)
        else:
            _atomic_write(Path(args.output).expanduser().resolve(), report)
        return 0
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
