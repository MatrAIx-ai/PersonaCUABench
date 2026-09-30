# Food & Drink main-style Setting 1 — formal post-hoc analysis

This report is generated deterministically from the replicate roots listed below. Judge A and Judge B experience scores are always shown separately. Unless a section is explicitly labeled KEEP-only, metrics use all selected numeric scored execution cells and do not assert environment validity.

## Inputs and attempt accounting

| Replicate | Date block | Planned | Attempts | Selected numeric scored | Execution-integrity excluded | Errors |
| --- | --- | --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 2026-09-28 | 30 | 47 | 30 | 17 | 5 |

### Formal-input integrity

Status: **pass**. results/ is the only hard requirement; formal Food roots are expected to include RUN_MANIFEST.json, inputs/runtime-config.json, and inputs/tasks.json. Diagnostics do not remove or alter numeric results.

All supplied roots contain the formal manifest/runtime/task snapshots, and the task/persona grids agree across replicates.

Across all roots: **30 planned cells**, **30 selected numeric scored cells**, **17 execution-integrity excluded attempts**, and **5 attempts containing `error.txt`**. Error counts overlap the execution-selected/excluded partition if an attempt ever contains both a scored result and an error file.

A selected numeric scored cell is the latest execution-integrity-eligible finite numeric `judgement.score` for one (replicate, task, persona, execution model). This is **not** an environment-validity claim. Error-only attempts are never scored.

| Exclusion reason | Attempts |
| --- | --- |
| error_only_attempt | 5 |
| older_duplicate_scored_attempt | 12 |

## Environment-validity overlay

This section is separate from the all-numeric execution results. Environment-excluded cells remain preserved in every all-numeric section below.

Audited selected numeric cells: **30**; **KEEP 25**; **EXCLUDE_RERUN 5**; unclassified selected numeric cells: **0**.

| Replicate | Audit version | Selected numeric | Audited/matched | KEEP | EXCLUDE_RERUN | Unclassified |
| --- | --- | --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 4 | 30 | 30 | 25 | 5 | 0 |

### KEEP-only completion and communication

This subset can be imbalanced by task/persona and is not automatically an overall Food & Drink performance estimate.

- Cells: **25**.
- Task-macro completion: **0.619** across 6 represented tasks.
- Cell-macro completion: **0.664**.
- Rubric-micro completion: **78/124 = 0.629**.
- Communication coverage: **95/124 = 0.766**.
- Communicated-only completion: **75/95 = 0.789**.

| Arm | KEEP cells | Score mean | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 5 | 0.614 | 14 / 26 | 0.538 |
| food-busy-host / gpt-5.6-terra | 6 | 0.601 | 17 / 30 | 0.567 |
| food-cautious-dietary-planner / gpt-5.6-terra | 5 | 0.621 | 15 / 26 | 0.577 |
| food-culinary-researcher / gpt-5.6-terra | 5 | 0.721 | 17 / 23 | 0.739 |
| none / gpt-5.6-terra | 4 | 0.803 | 15 / 19 | 0.789 |

### KEEP-only completion by replicate

| Replicate | KEEP cells | Score mean | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 25 | 0.664 | 78 / 124 | 0.629 |

### Arm × task KEEP counts

| Arm | T1 | T2 | T3 | T4 | T5 | T6 | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 1 | 1 | 1 | 1 | 0 | 1 | 5 |
| food-busy-host / gpt-5.6-terra | 1 | 1 | 1 | 1 | 1 | 1 | 6 |
| food-cautious-dietary-planner / gpt-5.6-terra | 1 | 1 | 1 | 1 | 0 | 1 | 5 |
| food-culinary-researcher / gpt-5.6-terra | 1 | 1 | 1 | 1 | 1 | 0 | 5 |
| none / gpt-5.6-terra | 1 | 1 | 1 | 1 | 0 | 0 | 4 |

### Environment-valid matched persona-minus-control deltas

A persona/control pair is eligible only when both selected numeric cells have audit status KEEP for the same replicate, task_id, and execution model.

