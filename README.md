# PersonaCUABench

PersonaCUABench measures how a computer-use agent behaves when the same web
task is requested by users with different, controlled preferences. A persona
model turns a fixed benchmark task into a natural request, the CUA works in a
real Chrome session, and independent judges score task success, communication,
persona expression, and user experience.

The registered default suite is **Ecommerce & Shopping**. Its formal
protocol uses six matched pairs: **12 named personas, 18 task–axis pairs, and
36 persona cells per replicate**. The `none` arm is a separate verbatim-task
control and is not part of the 6–12 persona budget.

## Experimental boundary

The benchmark deliberately separates four questions:

1. **Task success (R1–Rn):** did the CUA satisfy the frozen Odysseys rubric?
2. **Persona expression:** did the simulated user clearly express the assigned
   behavioral pole, beyond words already inherited from the task?
3. **CUA alignment:** did the CUA respond appropriately to what that user
   expressed?
4. **User experience (P1–P5):** was the result asked-for, readable, actionable,
   honest about gaps, and good overall for that person?

These scores must remain separate. A persona may not delete an original task
requirement to appear concise, cost-sensitive, trusting, or rushed. Likewise,
a successful task does not prove that the persona was expressed or respected.

The current code materializes task success/communication, persona expression,
and P1–P5. It does not yet write a standalone CUA-alignment verdict; do not
rename P1 or persona fidelity as alignment when analyzing this implementation.

The CUA never receives the private persona profile or hidden expert rubric. It
sees only the simulated user's utterances. The persona model may see the task
and profile, but it does not browse or execute the task.

## Repository layout

```text
.
├── .env.example
├── README.md
├── docs/
│   └── adding-tasks/README.md           # contributor task/persona/OSWorld guide
└── odyssey/
    ├── README.md                         # implementation and runner reference
    ├── dimensions.json                   # pinned MatrAIx dimension catalog
    ├── task_suites.json                  # suite router manifest
    ├── task_router.py                    # one loader for run/grid/report
    ├── task_suites/
    │   ├── README.md                     # scenario-owner contribution guide
    │   └── shopping/
    │       ├── README.md                 # Shopping protocol and runbook
    │       ├── 000-core.json             # six frozen Shopping tasks
    │       └── personas/
    │           └── persona_experiment.json
    ├── personas/
    │   └── shopping/matched_pairs/       # 12 generated YAML profiles
    ├── persona_experiment.py             # shared protocol validation
    ├── make_matched_personas.py          # generate/check profiles
    ├── run_matched_pairs.py              # applicable-cell planner/runner
    ├── run.py                            # persona + CUA + R1–Rn judge
    ├── experience_judge.py               # independent P1–P5 judges
    ├── persona_fidelity_judge.py          # 0/1/2 persona expression judge
    ├── report.py                          # aggregate result tables
    └── test_pipeline.py                  # offline self-check
```

Generated results and browser profiles live under `odyssey/results/` or
`artifacts/` and are ignored by Git. Credentials are also ignored.

## Reproducible environment

Requirements:

- macOS or Linux with Google Chrome installed;
- Python 3.10 or newer;
- the packages in `odyssey/requirements.txt`;
- an OpenAI-compatible model endpoint for real runs.

Use the existing project environment when present:

```bash
.osworld/OSWorld/.venv/bin/python -m pip install -r odyssey/requirements.txt
.osworld/OSWorld/.venv/bin/python odyssey/test_pipeline.py
```

Or create a dedicated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r odyssey/requirements.txt
.venv/bin/python odyssey/test_pipeline.py
```

The offline self-check makes no model, network, or browser call. It validates
task routing, the 6–12 persona contract, generated-profile freshness, exact
one-dimension pair deltas, and the 36-cell Shopping matrix.

## API configuration

`odyssey/run.py` reads `.env` from the repository root. Start from the tracked,
secret-free example:

```bash
cp .env.example .env
cp /secure/path/to/azure_api_key.txt ./azure_api_key.txt
chmod 600 azure_api_key.txt
```

The example `.env` contains the Azure endpoint and a path to the key file; it
does not contain the secret itself. Both `.env` and `azure_api_key.txt` are
ignored by Git. Exported environment variables take precedence over values in
`.env`.

For the configured Azure GPT-5.6 Terra deployment, pass all three roles through
the OpenAI-compatible provider and use temperature 1:

```bash
--model gpt-5.6-terra --provider openai \
--persona-model gpt-5.6-terra --persona-provider openai \
--judge-model gpt-5.6-terra --judge-provider openai \
--temperature 1
```

Never commit, print, or paste an API key into a command, log, result, README, or
issue.

## Task-suite router

Every task consumer uses `odyssey/task_router.py`. The branch defaults to
`shopping`; the original shared-main tasks remain available as `main-original`.

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run.py --list-suites
.osworld/OSWorld/.venv/bin/python odyssey/run.py --suite shopping --list-tasks
.osworld/OSWorld/.venv/bin/python odyssey/run.py --suite main-original --list-tasks
```

