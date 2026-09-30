#!/usr/bin/env python3
"""Read-only integrity and environment-signal audit for formal result roots.

The helper never mutates an experiment directory.  It inventories the expected
task/persona grid, validates completed ``result.json`` files, and reports
evidence that *may* require environment exclusion review.  It deliberately does
not turn every 403/CAPTCHA/timeout into an exclusion: materiality still depends
on whether required or persona-communicated evidence was actually blocked and
whether the run recovered.

Typical use::

    python artifacts/experiments/food_result_audit.py \
      artifacts/experiments/2026-09-28/food-main-nocap-setting1-r1

    python artifacts/experiments/food_result_audit.py ROOT --format json

Exit status is zero for a normal audit, including an in-progress grid.  Use
``--require-complete`` and/or ``--fail-on-review`` for a stricter gate.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SIGNAL_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    # Do not match bare 403/429: those can be prices or product identifiers.
    "http_403": (
        re.compile(r"\b(?:http(?:/\d(?:\.\d)?)?\s*)?(?:status(?:\s+code)?|error|response)\s*[:=]?\s*403\b", re.I),
        re.compile(r"\b403\s+(?:forbidden|access\s+denied)\b", re.I),
        re.compile(r"\bhttp\s*403\b", re.I),
    ),
    "http_429": (
        re.compile(r"\b(?:http(?:/\d(?:\.\d)?)?\s*)?(?:status(?:\s+code)?|error|response)\s*[:=]?\s*429\b", re.I),
        re.compile(r"\b429\s+too\s+many\s+requests\b", re.I),
        re.compile(r"\b(?:rate[ -]?limit(?:ed|ing)?|too\s+many\s+requests)\b", re.I),
    ),
    "captcha_or_verification": (
        re.compile(r"\bcaptcha\b", re.I),
        re.compile(r"\bsecurity\s+verification\b", re.I),
        re.compile(r"\bverify\s+(?:that\s+)?you(?:'re|\s+are)\s+(?:a\s+)?human\b", re.I),
        re.compile(r"\bunusual\s+traffic\b", re.I),
        re.compile(r"(?:google\.com/)?sorry/index", re.I),
        re.compile(r"\bchecking\s+(?:if\s+)?(?:your\s+)?browser\b", re.I),
        re.compile(r"\bcloudflare\b.{0,80}\b(?:challenge|verification|checking)\b", re.I | re.S),
        re.compile(r"\bcf-chl-[\w-]+", re.I),
    ),
    "access_or_login_wall": (
        re.compile(r"\baccess\s+denied\b", re.I),
        re.compile(r"\bforbidden\b", re.I),
        re.compile(r"\b(?:sign[ -]?in|log[ -]?in)\s+(?:is\s+)?required\b", re.I),
        re.compile(r"\bredirect(?:ed|s|ing)?\s+to\s+(?:a|the)\s+(?:sign[ -]?in|log[ -]?in)\b", re.I),
    ),
    "dns_failure": (
        re.compile(r"\bERR_NAME_NOT_RESOLVED\b", re.I),
        re.compile(r"\bDNS_PROBE_FINISHED(?:_NXDOMAIN)?\b", re.I),
        re.compile(r"\bNXDOMAIN\b", re.I),
        re.compile(r"\b(?:could\s+not|couldn't|failed\s+to)\s+resolve\s+(?:the\s+)?host\b", re.I),
        re.compile(r"\bname\s+or\s+service\s+not\s+known\b", re.I),
    ),
    "timeout_or_crash": (
        # Deliberately exclude ordinary Locator.click/fill waits.  Those are
        # agent/tool interaction failures, not proof that a site was blocked.
        re.compile(r"\b(?:page\.)?goto\b.{0,100}\bTimeout(?:Error)?\b", re.I | re.S),
        re.compile(r"\bNavigation\s+timeout\b", re.I),
        re.compile(r"\bBrowserType\.launch(?:_persistent_context)?\b.{0,100}\bTimeout(?:Error)?\b", re.I | re.S),
        re.compile(r"\bERR_TIMED_OUT\b", re.I),
        re.compile(r"\b(?:target|page|browser|context).{0,60}\bcrash(?:ed)?\b", re.I | re.S),
        re.compile(r"\bTarget page, context or browser has been closed\b", re.I),
        re.compile(r"\bAw,\s*Snap!?\b", re.I),
    ),
    "tab_limit": (
        re.compile(r"\[?tab\s+limit(?:\s+\d+)?\s+reached\]?", re.I),
        re.compile(r"\bmaximum\s+(?:number\s+of\s+)?tabs?\s+(?:has\s+been\s+)?reached\b", re.I),
    ),
}

ENVIRONMENT_SIGNAL_TYPES = {
    "http_403",
    "http_429",
    "captcha_or_verification",
    "access_or_login_wall",
    "dns_failure",
    "timeout_or_crash",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(api[-_ ]?key\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+"),
)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        if pattern.groups:
            redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def excerpt(text: str, start: int, end: int, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    clipped = re.sub(r"\s+", " ", text[left:right]).strip()
    if left:
        clipped = "…" + clipped
    if right < len(text):
        clipped += "…"
    return redact(clipped)


def scan_text(text: Any, source: str) -> list[dict[str, Any]]:
    if not isinstance(text, str) or not text:
        return []
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for signal_type, patterns in SIGNAL_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                evidence = excerpt(text, match.start(), match.end())
                key = (signal_type, evidence)
                if key in seen:
                    continue
                seen.add(key)
                found.append(
                    {
                        "type": signal_type,
                        "source": source,
                        "match": redact(match.group(0)),
                        "excerpt": evidence,
                    }
                )
                # One compact excerpt per signal type and source is sufficient.
                break
            if any(item["type"] == signal_type for item in found):
                break
    return found


def scan_result(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    run = data.get("run") if isinstance(data.get("run"), Mapping) else {}
    trajectory = run.get("trajectory") if isinstance(run.get("trajectory"), list) else []
    for position, item in enumerate(trajectory):
        if not isinstance(item, Mapping):
            continue
        step = item.get("step", position)
        evidence.extend(scan_text(item.get("result_preview"), f"trajectory.step[{step}].result_preview"))

    evidence.extend(scan_text(run.get("answer"), "run.answer"))

    open_tabs = run.get("open_tabs") if isinstance(run.get("open_tabs"), list) else []
    for position, tab in enumerate(open_tabs):
        if not isinstance(tab, Mapping):
            continue
        evidence.extend(scan_text(tab.get("title"), f"run.open_tabs[{position}].title"))
        evidence.extend(scan_text(tab.get("url"), f"run.open_tabs[{position}].url"))

    judgement = data.get("judgement") if isinstance(data.get("judgement"), Mapping) else {}
    verdicts = judgement.get("verdicts") if isinstance(judgement.get("verdicts"), Mapping) else {}
    for rubric_id, verdict in verdicts.items():
        if isinstance(verdict, Mapping):
            evidence.extend(scan_text(verdict.get("reason"), f"judgement.verdicts.{rubric_id}.reason"))

    # Avoid repeating identical signal/excerpt pairs surfaced in multiple fields.
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        key = (item["type"], item["excerpt"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def task_label(task: Mapping[str, Any], index: int) -> str:
    raw = task.get("confirmed_task") or task.get("task") or task.get("description") or ""
    if not isinstance(raw, str) or not raw.strip():
        return f"Task {index}"
    words = re.sub(r"\s+", " ", raw).strip().split(" ")
    compact = " ".join(words[:8])
    return compact + ("…" if len(words) > 8 else "")


def validate_result(
    data: Mapping[str, Any],
    expected_task: Mapping[str, Any] | None,
    expected_personas: set[str],
    path: Path,
) -> list[str]:
    issues: list[str] = []
    task_id = data.get("task_id")
    persona = data.get("persona")
    if not isinstance(task_id, str) or not task_id:
        issues.append("missing string task_id")
    if not isinstance(persona, str) or not persona:
        issues.append("missing string persona")
    elif persona not in expected_personas:
        issues.append(f"unexpected persona {persona!r}")
    if expected_task is not None:
        expected_id = expected_task.get("task_id")
        if task_id != expected_id:
            issues.append(f"task_id mismatch: expected {expected_id!r}, got {task_id!r}")
        expected_level = expected_task.get("level")
        if expected_level is not None and data.get("level") != expected_level:
            issues.append(f"level mismatch: expected {expected_level!r}, got {data.get('level')!r}")

    parent_prefix = path.parent.parent.name
    if isinstance(task_id, str) and not task_id.startswith(parent_prefix):
        issues.append(f"task directory prefix {parent_prefix!r} does not match task_id")

    run = data.get("run")
    if not isinstance(run, Mapping):
        issues.append("missing run object")
        run = {}
    trajectory = run.get("trajectory")
    if not isinstance(trajectory, list):
        issues.append("run.trajectory is not a list")
    steps = run.get("steps")
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
        issues.append("run.steps is not a non-negative integer")
    elif isinstance(trajectory, list) and steps != len(trajectory):
        issues.append(f"run.steps={steps} but trajectory length={len(trajectory)}")
    if not isinstance(run.get("stop_reason"), str) or not run.get("stop_reason"):
        issues.append("missing run.stop_reason")

    judgement = data.get("judgement")
    if not isinstance(judgement, Mapping):
        issues.append("missing judgement object")
        return issues
    verdicts = judgement.get("verdicts")
    if not isinstance(verdicts, Mapping):
        issues.append("judgement.verdicts is not an object")
        return issues

    verdict_items = [(key, value) for key, value in verdicts.items() if isinstance(value, Mapping)]
    if len(verdict_items) != len(verdicts):
        issues.append("one or more rubric verdicts are not objects")
    actual_total = len(verdict_items)
    actual_met = sum(value.get("met") is True for _, value in verdict_items)
    actual_communicated = sum(value.get("communicated") is True for _, value in verdict_items)
    met_communicated = sum(
        value.get("met") is True and value.get("communicated") is True for _, value in verdict_items
    )

    expected_rubrics = expected_task.get("rubrics") if isinstance(expected_task, Mapping) else None
    if isinstance(expected_rubrics, Mapping) and set(verdicts) != set(expected_rubrics):
        missing = sorted(set(expected_rubrics) - set(verdicts))
        extra = sorted(set(verdicts) - set(expected_rubrics))
        issues.append(f"rubric ID mismatch: missing={missing}, extra={extra}")

    for field, actual in (
        ("total", actual_total),
        ("met", actual_met),
        ("communicated", actual_communicated),
    ):
        if judgement.get(field) != actual:
            issues.append(f"judgement.{field}={judgement.get(field)!r}, recomputed={actual}")

    score = judgement.get("score")
    if not is_number(score):
        issues.append("judgement.score is not finite numeric")
    elif actual_total:
        expected_score = actual_met / actual_total
        # Main's judge output commonly rounds rubric ratios to three decimals.
        if not math.isclose(float(score), expected_score, rel_tol=0, abs_tol=5e-4):
            issues.append(f"judgement.score={score}, recomputed={expected_score}")

    score_communicated = judgement.get("score_communicated")
    if actual_communicated and not is_number(score_communicated):
        issues.append("judgement.score_communicated is not finite numeric")
    elif actual_communicated and is_number(score_communicated):
        expected_score = met_communicated / actual_communicated
        if not math.isclose(float(score_communicated), expected_score, rel_tol=0, abs_tol=5e-4):
            issues.append(
                f"judgement.score_communicated={score_communicated}, recomputed={expected_score}"
            )
    elif not actual_communicated and score_communicated not in (None, 0, 0.0):
        issues.append(
            f"judgement.score_communicated={score_communicated!r} with zero communicated rubrics"
        )

    efficiency = judgement.get("trajectory_efficiency")
    if actual_total and isinstance(steps, int) and steps > 0 and is_number(efficiency):
        # Mirror run.py exactly: efficiency is derived from the unrounded
        # rubric ratio, then persisted at four decimals.  Dividing the already
        # rounded three-decimal ``judgement.score`` creates false half-step
        # mismatches such as 0.0286 versus 0.02855.
        expected_efficiency = round(actual_met / actual_total / steps, 4)
        if not math.isclose(float(efficiency), expected_efficiency, rel_tol=0, abs_tol=1e-9):
            issues.append(
                f"judgement.trajectory_efficiency={efficiency}, recomputed={expected_efficiency}"
            )
    return issues


def get_runtime(root: Path) -> tuple[dict[str, Any], Path | None, list[str]]:
    issues: list[str] = []
    candidates = (root / "inputs" / "runtime-config.json", root / "RUN_MANIFEST.json")
    for path in candidates:
        if not path.is_file():
            continue
        data, error = load_json(path)
        if error:
            issues.append(f"cannot parse {path}: {error}")
            continue
        if isinstance(data, dict):
            return data, path, issues
        issues.append(f"{path} is not a JSON object")
    return {}, None, issues


def get_personas(runtime: Mapping[str, Any], root: Path) -> tuple[list[str], str | None]:
    for field in ("personas", "arms"):
        value = runtime.get(field)
        if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            return list(dict.fromkeys(value)), field

    config, error = load_json(root / "inputs" / "runtime-config.json")
    if not error and isinstance(config, Mapping):
        value = config.get("personas")
        if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            return list(dict.fromkeys(value)), "inputs/runtime-config.json:personas"
    return [], None


def infer_log_cell(path: Path, personas: Sequence[str], task_count: int) -> tuple[str, int] | None:
    name = path.name
    for persona in sorted(personas, key=len, reverse=True):
        match = re.fullmatch(re.escape(persona) + r"-task(\d+)-attempt\d+\.log", name)
        if match:
            task_index = int(match.group(1))
            if 1 <= task_index <= task_count:
                return persona, task_index
    return None


def signal_types(evidence: Iterable[Mapping[str, Any]]) -> set[str]:
    return {str(item.get("type")) for item in evidence if item.get("type")}


def result_metrics(data: Mapping[str, Any]) -> dict[str, Any]:
    judgement = data.get("judgement") if isinstance(data.get("judgement"), Mapping) else {}
    verdicts = judgement.get("verdicts") if isinstance(judgement.get("verdicts"), Mapping) else {}
    communicated_ids = [
        str(rubric_id)
        for rubric_id, verdict in verdicts.items()
        if isinstance(verdict, Mapping) and verdict.get("communicated") is True
    ]
    unmet_communicated_ids = [
        str(rubric_id)
        for rubric_id, verdict in verdicts.items()
        if isinstance(verdict, Mapping)
        and verdict.get("communicated") is True
        and verdict.get("met") is not True
    ]
    run = data.get("run") if isinstance(data.get("run"), Mapping) else {}
    return {
        "score": judgement.get("score"),
        "met": judgement.get("met"),
        "total": judgement.get("total"),
        "communicated": judgement.get("communicated"),
        "score_communicated": judgement.get("score_communicated"),
        "communicated_rubrics": communicated_ids,
        "unmet_communicated_rubrics": unmet_communicated_ids,
        "stop_reason": run.get("stop_reason"),
        "steps": run.get("steps"),
        "experience_present": isinstance(data.get("experience"), Mapping),
    }


def no_cap_configured(runtime: Mapping[str, Any], root: Path) -> bool:
    configured_values: list[Any] = []
    for field in ("max_tabs", "odyssey_max_tabs"):
        if field in runtime:
            configured_values.append(runtime[field])
    protocol = runtime.get("protocol")
    if isinstance(protocol, Mapping):
        for field in ("max_tabs", "odyssey_max_tabs"):
            if field in protocol:
                configured_values.append(protocol[field])
    config, error = load_json(root / "inputs" / "runtime-config.json")
    if not error and isinstance(config, Mapping):
        for field in ("max_tabs", "odyssey_max_tabs"):
            if field in config:
                configured_values.append(config[field])
        env_value = config.get("max_tabs_env")
        if isinstance(env_value, str) and re.search(r"ODYSSEY_MAX_TABS\s*=\s*0\b", env_value):
            return True
    return any(value in (0, None) for value in configured_values)


def classify_cell(
    result_count: int,
    valid_numeric_count: int,
    chosen: Mapping[str, Any] | None,
    schema_issues: Sequence[str],
    result_signal_types: set[str],
    attempt_count: int,
    attempt_signal_types: set[str],
    log_count: int,
    manifest_status: str,
    configured_no_cap: bool,
) -> tuple[str, str]:
    if result_count > 1:
        return "DUPLICATE_RESULT_REVIEW", "Multiple result.json files map to the same task/persona cell."
    if result_count and valid_numeric_count == 0:
        if "http_429" in result_signal_types | attempt_signal_types:
            return "NO_RESULT_RERUN_RATE_LIMIT", "No numeric score; 429/rate-limit evidence is retryable operational failure."
        return "MALFORMED_RESULT_REVIEW", "A result artifact exists but has no valid numeric judge score."
    if valid_numeric_count:
        if "tab_limit" in result_signal_types:
            if configured_no_cap:
                return (
                    "CONFIGURATION_ANOMALY_REVIEW",
                    "A tab-limit hit contradicts the recorded no-cap setting; inspect launch/configuration before use.",
                )
            return (
                "STRUCTURAL_PROTOCOL_CENSORING_REVIEW",
                "Tab capacity may make a task requirement unattainable; this is not a transient web rerun.",
            )
        if schema_issues:
            return "RESULT_SCHEMA_REVIEW", "Numeric score exists, but result schema/arithmetic checks failed."
        environment_hits = result_signal_types & ENVIRONMENT_SIGNAL_TYPES
        metrics = result_metrics(chosen or {})
        if environment_hits and metrics["unmet_communicated_rubrics"]:
            return (
                "ENVIRONMENT_EXCLUSION_CANDIDATE",
                "Blocking evidence co-occurs with unmet communicated rubrics; manually verify source materiality and recovery.",
            )
        if environment_hits:
            return (
                "KEEP_RECOVERED_OR_INCIDENTAL_ENV_SIGNAL",
                "Environment evidence appears, but no communicated rubric is unmet; keep unless manual evidence shows material blockage.",
            )
        score = metrics.get("score")
        if is_number(score) and math.isclose(float(score), 1.0, rel_tol=0, abs_tol=1e-9):
            return "KEEP_CLEAN_SUCCESS", "Numeric complete result with no scanned blocking evidence."
        return (
            "KEEP_GENUINE_TASK_OR_AGENT_OUTCOME",
            "Low/partial score has no scanned environment blocker; treat as task/agent/protocol outcome.",
        )

    if attempt_count:
        if "http_429" in attempt_signal_types:
            return "NO_RESULT_RERUN_RATE_LIMIT", "No result; failed attempt shows 429/rate-limit evidence."
        if attempt_signal_types & ENVIRONMENT_SIGNAL_TYPES:
            return "NO_RESULT_RERUN_OPERATIONAL", "No result; failed attempt shows an operational/environment error."
        return "NO_RESULT_RERUN_OPERATIONAL", "No result; one or more failed attempt artifacts exist."
    if log_count:
        # A live log can contain a transient 403/CAPTCHA/timeout from which the
        # still-running cell later recovers.  Do not prejudge an active cell.
        if manifest_status.lower() == "running":
            if attempt_signal_types:
                return "PENDING", "Active run log contains preliminary signals; wait for the final result before adjudicating."
            return "PENDING", "Run log exists and manifest is still running."
        if "http_429" in attempt_signal_types:
            return "NO_RESULT_RERUN_RATE_LIMIT", "No result; run log shows 429/rate-limit evidence."
        if attempt_signal_types & ENVIRONMENT_SIGNAL_TYPES:
            return "NO_RESULT_RERUN_OPERATIONAL", "No result; run log shows an operational/environment error."
        return "MISSING_RESULT_REVIEW", "A run log exists but no result was found after the run stopped."
    if manifest_status.lower() == "running":
        return "PENDING", "Cell has not produced an artifact in the active grid."
    return "MISSING_RESULT_REVIEW", "Expected cell has no result or attempt artifact."


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    tasks_path = root / "inputs" / "tasks.json"
    tasks_data, tasks_error = load_json(tasks_path)
    top_issues: list[str] = []
    if tasks_error:
        raise ValueError(f"cannot load {tasks_path}: {tasks_error}")
    if not isinstance(tasks_data, list) or not tasks_data:
        raise ValueError(f"{tasks_path} must contain a non-empty JSON array")
    tasks: list[dict[str, Any]] = []
    for index, task in enumerate(tasks_data, 1):
        if not isinstance(task, dict) or not isinstance(task.get("task_id"), str):
            raise ValueError(f"task {index} lacks a string task_id")
        tasks.append(task)
    task_ids = [task["task_id"] for task in tasks]
    if len(set(task_ids)) != len(task_ids):
        top_issues.append("inputs/tasks.json contains duplicate task_id values")

    runtime, runtime_path, runtime_issues = get_runtime(root)
    top_issues.extend(runtime_issues)
    personas, persona_source = get_personas(runtime, root)
    if not personas:
        raise ValueError("cannot determine persona arms from runtime-config.json or RUN_MANIFEST.json")
    if len(set(personas)) != len(personas):
        top_issues.append("runtime configuration contains duplicate persona arms")

    manifest_data, manifest_error = load_json(root / "RUN_MANIFEST.json")
    manifest = manifest_data if isinstance(manifest_data, Mapping) else {}
    if manifest_error and (root / "RUN_MANIFEST.json").exists():
        top_issues.append(f"cannot parse RUN_MANIFEST.json: {manifest_error}")
    manifest_status = str(manifest.get("status", runtime.get("status", "unknown")))
    configured_no_cap = no_cap_configured(runtime, root)

    task_by_id = {task["task_id"]: task for task in tasks}
    task_index_by_id = {task["task_id"]: index for index, task in enumerate(tasks, 1)}
    task_by_prefix: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        task_by_prefix[task["task_id"][:12]].append(task)

    result_records: list[dict[str, Any]] = []
    unknown_artifacts: list[dict[str, Any]] = []
    results_root = root / "results"
    result_paths = sorted(results_root.glob("*/*/result.json")) if results_root.is_dir() else []
    for path in result_paths:
        data, error = load_json(path)
        record: dict[str, Any] = {
            "path": str(path.relative_to(root)),
            "data": data if isinstance(data, Mapping) else None,
            "parse_error": error or (None if isinstance(data, Mapping) else "top-level JSON is not an object"),
            "signals": [],
            "schema_issues": [],
        }
        if isinstance(data, Mapping):
            record["signals"] = scan_result(data)
            expected_task = task_by_id.get(data.get("task_id"))
            record["schema_issues"] = validate_result(data, expected_task, set(personas), path)
            record["task_id"] = data.get("task_id")
            record["persona"] = data.get("persona")
            record["metrics"] = result_metrics(data)
        else:
            parent_prefix = path.parent.parent.name
            candidates = task_by_prefix.get(parent_prefix, [])
            record["task_id"] = candidates[0]["task_id"] if len(candidates) == 1 else None
            record["persona"] = path.parent.name.split("__", 1)[0]
            record["metrics"] = {}
        result_records.append(record)

    attempt_records: list[dict[str, Any]] = []
    error_paths = sorted(results_root.glob("*/*/error.txt")) if results_root.is_dir() else []
    for path in error_paths:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            read_error = None
        except OSError as exc:
            content = ""
            read_error = f"{type(exc).__name__}: {exc}"
        parent_prefix = path.parent.parent.name
        candidates = task_by_prefix.get(parent_prefix, [])
        task_id = candidates[0]["task_id"] if len(candidates) == 1 else None
        persona = path.parent.name.split("__", 1)[0]
        attempt_records.append(
            {
                "path": str(path.relative_to(root)),
                "task_id": task_id,
                "persona": persona,
                "read_error": read_error,
                "signals": scan_text(content, "error.txt"),
            }
        )

    log_records: list[dict[str, Any]] = []
    logs_root = root / "logs"
    for path in sorted(logs_root.glob("*.log")) if logs_root.is_dir() else []:
        inferred = infer_log_cell(path, personas, len(tasks))
        if inferred is None:
            continue
        persona, task_index = inferred
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            read_error = None
        except OSError as exc:
            content = ""
            read_error = f"{type(exc).__name__}: {exc}"
        log_records.append(
            {
                "path": str(path.relative_to(root)),
                "task_id": tasks[task_index - 1]["task_id"],
                "persona": persona,
                "read_error": read_error,
                "signals": scan_text(content, "run.log"),
            }
        )

    results_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    attempts_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    logs_by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in result_records:
        key = (record.get("task_id"), record.get("persona"))
        if key[0] in task_by_id and key[1] in personas:
            results_by_cell[key].append(record)
        else:
            unknown_artifacts.append({"kind": "result", "path": record["path"], "cell": list(key)})
    for record in attempt_records:
        key = (record.get("task_id"), record.get("persona"))
        if key[0] in task_by_id and key[1] in personas:
            attempts_by_cell[key].append(record)
        else:
            unknown_artifacts.append({"kind": "error", "path": record["path"], "cell": list(key)})
    for record in log_records:
        logs_by_cell[(record["task_id"], record["persona"])].append(record)

    cells: list[dict[str, Any]] = []
    for task_index, task in enumerate(tasks, 1):
        task_id = task["task_id"]
        for persona in personas:
            key = (task_id, persona)
            result_list = sorted(results_by_cell.get(key, []), key=lambda item: item["path"])
            attempt_list = sorted(attempts_by_cell.get(key, []), key=lambda item: item["path"])
            log_list = sorted(logs_by_cell.get(key, []), key=lambda item: item["path"])
            valid_numeric = [
                item
                for item in result_list
                if isinstance(item.get("data"), Mapping)
                and is_number((item.get("metrics") or {}).get("score"))
            ]
            chosen = valid_numeric[-1] if valid_numeric else (result_list[-1] if result_list else None)
            chosen_data = chosen.get("data") if chosen and isinstance(chosen.get("data"), Mapping) else None
            result_signals = chosen.get("signals", []) if chosen else []
            attempt_signals = [signal for item in attempt_list + log_list for signal in item.get("signals", [])]
            schema_issues = chosen.get("schema_issues", []) if chosen else []
            classification, rationale = classify_cell(
                result_count=len(result_list),
                valid_numeric_count=len(valid_numeric),
                chosen=chosen_data,
                schema_issues=schema_issues,
                result_signal_types=signal_types(result_signals),
                attempt_count=len(attempt_list),
                attempt_signal_types=signal_types(attempt_signals),
                log_count=len(log_list),
                manifest_status=manifest_status,
                configured_no_cap=configured_no_cap,
            )
            cells.append(
                {
                    "task_index": task_index,
                    "task_id": task_id,
                    "task_id_short": task_id[:12],
                    "task_label": task_label(task, task_index),
                    "level": task.get("level"),
                    "persona": persona,
                    "result_count": len(result_list),
                    "numeric_result_count": len(valid_numeric),
                    "result_paths": [item["path"] for item in result_list],
                    "attempt_error_count": len(attempt_list),
                    "attempt_error_paths": [item["path"] for item in attempt_list],
                    "log_count": len(log_list),
                    "log_paths": [item["path"] for item in log_list],
                    "metrics": chosen.get("metrics", {}) if chosen else {},
                    "schema_issues": schema_issues,
                    "result_signals": result_signals,
                    "attempt_signals": attempt_signals,
                    "classification": classification,
                    "classification_rationale": rationale,
                }
            )

    classification_counts = Counter(cell["classification"] for cell in cells)
    complete_cells = sum(cell["numeric_result_count"] == 1 and cell["result_count"] == 1 for cell in cells)
    missing_cells = sum(cell["numeric_result_count"] == 0 for cell in cells)
    duplicate_cells = sum(cell["result_count"] > 1 for cell in cells)
    schema_issue_cells = sum(bool(cell["schema_issues"]) for cell in cells)

    completed = [cell for cell in cells if cell["numeric_result_count"] >= 1]
    scores = [float(cell["metrics"]["score"]) for cell in completed if is_number(cell["metrics"].get("score"))]
    met = sum(int(cell["metrics"].get("met", 0)) for cell in completed if isinstance(cell["metrics"].get("met"), int))
    total = sum(int(cell["metrics"].get("total", 0)) for cell in completed if isinstance(cell["metrics"].get("total"), int))
    communicated = sum(
        int(cell["metrics"].get("communicated", 0))
        for cell in completed
        if isinstance(cell["metrics"].get("communicated"), int)
    )
    communicated_met = 0
    for cell in completed:
        communicated_ids = set(cell["metrics"].get("communicated_rubrics", []))
        unmet_ids = set(cell["metrics"].get("unmet_communicated_rubrics", []))
        communicated_met += len(communicated_ids - unmet_ids)

    stop_reasons = Counter(str(cell["metrics"].get("stop_reason")) for cell in completed)
    score_distribution = Counter(f"{float(score):.6g}" for score in scores)
    result_signal_cell_counts = Counter()
    attempt_signal_cell_counts = Counter()
    for cell in cells:
        for kind in signal_types(cell["result_signals"]):
            result_signal_cell_counts[kind] += 1
        for kind in signal_types(cell["attempt_signals"]):
            attempt_signal_cell_counts[kind] += 1

    persona_scores: dict[str, dict[str, Any]] = {}
    for persona in personas:
        values = [
            float(cell["metrics"]["score"])
            for cell in completed
            if cell["persona"] == persona and is_number(cell["metrics"].get("score"))
        ]
        persona_scores[persona] = {
            "completed": len(values),
            "mean_score": sum(values) / len(values) if values else None,
        }

    task_scores: dict[str, dict[str, Any]] = {}
    for task_id in task_ids:
        values = [
            float(cell["metrics"]["score"])
            for cell in completed
            if cell["task_id"] == task_id and is_number(cell["metrics"].get("score"))
        ]
        task_scores[task_id[:12]] = {
            "task_index": task_index_by_id[task_id],
            "completed": len(values),
            "mean_score": sum(values) / len(values) if values else None,
        }

    return {
        "audit_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "read_only": True,
        "experiment_root": str(root),
        "experiment_id": runtime.get("experiment_id") or manifest.get("experiment_id") or root.name,
        "manifest_status": manifest_status,
        "runtime_source": str(runtime_path.relative_to(root)) if runtime_path else None,
        "persona_source": persona_source,
        "configured_no_cap": configured_no_cap,
        "decision_rule": {
            "environment_exclusion_candidate": (
                "A completed cell has scanned blocking evidence and at least one unmet persona-communicated rubric. "
                "Manual review must still prove that the blocker affected required/communicated evidence and was not recovered."
            ),
            "genuine_task_or_agent_outcome": (
                "A completed low/partial score has no scanned environment blocker. Persona omissions, bad navigation, "
                "early stopping, or unperformed actions remain experimental outcomes."
            ),
            "no_result": (
                "A 429 or other operational error without a numeric result is unscored and should be rerun; it is not a task failure."
            ),
            "tab_limit": (
                "Tab-limit evidence is structural/configuration censoring, not a transient web failure. Under a recorded no-cap run it is an anomaly."
            ),
            "caution": (
                "Signal matching is triage, not final causal adjudication. A recovered/transient or incidental block is KEEP."
            ),
        },
        "grid": {
            "tasks": len(tasks),
            "personas": len(personas),
            "expected_cells": len(tasks) * len(personas),
            "complete_unique_numeric_cells": complete_cells,
            "cells_without_numeric_result": missing_cells,
            "duplicate_result_cells": duplicate_cells,
            "schema_issue_cells": schema_issue_cells,
            "unknown_artifacts": len(unknown_artifacts),
            "historical_error_attempts": len(attempt_records),
            "mapped_cell_logs": len(log_records),
        },
        "personas": personas,
        "tasks": [
            {
                "task_index": index,
                "task_id": task["task_id"],
                "task_id_short": task["task_id"][:12],
                "level": task.get("level"),
                "label": task_label(task, index),
                "rubric_count": len(task.get("rubrics", {})) if isinstance(task.get("rubrics"), Mapping) else None,
            }
            for index, task in enumerate(tasks, 1)
        ],
        "classification_counts": dict(sorted(classification_counts.items())),
        "score_summary": {
            "numeric_results": len(scores),
            "mean_cell_score": sum(scores) / len(scores) if scores else None,
            "rubric_met": met,
            "rubric_total": total,
            "rubric_micro_score": met / total if total else None,
            "communicated_met": communicated_met,
            "communicated_total": communicated,
            "communicated_micro_score": communicated_met / communicated if communicated else None,
            "score_distribution": dict(sorted(score_distribution.items())),
            "stop_reasons": dict(sorted(stop_reasons.items())),
            "experience_judged_results": sum(bool(cell["metrics"].get("experience_present")) for cell in completed),
            "by_persona": persona_scores,
            "by_task": task_scores,
        },
        "signal_cell_counts": {
            "completed_result": dict(sorted(result_signal_cell_counts.items())),
            "attempt_or_log": dict(sorted(attempt_signal_cell_counts.items())),
        },
        "top_level_issues": top_issues,
        "unknown_artifacts": unknown_artifacts,
        "cells": cells,
    }


def md_escape(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def format_score(value: Any) -> str:
    return f"{float(value):.3f}" if is_number(value) else "—"


def render_markdown(report: Mapping[str, Any], max_evidence: int) -> str:
    grid = report["grid"]
    score = report["score_summary"]
    lines = [
        f"# Result audit — {report['experiment_id']}",
        "",
        f"Read-only snapshot: `{report['generated_at_utc']}`",
        f"Root: `{report['experiment_root']}`",
        f"Manifest status: `{report['manifest_status']}`; no-cap recorded: `{report['configured_no_cap']}`.",
        "",
        "## Grid integrity",
        "",
        f"- Expected cells: **{grid['expected_cells']}** ({grid['tasks']} tasks × {grid['personas']} arms).",
        f"- Unique numeric cells: **{grid['complete_unique_numeric_cells']}**; without numeric result: **{grid['cells_without_numeric_result']}**.",
        f"- Duplicate-result cells: **{grid['duplicate_result_cells']}**; schema-issue cells: **{grid['schema_issue_cells']}**; unknown artifacts: **{grid['unknown_artifacts']}**.",
        f"- Historical `error.txt` attempts: **{grid['historical_error_attempts']}**; mapped per-cell logs: **{grid['mapped_cell_logs']}**.",
        "",
        "## Decision rule",
        "",
        "- `ENVIRONMENT_EXCLUSION_CANDIDATE` is triage only: a reviewer must show that 403/429/CAPTCHA/DNS/timeout/login evidence materially blocked required or persona-communicated evidence and that the run did not recover.",
        "- A low score with no scanned blocker is `KEEP_GENUINE_TASK_OR_AGENT_OUTCOME`; wrong navigation, omission, early stopping, or failure to act are not environment exclusions.",
        "- A 429/operational error with no numeric result is unscored and rerunnable, not a task failure.",
        "- A tab-limit hit is structural/configuration censoring; when no-cap is recorded it is a configuration anomaly, not a web rerun case.",
        "",
        "## Classification summary",
        "",
        "| Classification | Cells |",
        "|---|---:|",
    ]
    for classification, count in report["classification_counts"].items():
        lines.append(f"| `{md_escape(classification)}` | {count} |")

    lines.extend(
        [
            "",
            "## Score and stop summary",
            "",
            f"- Numeric results: **{score['numeric_results']}**; mean cell score: **{format_score(score['mean_cell_score'])}**.",
            f"- Rubric micro: **{score['rubric_met']}/{score['rubric_total']}** ({format_score(score['rubric_micro_score'])}).",
            f"- Communicated-rubric micro: **{score['communicated_met']}/{score['communicated_total']}** ({format_score(score['communicated_micro_score'])}).",
            f"- Experience-judged result files: **{score['experience_judged_results']}**.",
            f"- Score distribution: `{json.dumps(score['score_distribution'], sort_keys=True)}`.",
            f"- Stop reasons: `{json.dumps(score['stop_reasons'], sort_keys=True)}`.",
            "",
            "Signal counts below are numbers of cells, not raw match counts.",
            "",
            f"- Completed-result signals: `{json.dumps(report['signal_cell_counts']['completed_result'], sort_keys=True)}`.",
            f"- Attempt/log signals: `{json.dumps(report['signal_cell_counts']['attempt_or_log'], sort_keys=True)}`.",
            "",
            "## Cell ledger",
            "",
            "| Task | Persona | Results | Errors | Score | Rubrics | Comm. unmet | Stop | Signals | Classification |",
            "|---|---|---:|---:|---:|---:|---|---|---|---|",
        ]
    )
    for cell in report["cells"]:
        metrics = cell["metrics"]
        rubric = (
            f"{metrics.get('met')}/{metrics.get('total')}"
            if metrics.get("met") is not None and metrics.get("total") is not None
            else "—"
        )
        signals = ", ".join(sorted(signal_types(cell["result_signals"]))) or "—"
        unmet = ", ".join(metrics.get("unmet_communicated_rubrics", [])) or "—"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"T{cell['task_index']} `{cell['task_id_short']}`",
                    f"`{md_escape(cell['persona'])}`",
                    str(cell["result_count"]),
                    str(cell["attempt_error_count"]),
                    format_score(metrics.get("score")),
                    md_escape(rubric),
                    md_escape(unmet),
                    f"`{md_escape(metrics.get('stop_reason'))}`" if metrics.get("stop_reason") else "—",
                    md_escape(signals),
                    f"`{md_escape(cell['classification'])}`",
                ]
            )
            + " |"
        )

    issue_cells = [cell for cell in report["cells"] if cell["schema_issues"]]
    if report["top_level_issues"] or report["unknown_artifacts"] or issue_cells:
        lines.extend(["", "## Integrity issues", ""])
        for issue in report["top_level_issues"]:
            lines.append(f"- {md_escape(issue)}")
        for artifact in report["unknown_artifacts"]:
            lines.append(f"- Unknown {artifact['kind']} artifact: `{md_escape(artifact['path'])}` → `{artifact['cell']}`")
        for cell in issue_cells:
            for issue in cell["schema_issues"]:
                lines.append(f"- T{cell['task_index']} / `{cell['persona']}`: {md_escape(issue)}")

    evidence_cells = [
        cell
        for cell in report["cells"]
        if cell["result_signals"] or cell["attempt_signals"]
    ]
    if evidence_cells:
        lines.extend(["", "## Signal evidence", ""])
        for cell in evidence_cells:
            lines.append(
                f"### T{cell['task_index']} `{cell['task_id_short']}` / `{cell['persona']}` — `{cell['classification']}`"
            )
            lines.append("")
            evidence = list(cell["result_signals"]) + list(cell["attempt_signals"])
            for item in evidence[:max_evidence]:
                lines.append(
                    f"- `{item['type']}` at `{md_escape(item['source'])}`: {md_escape(item['excerpt'])}"
                )
            if len(evidence) > max_evidence:
                lines.append(f"- … {len(evidence) - max_evidence} additional matches omitted; use JSON output for all evidence.")

    lines.extend(
        [
            "",
            "## Interpretation limit",
            "",
            "This helper is intentionally conservative. Text matching cannot prove that a blocker caused a rubric miss. Final `KEEP` versus `EXCLUDE_RERUN` adjudication still requires reading the persona opening, relevant trajectory steps, final tabs/answer, and rubric verdicts. Raw result files are never modified.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment_root", type=Path, help="Experiment root containing inputs/tasks.json and results/")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--max-evidence", type=int, default=6, help="Maximum evidence bullets per cell in Markdown")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Exit 2 unless every expected cell has exactly one numeric result",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Exit 3 if a completed cell has duplicate/schema/environment/configuration review status",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.max_evidence < 0:
        print("error: --max-evidence must be non-negative", file=sys.stderr)
        return 2
    try:
        report = audit(args.experiment_root)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(render_markdown(report, args.max_evidence))

    if args.require_complete:
        grid = report["grid"]
        if grid["complete_unique_numeric_cells"] != grid["expected_cells"]:
            return 2
    if args.fail_on_review:
        review_statuses = {
            "DUPLICATE_RESULT_REVIEW",
            "MALFORMED_RESULT_REVIEW",
            "RESULT_SCHEMA_REVIEW",
            "ENVIRONMENT_EXCLUSION_CANDIDATE",
            "CONFIGURATION_ANOMALY_REVIEW",
            "STRUCTURAL_PROTOCOL_CENSORING_REVIEW",
        }
        if any(cell["classification"] in review_statuses for cell in report["cells"]):
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