| Persona | Eligible pairs | Tasks represented | Completion Δ mean | W / T / L | Coverage Δ mean (n) | Communicated completion Δ mean (n) | Missing task IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice | 4 | 4 | -0.036 | 1 / 1 / 2 | -0.223 (n=4) | 0.113 (n=4) | T5:18ddad3e0781d4b8fb2e1998ff836a0b07d0cdce, T6:e20742e26a4d6f9c3d62a9d1cef634297bd4204f |
| food-busy-host | 4 | 4 | -0.071 | 1 / 1 / 2 | -0.232 (n=4) | 0.051 (n=4) | T5:18ddad3e0781d4b8fb2e1998ff836a0b07d0cdce, T6:e20742e26a4d6f9c3d62a9d1cef634297bd4204f |
| food-cautious-dietary-planner | 4 | 4 | -0.098 | 0 / 2 / 2 | -0.196 (n=4) | 0.001 (n=4) | T5:18ddad3e0781d4b8fb2e1998ff836a0b07d0cdce, T6:e20742e26a4d6f9c3d62a9d1cef634297bd4204f |
| food-culinary-researcher | 4 | 4 | -0.089 | 2 / 1 / 1 | -0.098 (n=4) | -0.033 (n=4) | T5:18ddad3e0781d4b8fb2e1998ff836a0b07d0cdce, T6:e20742e26a4d6f9c3d62a9d1cef634297bd4204f |

### KEEP-only run behavior

Stop reasons: finish=18, no_tool_call=7. Steps: mean **21.76**, median **20.00**, range 11–42. Questions (`ask_user` calls): **0 total**.

### KEEP-only experience

| Dimension | A mean / median / n | A ≥4 / n | B mean / median / n | B ≥4 / n | Exact / paired | Within 1 / paired |
| --- | --- | --- | --- | --- | --- | --- |
| P1_asked_for | 4.00 / 4.00 / 25 | 23 / 25 | 4.04 / 4.00 / 25 | 22 / 25 | 20 / 25 | 25 / 25 |
| P2_readable_for_them | 4.40 / 5.00 / 25 | 22 / 25 | 4.36 / 4.00 / 25 | 22 / 25 | 20 / 25 | 25 / 25 |
| P3_actionable | 3.64 / 4.00 / 25 | 14 / 25 | 3.84 / 4.00 / 25 | 15 / 25 | 14 / 25 | 25 / 25 |
| P4_gap_handling | 3.88 / 4.00 / 24 | 16 / 24 | 3.79 / 4.00 / 24 | 17 / 24 | 18 / 23 | 23 / 23 |
| P5_overall | 3.80 / 4.00 / 25 | 20 / 25 | 3.76 / 4.00 / 25 | 18 / 25 | 16 / 25 | 25 / 25 |

### KEEP-only perfect slices

Full-task perfect (`judgement.score == 1.0`): **4/25**. Communicated-perfect (`judgement.score_communicated == 1.0`): **11/25**.


## All selected numeric scored cells — task completion

- Task-macro completion: **0.604** across 6 tasks.
- Cell-macro completion: **0.604**.
- Rubric-micro completion: **87/150 = 0.580**.

### Completion by arm

| Arm | Cells | Score mean | Score median | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | 0.512 | 0.660 | 14 / 30 | 0.467 |
| food-busy-host / gpt-5.6-terra | 6 | 0.601 | 0.590 | 17 / 30 | 0.567 |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | 0.559 | 0.660 | 16 / 30 | 0.533 |
| food-culinary-researcher / gpt-5.6-terra | 6 | 0.673 | 0.750 | 20 / 30 | 0.667 |
| none / gpt-5.6-terra | 6 | 0.672 | 0.732 | 20 / 30 | 0.667 |

### Completion by task

| Task | Cells | Score mean | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- |
| T1 | 5 | 0.900 | 18 / 20 | 0.900 |
| T2 | 5 | 0.750 | 15 / 20 | 0.750 |
| T3 | 5 | 0.700 | 14 / 20 | 0.700 |
| T4 | 5 | 0.628 | 22 / 35 | 0.629 |
| T5 | 5 | 0.300 | 6 / 20 | 0.300 |
| T6 | 5 | 0.343 | 12 / 35 | 0.343 |

### Completion by replicate

| Replicate | Cells | Score mean | Score median | Rubric met / total | Rubric micro |
| --- | --- | --- | --- | --- | --- |
| food-main-nocap-setting1-r1 | 30 | 0.604 | 0.750 | 87 / 150 | 0.580 |

### Arm × task completion