Use a full task ID in automation. Ordinals such as `--task 1` are convenient
for local smoke tests but may move when an earlier shard is added.

## Persona design policy for every scenario

Every person assigned a concrete scenario must define **3–6 matched pairs,
which is exactly 6–12 named personas**:

- fewer than 6 or more than 12 named personas is invalid without a protocol
  review;
- `none` is an additional control and does not count toward 6–12;
- each pair targets one official MatrAIx dimension and contains two distinct
  allowed values;
- within a pair, copy one shared baseline and override exactly that one target
  dimension;
- keep the display name, task, models, prompts, browser policy, limits, and
  replicate ID identical across the two arms;
- assign an axis only to tasks on which the behavior can be observed naturally;
- write task-specific positive and negative observables, inherited task
  signals, and contradictions before running;
- do not infer behavior from age, nationality, gender, disability, or another
  demographic stereotype;
- neither pole is the “better” user. The experiment measures separation and
  agent adaptation, not moral value.

The protocol validator enforces the count, allowed values, task coverage,
unique dimensions, expected matrix size, and one-dimension pair delta. See
[`odyssey/task_suites/README.md`](odyssey/task_suites/README.md) for the reusable
scenario-owner template.

## Shopping formal design

Shopping uses all six allowed pairs, for 12 personas. Its machine-readable
source of truth is
[`persona_experiment.json`](odyssey/task_suites/shopping/personas/persona_experiment.json),
and the complete task mapping and behavioral rubric are documented in the
[`Shopping runbook`](odyssey/task_suites/shopping/README.md).

| Pair | MatrAIx dimension | Arm A | Arm B | Applicable Shopping tasks |
|---|---|---|---|---|
| Evidence verification | `trust_level` | Verifying | Trusting | Kobe; UK subscription night |
| Price orientation | `economic_motivation` | Cost-sensitive | Premium-seeking | all except Minneapolis family car |
| Purchase risk | `risk_tolerance` | Risk-averse | Risk-tolerant | Kobe; both car tasks; accessories |
| Decision style | `decision_style` | Analytical | Intuitive | Theory outfit; Minneapolis car |
| Time pressure | `time_pressure` | Deadline | No rush | Theory outfit; UK subscription night |
| Detail depth | `cog_detail_orientation` | Very high | Low | both car tasks; accessories |

All arms start from this baseline:

```text
risk_tolerance=Balanced
decision_style=Deliberative
trust_level=Trusting
time_pressure=Moderate
economic_motivation=Value-driven
cog_detail_orientation=Moderate
```

Only the pair's target field changes. For example, the price pair differs only
between `Cost-sensitive` and `Premium-seeking`; all other fields remain at the
baseline values.

## End-to-end execution guidance

### 1. Validate tasks, protocol, and generated personas

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run.py --suite shopping --list-tasks
.osworld/OSWorld/.venv/bin/python odyssey/make_matched_personas.py \
  --suite shopping --check
.osworld/OSWorld/.venv/bin/python odyssey/test_pipeline.py
```

Edit the protocol, not generated YAML. After an intentional protocol change,
regenerate and inspect the diff:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/make_matched_personas.py \
  --suite shopping
git diff -- odyssey/task_suites/shopping/personas odyssey/personas/shopping
```

### 2. Preview one persona without opening a browser

For Kobe, the applicable axes are evidence verification, price orientation,
and purchase risk. Preview both evidence-verification arms first:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run.py \
  --suite shopping --task 1 \
  --persona mp_evidence_verification_positive \
  --replicate-id smoke-kobe --preview \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1

