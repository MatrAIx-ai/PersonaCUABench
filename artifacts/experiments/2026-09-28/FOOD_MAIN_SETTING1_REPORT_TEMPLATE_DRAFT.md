# Food & Drink main-style Setting 1 — report template (DRAFT)

> **DRAFT / NOT A RESULT.** Numeric placeholders in this file must be filled
> only from finalized r1–r3 manifests, deterministic post-hoc output, and the
> environment-validity ledgers. Do not cite this template as experimental
> evidence.

## 1. Result

### Headline result

- Formal grid: 6 tasks × 5 arms × 3 replicates = 90 planned cells.
- Selected numeric scored cells: `[N_SELECTED] / 90`.
- Cell-macro full-task completion: `[CELL_MACRO]%`.
- Rubric-micro full-task completion: `[MET] / 450 = [MICRO]%`.
- Environment audit: `KEEP [N_KEEP]`; `EXCLUDE_RERUN [N_EXCLUDE]`;
  unclassified `[N_UNCLASSIFIED]`.
- Main finding: `[ONE_SENTENCE_FINDING]`.

Keep the raw numeric result and the environment-validity result separate. A
scored cell with a material live-web block remains a raw observation, but is
not a valid result for the KEEP-only analysis.

### Result by arm

| Arm | Selected cells | Completion mean | Rubric met / total | Paired delta vs control | W / T / L | Communication coverage | Communicated-only completion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Control (`none`) | `[N]` | `[X]%` | `[A] / [B]` | baseline | — | `100%` | `[X]%` |
| P1 Budget Novice | `[N]` | `[X]%` | `[A] / [B]` | `[DELTA] pp` | `[W/T/L]` | `[X]%` | `[X]%` |
| P2 Cautious Dietary Planner | `[N]` | `[X]%` | `[A] / [B]` | `[DELTA] pp` | `[W/T/L]` | `[X]%` | `[X]%` |
| P3 Busy Host | `[N]` | `[X]%` | `[A] / [B]` | `[DELTA] pp` | `[W/T/L]` | `[X]%` | `[X]%` |
| P4 Culinary Researcher | `[N]` | `[X]%` | `[A] / [B]` | `[DELTA] pp` | `[W/T/L]` | `[X]%` | `[X]%` |

Paired deltas compare a persona with `none` on the same task, replicate, and
execution model. Positive completion delta favors the persona arm.

### Replicate and environment audit

| Replicate | Local date block | Planned | Selected numeric | Cell macro | Rubric micro | Coverage | KEEP | EXCLUDE_RERUN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| r1 | `2026-09-28` | 30 | `[N]` | `[X]%` | `[A]/[B]` | `[X]%` | `[N]` | `[N]` |
| r2 | `[ACTUAL_START_DATE]` | 30 | `[N]` | `[X]%` | `[A]/[B]` | `[X]%` | `[N]` | `[N]` |
| r3 | `[ACTUAL_START_DATE]` | 30 | `[N]` | `[X]%` | `[A]/[B]` | `[X]%` | `[N]` | `[N]` |
| Combined | `[DATE_RANGE]` | 90 | `[N]` | `[X]%` | `[A]/450` | `[X]%` | `[N]` | `[N]` |

### Persona experience (Judge A and Judge B kept separate)

| Dimension (1–5) | Judge A mean / median / n | Judge B mean / median / n | Exact agreement | Within one point |
| --- | ---: | ---: | ---: | ---: |
| Asked-for fit | `[VALUE]` | `[VALUE]` | `[A]/[B]` | `[A]/[B]` |
| Readable for this persona | `[VALUE]` | `[VALUE]` | `[A]/[B]` | `[A]/[B]` |
| Actionable | `[VALUE]` | `[VALUE]` | `[A]/[B]` | `[A]/[B]` |
| Gap handling / proactivity | `[VALUE]` | `[VALUE]` | `[A]/[B]` | `[A]/[B]` |
| Overall experience | `[VALUE]` | `[VALUE]` | `[A]/[B]` | `[A]/[B]` |

Do not average Judge A and Judge B into one score. Report `n/a` counts and the
paired denominator for agreement.

### Perfect-task slices

- Full-task perfect (`score == 1.0`): `[N] / [N_SELECTED]`.
- Communicated-perfect (`score_communicated == 1.0`):
  `[N] / [N_WITH_DEFINED_COMMUNICATED_SCORE]`.
- Persona factor 2 conclusion: `[SUPPORTED / NOT ANSWERED]`. Compare persona
  experience after genuinely perfect completion only when there is adequate
  support across persona arms; do not substitute the communicated-perfect
  slice for this question.

