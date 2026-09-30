# src/ — the runner

How a cell runs, what it records, and how to extend it. The overview, the task
and persona counts and the model table are in the [root README](../README.md).

## Pipeline

| role | model | sees | does |
|---|---|---|---|
| Persona | `gpt-5.6-terra` (Azure) | its profile + the task as its own need | writes the request in character, answers the agent's questions |
| CUA | one of the nine | only what the persona said | browses a real Chrome, may ask back (≤ 5), gives a final answer |
| Rubric judge | `gpt-5.6-terra` (Azure) | task, conversation, actions, answer, open tabs | per rubric item: `met`, `communicated` |
| Experience judge A | `gpt-5.6-terra` (Azure) | the same, plus who the person is | P1–P5, 1–5 each |
| Experience judge B | `claude-opus-4.8` (OpenRouter) | the same prompt, independently | P1–P5, never averaged with A |
| REAL checker | none — a Python script | the sandbox's final state | SUCCESS or FAILURE |

Two judges from two vendors is the point of judge B: their agreement is what
licenses the experience numbers (290 of 300 dimension pairs within one point in
the first full run).

## Task suites

`benchmark/v1_tasks.json` is the source of truth. `prepare_v1.py` turns it into
suites and refuses to invent anything for a source it cannot run:

```bash
python src/prepare_v1.py            # rewrite the suites from the manifest
python src/prepare_v1.py --check    # fail if they have drifted
python src/task_router.py suites    # what is registered
```

- `odysseys` — 38 live-web tasks, 206 rubric items, judged by the rubric judge.
- `real` — 36 sandbox tasks. `prepare_real.py` fetches their checkers from
  agisdk at a pinned commit; the runner loads the task's starting state through
  the site's `/config`, reads the final state from `/finish`, and applies the
  task's checks to it. Three kinds, and a task may carry several:

  | check | where it lives | costs |
  |---|---|---|
  | vendored agisdk script | `src/real_evals/eval_*.py`, must print SUCCESS | nothing |
  | `jmespath` | a query and expected value in the manifest, run on the final state | nothing |
  | `llm_boolean` | a yes/no rubric in the manifest, asked of the judge about the agent's answer | one judge call |

  34 tasks use scripts; the two FlyUnified tasks use manifest checks only (11
  jmespath queries and one `llm_boolean`). A task passes only if every check
  passes. A check that cannot run leaves the cell **unscored with the reason**,
  never at zero, so a broken checker never looks like a failing agent —
  including an `llm_boolean` task judged with no judge model configured.
- Nothing in the manifest is unrunnable as of 2026-09-29. Should a later task
  need a runtime this repo lacks, `prepare_v1.py` reports it as not prepared
  instead of dropping it.

The per-scenario suites of the earlier assignment (`main-original`, `shopping`,
`science-education`) are **retired**: v1 owns their task ids and the router
requires ids to be globally unique. Their data is still on disk and
`task_router.TaskCatalog.load_retired("shopping")` still loads one on its own,
which is how the matched-pair tests keep running against real data.

## Adding tasks

1. Add the entries to `benchmark/v1_tasks.json` — Odysseys entries carry their
   own `rubrics`, REAL entries a `url` and `evals`.
2. `python src/prepare_v1.py` (and `prepare_real.py` first, for REAL).
3. If the new tasks bring a domain no family claims, `persona_assignments.py`
   will say so by name. Add the domain to `DOMAIN_FAMILY`, and if it needs a new
   family, add its four personas to `make_personas.py`, its five dimensions to
   `FAMILY_DIMENSIONS` and their per-role values to `FAMILY_DEFAULTS`.
4. `python src/persona_assignments.py --check --write`.

## Adding or changing personas

Never edit a file under `src/personas/`; they are generated.

```bash
python src/make_personas.py                 # rewrite them from PROFILES
python src/make_personas.py --check         # fail if a file has drifted
python src/persona_assignments.py --check   # every task still has four
```

A persona is the shared 32 dimensions plus its family's five, always 37. The
family default for its role fills what the profile does not say and the profile
always wins. `make_personas.py` refuses, rather than quietly accepting: a value
the schema does not allow, a family with anything but five own dimensions, a
family dimension that duplicates a shared one, a profile that sets another
family's dimension, two personas with identical values, and a persona missing
one of the five branching dimensions (`BRANCHING_DIMENSIONS`: age, education,
income, seniority, time pressure).

## Setup

```bash
pip install -r src/requirements.txt   # also needs Google Chrome installed
cp .env.example .env                      # repo root
bash scripts/check_all.sh                 # every offline check, real exit code
```

`scripts/check_all.sh` runs the self-checks without a key, a browser or the
network: the pipeline, the accounting and caching, pair separation, the
Responses shim, the suites against the manifest, the personas against their
generator, the task-persona assignment, and the model routes. Run it before
pushing. The three `test_*.py` live in `scripts/` beside it; everything that
runs a cell lives in `src/`.

