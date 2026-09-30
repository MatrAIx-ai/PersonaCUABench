# Food & Drink main-style Setting 1 — formal post-hoc analysis

This report is generated deterministically from the replicate roots listed below. Judge A and Judge B experience scores are always shown separately. Unless a section is explicitly labeled KEEP-only, metrics use all selected numeric scored execution cells and do not assert environment validity.

## Inputs and attempt accounting

| Replicate | Date block | Planned | Attempts | Selected numeric scored | Execution-integrity excluded | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 2026-09-28 | 30 | 42 | 30 | 12 | 5 |

### Formal-input integrity

Status: **pass**. results/ is the only hard requirement; formal Food roots are expected to include RUN_MANIFEST.json, inputs/runtime-config.json, and inputs/tasks.json. Diagnostics do not remove or alter numeric results.

All supplied roots contain the formal manifest/runtime/task snapshots, and the task/persona grids agree across replicates.

Across all roots: **30 planned cells**, **30 selected numeric scored cells**, **12 execution-integrity excluded attempts**, and **5 attempts containing `error.txt`**. Error counts overlap the execution-selected/excluded partition if an attempt ever contains both a scored result and an error file.

A selected numeric scored cell is the latest execution-integrity-eligible finite numeric `judgement.score` for one (replicate, task, persona, execution model). This is **not** an environment-validity claim. Error-only attempts are never scored.

| Exclusion reason | Attempts |
| --- | --- |
| error_only_attempt | 5 |
| older_duplicate_scored_attempt | 7 |

## Environment-validity overlay

This section is separate from the all-numeric execution results. Environment-excluded cells remain preserved in every all-numeric section below.

Audited selected numeric cells: **30**; **KEEP 23**; **EXCLUDE_RERUN 7**; unclassified selected numeric cells: **0**.

| Replicate | Audit version | Selected numeric | Audited/matched | KEEP | EXCLUDE_RERUN | Unclassified |
| --- | --- | --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 1 | 30 | 30 | 23 | 7 | 0 |

### KEEP-only completion and communication

This subset can be imbalanced by task/persona and is not automatically an overall Food & Drink performance estimate.

- Cells: **23**.
- Task-macro completion: **0.568** across 6 represented tasks.
- Cell-macro completion: **0.652**.
- Rubric-micro completion: **69/113 = 0.611**.
- Communication coverage: **86/113 = 0.761**.
- Communicated-only completion: **66/86 = 0.767**.

| Arm | KEEP cells | Score mean | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 5 | 0.614 | 14 / 26 | 0.538 |
| food-busy-host / gpt-5.6-terra | 6 | 0.601 | 17 / 30 | 0.567 |
| food-cautious-dietary-planner / gpt-5.6-terra | 5 | 0.621 | 15 / 26 | 0.577 |
| food-culinary-researcher / gpt-5.6-terra | 3 | 0.667 | 8 / 12 | 0.667 |
| none / gpt-5.6-terra | 4 | 0.803 | 15 / 19 | 0.789 |

### KEEP-only run behavior

Stop reasons: finish=17, no_tool_call=6. Steps: mean **20.43**, median **20.00**, range 11–35. Questions (`ask_user` calls): **0 total**.

### KEEP-only experience

| Dimension | A mean / median / n | A ≥4 / n | B mean / median / n | B ≥4 / n | Exact / paired | Within 1 / paired |
| --- | --- | --- | --- | --- | --- | --- |
| P1_asked_for | — / — / 0 | 0 / 0 | — / — / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P2_readable_for_them | — / — / 0 | 0 / 0 | — / — / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P3_actionable | — / — / 0 | 0 / 0 | — / — / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P4_gap_handling | — / — / 0 | 0 / 0 | — / — / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| P5_overall | — / — / 0 | 0 / 0 | — / — / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

### KEEP-only perfect slices

Full-task perfect (`judgement.score == 1.0`): **4/23**. Communicated-perfect (`judgement.score_communicated == 1.0`): **9/23**.


## All selected numeric scored cells — task completion

- Task-macro completion: **0.627** across 6 tasks.
- Cell-macro completion: **0.627**.
- Rubric-micro completion: **89/150 = 0.593**.

### Completion by arm

| Arm | Cells | Score mean | Score median | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | 0.553 | 0.660 | 15 / 30 | 0.500 |
| food-busy-host / gpt-5.6-terra | 6 | 0.601 | 0.590 | 17 / 30 | 0.567 |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | 0.601 | 0.660 | 17 / 30 | 0.567 |
| food-culinary-researcher / gpt-5.6-terra | 6 | 0.673 | 0.750 | 20 / 30 | 0.667 |
| none / gpt-5.6-terra | 6 | 0.708 | 0.750 | 20 / 30 | 0.667 |

### Completion by task

