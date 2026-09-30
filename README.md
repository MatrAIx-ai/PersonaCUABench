# PersonaCUABench

The same web task, asked for by different people, done by different agents.

A **persona model** turns a benchmark task into the request a particular person
would actually make; a **computer-use agent** does the work in a real Chrome
session, knowing only what that person said; **judges** score it three ways —
did the task get done, was it done for *this* user, and what did it cost.

    persona (GPT 5.6 Terra) ──"help me…"──▶ CUA (one of nine) ──▶ Chrome
                  ▲                                                │
                  └──────────── ask_user ◀─────────────────────────┤
                                                                   ▼
        rubric judge · experience judges A/B · deterministic state checkers

## What is in the benchmark

| | | |
|---|---|---|
| **Tasks** | 74, all runnable | 38 Odysseys on the live web, 36 REAL sandbox sites |
| **Personas** | 44 | eleven domain families × four roles, plus a `none` control |
| **Models** | 9 execution backbones | one per collaborator, listed below |
| **Cells** | 370 per model per replicate | 74 tasks × (4 personas + control) |

`benchmark/v1_tasks.json` is the source of truth for tasks, and every entry in
it is runnable here. The four ClawBench tasks that needed a harness we have no
access to were replaced (2026-09-29) by one Odysseys and two REAL tasks; they
and 25 others sit in the manifest's `dropped` list with the reason for each.
`prepare_v1.py` still reports anything it cannot prepare rather than dropping it
quietly.

**Two task runtimes, two ways of scoring.** An Odysseys task runs on the open
web and is judged against its own rubric by an LLM. A REAL task runs on a
deterministic replica of a real site (a DoorDash, a Gmail); the runner loads the
task's starting state, lets the agent work, then reads the site's final state
and applies the task's own checks — a vendored agisdk script that must print
SUCCESS, or a JMESPath query on the final state that must equal an expected
value. Both are free and deterministic. Two tasks additionally ask one yes/no
question about what the agent reported back, and only those call a model.

## Personas