`src/run.py` reads `.env` from the **repository root**. For the local Azure
setup, `.env` contains only `AZURE_OPENAI_API_KEY_FILE=azure_api_key.txt` and
`AZURE_OPENAI_BASE_URL=...`; the secret itself remains in the ignored,
permission-restricted key file. Direct `OPENAI_API_KEY=...` and exported shell
variables remain supported, but a key file avoids copying a secret into shell
history. The OpenAI SDK route is used because the Azure project endpoint is
OpenAI-compatible.

## Draft task sets

`--tasks-file /path/to/draft.json` runs an unregistered list without touching
the manifest: a plain task list, or an object with `suite_id`, `title`,
`version`, `default_personas` and `tasks`. A plain list gets a content-derived
ad-hoc id, so renaming the file does not orphan its results, and an explicit
ad-hoc id may not shadow a registered suite.

The router rejects malformed tasks, duplicate ids (including ids duplicated
across suites), paths that escape `src/`, invalid ordinals and ambiguous id
prefixes — all before any model call.

## Two settings, nine models, and the bill

`--setting` labels an experiment and namespaces its results, so the two designs
never share a directory or a report row:

| setting | personas | question it answers |
|---|---|---|
| `s1` | one per group of people, tens of dimensions set at once | how differently is each group served? |
| `s2` | matched pairs, one dimension flipped, everything else held | which single dimension causes the difference? |

```bash
SETTING=s1 MODELS="glm-5.3" bash src/run_all.sh        # grid, judges, reports
SETTING=s2 MODELS="glm-5.3 terra" bash src/run_all.sh  # 3 replicates each
DRY_RUN=1 SETTING=s2 MODELS=terra bash src/run_all.sh  # plan only, no spend
```

**Models under test** live in `src/models.json`. A run names one by its short
key and the key resolves to **Azure when that model is deployed there** (free for
this project) and to OpenRouter otherwise -- so putting a deployment name in a
model's `azure` field is all it takes to stop paying for it.

```bash
python src/models.py                 # what each key resolves to right now
python src/models.py --probe         # ask Azure which of these ids it serves
python src/models.py --estimate 294  # price a plan of 294 cells per model
```

Gemini 4 Pro is in the registry as `gemini-pro` pointing at Gemini 3.1 Pro:
Google confirmed Gemini 4 is training but has shipped no model, id or price.
Repoint that one entry when it exists.

