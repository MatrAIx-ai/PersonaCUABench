# Food & Drink / main-style Persona Experiment Plan

> Date opened: `2026-09-28` (America/Los_Angeles)
> Branch: `codex/food-main-2026-09-28`
> Base protocol: local `main@4a1c0f2`
> Upstream task snapshot: `Odysseys@837814633ef948479abb3d142458f0acdb73fa65`

## 1. Scope

This experiment applies the same causal comparison structure used for the
Shopping study to the six assigned Food & Drink tasks:

```text
per formal replicate
  6 tasks × (4 Food personas + none control) = 30 cells

formal series
  30 cells × 3 independent replicates = 90 cells
```

Every persona runs every task. A persona is not assigned to only one task.
This complete task-by-arm design permits paired comparisons within the same
task and replicate, so site/task difficulty is not confused with a persona
effect.

The attachment lists Food ownership as `TBD - Jade Xu`; this branch does not
change team ownership and records it as unresolved metadata only.

## 2. Frozen Food tasks

The attachment contains truncated summaries for several tasks. Formal inputs
therefore use the canonical full task text and rubrics recovered from the
repo-local upstream snapshot rather than the truncated pasted text.

| Difficulty | Task ID | Short label | Rubric items |
| --- | --- | --- | ---: |
| Easy | `082aa17f3e88c3ce10796244e3677c5643dd19c9` | Brussels sprouts, Le Creuset, dishwasher air gap | 4 |
| Easy | `0ab48db6076089bbcf42047d162009a50eb9ca50` | Lentils, turkey chili, make-ahead desserts | 4 |
| Easy | `eb8a01554a84cf5d16a84a766d0f6cfb55d33c81` | Minneapolis bar caterers and mulligatawny | 4 |
| Medium | `5944875c7f32a98df978040e4447534f7ba0aadb` | BOTW desserts and presentation setup | 7 |
| Medium | `18ddad3e0781d4b8fb2e1998ff836a0b07d0cdce` | Boston business and anniversary dinners | 4 |
| Medium | `e20742e26a4d6f9c3d62a9d1cef634297bd4204f` | UK Christmas menu and gifts | 7 |

There are 30 original rubric items per arm per replicate and 450 rubric-item
judgements across the full 90-cell series.

## 3. Persona arms

All four profiles use the same 36 MatrAIx schema dimensions. Only values differ.
They are hand-specified experimental archetypes, not sampled population
representatives, so results must not be generalized to demographic groups.

### P1 — Budget Novice (`food-budget-novice`)

A 25–34-year-old early-career home cook with lower-middle income. Digitally
fluent and mobile-first, but a beginner at cooking research; cost-sensitive,
impatient, intuitive, and interested in short practical answers. This profile
tests whether bargain focus and low patience cause hard requirements to be
compressed or omitted.

### P2 — Cautious Dietary Planner (`food-cautious-dietary-planner`)

A 55–64-year-old working adult who manages a food allergy and uses a magnifier.
Risk-averse, skeptical of unsupported claims, patient, nutrition-aware, and
detail-leaning. This profile tests dietary-safety verification, readable page
selection, uncertainty handling, and accessibility.

### P3 — Busy Host (`food-busy-host`)

A 35–44-year-old middle-income operations manager who cooks frequently and
hosts household events under deadline pressure. Comfortable with technology,
value-driven, practical, and brief-leaning. This profile tests whether the
agent can preserve logistics and comparison requirements while staying concise.

### P4 — Culinary Researcher (`food-culinary-researcher`)

A 45–54-year-old high-income culinary and hospitality director. An expert cook
and master researcher who is analytical, evidence-seeking, quality-first,
patient, and expects every detail. This is the upper-bound communication and
domain-expertise condition.

### Control (`none`)

The original canonical task text is sent directly to the executor without
persona simulation. Models, prompts, limits, task judge, and experience judge
remain the same. It is the within-task baseline for persona paired deltas.

## 4. Frozen protocol

- Persona simulator: Azure `gpt-5.6-terra`, selected by the dated preflight.
- Executor: Azure `gpt-5.6-terra` through the same unchanged Chat Completions
  tool loop as `main`.
- Task judge: unchanged original rubric judge.
- Persona experience judge: unchanged person-side judge, sampled twice and
  retained as Judge A and Judge B rather than averaged.
- Maximum steps: `50`.
- Browser: installed Google Chrome, live web, headless, fresh profile per cell.
- Original `main` browser tool surface and prompts remain unchanged.
- Formal repeats: `r1`, `r2`, and `r3`, stored under separate dated roots.

### Infrastructure-capacity decision

`main` has `MAX_TABS=8`. A rubric-level capacity audit found no Food task that
deterministically requires more than eight tabs to remain open simultaneously:
the densest task only requires three selected proof tabs at the end. Therefore
the first formal setting keeps the exact `main` cap for Shopping comparability.

Every trajectory will still be audited for an observed tab-limit hit. If the
cap materially blocks required evidence, that cell is protocol-censored and is
not counted as an executor failure. A higher-cap run, if needed to satisfy the
meeting note “without the infra limitation,” must be recorded as a separate
setting/version and cannot silently replace the exact-main result.

## 5. Evaluation dimensions

### Original task completion

- Full-task completion: rubric items met divided by all original rubric items.
- Communication coverage: original rubric items communicated by the persona or
  elicited by the executor, divided by all original rubric items.
- Communicated-only completion: met divided by communicated items. This is a
  diagnostic and does not replace full-task completion.
- Trajectory efficiency and final browser-tab evidence are retained.

### Persona experience

The unchanged person-side judge scores each result from 1–5 on:

1. asked-for fit;
2. readability for that persona;
3. actionability;
4. gap handling/proactivity;
5. overall experience.

Judge A/B agreement is reported exactly and within one point. Experience is
never blended with task completion into one score.

### Registered persona factors

1. Persona paraphrasing and dialogue may change how much of the original task
   reaches the executor and therefore change completion.
2. Among genuinely full-task-perfect cells, personas may differ in experience
   even when completion is equal. If there is insufficient full-perfect support,
   the second question is reported as unanswered rather than replaced by a
   weaker slice.

## 6. Failure and environment policy

- API/provider failure, empty model output, or unparseable judge output is not a
  scored zero; it remains unscored and is retried under the same configuration.
- A `403`, `429`, CAPTCHA, DNS failure, region wall, persistent timeout, or
  unusable page triggers `EXCLUDE_RERUN` only when it materially blocks required
  or communicated evidence.
- Recovered or irrelevant errors do not automatically invalidate a cell.
- Environment-blocked cells remain available as raw observations but count as
  no valid result pending a configuration-matched environment reattempt; they
  are not labeled executor failures.
- The Boston task's relative “next two days” requirement is evaluated against
  the actual dated run window and recorded in the manifest.

## 7. Run order and deliverables

1. Validate tasks and generated profiles offline.
2. Preflight the configured API deployment and unchanged function-tool loop.
3. Generate and audit 24 persona openings before browser execution.
4. Run r1–r3, 30 cells per replicate, with exact per-cell result directories.
5. Run experience Judge A/B for every numeric result.
6. Produce dated manifests, raw summary, environment-validity ledger, combined
   post-hoc analysis, and a final Food Markdown/HTML report.