Every domain family has the same four roles and every persona is described by
exactly 37 dimensions — 32 shared plus five of its family's own — so no persona
is drawn in more detail than another and the comparison across domains is like
for like. Five of the 32 are the axes the persona tree branches on, and no
persona may be silent on any of them: **age**, **education**, **income**,
**expertise** (seniority plus the family's own skills) and **time pressure**.

| role | who they are | what changes per family |
|---|---|---|
| `expert` | works in the field, wants every detail, no accessibility needs, desktop | the family's industry, skill and familiarity dimensions at their highest |
| `senior` | 65–84, cautious, reluctant with technology, low vision and a magnifier, wants the gist | the same dimensions low, plus their own health and history |
| `young` | 18–34, low income, phone-first, impatient, cost-sensitive | domain interest high, domain skill low |
| `practical` | 45–54, middle income, working to a deadline, wants a decision | domain competence in the middle |

The eleven families are `travel`, `science`, `tech`, `community`, `art`,
`lifestyle`, `ecommerce`, `health`, `food`, `productivity`, `professional`. A
food expert is a food-and-hospitality veteran who cooks at master level; a
productivity senior reaches inbox zero rarely; a professional young one is just
starting a career. Within a role the values still differ by family, so travel's
`practical` is a recent immigrant working around a language barrier while
science's is a parent hunting down free school resources.

Personas are generated, never hand-edited: `src/make_personas.py` builds
them from the MatrAIx 1,290-dimension schema and refuses any value the schema
does not allow, any family that does not carry exactly five own dimensions, and
any persona file that has drifted from the generator (`--check`). Which personas ask for which task is derived from the task's
domain, not written by hand (`src/persona_assignments.py`), so it cannot go
stale when the task set changes.

## The harness

Every model runs in **the same harness**: one Chrome, nine tools
(`open_tab`, `goto`, `read_page`, `click`, `type_text`, `list_tabs`,
`close_tab`, `ask_user`, `finish`), one observation format. That uniformity is
the control that makes a cross-model number mean anything — a benchmark where
the harness varies with the model measures model *and* harness, and cannot
separate them. Three further reasons it is not negotiable here:

- **Half the benchmark needs our browser.** The 36 REAL tasks load the task's
  starting state through the sandbox's `/config` and read the final state from
  `/finish` in the same session. A vendor harness that runs in the vendor's own
  managed desktop cannot expose that state to us, so those tasks would have no
  score at all.
- **Only four of nine models have an official harness** (Claude, GPT, Gemini,
  Qwen-CUA), and those four disagree with each other: pixel-driven, DOM-driven
  and vendor-sandboxed respectively. "Official where available" means five
  models on ours plus four mutually incompatible others.

The observation is page **text**, not pixels — `read_page` returns the visible
text, then the page's interactive fields, then any control whose only name is an
`aria-label`. Screenshots are captured every step, but for auditing a
trajectory, not for the agent: no image enters a model's context.

**The harness's own failure rate is reported, not assumed.** Over the first
trajectories, `type_text` failed 45% of calls against `click`'s 12%, because
`read_page` gave the model no element identity while `type_text` demanded a CSS
selector — the model had to invent one. Fields and handles were added for that
reason, and the same measurement is the acceptance test for any future change:

```bash
python src/cost_report.py src/results/s1      # click%, failed clicks, per arm
```

## Models

Each model resolves to a provider at run time: **the owner's own endpoint**,
then the **shared Azure deployment**, then **OpenRouter**. Fill in your own two
environment variables and every other model still works for you through
whatever else is configured. A model with no configured route raises and names
what it wants, rather than quietly running somewhere else.

| model | owner | key |
|---|---|---|
| Claude Opus 5.5 | Yiyang | `opus-5.5` |
| GPT 6 Astra | Haoming | `gpt-6-astra` |
| Muse Spark 1.1 | Xu Hu | `muse-spark-1.1` |
| Gemini 3.8 Flash | Sherry | `gemini-3.8-flash` |
| Kimi K3 | Sherry | `kimi-k3` |
| Grok 4.7 | Defu | `grok-4.7` |
| MiniMax M3 | Charles | `minimax-m3` |
| Qwen 3.8 27B | Xu Hu | `qwen3.8-27b` |
| DeepSeek V4.1 Flash | unassigned | `deepseek-v4.1` |

`python src/models.py` prints what each one resolves to on your machine, and
`python scripts/check_models.py` puts a real two-turn tool-calling exchange
through each of them — about five cents for all nine, and the only way to know
a route works before a grid depends on it. All nine were verified on
2026-09-30.
GPT 5.6 Terra is the shared persona and judge model, not an execution backbone.

## Running your model

**If you have been assigned a model, read [`RUNNING.md`](RUNNING.md)** — setup,
the checks to run before spending anything, the grid, the proactivity ablation
and how to send the results back. The short version:

```bash
git clone <this repo> && cd PersonaCUABench
python3 -m venv .venv && .venv/bin/pip install -r src/requirements.txt
cp .env.example .env            # fill in your two variables

bash scripts/check_all.sh   # every offline check, no keys, no network
python src/models.py        # confirm your model has a route

# one cell first: free if your model is on Azure, cents otherwise
python src/run.py --suite odysseys --task 1 --persona none \
  --model <your key> --setting s1 --headless

# then the grid: every task, each with its own four personas and the control
SETTING=s1 MODELS="<your key>" JOBS=4 bash src/run_all.sh
```

`DRY_RUN=1` in front of either script lists the cells without running them.
`JOBS=N` runs N cells at once, each in its own Chrome profile — budget about
1.5 GB of RAM per worker. A machine without root sets `CHROME_CHANNEL=chromium`
and uses Playwright's own browser.

## What a run records

Everything needed to reproduce, re-judge and cost a cell, written per cell:

- **the task and the run's identity** — the task and rubrics as they were at run
  time with their hash, the suite, the persona profile's hash, every model,
  provider and endpoint (hashed, never the URL), every prompt's hash, the
  browser, the commit and whether the tree was dirty
- **the whole trajectory** — each model turn's full response including its
  reasoning where the provider returns one, each tool call with its arguments
  and the entire result the model saw, and a screenshot of every step
- **the judgements** — per rubric item `met` and `communicated` with reasons,
  the experience scores P1–P5 from two independent judges with their agreement,
  and for REAL tasks the state checkers' own output beside the state that
  produced it
- **the bill and the clock** — every model call's tokens, cached tokens,
  reasoning tokens, retries, latency and dollars, split into what we paid and
  what the shared Azure endpoint was asked to do

`src/report.py` prints the scores, `src/cost_report.py` the cost, time
and navigation style, `src/judge_all.py` re-judges saved runs in parallel.

## Where things live

| | |
|---|---|
| `benchmark/v1_tasks.json` | the task set, the only source of truth for tasks |
| `benchmark/tasks.json` | one collaborator's own seven-task working slice; a record, read by nothing |
| `src/` | everything that runs |
| `scripts/` | the checks: `check_all.sh`, the three `test_*.py`, and `check_models.py` |
| `src/prepare_v1.py` | turns it into the runnable suites |
| `src/task_suites/` | `odysseys/` and `real/`, generated |
| `src/personas/` | generated persona profiles |
| `src/models.json` | the nine models, their owners, routes and prices |
| `src/prompts/` | every prompt, one file each |
| `src/run.py` | persona → CUA → judge, one cell |
| `src/run_grid.sh`, `run_all.sh` | a model's whole grid, then the judges and reports |
| `src/real_evals/` | REAL's own state checkers, vendored (Apache-2.0) |

| `RUNNING.md` | what a collaborator does with their assigned model, start to finish |

See [`src/README.md`](src/README.md) for the detail: settings, judges,
caching, the matched-pair design, and how to add tasks or personas.