| Arm | T1 | T2 | T3 | T4 | T5 | T6 |
| --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.571 (n=1) | 0.000 (n=1) | 0.000 (n=1) |
| food-busy-host / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.429 (n=1) | 0.250 (n=1) | 0.429 (n=1) |
| food-cautious-dietary-planner / gpt-5.6-terra | 0.750 (n=1) | 0.750 (n=1) | 0.750 (n=1) | 0.571 (n=1) | 0.250 (n=1) | 0.286 (n=1) |
| food-culinary-researcher / gpt-5.6-terra | 1.000 (n=1) | 0.750 (n=1) | 0.250 (n=1) | 0.857 (n=1) | 0.750 (n=1) | 0.429 (n=1) |
| none / gpt-5.6-terra | 0.750 (n=1) | 0.750 (n=1) | 1.000 (n=1) | 0.714 (n=1) | 0.250 (n=1) | 0.571 (n=1) |

## All selected numeric scored cells — communication-conditioned metrics

Overall communication coverage is **118/150 = 0.787** (micro); the cell-macro rate is **0.801** over 30 cells.

Communicated-only completion is **84/118 = 0.712** (micro); the cell-macro rate is **0.697** over 30 cells. Cells with zero communicated rubric items: 0.

| Arm | Coverage numerator / denominator | Coverage | Communicated met / denominator | Communicated completion |
| --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 18 / 30 | 0.600 | 13 / 18 | 0.722 |
| food-busy-host / gpt-5.6-terra | 20 / 30 | 0.667 | 16 / 20 | 0.800 |
| food-cautious-dietary-planner / gpt-5.6-terra | 23 / 30 | 0.767 | 15 / 23 | 0.652 |
| food-culinary-researcher / gpt-5.6-terra | 27 / 30 | 0.900 | 20 / 27 | 0.741 |
| none / gpt-5.6-terra | 30 / 30 | 1.000 | 20 / 30 | 0.667 |

## All selected numeric scored cells — run behavior

| Stop reason | Cells |
| --- | --- |
| finish | 23 |
| no_tool_call | 7 |

Steps: mean **24.60**, median **20.50**, range 11–57 over 30 cells. Questions are reconstructed as `ask_user` trajectory calls: **0 total**, mean **0.00** per cell.

| Arm | Cells | Step mean | Step median | Questions total | Questions mean |
| --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | 18.50 | 17.50 | 0 | 0.00 |
| food-busy-host / gpt-5.6-terra | 6 | 18.50 | 19.50 | 0 | 0.00 |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | 26.33 | 25.50 | 0 | 0.00 |
| food-culinary-researcher / gpt-5.6-terra | 6 | 32.33 | 29.50 | 0 | 0.00 |
| none / gpt-5.6-terra | 6 | 27.33 | 23.00 | 0 | 0.00 |

## All selected numeric scored cells — experience judges

Scores are 1–5. `n/a` is missing or invalid at the relevant judge/dimension; A/B values are not averaged together.

| Dimension | A mean / median | A ≥4 / n | A n/a | B mean / median | B ≥4 / n | B n/a | Exact / paired | Within 1 / paired |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1_asked_for | 3.90 / 4.00 | 25 / 30 (83.3%) | 0 | 3.90 / 4.00 | 23 / 30 (76.7%) | 0 | 24 / 30 (80.0%) | 30 / 30 (100.0%) |
| P2_readable_for_them | 4.43 / 5.00 | 27 / 30 (90.0%) | 0 | 4.37 / 4.50 | 26 / 30 (86.7%) | 0 | 23 / 30 (76.7%) | 29 / 30 (96.7%) |
| P3_actionable | 3.53 / 3.00 | 14 / 30 (46.7%) | 0 | 3.70 / 3.50 | 15 / 30 (50.0%) | 0 | 19 / 30 (63.3%) | 30 / 30 (100.0%) |
| P4_gap_handling | 3.69 / 4.00 | 17 / 29 (58.6%) | 1 | 3.59 / 4.00 | 17 / 29 (58.6%) | 1 | 20 / 28 (71.4%) | 28 / 28 (100.0%) |
| P5_overall | 3.73 / 4.00 | 22 / 30 (73.3%) | 0 | 3.63 / 4.00 | 18 / 30 (60.0%) | 0 | 19 / 30 (63.3%) | 30 / 30 (100.0%) |

Across dimensions, exact agreement is **105/148 = 70.9%**; within-one agreement is **147/148 = 99.3%**; paired-score n/a count is 2.

## All selected numeric scored cells — perfect-task slices

These slices are separate: full-task perfect uses all original rubrics, while communicated-perfect uses only rubric items the persona communicated.

### Full-task perfect (`judgement.score == 1.0`)

4 / 30 selected numeric scored cells (13.3%).