**Prompt caching is on by default and `--no-prompt-cache` turns it off**, because
the bill is itself a measurement here -- the collaborator sees the Azure spend,
and a run whose caching state is unknown cannot be costed. The switch only
governs our own breakpoints: OpenAI/Azure, Grok, Moonshot, DeepSeek and Z.AI
cache automatically whatever we pass, so an "off" run is only truly uncached on
Anthropic and Qwen. Every run records which it was in
`run_config.prompt_cache` and `run.arm.prompt_cache`. Every step resends the transcript, so the cacheable
prefix is most of the bill. Anthropic and Qwen only cache what an explicit
breakpoint marks, so those runs carry `cache_control` on the system prompt and
the newest few turns (four breakpoints, Anthropic's limit); the rest of the
providers cache on their own. A provider that rejects a breakpoint gets one
plain retry and is never marked again in that process, so a caching optimisation
cannot lose hours of browsing. Measured second-call cost on a repeated prefix,
2026-09-26: Opus 5.5 0.10x, GPT 6 Astra 0.09x, Kimi K3 0.12x, Grok 4.7 0.30x;
Gemini 3.1 Pro, GLM 5.3, MiniMax M3 and Qwen reported no cached tokens at all.
Those factors live in `models.json` as `cache_read_multiplier` and feed
`models.py --estimate`, which prices a plan both ways.

**Every run records its own bill and clock.** `result.json` carries
`accounting`: one entry per model call (role, model, provider, tokens, cached
tokens, dollars, milliseconds) plus per-role and per-cell totals, and
`run.timing` holds the wall clock. OpenRouter's reported charge wins over the
registry's list price; a call nobody can price is counted in `unpriced_calls`
rather than silently treated as free.

```bash
python src/cost_report.py src/results/s2 --csv cells.csv
```
gives cost and minutes per setting, per model and per task, with judge spend
kept separate from browsing spend.

**Screenshots are kept by default.** Every page-changing tool call and every tab
left open at the end writes a JPEG under the cell's `shots/`, referenced from
the trajectory entry (`screenshot.file`). The agent never sees them -- it works
from text -- but a person reading a trajectory cannot otherwise tell a captcha
wall from a page that simply had little text, and that distinction decided
several scores in earlier runs. Keeping them means Chrome must load images,
which costs memory, and roughly 1-3 MB of disk per cell; `--no-screenshots`
turns them off and records that it did.

**Reasoning traces are kept where the provider gives them.** OpenRouter models
return the chain of thought in the message (`reasoning`, `reasoning_details`).
Azure/OpenAI chat completions return a `reasoning_tokens` count and no text, so
those calls go through the **Responses API** instead (`src/responses_shim.py`
converts in both directions; the rest of the pipeline still speaks chat
completions). Same deployment, same tokens, same tool calling, plus a reasoning
summary when the model reasoned enough to have one -- a short turn has no
summary to give. `--no-responses-api` switches back.

**Every step is kept.** `run.turns` holds one entry per model turn with the
provider's whole response -- content, tool calls, and the reasoning trace when
the provider returns one -- plus that turn's tokens, cost and latency.
`run.trajectory` holds each tool call with its arguments and the full result the
model was given (`result`), next to the short `result_preview` the judge reads.

## Output

`src/results/<setting>/<suite>/<task-id>/<task-hash>/<persona>__<model>__<resume-hash>__<stamp>/`
(gitignored; `/` in a model id becomes `-`). Each cell holds `result.json`, a
`shots/` directory with one JPEG per step and per tab left open, and for a REAL
task `real_state.json` — the site's final state, the evidence its checker read,
kept beside the record with its hash because it is a quarter of a megabyte.

`result.json` carries `run.conversation`, `run.turns` (every model response,
reasoning included where the provider returns it), `run.trajectory` (every tool
call with its arguments, full result and screenshot), `run.answer`,
`run.open_tabs`, `run.stop_reason`, `run.timing`, `judgement`, `experience`,
`provenance` and `accounting`.

Version-2 results also store `suite_id`, a `suite_snapshot` (title, version,
catalog hash, shard source, and task index), `task_sha256`, and the complete
`task_snapshot`. They also freeze a secret-free `run_config` and its hash
(models/providers/backends, endpoint hashes, temperatures, step budget,
persona-profile hash, prompt hashes, browser policy, and replicate ID). A
matched-pair run additionally freezes the protocol hash and task-specific
adherence rubric in its persona snapshot, plus the planned pair order and a
content-addressed persona-opening cache key. Preview and execute reuse the exact
same opening when their task/profile/model/prompt/temperature/replicate identity
matches. A separate local
`resume_config` hashes the actual Chrome-profile path without exposing it.
`--skip-existing` reuses a score only when task, comparable run configuration,
and local resume identity all match. Reports use full IDs and task hashes
internally and accept `--suite`, `--tasks-file`, or `--all-suites`; old
short-path results remain readable and unverified legacy task revisions are
shown separately.
Report arm names end in `#<comparison-config-hash>`; task-bound opening-cache
and pair-order fields are excluded so one persona/replicate remains comparable
across task rows. `#legacy` means an older result did not freeze enough
configuration to prove it matches a newer run. If the same task/arm/config was
run with multiple browser-profile identities, the report retains each one with
a `~profile-<hash>` suffix instead of silently choosing the newest.

Running `experience_judge.py` adds `experience` (P1-P5, two judge outputs and
agreement). Running `persona_fidelity_judge.py` adds `persona_fidelity`
(per-target 0/1/2 expression scores, an independent contradiction flag,
evidence, issues and confidence). The
profile values and hash are frozen into the run before browsing, so later YAML
edits cannot silently change what is judged. These axes remain separate from
task success.

The fidelity field is specifically **persona target-expression coverage**, not
one overall or cross-persona fidelity score. A zero can mean that this task gave
the persona no natural reason to express a target; compare individual evidence
and contradictions, not just raw target counts. Future task-specific persona
rubrics can narrow the denominator further.

New runs freeze the complete task text and rubrics in `task_snapshot`, freeze
their suite routing metadata, and record the API backend separately from the
provider name. Post-hoc judges prefer those frozen snapshots; legacy results
are explicitly marked unverified when a live task/profile fallback is
unavoidable. A legacy result without a suite is resolved across the catalog by
its full task ID rather than against whichever suite happens to be the default.

Prompts live in `src/prompts/*.md`, one per role, and are loaded at import:
`agent.md`, `persona_user.md`, `persona_user_matched_pair.md`,
`rubric_judge.md`, `experience_judge.md`, and `persona_fidelity_judge.md`. The
matched-pair persona prompt enforces complete original-rubric communication;
the exploratory persona prompt intentionally allows natural omission. Each
file's leading HTML comment lists its placeholders and is stripped before the
text reaches a model.

Check a low score before you trust it. If the trajectory shows `403`, a captcha,
or empty page reads, the environment failed, not the agent. Rerun the cell and
tell us.