### Task-level result

Include both completion by task and the arm × task matrix from the deterministic
post-hoc report. This is necessary because six live-web tasks differ materially
in site access, number of requested tabs, and rubric count.

## 2. How the experiment was run

### Design

Every arm runs every task in each replicate; personas are not assigned to
individual tasks. This complete task-by-arm design supports within-task paired
comparisons and avoids confounding one persona with one website or task.

| Component | Frozen setting |
| --- | --- |
| Tasks | Six canonical Food & Drink tasks from `Odysseys@837814633ef948479abb3d142458f0acdb73fa65` |
| Arms | P1–P4 plus `none` control |
| Formal repeats | r1, r2, r3; 30 cells each |
| Persona simulator | Azure `gpt-5.6-terra`, temperature 1 |
| Browser executor | Azure `gpt-5.6-terra`, temperature 1 |
| Task judge | Azure `gpt-5.6-terra`, unchanged rubric prompt |
| Experience judges | Two independent calls to Azure `gpt-5.6-terra` |
| Browser | Installed Google Chrome, live web, headless, fresh profile per cell |
| Limits | 50 agent steps, at most 5 `ask_user` calls, no artificial tab cap |

The pipeline for a persona cell is:

1. The simulator receives the persona's rendered dimension attributes plus the
   hidden canonical need and writes a natural opening request.
2. The neutral browser agent sees only that request and any simulated replies;
   it does not receive the persona profile or hidden canonical task.
3. The task judge independently marks each original rubric item `met` and
   `communicated` using the conversation, action log, final answer, and final
   open tabs.
4. Two independent experience-judge calls score the same completed interaction
   from that persona's perspective.
5. A separate environment audit labels the selected numeric cell `KEEP` or
   `EXCLUDE_RERUN` according to whether live-web conditions materially blocked
   required or communicated evidence.

For the `none` control, the canonical task text is sent verbatim to the executor
and communication coverage is therefore 100% by construction. All other
settings and judges remain identical.

### Protocol difference from repository `main`

The base protocol is local `main@4a1c0f221b0a80384d059cb487b3be1e470a148e`.
The formal Food runs set `ODYSSEY_MAX_TABS=0`, disabling the runner's artificial
eight-tab guard. A three-cell cap-8 pilot reached the guard in all three cells;
that pilot is preserved separately and excluded from r1–r3. Models, prompts,
browser tools, step/question budgets, and scoring rules are otherwise unchanged.

Accordingly, label this report **Food main-style / no-cap Setting 1**, not an
unqualified exact-main run. Within-Food persona/control comparisons share the
same no-cap setting; absolute comparisons with Shopping must disclose the tab
policy difference.

### Persona arms and control

All four persona files contain the same 36 MatrAIx dimensions; only their values
differ.

| Arm | Runtime-relevant profile | Experimental contrast |
| --- | --- | --- |
| P1 Budget Novice (`food-budget-novice`) | 25–34, lower-middle income, beginner cook/researcher, cost-sensitive, low patience/detail, gist-first, mobile | Whether low patience and bargain focus compress or omit requirements |
| P2 Cautious Dietary Planner (`food-cautious-dietary-planner`) | 55–64, intermediate cook, allergy, risk-averse, skeptical, high detail/patience, low vision with magnifier | Dietary caution, verification, uncertainty handling, and accessibility |
| P3 Busy Host (`food-busy-host`) | 35–44 operations manager, intermediate daily cook, value-driven, under deadline, brief-leaning, mobile | Whether concise, time-pressured communication preserves logistics and comparisons |
| P4 Culinary Researcher (`food-culinary-researcher`) | 45–54 hospitality director, master cooking/research skills, premium/quality-first, analytical, every-detail, desktop | Synthetic expert upper-bound communication condition |
| Control (`none`) | Verbatim canonical task; no persona simulation for the opening | Within-task baseline |

Important interpretation details:

- The top-level YAML `note` is documentation only; the simulator prompt renders
  non-null `attributes`. In particular, P3's runtime profile does not literally
  state “frequent host”; report conclusions from its actual attributes.
- P2 specifies a generic allergy but no allergen, so it is a dietary-caution
  condition rather than an allergen-specific safety test.
- P4 is deliberately synthetic and should not be generalized to culinary
  professionals or affluent users.

## 3. Scoring standard

### Original task completion

For cell `i`, with original rubric set `R_i`:

- Full-task completion: `met_i / |R_i|`.
- Communication coverage: `communicated_i / |R_i|`.
- Communicated-only completion: `met_and_communicated_i / communicated_i`;
  undefined when no item was communicated.
- Trajectory efficiency: `full_task_completion_i / max(steps_i, 1)`.

Report all three completion aggregations without conflating them:

- Cell macro: mean of cell completion scores.
- Task macro: mean of the six task-level means, weighting tasks equally.
- Rubric micro: total rubric items met divided by total original rubric items.

The six tasks contain 30 original rubric items, so each complete arm × replicate
has 30 item judgements and the full 90-cell design has 450.

### Persona experience

Each judge scores 1–5 (or `n/a`) on:

1. asked-for fit;
2. readability for that persona;
3. actionability;
4. gap handling / proactivity;
5. overall experience.

The experience score is not blended with task completion. Report each judge's
mean, median, valid `n`, share scoring at least 4, exact agreement, and
within-one-point agreement.

### Failure and rerun policy

- API/provider failure, empty model output, or unparseable task-judge output is
  unscored and retried under the same configuration; it is not a scored zero.
- A 403, 429, CAPTCHA, DNS failure, region wall, persistent timeout, or unusable
  page is `EXCLUDE_RERUN` only when it materially blocks required or
  communicated evidence.
- A recovered or irrelevant error does not automatically invalidate a cell.
- Environment-blocked cells remain raw observations but are no valid result
  pending a configuration-matched environment reattempt; they are not labeled
  executor failures.
- Relative-date requirements, especially Boston's “next two days,” use the
  actual local run window recorded in each manifest.

## 4. Limitations and interpretation boundary

Replace the placeholders below only after r1–r3 and the audits are complete:

- Live-web environment blocks affected `[N] / [N_SELECTED]` selected numeric
  cells; explain the dominant sites/error classes and whether KEEP is balanced
  across task and arm.
- Results apply to four hand-constructed bundles of 36 persona dimensions, not
  to demographic groups and not to individual causal dimensions.
- All simulator, executor, and judge roles use the same Terra deployment; this
  creates shared-model dependence even though experience A/B are independent
  calls.
- There are only six Food tasks and three replicates. Report effect sizes and
  W/T/L counts descriptively; do not overstate statistical generality.
- Live content and availability are dated. Any cross-category comparison with
  Shopping is descriptive because Food removes the artificial eight-tab cap.
- If full-perfect support is sparse or absent across persona arms, report the
  “satisfaction despite perfect completion” question as unanswered.

## 5. Date and provenance record

Fill one row from each finalized manifest; do not infer dates from directory
names when a run crosses midnight.

| Replicate | Started local | Finished local | Result root | Base SHA | Input SHA | Food protocol SHA | Input hash manifest | Audit version |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | `2026-09-28T14:33:51-0700` | `[TIME]` | `artifacts/experiments/2026-09-28/food-main-nocap-setting1-r1/results` | `4a1c0f221b0a80384d059cb487b3be1e470a148e` | `19e06333c6d9bc1fbc7c931b29e990b4e0dc1731` | `4c4212d4c215b90f324fbae0cbdbe3149712800e` | `[PATH]` | `[VERSION]` |
| r2 | `[TIME]` | `[TIME]` | `[PATH]` | `[SHA]` | `[SHA]` | `[SHA]` | `[PATH]` | `[VERSION]` |
| r3 | `[TIME]` | `[TIME]` | `[PATH]` | `[SHA]` | `[SHA]` | `[SHA]` | `[PATH]` | `[VERSION]` |

Required source artifacts for the final report:

- finalized `RUN_MANIFEST.json` and human-readable manifest for each replicate;
- frozen task, persona, prompt, runner, and runtime-config snapshots with SHA-256;
- deterministic per-replicate and combined post-hoc JSON/Markdown;
- environment-validity audit JSON/Markdown for every selected numeric cell;
- raw report after experience judging;
- excluded-attempt ledger and descriptive external-noise evidence;
- separate record of the excluded cap-8 pilot.

## 6. HTML companion

Match the established Shopping HTML convention while sourcing every value from
the finalized Food Markdown/JSON:

1. title and protocol-qualified subtitle;
2. four headline cards: selected numeric, completion, KEEP, EXCLUDE_RERUN;
3. result-by-arm table;
4. prominent interpretation-boundary callout;
5. replicate/environment table;
6. persona-experience table;
7. conclusion callout and limitations;
8. footer linking the actual canonical Food report and combined post-hoc file.

Do not copy Shopping's stale footer reference. The Food HTML footer must point
to files that exist in the repository.