.osworld/OSWorld/.venv/bin/python odyssey/run.py \
  --suite shopping --task 1 \
  --persona mp_evidence_verification_negative \
  --replicate-id smoke-kobe --preview \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1
```

Confirm that both requests preserve every hard task requirement and express
opposite evidence preferences beyond merely repeating the Kobe task. The
openings are cached under `artifacts/persona-openings/`; using the same task,
persona model, profile, prompt, temperature, and replicate ID in execution
reuses the exact reviewed text rather than sampling it again.

### 3. Plan the formal matrix without spending API budget

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --headless
```

Expected first line:

```text
DRY RUN: suite=shopping replicate=r1 cells=36 tasks=6 axes=6
```

Do **not** use `run_grid.sh` for the formal matched-pair experiment. Its full
persona × task Cartesian product would run 72 cells, including 36 invalid
axis–task combinations. `run_matched_pairs.py` reads applicability directly
from the protocol.

To plan only Kobe or one pair:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --task 1 --headless

.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --axis evidence_verification --headless
```

### 4. Run a paid Kobe smoke pair

Materialize and review both persona openings first. This makes two persona-model
calls but no browser, CUA, or judge call:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id smoke-kobe \
  --task 1 --axis evidence_verification \
  --materialize-openings -- \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1
```

Then run the two arms with the same task, models, settings, and replicate ID:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id smoke-kobe \
  --task 1 --axis evidence_verification --headless --execute -- \
  --model gpt-5.6-terra --provider openai \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --judge-model gpt-5.6-terra --judge-provider openai \
  --temperature 1 --max-steps 50 \
  --out artifacts/shopping-results
```

This command runs two cells. `--skip-existing` is added automatically, so the
same command resumes safely after an interruption. The replicate ID is part of
the run fingerprint; never rename `r1` into `r2` merely to bypass a failure.
The planner also assigns an isolated Chrome profile to every
replicate/task/axis/arm cell, preventing one persona or replicate's cookies and
history from leaking into another cell while preserving state for an exact
resume.

Arm order is deterministic and counterbalanced. Some task–axis pairs run
positive→negative and others negative→positive; `r2` reverses every `r1` pair,
and the chosen order/position is frozen in each result. This reduces systematic
confounding from live prices, stock, and page changes over time.

### 5. Run the full formal experiment

The registered design recommends three controlled replicates. Each replicate
has 36 persona cells; three replicates have 108 persona cells total:

```bash
# First materialize and review the exact openings that execution will reuse.
for replicate in r1 r2 r3; do
  .osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
    --suite shopping --replicate-id "$replicate" \
    --materialize-openings -- \
    --persona-model gpt-5.6-terra --persona-provider openai \
    --temperature 1 || break
done

# After review, browse and judge those frozen openings.
for replicate in r1 r2 r3; do
  .osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
    --suite shopping --replicate-id "$replicate" --headless --execute -- \
    --model gpt-5.6-terra --provider openai \
    --persona-model gpt-5.6-terra --persona-provider openai \
    --judge-model gpt-5.6-terra --judge-provider openai \
    --temperature 1 --max-steps 50 \
    --out artifacts/shopping-results || break
done
```

If controls are required, run `none` separately with the same CUA and judge
configuration. Decide and document whether the control is once per task or once
per replicate before collecting results; do not silently mix both policies.

### 6. Run persona-side judges

The main runner writes R1–Rn task judgements. Add P1–P5 and persona-expression
scores to completed results:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/experience_judge.py \
  --results artifacts/shopping-results \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra

.osworld/OSWorld/.venv/bin/python odyssey/persona_fidelity_judge.py \
  --results artifacts/shopping-results \
  --judge-model gpt-5.6-terra --judge-provider openai
```

Using Terra in both P1–P5 slots produces two independent calls to the same
model. A cross-model agreement study requires a second configured model.

Persona expression is scored per arm on 0/1/2:

- `0`: absent, contradicted, or expressed by violating a hard task requirement;
- `1`: weak or ambiguous, including wording inherited from the original task;
- `2`: clear task-specific expression beyond inherited wording, with no
  contradiction.

