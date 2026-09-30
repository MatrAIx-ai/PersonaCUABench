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

Personas are generated, never hand-edited: `odyssey/make_personas.py` builds
them from the MatrAIx 1,290-dimension schema and refuses any value the schema
does not allow, any family that does not carry exactly five own dimensions, and
any persona file that has drifted from the generator (`--check`). Which personas ask for which task is derived from the task's
domain, not written by hand (`odyssey/persona_assignments.py`), so it cannot go
stale when the task set changes.

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
| GLM 5.3 | Charles | `glm-5.3` |
| Qwen 3.8 27B | Xu Hu | `qwen3.8-27b` |

`python odyssey/models.py` prints what each one resolves to on your machine.
GPT 5.6 Terra is the shared persona and judge model, not an execution backbone.

## Running your model

```bash
git clone <this repo> && cd PersonaCUABench
python3 -m venv .venv && .venv/bin/pip install -r odyssey/requirements.txt
cp .env.example .env            # fill in your two variables

bash odyssey/check_all.sh       # every offline check, no keys, no network
python odyssey/models.py        # confirm your model has a route

# one cell first: free if your model is on Azure, cents otherwise
python odyssey/run.py --suite odysseys --task 1 --persona none \
  --model <your key> --setting s1 --headless

# then the grid: every task, each with its own four personas and the control
SETTING=s1 MODELS="<your key>" JOBS=4 bash odyssey/run_all.sh
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

`odyssey/report.py` prints the scores, `odyssey/cost_report.py` the cost, time
and navigation style, `odyssey/judge_all.py` re-judges saved runs in parallel.

## Where things live

| | |
|---|---|
| `benchmark/v1_tasks.json` | the task set, the only source of truth for tasks |
| `odyssey/prepare_v1.py` | turns it into the runnable suites |
| `odyssey/task_suites/` | `odysseys/` and `real/`, generated |
| `odyssey/personas/` | generated persona profiles |
| `odyssey/models.json` | the nine models, their owners, routes and prices |
| `odyssey/prompts/` | every prompt, one file each |
| `odyssey/run.py` | persona → CUA → judge, one cell |
| `odyssey/run_grid.sh`, `run_all.sh` | a model's whole grid, then the judges and reports |
| `odyssey/real_evals/` | REAL's own state checkers, vendored (Apache-2.0) |

See [`odyssey/README.md`](odyssey/README.md) for the detail: settings, judges,
caching, the matched-pair design, and how to add tasks or personas.
