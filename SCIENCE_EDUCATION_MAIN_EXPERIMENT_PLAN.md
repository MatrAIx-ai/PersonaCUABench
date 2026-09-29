# Science and Education — main / Setting 1 experiment plan

Owner: Jiashu He. Base: `main@4a1c0f2` (runner, prompts, rubrics and Haoming's person-side
judge, all unmodified). Structure follows the maintainers' Shopping reference on
`codex/shopping-main-2026-09-26`.

## Design

Setting 1: **four named personas plus the `none` control, every persona on all six tasks.**
One execution backbone therefore runs `6 tasks x (4 personas + none) = 30 cells` per
replicate. Task completion, persona-mediated communication and persona satisfaction are
reported separately and never combined into one score.

## Tasks

The six Science and Education tasks, copied unchanged by `task_id` from `ljang0/Odysseys`
`data/odysseys.json` and verified byte-identical. 32 rubric items. They are in
`odyssey/tasks.json`.

| # | level | rubrics | task_id | what it asks for |
|---|---|---|---|---|
| 1 | easy | 4 | `65c9e7d383e0` | Bing search on latent growth models, a ChatGPT prompt template, the 10015.io bionic converter, a free plagiarism checker |
| 2 | easy | 4 | `e15345ed27f1` | 5th-grade grammar quiz, 8th-grade marketing worksheet, a Slidesgo template, bionic conversion of a fixed lesson intro |
| 3 | easy | 6 | `8c30f2f9ceea` | IBM's AI/ML categories, Copilot.com, the Tom's Hardware Granite Rapids article |
| 4 | medium | 7 | `6421b906fe97` | graduate outreach across six institutions |
| 5 | medium | 4 | `4614aa083147` | three Maryland/DC law schools: outreach routes, an event, the PIPS scholarship, who to contact first |
| 6 | medium | 7 | `976970ff5d37` | youth mental-health evidence pack: three cited sources and a Wikipedia track list |

## Personas

Built from the 1,290-dimension MatrAIx schema in `odyssey/dimensions.json`, not sampled
from the persona pool: four science-and-education archetypes. All four set the same 32
dimensions and differ only in the values; `make_personas.py` checks every value against
the schema. No value is one that `persona.py` drops as nullish, so every persona renders all
32 attributes.

- **Faculty advisor** — tenured social scientist who advises graduate students. Upper bound
  on domain fluency: names sources and methods and holds the agent to citation standards.
- **K-12 teacher** — middle-school humanities teacher. Fluent in teaching, not research
  methods; wants usable material and buries the constraints in context.
- **First-gen applicant** — first-in-family community-college student, Spanish-dominant
  with intermediate English. At ease with the tools; limited English narrows what they say.
- **Parent helper** — bookkeeper researching for their children. Lower bound on technical
  and academic fluency; describes outcomes rather than naming sites and tools.

Left out on purpose: mental-health, neurodivergence, vision, text-size and accessibility
attributes. Task 6 is itself about eating-disorder research and task 2 is itself about
easier-to-scan text, so a persona with those traits would make it impossible to tell
whether the agent was serving the rubric or the persona.

Role fit: the six tasks imply mixed roles — a learner with classmates (task 1), someone
choosing a law school (task 5), someone teaching or advising (tasks 2, 4, 6). No persona
fits all six, and none of the 32 attributes contradicts a task fact, so the simulator
adapts the framing. No rubric item depends on who the user is.

| dimension | faculty-advisor | k12-teacher | first-gen-applicant | parent-helper |
|---|---|---|---|---|
| `age_bracket` | 55-64 | 35-44 | 25-34 | 45-54 |
| `life_stage` | Empty nester | Parent of young kids | Student | Mid-life |
| `highest_education` | Doctorate | Master's | Some college | Vocational / cert |
| `institution_tier` | Top-tier research | Mid-tier university | Community college | Online / bootcamp |
| `academic_field` | Social science | Humanities | Interdisciplinary | Business |
| `demo_employment_status` | Full-time | Full-time | Part-time | Full-time |
| `role_function` | Teaching | Teaching | Operations | Finance |
| `seniority` | Lead / Principal | Senior | Student / intern | Mid |
| `socioeconomic_band` | Upper-middle | Middle | Low income | Lower-middle |
| `fam_statistics` | Expert | Familiar | Aware | Proficient |
| `fam_pedagogy` | Proficient | Expert | Aware | Familiar |
| `skill_research` | Master | Advanced | Beginner | Intermediate |
| `skill_fact_checking` | Master | Intermediate | Beginner | Advanced |
| `skill_technical_writing` | Master | Advanced | Beginner | Intermediate |
| `att_higher_education` | Positive | Neutral | Enthusiast | Positive |
| `register` | Technical jargon | Colloquial | Code-switching | Formal / standard |
| `cog_formality` | Formal | Casual | Neutral | Very formal |
| `cog_directness` | Blunt | Balanced | Direct | Indirect |
| `cog_politeness` | Brusque | Polite | Neutral | Very polite |
| `cog_use_of_jargon` | Heavy | Moderate | Avoids jargon | Light |
| `pref_detail_brief_vs_full` | Brief-leaning | Every detail | Just the gist | Detail-leaning |
| `english_proficiency` | Native | Native | Intermediate (B1-B2) | Native |
| `primary_language` | English | English | Spanish | English |
| `cog_abstraction` | Abstract | Balanced | Very concrete | Concrete |
| `intent` | Get task done | Brainstorm | Learn / explain | Decide |
| `time_pressure` | Moderate | No rush | Deadline | Moderate |
| `prior_context` | Cold start | Long ongoing project | Returning user | Frustrated re-ask |
| `query_complexity` | Multi-step | Open-ended creative | Simple factual | Ambiguous / underspecified |
| `tech_savviness` | Cautious adopter | Comfortable | Digital native | Reluctant |
| `att_ai` | Skeptical | Positive | Enthusiast | Neutral |
| `trust_level` | Verifying | Trusting | Trusting | Skeptical |
| `cog_attention_span` | Very long | Long | Short | Average |

