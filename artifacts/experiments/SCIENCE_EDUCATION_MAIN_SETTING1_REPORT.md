# Science and Education — main / Setting 1 report

Owner: Jiashu He. Plan and design: [`SCIENCE_EDUCATION_MAIN_EXPERIMENT_PLAN.md`](../../SCIENCE_EDUCATION_MAIN_EXPERIMENT_PLAN.md).
Base `main@4a1c0f2`, runner, prompts, rubrics and judges unmodified.

## Status

- **Terra: complete.** Three replicates, 90/90 cells scored, 90/90 with both experience
  judgements, every cell audited by hand.
- **The other execution backbones: not run, blocked on OpenRouter credit.** Seven of the
  nine candidates passed the tool-loop preflight, but the OpenRouter account ran out of
  credit before their grid could run. See [section 4](#4-what-is-needed-from-the-maintainers).

## 1. Terra results (r1–r3)

Execution `openai/gpt-5.6-terra` via OpenRouter; persona simulator, rubric judge and both
experience judges `gpt-5.6-terra` on the direct OpenAI API. All numbers are raw
observations from four hand-built archetypes, one profile each, so they describe these
four profiles, not the populations they stand for.

### 1.1 Task completion, mean over three replicates

| arm | T1 LGM study | T2 mini lesson | T3 AI explainer | T4 grad outreach | T5 law schools | T6 MH evidence | 6-task macro |
|---|---:|---:|---:|---:|---:|---:|---:|
| none (control) | 0.500 | 0.917 | 0.833 | 0.429 | 0.667 | 0.905 | **0.708** |
| Faculty advisor | 0.500 | 0.750 | 0.889 | 0.571 | 0.833 | 0.476 | **0.670** |
| K-12 teacher | 0.250 | 0.750 | 0.722 | 0.334 | 0.750 | 0.714 | **0.587** |
| First-gen applicant | 0.000 | 0.583 | 0.445 | 0.238 | 0.417 | 0.333 | **0.336** |
| Parent helper | 0.000 | 0.667 | 0.667 | 0.571 | 0.583 | 0.714 | **0.534** |

All 90 cells: cell-macro `0.567`, rubric micro `273/480 = 0.569`.

| replicate | cell-macro | rubric micro | communicated coverage (micro) |
|---|---:|---:|---:|
| r1 | 0.610 | 99/160 = 0.619 | 138/160 = 0.863 |
| r2 | 0.587 | 92/160 = 0.575 | 136/160 = 0.850 |
| r3 | 0.504 | 82/160 = 0.513 | 140/160 = 0.875 |

### 1.2 Environment validity

Audited cell by cell: [`2026-09-28/ENV_AUDIT_terra_r1-r3.md`](2026-09-28/ENV_AUDIT_terra_r1-r3.md).
**KEEP 89 / EXCLUDE_RERUN 1.** Google served no bot wall in any cell (743 successful
searches). The one exclusion is r3, task 3, first-gen applicant: the Tom's Hardware article
the persona asked about timed out twice and the fallback source returned 403. PubMed's search
page showed a reCAPTCHA wall in several task 6 cells, but in every one the agent reached the
peer-reviewed article through Google and PMC instead, so those are kept. Most other signals
were URLs the agent built wrongly (a search string typed as a hostname, an added `www.`).

Environment-valid subset (89 cells): cell-macro `0.568`, micro `270/474 = 0.570`. The one
exclusion barely moves anything. Its configuration-matched reattempt needs OpenRouter, so it
is still pending.

### 1.3 Persona factor 1 — how the persona's way of asking changes completion

Paired against `none` on the same task and replicate:

| persona | completion delta | communicated coverage | communicated-only score |
|---|---:|---:|---:|
| Faculty advisor | −0.038 | 0.916 | 0.701 |
| K-12 teacher | −0.122 | 0.830 | 0.649 |
| Parent helper | −0.175 | 0.811 | 0.584 |
| First-gen applicant | **−0.372** | 0.701 | **0.390** |

- **What gets dropped is almost always a named tool or site.** The rubric items personas
  most often left unsaid are "use Google" (task 2), "use Bing" (task 1), the Wikipedia track
  list (task 6), the 10015.io converter (tasks 1, 2) and "open it in a new tab" (task 3). The
  persona states the goal in its own words and the specific tool falls away.
- **First-gen applicant loses more than omission explains.** Its communicated-only score is
  0.390, far below the others, so even the requirements it did state were met less often.
  Short, plain requests leave the agent more room to pick the wrong source.
- **The agent never asked.** `ask_user` was used 0 times in all 90 cells, control and
  persona arms alike. With a zero baseline, any question in a persona arm would have been
  attributable to the persona; none occurred. Every requirement a persona left out stayed out.

### 1.4 Persona factor 2 — satisfaction

Two independent `gpt-5.6-terra` calls (A and B) per cell. This is same-model
self-consistency, not cross-model agreement.

| dimension | A mean | B mean | exact | within one |
|---|---:|---:|---:|---:|
| P1 asked for | 3.87 | 3.87 | 73/90 | 89/90 |
| P2 readable for them | 4.59 | 4.56 | 77/90 | 90/90 |
| P3 actionable | 3.97 | 3.98 | 70/90 | 89/90 |
| P4 gap handling | 3.78 (n=86) | 3.77 (n=81) | 44/80 | 77/80 |
| P5 overall | 3.82 | 3.82 | 69/90 | 89/90 |
| **all** | | | **333/440 = 75.7%** | **434/440 = 98.6%** |

P5 overall by arm (A/B mean, 18 cells each):

| arm | P5, all cells | P5 where the original task scored 1.0 |
|---|---:|---:|
| none (control) | 3.67 | 3.88 (n=4) |
| Faculty advisor | 3.67 | 3.88 (n=4) |
| K-12 teacher | 4.00 | 4.00 (n=1) |
| First-gen applicant | 3.83 | — (n=0) |
| Parent helper | 3.94 | — (n=0) |

Satisfaction does not follow completion. The three lower-completion personas rate the
result as well as or better than the control and the faculty advisor, who score highest on
completion. Only 9 of 90 cells completed the original task fully, and none of those were
first-gen or parent, so the planned "same perfect result, different satisfaction" slice is
too thin to conclude from.

## 2. The other execution backbones

Preflight (2026-09-28, main's own tool path): Claude Opus 5.5, GPT 6 Astra, Kimi-K3,
Grok 4.7, MiniMax M3, GLM 5.3 and Qwen 3.8 27B pass through OpenRouter. Muse Spark 1.1 is
blocked by an OpenRouter account-level 18+ confirmation. Gemini V4 Pro does not exist on
either provider and was not substituted. Record: [`2026-09-28/API_MODEL_PREFLIGHT.md`](2026-09-28/API_MODEL_PREFLIGHT.md).

The grid for the seven started and stopped when the OpenRouter account ran out of credit.
The account held $25 in total; the key carries a $100 limit, which is a cap above the
balance, so the runner's budget guard, which read the key's remaining limit, did not see it
coming. From 05:22 UTC on 2026-09-29 every call returned 402. Those attempts are kept under
`science-education-main-setting1-r1/provider-failures/` and are not scored.

Before that, one cell per executor completed, task 1 × `none`. With n = 1 per model this
only shows that each backbone completes the full loop; it supports no comparison.

| executor | task 1 × none | steps |
|---|---:|---:|
| Claude Opus 5.5 | 0.750 | 25 |
| GPT 6 Astra | 0.750 | 22 |
| Kimi-K3 | 0.750 | 27 |
| Grok 4.7 | 0.750 | 57 |
| MiniMax M3 | 0.750 | 38 |
| GLM 5.3 | 0.750 | 42 |
| Qwen 3.8 27B | 0.750 | 42 |
| GPT 5.6 Terra (r1, r2, r3) | 0.500, 0.500, 0.500 | 31, 28, 30 |

Kept under `science-education-main-setting1-r1/partial-executors-unfunded/`.

## 3. How it was run

`6 tasks × (4 personas + none) = 30 cells` per replicate, `temperature 1`, `max_steps 50`,
`MAX_TABS 8`, headless, one fresh Chrome profile per cell seeded from an identical warm
cookie template, task-major order with persona order rotated per task. Each block holds its
`RUN_MANIFEST.json`, the exact `inputs/` that ran, `results/` and per-cell `logs/`. The
scripts used are in [`analysis/`](analysis/); they were run from the contributor's working
tree, so their paths assume that layout.

## 4. What is needed from the maintainers

1. **Credit for the cross-executor grid.** One replicate of the seven passing backbones is
   210 cells. From Terra's measured cost ($4.85 per 30 cells, $12.53 for all three
   replicates) and the models' OpenRouter input prices, that is roughly **$150–200**, most
   of it Astra and Grok. Either top up the OpenRouter account behind this key, or say if you
   would rather these run on your Azure deployments; the runner takes any provider main
   supports.
2. **The one pending reattempt** (r3 × task 3 × first-gen) needs the same credit.
3. **Muse Spark 1.1** needs the OpenRouter account's 18+ confirmation to be completed.

Everything above will be rerun into new dated blocks as soon as credit is available; the
Terra results here do not depend on it.
