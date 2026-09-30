#!/usr/bin/env python3
"""Render the Food Setting 1 formal-results HTML from dated replicate roots.

The page deliberately separates four populations:

* environment-KEEP matched persona/control pairs (primary comparison);
* balanced raw persona/control pairs (secondary diagnostic);
* all selected numeric scored cells (raw, including environment exclusions);
* the descriptive KEEP-only sensitivity subset.

Run without arguments to discover r1/r2/r3 under dated experiment folders::

    python3 artifacts/experiments/food_main_setting1_html.py

The cap-8 pilot is never discovered. The renderer tolerates replicates that are
still running, missing audits, or missing experience scores; such a page is
labelled preliminary rather than formal-complete.
"""

from __future__ import annotations

import argparse
import html
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import food_main_setting1_analysis as analysis


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "FOOD_MAIN_SETTING1_FORMAL_RESULTS.html"
EXPECTED_REPLICATES = 3
EXPECTED_CELLS = 90
ARMS = (
    ("none", "Control · 原始任务", "Control"),
    ("food-budget-novice", "P1 · 预算敏感的烹饪新手", "P1"),
    ("food-cautious-dietary-planner", "P2 · 谨慎的饮食规划者", "P2"),
    ("food-busy-host", "P3 · 时间紧张的家庭餐饮规划者", "P3"),
    ("food-culinary-researcher", "P4 · 专业餐饮研究者", "P4"),
)
TASK_LABELS = (
    "抱子甘蓝、Le Creuset 与洗碗机气隙",
    "扁豆、火鸡辣椒和提前准备的甜点",
    "明尼阿波利斯酒吧餐饮与 mulligatawny",
    "BOTW 甜点与展示设备",
    "波士顿商务和纪念日晚餐",
    "英国圣诞菜单与礼品",
)
DIMENSIONS = (
    ("P1_asked_for", "要求符合度"),
    ("P2_readable_for_them", "Persona 可读性"),
    ("P3_actionable", "可执行性"),
    ("P4_gap_handling", "缺口处理与主动性"),
    ("P5_overall", "整体体验"),
)


def e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def pct(value: Any, digits: int = 1) -> str:
    return "—" if value is None else f"{float(value) * 100:.{digits}f}%"


def delta(value: Any) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:+.1f} pp".replace("-", "−")


