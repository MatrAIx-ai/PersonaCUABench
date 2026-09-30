#!/usr/bin/env python3
"""Render the manually reviewed Food r1 environment-validity snapshot.

The timestamp matrix freezes the exact selected numeric result for every cell.
After any numeric rerun, review that new trajectory, update its timestamp and
decision below, then rerun this script. A changed selected path fails closed.
This script never changes result.json, error.txt, trajectories, or profiles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from food_main_setting1_analysis import discover_attempts, load_replicate, select_latest_scored
from food_result_audit import audit as triage_audit


PERSONAS = (
    "none",
    "food-budget-novice",
    "food-busy-host",
    "food-cautious-dietary-planner",
    "food-culinary-researcher",
)
MODEL = "gpt-5.6-terra"

# Task order follows inputs/tasks.json; persona order follows PERSONAS above.
# These are the manually reviewed initial r1 numeric attempts, not error-only
# attempts or the separately archived cap-8 pilot.
EXPECTED_TIMESTAMPS = (
    ("20260928T213351Z", "20260928T215230Z", "20260928T221632Z", "20260928T223839Z", "20260930T001448Z"),
    ("20260928T213759Z", "20260928T215600Z", "20260928T222253Z", "20260928T224615Z", "20260930T001857Z"),
    ("20260928T213944Z", "20260928T215739Z", "20260928T222426Z", "20260928T224952Z", "20260930T002222Z"),
    ("20260928T214437Z", "20260928T220250Z", "20260928T222734Z", "20260928T225616Z", "20260929T032844Z"),
    ("20260928T214620Z", "20260928T220857Z", "20260928T222943Z", "20260928T230346Z", "20260929T165225Z"),
    ("20260928T214751Z", "20260928T221359Z", "20260928T223341Z", "20260930T001048Z", "20260930T002457Z"),
)


def keep(evidence: str, basis: str) -> dict[str, object]:
    return {
        "status": "KEEP",
        "impacted_rubrics": [],
        "blocking_causes": [],
        "evidence": evidence,
        "decision_basis": basis,
    }


def rerun(rubrics: str, causes: list[str], evidence: str, basis: str) -> dict[str, object]:
    return {
        "status": "EXCLUDE_RERUN",
        "impacted_rubrics": rubrics.split(),
        "blocking_causes": causes,
        "evidence": evidence,
        "decision_basis": basis,
    }


# Every cell with a browser-environment signal is manually adjudicated here.
# This also covers Google's `sorry` pages, which the generic regex triage does
# not currently flag. Cells without such evidence are retained below.
REVIEWED_SIGNAL_DECISIONS: dict[tuple[int, str], dict[str, object]] = {
    (1, "food-busy-host"): keep(
        "Le Creuset and Brussels-sprouts URLs initially timed out, but usable evidence was recovered and all four rubrics passed.",
        "Transient navigation failures did not censor any rubric.",
    ),
    (1, "food-culinary-researcher"): keep(
        "Two Google queries reached an unusual-traffic page, but the recipe, Le Creuset product, and YouTube evidence were recovered and all four rubrics passed.",
        "The search challenge did not censor any scored evidence.",
    ),
    (2, "food-budget-novice"): keep(
        "A Feel Good Foodie page-text read crashed, but communicated R1/R4 passed; the hidden R2 miss was a turkey-chili title mismatch.",
        "The crash did not cause the unmet rubric.",
    ),
    (2, "food-culinary-researcher"): keep(
        "Google queries reached unusual-traffic pages, but the lentil recipe and Ambitious Kitchen chili page were opened; R1 and the other non-title rubrics passed.",
        "R2 failed because the reported chili title omitted its final words, not because the page was inaccessible.",
    ),
    (3, "food-budget-novice"): keep(
        "One bar-service vendor timed out; the hidden R1 miss arose because The Knot listings were never visited.",
        "An unrelated vendor timeout did not force the omitted The Knot step.",
    ),
    (3, "food-cautious-dietary-planner"): keep(
        "Two vendor sites timed out; the hidden R1 miss arose because The Knot listings were never visited.",
        "The vendor timeouts did not prevent the omitted source-specific action.",
    ),
    (3, "food-culinary-researcher"): rerun(
        "R3",
        ["Google unusual-traffic/sorry page for mulligatawny search"],
        "The Google soup query ended on a verification page. The agent reached a valid recipe through DuckDuckGo, but never recovered the explicitly required Google-to-recipe route.",
        "Canonical R3 requires the soup recipe be found via Google, and the judge failed R3 for the missing Google route. Separate R1/R2 misses arose from shortlist and Surdyk's handling.",
    ),
    (4, "food-budget-novice"): keep(
        "Sally's and IGN timeouts recovered. The selected frame video was unavailable, and an Apple link landed on a generic iPad guide.",
        "Unmet communicated R4/R6 followed source selection and early stopping while other search/help routes remained usable.",
    ),
    (4, "food-busy-host"): keep(
        "The help.easel.com DNS failure recovered through an accessible Inventables Easel page.",
        "Communicated R7 failed because the chocolate comparison recipe was not identified or left open, unrelated to Easel.",
    ),
    (4, "food-cautious-dietary-planner"): keep(
        "The D23 Dole Whip URL timed out then resolved as a 404; Google still exposed a usable Dole Whip result route.",
        "Communicated R2 failed after the agent stopped without opening another recipe page; this was a stale-source/navigation outcome.",
    ),
    (4, "food-culinary-researcher"): rerun(
        "R4",
        ["Google block page", "DuckDuckGo human-verification challenge", "repeated Inventables/X-Carve timeouts"],
        "Targeted custom-frame searches were blocked, and only a generic Inventables signs page remained open.",
        "A frame-specific X-Carve source required for communicated R4 was not recovered.",
    ),
    (5, "none"): rerun(
        "R2",
        ["OpenTable Mamma Maria Access Denied"],
        "The only OpenTable tab was an Access Denied page; official/Google pages did not provide a visually verifiable OpenTable listing.",
        "The canonical task and R2 explicitly required the OpenTable restaurant listing.",
    ),
    (5, "food-budget-novice"): rerun(
        "R3",
        ["OpenTable Mistral Access Denied", "OpenTable Mamma Maria Access Denied"],
        "Both booking listings were denied, and Google Maps/official routes did not expose next-two-day live slots.",
        "The persona requested two-day availability; the booking blocks materially censored R3.",
    ),
    (5, "food-busy-host"): keep(
        "Mistral's OpenTable page was denied, but Google Reserve exposed concrete September 28 slots for R3.",
        "R1 lacked an independent fine-dining source; R4 failed when the agent did not change the booking date or try the usable SevenRooms route.",
    ),
    (5, "food-cautious-dietary-planner"): rerun(
        "R3",
        ["Mooo official page timeout", "Mooo OpenTable Access Denied"],
        "No usable Mooo reservation interface or September 28–29 availability evidence was recovered.",
        "The blocked business-dinner evidence caused communicated R3 to fail; the separate R4 miss is an agent issue.",
    ),
    (5, "food-culinary-researcher"): rerun(
        "R4",
        ["Mamma Maria menu DNS/timeout", "Google block page", "DuckDuckGo/Resy DNS failures"],
        "SevenRooms supplied occasion and availability evidence, but repeated current-menu/price attempts failed and no price range was recovered.",
        "The persona explicitly asked for expected price; the unrecovered source failures materially blocked R4.",
    ),
    (6, "none"): rerun(
        "R3",
        ["The Kitchn human-verification and Access Denied page"],
        "The spiral-ham article never opened; Google snippets could not verify the article-specific preparation, heating, and finish method.",
        "The required Kitchn source for communicated R3 was materially unavailable.",
    ),
    (6, "food-cautious-dietary-planner"): keep(
        "Google searches reached unusual-traffic pages, but DuckDuckGo/Bing and the Sainsbury's, M&S, and Boots sites opened usable search/category or recipe pages.",
        "The failed starter-name/gluten-free checks and unvisited individual gift pages reflect source selection and execution; the persona omitted The Kitchn source behind hidden R3.",
    ),
    (6, "food-culinary-researcher"): rerun(
        "R3",
        ["The Kitchn human-verification and Access Denied page"],
        "The spiral-ham article remained an access-denied page; the agent relied on search-result summaries instead of a visible Kitchn method.",
        "The required Kitchn evidence for communicated R3 was materially unavailable. R1/R4/R5/R6 also failed, but accessible Sainsbury's, M&S, and Boots search/category pages make those separate agent/navigation outcomes.",
    ),
}


def non_signal_keep(record: dict[str, object]) -> dict[str, object]:
    verdicts = record["judgement"]["verdicts"]
    misses = [key for key, verdict in verdicts.items() if not verdict["met"]]
    if misses:
        return keep(
            "No scanned page-level environment blocker in the selected trajectory; unmet rubrics: " + ", ".join(misses) + ".",
            "The recorded misses remain communication, navigation, source choice, or agent-execution outcomes.",
        )
    return keep(
        "All original-task rubrics passed and no page-level environment blocker was scanned.",
        "The selected numeric result is an environment-valid observation.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Food r1 experiment root")
    args = parser.parse_args()
    replicate = load_replicate(args.root)
    if replicate.experiment_id != "food-main-nocap-setting1-r1":
        raise ValueError(f"unexpected experiment_id: {replicate.experiment_id}")
    if len(replicate.tasks) != 6 or len(EXPECTED_TIMESTAMPS) != 6:
        raise ValueError("expected exactly six frozen Food tasks")
    if any(len(row) != len(PERSONAS) for row in EXPECTED_TIMESTAMPS):
        raise ValueError("timestamp matrix must have five arms per task")

    attempts = discover_attempts(replicate)
    selected = select_latest_scored(attempts)
    if len(selected) != 30:
        raise ValueError(f"expected 30 selected numeric cells, found {len(selected)}")
    triage = triage_audit(replicate.root)
    triage_by_cell = {(cell["task_id"], cell["persona"]): cell for cell in triage["cells"]}

    rows: list[dict[str, object]] = []
    for index, task in enumerate(replicate.tasks, 1):
        task_id = task["task_id"]
        for persona_index, persona in enumerate(PERSONAS):
            candidates = [a for a in selected if a.task_id == task_id and a.persona == persona]
            if len(candidates) != 1:
                raise ValueError(f"selected numeric mapping is not unique: task {index}, {persona}")
            attempt = candidates[0]
            if attempt.model != MODEL or attempt.record is None or attempt.result_path is None:
                raise ValueError(f"unexpected model or missing result: task {index}, {persona}")
            stamp = EXPECTED_TIMESTAMPS[index - 1][persona_index]
            expected = f"results/{task_id[:12]}/{persona}__{MODEL}__{stamp}/result.json"
            actual = attempt.result_path.relative_to(replicate.root).as_posix()
            if actual != expected:
                raise ValueError(
                    f"selected result changed for task {index}, {persona}: expected {expected}, found {actual}; "
                    "manually review the new trajectory and update EXPECTED_TIMESTAMPS and decision"
                )
            triage_cell = triage_by_cell[(task_id, persona)]
            if triage_cell["schema_issues"]:
                raise ValueError(f"result schema issue in {actual}: {triage_cell['schema_issues']}")
            signal = bool(triage_cell["result_signals"])
            override = REVIEWED_SIGNAL_DECISIONS.get((index, persona))
            if signal and override is None:
                raise ValueError(
                    f"signal/review mismatch for task {index}, {persona}: signal={signal}; "
                    "manually inspect and update REVIEWED_SIGNAL_DECISIONS"
                )
            decision = override or non_signal_keep(attempt.record)
            verdicts = attempt.record["judgement"]["verdicts"]
            communicated = [key for key, verdict in verdicts.items() if verdict["communicated"]]
            row = {
                "task_id": task_id[:12],
                "task_label": task["confirmed_task"][:65].rstrip() + "…",
                "persona": persona,
                "model": MODEL,
                "status": decision["status"],
                "selected_result_path": actual,
                "selected_result_sha256": hashlib.sha256(attempt.result_path.read_bytes()).hexdigest(),
                "score": attempt.score,
                "communicated_rubrics": communicated,
                "impacted_rubrics": decision["impacted_rubrics"],
                "blocking_causes": decision["blocking_causes"],
                "evidence": decision["evidence"],
                "decision_basis": decision["decision_basis"],
            }
            rows.append(row)

    counts = Counter(row["status"] for row in rows)
    if counts["EXCLUDE_RERUN"] < 8:
        raise ValueError("initial eight material exclusions unexpectedly disappeared")
    historical_error_count = sum(len(a.error_paths) for a in attempts if not a.selected)
    counts_by_persona: dict[str, dict[str, int]] = {}
    for persona in PERSONAS:
        subset = Counter(row["status"] for row in rows if row["persona"] == persona)
        counts_by_persona[persona] = {"KEEP": subset["KEEP"], "EXCLUDE_RERUN": subset["EXCLUDE_RERUN"]}
    counts_by_task: dict[str, dict[str, object]] = {}
    for index, task in enumerate(replicate.tasks, 1):
        subset = Counter(row["status"] for row in rows if row["task_id"] == task["task_id"][:12])
        counts_by_task[task["task_id"][:12]] = {
            "label": f"Food task {index}",
            "KEEP": subset["KEEP"],
            "EXCLUDE_RERUN": subset["EXCLUDE_RERUN"],
        }
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    report = {
        "audit_version": 1,
        "audited_at": now,
        "experiment_id": replicate.experiment_id,
        "results_root": (replicate.root / "results").as_posix(),
        "scope": {
            "planned_cells": 30,
            "numeric_scored_cells": 30,
            "manually_audited_cells": 30,
            "task_id_format_in_this_audit": "12-character result-directory prefix",
            "inputs_checked_per_cell": [
                "frozen task and rubrics",
                "persona conversation",
                "trajectory and environment-signal triage",
                "final answer and open tabs",
                "task-judge verdicts",
            ],
            "selection_policy": "latest numeric result per task/persona/model; exact selected paths and SHA-256 hashes frozen below",
        },
        "decision_rule": {
            "KEEP": "No material unrecovered environment obstruction to required or communicated evidence. Persona omission, source choice, navigation, and early stop remain genuine outcomes.",
            "EXCLUDE_RERUN": "A 403/Access Denied, challenge, DNS failure, persistent timeout/crash, or unusable required page materially prevented rubric evidence. Preserve raw result and retry under the same configuration.",
            "transient_recovery": "Recovered or incidental errors do not invalidate a cell.",
            "score_mutation": False,
        },
        "counts": {
            "KEEP": counts["KEEP"],
            "EXCLUDE_RERUN": counts["EXCLUDE_RERUN"],
            "historical_attempt_errors_outside_scored_cells": historical_error_count,
            "structurally_limited_cells": 0,
        },
        "counts_by_persona": counts_by_persona,
        "counts_by_task": counts_by_task,
        "cells": rows,
        "retained_subset_descriptive_only": {
            "cells": counts["KEEP"],
            "warning": "The KEEP subset is task/persona imbalanced until excluded cells are reattempted; do not present it as the final Food score.",
        },
        "structural_limit": {
            "setting": "ODYSSEY_MAX_TABS=0",
            "affected_cells": 0,
            "interpretation": "The formal Food r1 run had no artificial browser-tab cap; the separate cap-8 pilot is excluded.",
        },
        "manifest_recommendation": {
            "manifest_path": (replicate.root / "RUN_MANIFEST.json").as_posix(),
            "needs_correction": True,
            "recommended_completed_numeric_results": 30,
            "recommended_environment_valid_cells": counts["KEEP"],
            "recommended_environment_excluded_rerun_cells": counts["EXCLUDE_RERUN"],
            "recommended_historical_attempt_errors": historical_error_count,
            "recommended_status": "initial_numeric_grid_complete; environment_excluded_cells_pending_same_config_rerun",
            "note": "This snapshot does not modify the manifest or declare the valid experiment complete.",
        },
        "refresh_policy": "After any numeric rerun, manually inspect the new selected result, update this generator's frozen timestamp and decision, regenerate both audit files, and rerun posthoc validation. Old paths/statuses must never be reused silently.",
    }

    lines = [
        "# Food r1 environment-validity audit — initial selected attempts",
        "",
        f"Audit time: {now}. Initial numeric grid: **30/30**. The {counts['EXCLUDE_RERUN']} material exclusions are pending same-configuration reruns; this is not the final environment-valid Food result.",
        "",
        f"**KEEP {counts['KEEP']} / EXCLUDE_RERUN {counts['EXCLUDE_RERUN']}**. {historical_error_count} error-only attempts are operational history outside the 30 selected scored cells. The cap-8 pilot is outside this root.",
        "",
        "The rule is materiality: an unrecovered browser/site block must prevent required or communicated evidence. Recovered errors, persona omissions, poor navigation, and early stopping remain KEEP.",
        "",
        "| Task | KEEP | EXCLUDE_RERUN |",
        "|---|---:|---:|",
    ]
    for index, task in enumerate(replicate.tasks, 1):
        tally = counts_by_task[task["task_id"][:12]]
        lines.append(f"| {index} (`{task['task_id'][:12]}`) | {tally['KEEP']} | {tally['EXCLUDE_RERUN']} |")
    lines.extend(["", "## Cell decisions", ""])
    for index, task in enumerate(replicate.tasks, 1):
        lines.extend([f"### Task {index} — `{task['task_id'][:12]}`", ""])
        for row in (item for item in rows if item["task_id"] == task["task_id"][:12]):
            impacted = f" ({', '.join(row['impacted_rubrics'])})" if row["impacted_rubrics"] else ""
            lines.append(
                f"- `{row['persona']}` — **{row['status']}**{impacted}. {row['evidence']} {row['decision_basis']} "
                f"Selected: `{row['selected_result_path']}`."
            )
        lines.append("")
    lines.extend([
        "## Refresh rule",
        "",
        "This is a snapshot of the exact selected initial attempts. Each JSON row includes its selected result path and SHA-256. After any numeric reattempt, inspect the new trajectory, update `EXPECTED_TIMESTAMPS` and the manual decision in `artifacts/experiments/food_r1_validity_audit.py`, regenerate this JSON/Markdown pair, and rerun the Food posthoc loader. The generator rejects a changed selected path until it has been reviewed. Error-only attempts are never scored. The pilot is never merged here.",
        "",
    ])
    analysis_dir = replicate.root / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    json_path = analysis_dir / "ENVIRONMENT_VALIDITY_AUDIT.json"
    md_path = analysis_dir / "ENVIRONMENT_VALIDITY_AUDIT.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {json_path} and {md_path}: KEEP={counts['KEEP']} EXCLUDE_RERUN={counts['EXCLUDE_RERUN']}")


if __name__ == "__main__":
    main()
