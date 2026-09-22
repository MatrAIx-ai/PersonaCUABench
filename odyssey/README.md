# Odysseys × MatrAIx Personas

A MatrAIx persona holds an [Odysseys](https://odysseysbench.com/) task as its own need
and asks a computer-use agent (CUA) for help in its own words. The CUA does the task
in a real Chrome on the live web, and a judge grades the result against the task's rubric.

For the formal Ecommerce & Shopping matched-pair protocol and exact execution
commands, start with [`task_suites/shopping/README.md`](task_suites/shopping/README.md).
Contributors adding another task or scenario should follow the repository-wide
[`task/persona/OSWorld guide`](../docs/adding-tasks/README.md).

## Pipeline

| Role | Model | Input | Output |
|---|---|---|---|
| Persona LLM | `qwen/qwen3.8-27b` (OpenRouter) | persona profile + Odysseys task | the request in character; answers the CUA's questions |
| CUA | `qwen/qwen3.8-27b` (OpenRouter) | only what the persona says | browses, may `ask_user` ≤ 5 times, final answer |
| Judge | `gpt-5.6-terra` (Azure) | task, conversation, actions, answer, open tabs | per rubric item: `met`, `communicated` |

These are the legacy exploratory defaults in `run.py`. Within any comparison,
pin the models and `--max-steps` (default 50) and do not change them between
arms. The formal Shopping/Azure commands below intentionally override the
legacy model defaults with GPT-5.6 Terra.

- **Personas**: legacy examples live in `personas/*.yaml`; formal suite-scoped
  matched pairs live in `personas/<suite>/matched_pairs/*.yaml` and are generated
  from the suite protocol by `make_matched_personas.py`. `none` is the control:
  the Odysseys text is sent verbatim.
- **Tasks**: routed by `task_suites.json`. This branch defaults to `shopping`;
  `main-original` preserves the shared `tasks.json`. Tasks are numbered 1..N
  within their selected suite.
- **Scores**: `score` = met / all rubric items. `score_communicated` = met / only
  the items that came up in the conversation.

## Setup

```bash
git clone git@github.com:MatrAIx-ai/PersonaCUABench.git && cd PersonaCUABench
pip install -r odyssey/requirements.txt   # also needs Google Chrome installed
cp .env.example .env                     # repo root; both files are explained below
python3 odyssey/test_pipeline.py          # offline self-check
```

`odyssey/run.py` reads `.env` from the **repository root**. For the local Azure
setup, `.env` contains only `AZURE_OPENAI_API_KEY_FILE=azure_api_key.txt` and
`AZURE_OPENAI_BASE_URL=...`; the secret itself remains in the ignored,
permission-restricted key file. Direct `OPENAI_API_KEY=...` and exported shell
variables remain supported, but a key file avoids copying a secret into shell
history. The OpenAI SDK route is used because the Azure project endpoint is
OpenAI-compatible.

## Task suites and future batches

All task consumers use `task_router.py`: the runner, grid, report, and legacy
judge fallback therefore agree on which task is being used.

```bash
python odyssey/run.py --list-suites
python odyssey/run.py --suite shopping --list-tasks
python odyssey/run.py --suite main-original --list-tasks
```

The `*` in `--list-suites` marks the default. The manifest currently selects `shopping`,
so the old `--task 1` shorthand still selects Kobe. Use a full task ID in
automation; numeric positions are convenient interactively but can move when a
new shard sorts before an older one.

There are three extension paths:

1. **Add another Shopping batch.** Put an unchanged Odysseys task list in a
   new file such as `task_suites/shopping/2026-q4.json`. The registered
   `task_suites/shopping/*.json` glob picks it up automatically, in filename
   order. No Python or manifest edit is needed.
2. **Add another domain.** Put its JSON file(s) under `task_suites/<suite>/`
   and add one suite entry to `task_suites.json`, including a stable ID, title,
   version, file paths/glob, and default personas.
3. **Try an unregistered draft.** Pass `--tasks-file /path/to/draft.json`.
   A plain task list works; an object may also contain `suite_id`, `title`,
   `version`, `default_personas`, and `tasks`. Plain lists get a content-derived
   ad-hoc suite ID, so renaming the file does not orphan its results; an explicit
   ad-hoc ID may not shadow a registered suite.

The router rejects malformed tasks, duplicate IDs (including IDs duplicated
across registered suites), paths that escape `odyssey/`, invalid ordinals, and
ambiguous ID prefixes before any model call. Details and the shard schema are
also in [`task_suites/README.md`](task_suites/README.md).

## Your job

**1. Branch.** Work only on your own branch. Don't push to `main`.

```bash
git checkout -b <your-name>
```

**2. Tasks.** Copy assigned entries unchanged, by `task_id`, from
[`ljang0/Odysseys`](https://github.com/ljang0/Odysseys) `data/odysseys.json`
into a suite shard. Do not replace the shared `odyssey/tasks.json`; it is kept
as the `main-original` compatibility suite. For this assignment, add later
Shopping batches under `odyssey/task_suites/shopping/`.

**3. Personas.** Define 3–6 controlled matched pairs: exactly 6–12 named
personas per scenario. `none` is extra and is not counted. Put the protocol at
`task_suites/<suite>/personas/persona_experiment.json`, register it in
`task_suites.json`, and let the shared generator create the YAML. Within each
pair only one official MatrAIx dimension may change; the other baseline values,
display name, task, models, prompts, limits, and replicate must remain fixed.

```bash
python3 odyssey/make_matched_personas.py --suite shopping --check
python3 odyssey/run.py --suite shopping --task 1 \
  --persona mp_evidence_verification_positive --replicate-id preview --preview
```

Check both arms before running. They must preserve the same task while clearly
expressing opposite, task-relevant behavior. Full schema and review rules are
in [`task_suites/README.md`](task_suites/README.md).

**4. Run.** `run_grid.sh` is available for exploratory Cartesian grids using
legacy/default personas:

```bash
TASK_SUITE=shopping PERSONAS="none <p1> <p2> <p3>" \
  nohup bash odyssey/run_grid.sh > grid.log 2>&1 &
python3 odyssey/report.py --suite shopping                    # tables
```

If it's interrupted, run the same command again. It picks up where it stopped.
If `PERSONAS` is omitted, the suite's manifest defaults are used. `TASKS="1 4"`
still limits a grid; automatic grids use full stable IDs. A different suite can
be selected with `TASK_SUITE=main-original` or `--suite main-original`. For an
ad-hoc file, use `TASKS_FILE=/path/to/draft.json`. For a single default-suite
cell: `python3 odyssey/run.py --task 1 --persona <p1> --headless`.

Do not use that Cartesian grid for a formal matched-pair experiment: it runs
personas on tasks where their axes are not applicable. Use the protocol-aware
planner instead. Its default is a dry run:

```bash
python3 odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --headless
```

Shopping must report 36 applicable cells, not 72. Add `--execute --` followed
by the normal `run.py` model/provider options only after reviewing the plan.

For the local Azure GPT-5.6 Terra setup, run a real persona arm and its two
separate persona-side evaluations with:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run.py \
  --suite shopping --task 1 --persona budget-student \
  --model gpt-5.6-terra --provider openai \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --judge-model gpt-5.6-terra --judge-provider openai \
  --temperature 1 --max-steps 50 --headless \
  --profile artifacts/chrome-profiles/budget-student \
  --out artifacts/main-playwright-results

# P1-P5: how well the CUA served this particular person. Pass the new run
# directory, not the whole results root, if only that run should be scored.
.osworld/OSWorld/.venv/bin/python odyssey/experience_judge.py \
  --results <new-run-directory> \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra

# Fidelity: whether the simulated user clearly expressed each frozen,
# behaviorally observable persona target (0/1/2 per target).
.osworld/OSWorld/.venv/bin/python odyssey/persona_fidelity_judge.py \
  --results <new-run-directory> \
  --judge-model gpt-5.6-terra --judge-provider openai
```

Terra requires `--temperature 1` for the agent/persona calls. Using Terra in
both P1-P5 judge slots makes two independent calls to the same model; a genuine
cross-model agreement study still requires a second configured provider/model.
The runner defaults to a separate persistent Chrome profile at
`artifacts/chrome-profiles/<suite>/<persona>`. This prevents a stale or
still-locked profile from blocking another arm and keeps consent/captcha
cookies reproducible within that arm; `--profile` remains available for an
explicit location.

**5. Push.** Push your tasks and personas to your branch. `results/` stays
gitignored and local -- send it separately, or push it only when asked:

```bash
git add odyssey/task_suites.json odyssey/task_suites odyssey/make_personas.py odyssey/personas
git commit -m "<your-name>: tasks + personas"
git push -u origin <your-name>
```

## Output

`odyssey/results/<suite>/<full-task-id>/<task-hash>/<persona>__<model>__<resume-hash>__<stamp>/result.json`
(gitignored; `/` in model IDs is rendered as `-`):
`run.conversation`, `run.trajectory`, `run.answer`, `run.open_tabs`, `run.stop_reason`,
`judgement.verdicts`, `judgement.score`, `judgement.score_communicated`.

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

Prompts live in `odyssey/prompts/*.md`, one per role, and are loaded at import:
`agent.md`, `persona_user.md`, `persona_user_matched_pair.md`,
`rubric_judge.md`, `experience_judge.md`, and `persona_fidelity_judge.md`. The
matched-pair persona prompt enforces complete original-rubric communication;
the exploratory persona prompt intentionally allows natural omission. Each
file's leading HTML comment lists its placeholders and is stripped before the
text reaches a model.

Check a low score before you trust it. If the trajectory shows `403`, a captcha,
or empty page reads, the environment failed, not the agent. Rerun the cell and
tell us.