| Dimension | A mean / median / n | B mean / median / n | Within 1 / paired |
| --- | --- | --- | --- |
| P1_asked_for | 4.00 / 4.00 / 4 | 4.00 / 4.00 / 4 | 4 / 4 (100.0%) |
| P2_readable_for_them | 4.50 / 5.00 / 4 | 4.75 / 5.00 / 4 | 4 / 4 (100.0%) |
| P3_actionable | 3.50 / 3.50 / 4 | 4.00 / 4.00 / 4 | 4 / 4 (100.0%) |
| P4_gap_handling | 4.25 / 4.50 / 4 | 4.25 / 4.50 / 4 | 4 / 4 (100.0%) |
| P5_overall | 4.00 / 4.00 / 4 | 3.75 / 4.00 / 4 | 4 / 4 (100.0%) |

### Communicated-perfect (`judgement.score_communicated == 1.0`)

11 / 30 selected numeric scored cells (36.7%).

| Dimension | A mean / median / n | B mean / median / n | Within 1 / paired |
| --- | --- | --- | --- |
| P1_asked_for | 4.18 / 4.00 / 11 | 4.27 / 4.00 / 11 | 11 / 11 (100.0%) |
| P2_readable_for_them | 4.36 / 5.00 / 11 | 4.36 / 5.00 / 11 | 11 / 11 (100.0%) |
| P3_actionable | 3.82 / 4.00 / 11 | 4.00 / 4.00 / 11 | 11 / 11 (100.0%) |
| P4_gap_handling | 3.91 / 4.00 / 11 | 3.82 / 4.00 / 11 | 11 / 11 (100.0%) |
| P5_overall | 3.91 / 4.00 / 11 | 3.82 / 4.00 / 11 | 11 / 11 (100.0%) |

## All selected numeric scored cells — paired persona-minus-none deltas

Baseline persona: `none`. Pairing is within replicate, task, and execution model. Positive completion delta favors the persona arm.

| Persona / model | Pairs | Completion Δ mean | Median | W / T / L | Coverage Δ mean | Communicated completion Δ mean (n) |
| --- | --- | --- | --- | --- | --- | --- |
| food-budget-novice / gpt-5.6-terra | 6 | -0.161 | -0.197 | 1 / 1 / 4 | -0.375 | -0.061 (n=6) |
| food-busy-host / gpt-5.6-terra | 6 | -0.071 | -0.071 | 1 / 2 / 3 | -0.292 | 0.119 (n=6) |
| food-cautious-dietary-planner / gpt-5.6-terra | 6 | -0.113 | -0.071 | 0 / 3 / 3 | -0.220 | -0.014 (n=6) |
| food-culinary-researcher / gpt-5.6-terra | 6 | 0.000 | 0.071 | 3 / 1 / 2 | -0.107 | 0.080 (n=6) |

## Descriptive external-noise keyword evidence

Categories are descriptive and overlapping: one attempt may contribute to multiple categories, and keyword evidence does not establish causal impact on score.

| Category | Attempts / all | Occurrences | Selected numeric scored | Execution-integrity excluded |
| --- | --- | --- | --- | --- |
| HTTP 403 / forbidden / access-denied evidence | 12 / 47 | 47 | 5 | 7 |
| verification, CAPTCHA, bot challenge, or Cloudflare evidence | 19 / 47 | 73 | 11 | 8 |
| timeout, DNS, or name-resolution evidence | 29 / 47 | 138 | 19 | 10 |
| maximum-tab / tab-limit evidence | 0 / 47 | 0 | 0 | 0 |

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
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-budget-novice__gpt-5.6-terra__20260930T004848Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-cautious-dietary-planner__gpt-5.6-terra__20260928T230346Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-cautious-dietary-planner__gpt-5.6-terra__20260930T005519Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/food-culinary-researcher__gpt-5.6-terra__20260929T165225Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/none__gpt-5.6-terra__20260928T214620Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/18ddad3e0781/none__gpt-5.6-terra__20260930T004312Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/5944875c7f32/food-culinary-researcher__gpt-5.6-terra__20260929T032844Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/food-cautious-dietary-planner__gpt-5.6-terra__20260928T231640Z | error_only_attempt | no | yes |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/food-culinary-researcher__gpt-5.6-terra__20260930T002457Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/food-culinary-researcher__gpt-5.6-terra__20260930T012011Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/none__gpt-5.6-terra__20260928T214751Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/e20742e26a4d/none__gpt-5.6-terra__20260930T010909Z | older_duplicate_scored_attempt | yes | no |
| food-main-nocap-setting1-r1 | results/eb8a01554a84/food-culinary-researcher__gpt-5.6-terra__20260929T013141Z | error_only_attempt | no | yes |