| Task | Cells | Score mean | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- |
| T1 | 5 | 0.900 | 18 / 20 | 0.900 |
| T2 | 5 | 0.750 | 15 / 20 | 0.750 |
| T3 | 5 | 0.700 | 14 / 20 | 0.700 |
| T4 | 5 | 0.628 | 22 / 35 | 0.629 |
| T5 | 5 | 0.500 | 10 / 20 | 0.500 |
| T6 | 5 | 0.286 | 10 / 35 | 0.286 |

### Arm × task completion

| Arm | T1 | T2 | T3 | T4 | T5 | T6 |
| --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.571 (n=1) | 0.250 (n=1) | 0.000 (n=1) |
| food-busy-host / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.429 (n=1) | 0.250 (n=1) | 0.429 (n=1) |
| food-cautious-dietary-planner / gpt-5.6-terra | 0.750 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.571 (n=1) | 0.500 (n=1) | 0.286 (n=1) |
| food-culinary-researcher / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.250 (n=1) | 0.857 (n=1) | 0.750 (n=1) | 0.429 (n=1) |
| none / gpt-5.6-terra | 0.750 (n=1) | 0.750 (n=1) | 1.000 (n=1) | 0.714 (n=1) | 0.750 (n=1) | 0.286 (n=1) |

## All selected numeric scored cells — communication-conditioned metrics

Overall communication coverage is **119/150 = 0.793** (micro); the cell-macro rate is **0.810** over 30 cells.

Communicated-only completion is **86/119 = 0.723** (micro); the cell-macro rate is **0.727** over 30 cells. Cells with zero communicated rubric items: 0.

| Arm | Coverage numerator / denominator | Coverage | Communicated met / denominator | Communicated completion |
| --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 19 / 30 | 0.633 | 14 / 19 | 0.737 |
| food-busy-host / gpt-5.6-terra | 20 / 30 | 0.667 | 16 / 20 | 0.800 |
| food-cautious-dietary-planner / gpt-5.6-terra | 23 / 30 | 0.767 | 16 / 23 | 0.696 |
| food-culinary-researcher / gpt-5.6-terra | 27 / 30 | 0.900 | 20 / 27 | 0.741 |
| none / gpt-5.6-terra | 30 / 30 | 1.000 | 20 / 30 | 0.667 |

## All selected numeric scored cells — run behavior

| Stop reason | Cells |
| --- | --- |
| finish | 22 |
| no_tool_call | 8 |

Steps: mean **24.07**, median **20.50**, range 11–48 over 30 cells. Questions are reconstructed as `ask_user` trajectory calls: **0 total**, mean **0.00** per cell.

| Arm | Cells | Step mean | Step median | Questions total | Questions mean |
| --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | 19.00 | 17.50 | 0 | 0.00 |
| food-busy-host / gpt-5.6-terra | 6 | 18.50 | 19.50 | 0 | 0.00 |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | 26.67 | 26.50 | 0 | 0.00 |
| food-culinary-researcher / gpt-5.6-terra | 6 | 30.83 | 29.50 | 0 | 0.00 |
| none / gpt-5.6-terra | 6 | 25.33 | 21.00 | 0 | 0.00 |

## All selected numeric scored cells — experience judges

Scores are 1–5. `n/a` is missing or invalid at the relevant judge/dimension; A/B values are not averaged together.

| Dimension | A mean / median | A ≥4 / n | A n/a | B mean / median | B ≥4 / n | B n/a | Exact / paired | Within 1 / paired |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1_asked_for | — / — | 0 / 0 (—) | 30 | — / — | 0 / 0 (—) | 30 | 0 / 0 (—) | 0 / 0 (—) |
| P2_readable_for_them | — / — | 0 / 0 (—) | 30 | — / — | 0 / 0 (—) | 30 | 0 / 0 (—) | 0 / 0 (—) |
| P3_actionable | — / — | 0 / 0 (—) | 30 | — / — | 0 / 0 (—) | 30 | 0 / 0 (—) | 0 / 0 (—) |
| P4_gap_handling | — / — | 0 / 0 (—) | 30 | — / — | 0 / 0 (—) | 30 | 0 / 0 (—) | 0 / 0 (—) |
| P5_overall | — / — | 0 / 0 (—) | 30 | — / — | 0 / 0 (—) | 30 | 0 / 0 (—) | 0 / 0 (—) |

Across dimensions, exact agreement is **0/0 = —**; within-one agreement is **0/0 = —**; paired-score n/a count is 150.

## All selected numeric scored cells — perfect-task slices

These slices are separate: full-task perfect uses all original rubrics, while communicated-perfect uses only rubric items the persona communicated.

### Full-task perfect (`judgement.score == 1.0`)

4 / 30 selected numeric scored cells (13.3%).