## Models and routes

| role | model | route |
|---|---|---|
| persona simulator | `gpt-5.6-terra`, temperature 1 | direct OpenAI API |
| rubric judge | `gpt-5.6-terra` | direct OpenAI API |
| experience judge A and B | `gpt-5.6-terra`, two independent calls | direct OpenAI API |
| execution | the backbones below | OpenRouter |

Every backbone was preflighted on 2026-09-28 through main's own `_client`,
`_create_with_retry` and tool schema: two turns of a real tool loop. Record:
`artifacts/experiments/2026-09-28/API_MODEL_PREFLIGHT.md`.

| backbone | OpenRouter id | preflight |
|---|---|---|
| GPT 5.6 Terra | `openai/gpt-5.6-terra` | pass |
| GPT 6 Astra | `openai/gpt-6-astra` | pass |
| Claude Opus 5.5 | `anthropic/claude-opus-5.5` | pass |
| Kimi-K3 | `moonshotai/kimi-k3` | pass |
| Grok 4.7 | `x-ai/grok-4.7` | pass |
| MiniMax M3 | `minimax/minimax-m3` | pass |
| GLM 5.3 | `z-ai/glm-5.3` | pass |
| Qwen 3.8 27B | `qwen/qwen3.8-27b` | pass |
| Muse Spark 1.1 | `meta/muse-spark-1.1` | blocked: OpenRouter requires an account-level 18+ age confirmation |
| Gemini V4 Pro | — | unavailable on either provider; not substituted |

Why execution goes through OpenRouter: on the direct OpenAI API, `gpt-5.6-terra` and
`gpt-6-astra` both reject function tools on `/v1/chat/completions` while any
`reasoning_effort` is in force. Terra accepts `"none"` but main never sends it; Astra
accepts no value that allows tools there. Through OpenRouter both run main's tool path
unmodified.

## Scale

- Terra: three replicates, r1–r3, 90 cells. Terra is not in the doc's nine execution
  candidates; it is run as an executor to match the Shopping reference, whose formal grid
  used Terra for execution because it was the only model that passed there.
- The other seven passing backbones: one replicate each, 30 cells each, as the OpenRouter
  budget allows (hard limit $100 on the key; Terra measured at $4.85 per replicate).

## Runtime

`temperature 1`, `max_steps 50`, main's `MAX_TABS 8`, headless. Each cell gets a fresh
persistent Chrome profile, seeded from one identical five-file warm cookie template, because
Google walls automated search and 8 of the 32 rubric items require a Google search. Same seed
for every cell, so no arm starts from a different browser state. Order is task-major, with
the persona order rotated per task and the executor order rotated per (task, persona) block.

`main` regenerates the persona opening in every cell; there is no frozen opening cache. The
24-opening preview gate (`artifacts/experiments/2026-09-28/PREVIEW_GATE.md`) checks a
sample, not the exact utterances that ran.

## Environment audit

`result.json` plus a numeric score proves the run completed, not that the web was usable.
Each cell is audited by hand, as in the Shopping report:

- `KEEP` — the environment was good enough to do what the persona actually asked.
- `EXCLUDE_RERUN` — a 403, Access Denied, CAPTCHA/Cloudflare, DNS failure, sustained timeout
  or unusable page stopped required or communicated evidence from being reached.
- A block on a page the persona never asked for, or one the agent recovered from, does not
  exclude.

## Results layout

```
artifacts/experiments/<date>/science-education-main-setting1-<rep>/
    RUN_MANIFEST.json   inputs/   results/   logs/
```

`inputs/` holds the exact tasks, persona YAMLs, prompts and `make_personas.py` that ran.
Chrome profiles hold session cookies and are kept outside the repository.

## Differences from the Shopping reference

- Execution routes through OpenRouter; persona and judges use the direct OpenAI API.
  Shopping used one Azure `gpt-5.6-terra` deployment for every role.
- Per-cell profiles are pre-seeded from a warm cookie template.
- Seven of nine candidate backbones pass here (Shopping: one), so this suite has
  cross-executor results that Shopping does not.