An arm counts as expressed only at 2. A matched pair separates only if both
arms score 2 for their assigned, opposite poles and both preserve 100% of the
original rubric communication. Otherwise mark the pair invalid or
non-separating; do not hide it in an average.

### 7. Produce the report

```bash
.osworld/OSWorld/.venv/bin/python odyssey/report.py \
  artifacts/shopping-results --suite shopping
```

Keep the following outputs separate in analysis: raw task score,
communicated-only task score, each P1–P5 judge, persona target-expression score,
contradictions, and pair validity/separation. Preserve cited utterances and
open-tab evidence for auditability. `report.py` prints the arm-level score
families; pair validity/separation is currently derived from those frozen arm
records and is not yet a separate automatic judge field. Because the replicate
ID is intentionally part of the run configuration hash, the generic report
also keeps replicates as separate arm columns instead of silently averaging
them.

## Caching and artifacts

Version-2 results freeze the suite, complete task and rubrics, task hash, model
and provider identities, endpoint hash, prompt hashes, step budget, persona
profile hash, browser policy, replicate ID, pair order/position, and the
content-addressed persona-opening cache key. The run snapshot records the exact
opening and its SHA-256. The matched-pair profile also freezes its protocol hash
and task-specific adherence rubric. A protocol, profile, prompt, temperature,
model, task, or replicate change therefore selects another opening cache/cell.

The normal output path is:

```text
<results>/<suite>/<full-task-id>/<task-hash>/
  <persona>__<model>__<resume-hash>__<timestamp>/result.json
```

Keep any captured screenshots, trajectories, and result JSON together. The
post-hoc P1–P5 and fidelity judges reuse a completed browse. A failure of the
inline R1–Rn judge is not yet judge-only resumable in the current runner and rerunning
`run.py` repeats the browse (while reusing the frozen opening). A different task
revision, persona profile, replicate, prompt, model configuration, or browser
identity is a different experimental cell.

## Adding another scenario

Start with the standalone
[`task/persona/OSWorld contributor guide`](docs/adding-tasks/README.md). It
defines the task schema, scenario-level 6–12 persona rule, matrix formula,
human review gates, smoke procedure, and the distinction between the tracked
Playwright runner and a strict OSWorld VM run.

1. Create `odyssey/task_suites/<scenario>/` and copy assigned upstream tasks
   unchanged into one or more task shards.
2. Register the suite and its nested `persona_experiment` in
   `odyssey/task_suites.json`.
3. Choose 3–6 task-relevant behavioral dimensions, producing 6–12 personas.
4. Define a shared baseline, two allowed poles per axis, task applicability,
   observables, inherited signals, and contradictions.
5. Generate profiles with `make_matched_personas.py`; never hand-edit generated
   YAML.
6. Make the dry plan match the declared cell count, preview both arms, run a
   two-cell smoke pair, then launch full replicates.
7. Commit tasks, protocol, generated profiles, README, and offline tests. Do not
   commit credentials, Chrome profiles, or result artifacts.

The reusable specification and checklist are in
[`odyssey/task_suites/README.md`](odyssey/task_suites/README.md).

## Troubleshooting

- **`No module named yaml`**: use the project virtualenv or install
  `odyssey/requirements.txt` into the selected Python.
- **Stale generated profiles**: run `make_matched_personas.py` without
  `--check`, inspect the diff, then rerun with `--check`.
- **Persona not applicable to task**: use `run_matched_pairs.py`; direct runner
  calls intentionally reject a matched persona outside its protocol mapping.
- **Azure rejects temperature**: GPT-5.6 Terra requires `--temperature 1` in
  this pipeline.
- **403, captcha, DNS timeout, or empty page**: treat it first as environment or
  site availability evidence, not agent failure. Preserve the artifact and
  rerun the same cell/replicate only after the environment is corrected.
- **Interrupted formal run**: rerun the exact command with the same replicate
  ID. Completed comparable cells are skipped.
- **Opening differs from the reviewed preview**: the preview and execute
  commands used different persona model/profile/prompt/temperature or replicate
  IDs. Use `--materialize-openings` and then execute with the same values.

For implementation details, legacy personas, generic grids, result schema, and
prompt files, continue with [`odyssey/README.md`](odyssey/README.md).