| Dimension | A mean / median / n | B mean / median / n | Within 1 / paired |
| --- | --- | --- | --- |
| P1_asked_for | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P2_readable_for_them | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P3_actionable | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P4_gap_handling | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P5_overall | — / — / 0 | — / — / 0 | 0 / 0 (—) |

### Communicated-perfect (`judgement.score_communicated == 1.0`)

11 / 30 selected numeric scored cells (36.7%).

| Dimension | A mean / median / n | B mean / median / n | Within 1 / paired |
| --- | --- | --- | --- |
| P1_asked_for | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P2_readable_for_them | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P3_actionable | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P4_gap_handling | — / — / 0 | — / — / 0 | 0 / 0 (—) |
| P5_overall | — / — / 0 | — / — / 0 | 0 / 0 (—) |

## All selected numeric scored cells — paired persona-minus-none deltas

Baseline persona: `none`. Pairing is within replicate, task, and execution model. Positive completion delta favors the persona arm.

| Persona / model | Pairs | Completion Δ mean | Median | W / T / L | Coverage Δ mean | Communicated completion Δ mean (n) |
| --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | -0.155 | -0.197 | 1 / 1 / 4 | -0.333 | -0.042 (n=6) |
| food-busy-host / gpt-5.6-terra | 6 | -0.107 | -0.125 | 2 / 1 / 3 | -0.292 | 0.083 (n=6) |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | -0.107 | -0.071 | 0 / 3 / 3 | -0.220 | 0.006 (n=6) |
| food-culinary-researcher / gpt-5.6-terra | 6 | -0.036 | 0.071 | 3 / 2 / 1 | -0.107 | 0.044 (n=6) |

## Descriptive external-noise keyword evidence

Categories are descriptive and overlapping: one attempt may contribute to multiple categories, and keyword evidence does not establish causal impact on score.

| Category | Attempts / all | Occurrences | Selected numeric scored | Execution-integrity excluded |
| --- | --- | --- | --- | --- |
| HTTP 403 / forbidden / access-denied evidence | 9 / 42 | 35 | 5 | 4 |
| verification, CAPTCHA, bot challenge, or Cloudflare evidence | 14 / 42 | 57 | 11 | 3 |
| timeout, DNS, or name-resolution evidence | 25 / 42 | 120 | 19 | 6 |
| maximum-tab / tab-limit evidence | 0 / 42 | 0 | 0 | 0 |

Scope: run.answer, run.trajectory[*].result_preview, and error.txt across all discovered attempts (selected and excluded); prompts and judge rationales are not searched.

## Task catalog

| Task | ID | Level | Rubrics | Prompt preview |
| --- | --- | --- | --- | --- |
| T1 | 082aa17f3e88 | easy | 4 | I’m setting up a new kitchen and want one of the first things I make to be roasted… |
| T2 | 0ab48db60760 | easy | 4 | I’m trying to put together a simple, semi-healthy meal prep menu for the week, mostly so I… |
| T3 | eb8a01554a84 | easy | 4 | I’m planning a holiday party in Minneapolis and want a quick shortlist of bar caterers… |
| T4 | 5944875c7f32 | medium | 7 | I’m putting together a small Zelda: Breath of the Wild–themed dessert setup for a… |
| T5 | 18ddad3e0781 | medium | 4 | I’m in Boston for the next two days on a work trip with my wife, and I want to lock in two… |
| T6 | e20742e26a4d | medium | 7 | I’m putting together a small Christmas get-together here in the UK and want one tidy plan… |

## Excluded attempts

| Replicate | Path | Reason | result.json | error.txt |
| --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | results/082aa17f3e88/food-culinary-researcher__gpt-5.6-terra__20260929T004513Z | error_only_attempt | no | yes |
| food-main-nocap-setting1-r1 | results/082aa17f3e88/food-culinary-researcher__gpt-5.6-terra__20260930T001505Z | error_only_attempt | no | yes |
| food-main-nocap-setting1-r1 | results/0ab48db60760/food-culinary-researcher__gpt-5.6-terra__20260929T010123Z | error_only_attempt | no | yes |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-budget-novice__gpt-5.6-terra__20260928T220857Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-cautious-dietary-planner__gpt-5.6-terra__20260928T230346Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-culinary-researcher__gpt-5.6-terra__20260929T165225Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/none__gpt-5.6-terra__20260928T214620Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/5944875c7f32/food-culinary-researcher__gpt-5.6-terra__20260929T032844Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/food-cautious-dietary-planner__gpt-5.6-terra__20260928T231640Z | error_only_attempt | no | yes |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/food-culinary-researcher__gpt-5.6-terra__20260930T002457Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/none__gpt-5.6-terra__20260928T214751Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/eb8a01554a84/food-culinary-researcher__gpt-5.6-terra__20260929T013141Z | error_only_attempt | no | yes |