def score(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{float(value):.{digits}f}"


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, min_width: int = 760) -> str:
    head = "".join(f'<th scope="col">{e(value)}</th>' for value in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>" for row in rows
    )
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">暂无可展示数据</td></tr>'
    return (
        f'<div class="table-wrap"><table style="min-width:{min_width}px">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def discover_roots() -> list[Path]:
    return sorted(
        path
        for path in HERE.glob("20??-??-??/food-main-nocap-setting1-r[123]")
        if (path / "results").is_dir()
    )


def selected_attempts(replicates: Sequence[analysis.Replicate]) -> list[analysis.Attempt]:
    attempts: list[analysis.Attempt] = []
    for replicate in replicates:
        attempts.extend(analysis.discover_attempts(replicate))
    return analysis.select_latest_scored(attempts)


def has_two_experience_judges(attempt: analysis.Attempt) -> bool:
    experience = (attempt.record or {}).get("experience")
    return (
        isinstance(experience, dict)
        and isinstance(experience.get("a"), dict)
        and isinstance(experience.get("b"), dict)
    )


def status_label(
    summary: dict[str, Any], replicates: Sequence[analysis.Replicate]
) -> tuple[str, bool, int]:
    selected = summary["counts"]["selected_numeric_scored_cells"]
    planned = summary["counts"].get("planned_cells")
    replicate_numbers = {row.get("replicate") for row in summary["inputs"]}
    validity = summary["environment_validity"]["counts"]
    attempts = selected_attempts(replicates)
    experience_judged = sum(has_two_experience_judges(item) for item in attempts)
    complete = (
        selected == EXPECTED_CELLS
        and planned == EXPECTED_CELLS
        and replicate_numbers == {1, 2, 3}
        and validity["audited_selected_numeric_scored_cells"] == EXPECTED_CELLS
        and validity["environment_unclassified_selected_numeric_cells"] == 0
        and validity.get("replicates_with_audit") == EXPECTED_REPLICATES
        and experience_judged == EXPECTED_CELLS
        and summary["input_integrity"]["status"] == "pass"
    )
    if complete:
        return "Formal results · 三次重复、环境审计与体验评分已完成", True, experience_judged
    return "Preliminary / incomplete · 正式实验仍在运行或审计中", False, experience_judged


def task_maps(summary: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    long_names: dict[str, str] = {}
    short_names: dict[str, str] = {}
    for index, task in enumerate(summary["task_catalog"]):
        task_id = str(task["task_id"])
        label = str(task.get("label") or f"T{index + 1}")
        long_label = TASK_LABELS[index] if index < len(TASK_LABELS) else task.get("prompt_preview", "")
        long_names[task_id] = f"{label} · {long_label}"
        short_names[task_id] = label
    return long_names, short_names


def missing_text(task_ids: Sequence[str], short_names: dict[str, str]) -> str:
    if not task_ids:
        return "无"
    return "、".join(e(short_names.get(str(task_id), str(task_id)[:8])) for task_id in task_ids)


def paired_rows(
    summary: dict[str, Any], *, keep_only: bool, short_names: dict[str, str]
) -> list[list[str]]:
    if keep_only:
        keep = summary["environment_validity"].get("keep_only")
        paired = keep.get("paired_persona_minus_none") if isinstance(keep, dict) else None
        aggregate = paired.get("aggregate_by_persona", []) if isinstance(paired, dict) else []
        by_persona = {row["persona"]: row for row in aggregate}
    else:
        paired = summary["paired_persona_minus_none"]
        aggregate = paired.get("aggregate_by_persona_and_model", [])
        pair_items: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in paired.get("pairs", []):
            pair_items[str(item.get("persona"))].append(item)
        by_persona = {}
        catalog_ids = [str(row["task_id"]) for row in summary["task_catalog"]]
        for row in aggregate:
            persona = str(row["persona"])
            items = pair_items.get(persona, [])
            represented = sorted({str(item["task_id"]) for item in items})
            represented_set = set(represented)
            by_persona[persona] = {
                **row,
                "eligible_pair_n": row.get("paired_cells", 0),
                "tasks_represented": len(represented),
                "missing_task_ids": [task_id for task_id in catalog_ids if task_id not in represented_set],
            }

    rows: list[list[str]] = []
    for persona, label, _ in ARMS[1:]:
        row = by_persona.get(persona)
        if not row:
            rows.append([e(label), "0", "0 / 6", "—", "—", "—", "—", "T1–T6"])
            continue
        rows.append(
            [
                e(label),
                str(row.get("eligible_pair_n", row.get("paired_cells", 0))),
                f'{row.get("tasks_represented", 0)} / 6',
                delta(row.get("completion_delta_mean")),
                f'{row.get("completion_wins", 0)} / {row.get("completion_ties", 0)} / {row.get("completion_losses", 0)}',
                delta(row.get("communication_coverage_delta_mean")),
                delta(row.get("communicated_only_completion_delta_mean")),
                missing_text(row.get("missing_task_ids", []), short_names),
            ]
        )
    return rows


def replicate_rows(
    summary: dict[str, Any], replicates: Sequence[analysis.Replicate]
) -> list[list[str]]:
    audits = {
        str(row["experiment_id"]): row for row in summary["environment_validity"].get("audits", [])
    }
    selected = selected_attempts(replicates)
    judged_by_root: dict[str, int] = defaultdict(int)
    for item in selected:
        if has_two_experience_judges(item):
            judged_by_root[item.replicate.root_key] += 1
    replicates_by_root = {item.root.as_posix(): item for item in replicates}
    rows: list[list[str]] = []
    present: set[int] = set()
    for item in sorted(summary["inputs"], key=lambda row: int(row.get("replicate") or 999)):
        replicate_number = int(item.get("replicate") or 0)
        present.add(replicate_number)
        replicate = replicates_by_root.get(str(item["root"]))
        audit = audits.get(str(item["experiment_id"]))
        selected_count = int(item["selected_numeric_scored_cells"])
        audited = int(audit["matched_selected_numeric_cells"]) if audit else 0
        keep = int(audit["environment_keep_cells"]) if audit else 0
        excluded = int(audit["environment_exclude_rerun_cells"]) if audit else 0
        unclassified = selected_count - audited
        manifest = replicate.manifest if replicate else {}
        rows.append(
            [
                f"r{replicate_number or '?'}",
                e(item.get("date_block") or "未记录"),
                e(manifest.get("status") or "未记录"),
                str(item["discovered_attempts"]),
                f'{selected_count} / {item.get("planned_cells") or "?"}',
                str(item["execution_integrity_excluded_attempts"]),
                f"{audited} / {keep} / {excluded} / {unclassified}",
                f"{judged_by_root.get(replicate.root_key, 0) if replicate else 0} / {selected_count}",
            ]
        )
    for number in range(1, EXPECTED_REPLICATES + 1):
        if number not in present:
            rows.append([f"r{number}", "待运行", "未发现", "0", "0 / 30", "0", "0 / 0 / 0 / 0", "0 / 0"])
    return rows


def keep_arm_rows(summary: dict[str, Any]) -> list[list[str]]:
    keep = summary["environment_validity"].get("keep_only")
    completion_rows = keep["completion"]["per_arm"] if isinstance(keep, dict) else []
    communication_rows = keep["communication"]["per_arm"] if isinstance(keep, dict) else []
    completion = {row["persona"]: row for row in completion_rows}
    communication = {row["persona"]: row for row in communication_rows}
    rows: list[list[str]] = []
    for persona, label, _ in ARMS:
        comp = completion.get(persona)
        comm = communication.get(persona)
        if not comp:
            rows.append([e(label), "0", "—", "—", "—", "—"])
            continue
        coverage = comm["coverage"] if comm else {}
        communicated = comm["communicated_only_completion"] if comm else {}
        rows.append(
            [
                e(label),
                str(comp["cells"]),
                pct(comp["score_mean"]),
                f'{comp["rubric_met"]} / {comp["rubric_total"]} = {pct(comp["rubric_micro_completion"])}',
                f'{coverage.get("communicated_rubrics", 0)} / {coverage.get("all_rubrics", 0)} = {pct(coverage.get("micro_rate"))}',
                f'{communicated.get("met_communicated_rubrics", 0)} / {communicated.get("communicated_rubrics", 0)} = {pct(communicated.get("micro_rate"))}',
            ]
        )
    return rows


def keep_matrix_rows(summary: dict[str, Any]) -> list[list[str]]:
    keep = summary["environment_validity"].get("keep_only")
    matrix = keep.get("arm_task_keep_counts") if isinstance(keep, dict) else None
    by_persona = {row["persona"]: row for row in matrix.get("rows", [])} if matrix else {}
    rows: list[list[str]] = []
    for persona, label, _ in ARMS:
        row = by_persona.get(persona)
        counts = [str(item["cells"]) for item in row["by_task"]] if row else ["0"] * 6
        rows.append([e(label), *counts, str(row["cells"] if row else 0)])
    return rows


def task_summary_rows(
    summary: dict[str, Any], long_names: dict[str, str]
) -> list[list[str]]:
    raw = {row["task_id"]: row for row in summary["completion"].get("per_task", [])}
    keep = summary["environment_validity"].get("keep_only")
    kept = {
        row["task_id"]: row
        for row in (keep["completion"].get("per_task", []) if isinstance(keep, dict) else [])
    }
    rows: list[list[str]] = []
    for task in summary["task_catalog"]:
        task_id = str(task["task_id"])
        raw_row = raw.get(task_id)
        keep_row = kept.get(task_id)
        rows.append(
            [
                e(long_names[task_id]),
                str(raw_row["cells"] if raw_row else 0),
                pct(raw_row.get("score_mean") if raw_row else None),
                pct(raw_row.get("rubric_micro_completion") if raw_row else None),
                str(keep_row["cells"] if keep_row else 0),
                pct(keep_row.get("score_mean") if keep_row else None),
                pct(keep_row.get("rubric_micro_completion") if keep_row else None),
            ]
        )
    return rows


def judge_text(judge: dict[str, Any] | None) -> str:
    if not judge or not judge.get("n"):
        n_a = int(judge.get("n_a", 0)) if judge else 0
        return f"— (n=0, 无数值={n_a})"
    return (
        f'{float(judge["mean"]):.2f} / {float(judge["median"]):g} '
        f'(n={judge["n"]}, 无数值={judge.get("n_a", 0)})'
    )


def experience_rows(summary: dict[str, Any]) -> list[list[str]]:
    raw = {row["dimension"]: row for row in summary["experience"]["dimensions"]}
    keep = summary["environment_validity"].get("keep_only")
    kept = {
        row["dimension"]: row
        for row in (keep["experience"]["dimensions"] if isinstance(keep, dict) else [])
    }
    rows: list[list[str]] = []
    for dimension, label in DIMENSIONS:
        raw_row = raw.get(dimension, {})
        keep_row = kept.get(dimension, {})
        raw_agreement = raw_row.get("agreement", {})
        keep_agreement = keep_row.get("agreement", {})
        rows.append(
            [
                e(label),
                judge_text(raw_row.get("judge_a")),
                judge_text(raw_row.get("judge_b")),
                f'{raw_agreement.get("within_one", 0)} / {raw_agreement.get("paired", 0)}' if raw_agreement.get("paired") else "—",
                judge_text(keep_row.get("judge_a")),
                judge_text(keep_row.get("judge_b")),
                f'{keep_agreement.get("within_one", 0)} / {keep_agreement.get("paired", 0)}' if keep_agreement.get("paired") else "—",
            ]
        )
    return rows


def slice_experience(slice_row: dict[str, Any], dimension: str) -> str:
    row = next(
        (item for item in slice_row.get("experience_dimensions", []) if item["dimension"] == dimension),
        None,
    )
    if not row:
        return "— / —"
    return f'{score(row["judge_a"].get("mean"), 2)} / {score(row["judge_b"].get("mean"), 2)}'


def slice_arm_counts(slice_row: dict[str, Any]) -> str:
    names = {persona: short for persona, _, short in ARMS}
    counts = {row["persona"]: row["cells"] for row in slice_row.get("per_arm", [])}
    return " · ".join(f"{names[persona]} {counts.get(persona, 0)}" for persona, _, _ in ARMS)


def perfect_slice_rows(summary: dict[str, Any]) -> list[list[str]]:
    populations: list[tuple[str, dict[str, Any] | None]] = [("Raw", summary["perfect_slices"])]
    keep = summary["environment_validity"].get("keep_only")
    populations.append(("KEEP", keep.get("perfect_slices") if isinstance(keep, dict) else None))
    rows: list[list[str]] = []
    for population, slices in populations:
        for key, label in (("full_task_perfect", "原任务满分"), ("communicated_perfect", "已沟通要求满分")):
            if not slices:
                rows.append([population, label, "0 / 0", "—", *(["—"] * len(DIMENSIONS))])
                continue
            item = slices[key]
            rows.append(
                [
                    population,
                    label,
                    f'{item["cells"]} / {item["all_selected_numeric_scored_cells"]}',
                    e(slice_arm_counts(item)),
                    *[slice_experience(item, dimension) for dimension, _ in DIMENSIONS],
                ]
            )
    return rows


def render(summary: dict[str, Any], replicates: Sequence[analysis.Replicate]) -> str:
    counts = summary["counts"]
    selected = counts["selected_numeric_scored_cells"]
    raw = summary["completion"]
    raw_micro = raw["rubric_micro_completion"]
    validity = summary["environment_validity"]
    validity_counts = validity["counts"]
    keep = validity.get("keep_only")
    status, final, experience_judged = status_label(summary, replicates)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dates = sorted({str(row.get("date_block") or "未记录") for row in summary["inputs"]})
    actual_dates = "、".join(dates) if dates else "未记录"
    long_names, short_names = task_maps(summary)

    audited = validity_counts["audited_selected_numeric_scored_cells"]
    keep_count = validity_counts["environment_keep_cells"]
    excluded = validity_counts["environment_exclude_rerun_cells"]
    unclassified = validity_counts["environment_unclassified_selected_numeric_cells"]
    keep_completion = keep.get("completion") if isinstance(keep, dict) else None
    keep_micro = keep_completion.get("rubric_micro_completion") if keep_completion else None
    keep_paired = keep.get("paired_persona_minus_none") if isinstance(keep, dict) else None
    paired_keep_n = sum(
        int(row.get("eligible_pair_n", 0))
        for row in (keep_paired.get("aggregate_by_persona", []) if keep_paired else [])
    )
    integrity = summary["input_integrity"]
    integrity_note = (
        "任务与运行配置快照一致。"
        if integrity["status"] == "pass"
        else f'输入快照核查为 {e(integrity["status"])}，需要检查分析输出中的 issues。'
    )
    profile = replicates[0].runtime_config if replicates else {}
    models = profile.get("models", {}) if isinstance(profile.get("models"), dict) else {}
    model = models.get("executor", "gpt-5.6-terra")
    simulator = models.get("persona_simulator", model)
    task_judge = models.get("task_judge", model)
    experience_judge_a = models.get("experience_judge_a", model)
    experience_judge_b = models.get("experience_judge_b", model)
    experience_judge = (
        experience_judge_a
        if experience_judge_a == experience_judge_b
        else f"A={experience_judge_a}；B={experience_judge_b}"
    )
    base_sha = profile.get("protocol_base_git_sha", "4a1c0f2")

    stats = [
        (f"{selected} / {EXPECTED_CELLS}", "Raw 数值结果 / 正式计划格"),
        (f"{keep_count} / {excluded} / {unclassified}", "KEEP / EXCLUDE_RERUN / 未分类"),
        (str(paired_keep_n), "主分析中的 KEEP 匹配 persona–control 对"),
        (pct(raw["cell_macro_completion"]), "Raw cell-macro 完成率（含环境排除格）"),
    ]
    stats_html = "".join(
        f'<div class="stat"><strong>{e(number)}</strong><span>{e(label)}</span></div>'
        for number, label in stats
    )

    validity_text = (
        f"已审计 {audited}/{selected} 个 raw 数值格：KEEP {keep_count}，EXCLUDE_RERUN {excluded}，未分类 {unclassified}。"
        if audited
        else f"尚无环境有效性审计；{selected} 个 raw 数值格均未分类。"
    )
    completion_detail = (
        f'Raw rubric micro 为 {raw_micro["met"]}/{raw_micro["total"]} = {pct(raw_micro["rate"])}。'
        + (f' KEEP-only rubric micro 为 {keep_micro["met"]}/{keep_micro["total"]} = {pct(keep_micro["rate"])}。' if keep_micro else " 暂无 KEEP-only 完成率。")
    )

    sections = f"""
    <header>
      <div class="eyebrow">Food &amp; Drink / Setting 1</div>
      <h1>Food Persona 正式实验结果</h1>
      <p class="subtitle">main-style / no-cap · live Chrome · 6 道题 × 4 个 Persona + Control × 3 次正式重复</p>
      <p class="status" role="status">{e(status)}</p>
      <p class="meta">日期块：{e(actual_dates)}（America/Los_Angeles）；页面生成：{e(generated)}；analysis schema {e(summary.get("schema_version", "unknown"))}。</p>
    </header>

    <section class="stats" aria-label="结果概览">{stats_html}</section>

    <aside class="callout warning">
      <strong>当前解读边界</strong>
      {e(validity_text)} 已完成双体验 Judge 的 raw 格为 {experience_judged}/{selected}。
      {"三次重复、审计和体验评分均已完成。" if final else "当前页面是自动更新的初步快照，不应作为最终 Persona 排名。"}
      EXCLUDE_RERUN 表示网页环境没有产生可用于主分析的有效结果，并不等于模型执行失败或 0 分。
    </aside>

    <section>
      <h2>结果</h2>
      <p>{completion_detail} 主结论只看下面同一 replicate、同一 task、同一执行模型中 persona 与 Control 双方都被审计为 KEEP 的匹配对。</p>

      <h3>主表：environment-KEEP 匹配的 Persona − Control</h3>
      {table(["Persona", "匹配对 n", "覆盖任务", "完成率 Δ", "胜 / 平 / 负", "沟通覆盖率 Δ", "仅已沟通完成率 Δ", "缺失任务"], paired_rows(summary, keep_only=True, short_names=short_names), min_width=1180)}
      <p class="caption">Δ = Persona − Control；每一对要求双方在同一重复、同一任务和同一执行模型上均为 KEEP。n 与覆盖任务数必须和效应值一起阅读；缺失任务不会被隐式补零。</p>

      <h3>次级表：balanced raw 匹配对</h3>
      {table(["Persona", "匹配对 n", "覆盖任务", "完成率 Δ", "胜 / 平 / 负", "沟通覆盖率 Δ", "仅已沟通完成率 Δ", "缺失任务"], paired_rows(summary, keep_only=False, short_names=short_names), min_width=1180)}
      <p class="caption">Balanced raw 仍按同格 persona–Control 配对，因此不会把尚未出现对应 persona 的孤立 Control 格混入差值；但它保留 EXCLUDE_RERUN 的数值结果，仅用于诊断和敏感性比较，不是环境有效的主结论。</p>
    </section>

    <section>
      <h2>重复运行、raw 与环境审计进度</h2>
      {table(["重复", "日期块", "manifest 状态", "发现尝试", "Raw 数值 / 计划", "执行完整性未选尝试", "审计 / KEEP / EXCLUDE / 未分类", "体验 A+B / Raw"], replicate_rows(summary, replicates), min_width=1120)}
      <p class="caption">Raw 数值格是每个 replicate/task/persona/model 的最新可评分结果；旧重复尝试、error-only 和无数值结果不会被当成 0 分。{integrity_note} cap-8 pilot 独立保存，不进入本页。</p>
    </section>

    <section>
      <h2>KEEP-only 敏感性分析（按实验组）</h2>
      {table(["实验组", "KEEP n", "Cell-macro 完成率", "Rubric micro", "沟通覆盖率", "仅已沟通要求完成率"], keep_arm_rows(summary), min_width=1050)}
      <p class="caption">这是被环境审计保留下来的描述性子集。各组 KEEP n 和任务构成可能不同，均值会受到 composition skew 影响，不能据此做简单横向排名。</p>

      <h3>Arm × Task KEEP 数量</h3>
      {table(["实验组", "T1", "T2", "T3", "T4", "T5", "T6", "合计"], keep_matrix_rows(summary), min_width=850)}
      <p class="caption">0 表示该 arm–task 在当前审计中没有 KEEP 格；此矩阵直接展示 KEEP-only 均值的样本构成是否平衡。</p>
    </section>

    <section>
      <h2>逐题 Raw / KEEP 汇总</h2>
      {table(["任务", "Raw n", "Raw cell-macro", "Raw rubric micro", "KEEP n", "KEEP cell-macro", "KEEP rubric micro"], task_summary_rows(summary, long_names), min_width=1080)}
      <p class="caption">Raw 包含被环境审计排除的数值格；KEEP 只包含审计为 KEEP 的格。未分类的正在运行格只出现在 Raw，不进入 KEEP。</p>
    </section>

    <section>
      <h2>Persona 体验评分：Raw 与 KEEP</h2>
      {table(["维度（1–5）", "Raw Judge A 均值/中位数", "Raw Judge B 均值/中位数", "Raw |A−B|≤1", "KEEP Judge A 均值/中位数", "KEEP Judge B 均值/中位数", "KEEP |A−B|≤1"], experience_rows(summary), min_width=1320)}
      <p class="caption">Judge A 与 Judge B 是两次独立调用，始终分别展示，绝不平均。“无数值”在未完成页面中既可能是尚未评分，也可能是 Judge 返回 N/A，二者都不是 0 分；Raw 体验包含 EXCLUDE_RERUN，KEEP 体验是环境有效子集。</p>

      <h3>满分任务切片</h3>
      {table(["人口", "切片", "格数 / 分母", "各组格数", *[f"{label} A/B" for _, label in DIMENSIONS]], perfect_slice_rows(summary), min_width=1450)}
      <p class="caption">“原任务满分”要求 judgement.score = 1；“已沟通要求满分”要求 score_communicated = 1。A/B 是切片内两个 Judge 各自的均值，不作合并。样本很小时只作探索性机制检查。</p>
    </section>

    <section>
      <h2>具体是怎么做的</h2>
      {table(["项目", "固定设置"], [
          ["正式网格", "6 个 canonical Food 任务 × Control/P1/P2/P3/P4 × r1/r2/r3 = 90 格；每个 Persona 都跑每道题"],
          ["Persona 模拟", e(simulator) + "；temperature=1；每次尝试重新生成 persona utterance"],
          ["网页执行", e(model) + "；live headless Chrome；每格全新 profile；最多 50 步、5 次 ask_user"],
          ["任务评分", e(task_judge) + "；沿用 canonical task 的原 rubric"],
          ["体验评分", e(experience_judge) + "；Judge A/B 为两次独立调用"],
          ["环境协议", "主分析使用独立轨迹审计；实质阻断必要证据才标 EXCLUDE_RERUN；同配置最多按计划重跑"],
          ["代码基线", e(base_sha) + "；main-style；ODYSSEY_MAX_TABS=0，仅移除人工 tab 数量上限"],
      ], min_width=900)}

      <h3>四个 Persona 与 Control</h3>
      {table(["组", "设定与检验重点"], [
          ["P1 · 预算敏感的烹饪新手", "25–34 岁、预算有限、烹饪研究经验少、偏好短而实用的移动端建议；检验成本与低耐心带来的需求压缩。"],
          ["P2 · 谨慎的饮食规划者", "55–64 岁、有未指定过敏原的食物过敏和放大阅读需求；检验风险核查、证据与可读性。"],
          ["P3 · 时间紧张的家庭餐饮规划者", "35–44 岁、有日常烹饪经验、时间紧、偏好务实简洁；检验物流和比较要求是否保留。"],
          ["P4 · 专业餐饮研究者", "45–54 岁、餐饮领域专家、重证据、品质与完整细节；作为合成专家上界条件。"],
          ["Control · none", "不做 Persona 改写，直接把 canonical task 原文交给同一执行模型。"],
      ], min_width=900)}
    </section>

    <section>
      <h2>评分标准</h2>
      <p><strong>原任务完成率</strong> = 命中的 canonical rubric 条目数 ÷ 原 rubric 条目数。报告 cell-macro（每格等权）、task-macro（每题等权）和 rubric-micro（所有条目汇总）时会明确标注。</p>
      <p class="spaced"><strong>沟通覆盖率</strong> = Persona utterance 已表达、或 Agent 通过 ask_user 补问而纳入的 rubric 条目数 ÷ 原 rubric 条目数。它衡量 Persona 改写有没有保留原任务要求。</p>
      <p class="spaced"><strong>仅已沟通要求的完成率</strong> = 已沟通且完成的 rubric 条目数 ÷ 已沟通 rubric 条目数；一个格没有已沟通条目时，不进入 cell-macro 分母，且会单独计数。</p>
      <p class="spaced"><strong>Persona 体验</strong>：Judge A/B 分别对要求符合度、Persona 可读性、可执行性、缺口处理与主动性、整体体验打 1–5 分。两次 Judge 不平均，并报告一致性与 N/A。</p>
      <p class="spaced"><strong>配对效应</strong>：在同一 replicate、task、execution model 内计算 Persona − Control；胜/平/负按完成率差值的正/零/负计数。主表进一步要求双方环境状态均为 KEEP。</p>
    </section>

    <section>
      <h2>限制与解读</h2>
      <ul>
        <li><strong>这不是 exact-main。</strong>这是 main-style / no-cap：prompt、工具、模型和评分规则保持计划设置，但 <code>ODYSSEY_MAX_TABS=0</code> 移除了 main 的人工 8-tab guard；因此不可把 Food 绝对分数与 Shopping exact-main 无条件横比。</li>
        <li><strong>EXCLUDE_RERUN 不是模型失败。</strong>403、429、CAPTCHA、DNS、超时或站点阻断只有在实质影响必要 rubric 证据时才排除；它表示该格没有环境有效结果。error-only 和无数值评分也不记为 0。</li>
        <li><strong>Raw 保留排除格。</strong>所有 raw 汇总与 balanced raw 配对都包含有数值的 EXCLUDE_RERUN 格；它们用于审计透明度和敏感性比较，不是主结果。</li>
        <li><strong>KEEP 均值可能构成偏斜。</strong>网站阻断并非随机，各 arm/task 的 KEEP 数不同；因此主表采用双方均 KEEP 的同格配对，同时仍显示 n、任务覆盖和缺失任务。</li>
        <li><strong>统计规模有限。</strong>即使 90 格完成，每个 Persona 最多只有 18 个 raw cell；满分切片更小。本报告给出描述性效应、配对胜平负和双 Judge 一致性，不将其包装成显著性结论。</li>
        <li><strong>重跑并非逐字重放。</strong>同配置重跑保持任务、persona YAML、模型、温度和规则不变，但 temperature=1 的 persona utterance 会重新采样，这是当前 runner 的既有行为。</li>
      </ul>
    </section>

    <footer>数据由 <code>food_main_setting1_analysis.py</code> 从日期分隔的正式目录重算；本页由 <code>food_main_setting1_html.py</code> 生成。命令：<code>python3 artifacts/experiments/food_main_setting1_html.py</code>。</footer>
    """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Food Persona 实验结果 — {e(status)}</title>
  <style>
    :root {{ color-scheme:light dark; --bg:#f7f8f6; --card:#fff; --text:#202821; --muted:#59675e; --line:#d9e0d8; --accent:#2c6b47; --soft:#e9f2eb; --warn:#875815; --warn-soft:#fff5e4; }}
    @media (prefers-color-scheme:dark) {{ :root {{ --bg:#171c18; --card:#222a23; --text:#f1f5ef; --muted:#b3c1b4; --line:#3b4a3e; --accent:#96d3a9; --soft:#2a4030; --warn:#efc27a; --warn-soft:#453824; }} }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.55 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(1260px,calc(100% - 32px)); margin:auto; padding:42px 0 64px; }}
    h1 {{ margin:2px 0 8px; font-size:clamp(1.8rem,4vw,2.55rem); line-height:1.15; }}
    h2 {{ margin:40px 0 13px; font-size:1.28rem; }} h3 {{ margin:25px 0 10px; font-size:1.02rem; }}
    p {{ margin:0; }} .spaced {{ margin-top:10px; }}
    .eyebrow {{ color:var(--accent); font-size:.8rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }}
    .subtitle,.meta,.caption,footer {{ color:var(--muted); }} .meta {{ margin-top:10px; font-size:.85rem; }}
    .status {{ display:inline-block; margin-top:17px; padding:6px 11px; border:1px solid var(--warn); border-radius:999px; background:var(--warn-soft); color:var(--warn); font-weight:700; font-size:.86rem; }}
    .stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:26px; }}
    .stat {{ padding:16px 18px; border:1px solid var(--line); border-radius:10px; background:var(--card); }}
    .stat strong {{ display:block; color:var(--accent); font-size:1.5rem; line-height:1.2; }}
    .stat span {{ display:block; margin-top:6px; color:var(--muted); font-size:.8rem; }}
    .table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:10px; background:var(--card); }}
    table {{ width:100%; border-collapse:collapse; font-size:.89rem; }}
    th,td {{ padding:11px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:var(--soft); font-size:.77rem; font-weight:700; white-space:nowrap; }}
    td:not(:first-child) {{ white-space:nowrap; }} tbody tr:last-child td {{ border-bottom:0; }} tbody tr:hover {{ background:var(--soft); }}
    .caption {{ margin-top:8px; font-size:.82rem; }}
    .callout {{ margin-top:23px; padding:15px 17px; border:1px solid var(--line); border-left:4px solid var(--warn); border-radius:8px; background:var(--warn-soft); }}
    .callout strong {{ display:block; margin-bottom:4px; }}
    ul {{ margin:8px 0 0; padding-left:22px; }} li + li {{ margin-top:7px; }}
    code {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.9em; }}
    footer {{ margin-top:42px; padding-top:18px; border-top:1px solid var(--line); font-size:.8rem; }}
    @media (max-width:800px) {{ .stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} main {{ width:calc(100% - 24px); padding-top:28px; }} }}
  </style>
</head>
<body><main>{sections}</main></body>
</html>
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path, help="formal r1/r2/r3 replicate roots")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validity-json", action="append", default=[], type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    roots = sorted({path.resolve() for path in (args.roots or discover_roots())})
    if not roots:
        raise SystemExit("No formal Food replicate roots with results/ were found.")
    replicates = [analysis.load_replicate(root) for root in roots]
    audits = analysis.load_validity_audits(replicates, args.validity_json)
    summary = analysis.analyze(replicates, "none", audits)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(summary, replicates), encoding="utf-8")
    status, _, judged = status_label(summary, replicates)
    print(f"wrote {output}")
    print(
        f"selected={summary['counts']['selected_numeric_scored_cells']}/{EXPECTED_CELLS} "
        f"audited={summary['environment_validity']['counts']['audited_selected_numeric_scored_cells']} "
        f"experience_a_b={judged} status={status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
