# Adding tasks, personas, and an OSWorld execution path

This is the contributor runbook for adding a benchmark scenario or another
task batch to PersonaCUABench. It defines what a scenario owner must change,
what must remain frozen, how to design the persona experiment, and what counts
as an OSWorld run.

The short version is:

1. freeze the task and ordinary rubric;
2. register it through the suite router;
3. define 3–6 controlled persona pairs for the scenario;
4. generate, never hand-edit, the 6–12 persona profiles;
5. validate and dry-run the applicability matrix;
6. inspect both persona openings, then run a two-cell smoke test;
7. collect formal replicates in one declared runtime;
8. preserve task, persona, environment, and judge results as separate outputs.

The complete Shopping implementation is the reference:

- [`src/task_suites/shopping/000-core.json`](../../src/task_suites/shopping/000-core.json)
  for task records;
- [`src/task_suites/shopping/personas/persona_experiment.json`](../../src/task_suites/shopping/personas/persona_experiment.json)
  for the matched-pair protocol;
- [`src/task_suites/shopping/README.md`](../../src/task_suites/shopping/README.md)
  for its experiment-specific runbook.

## 1. Know which layer owns what

Three projects or data layers are involved, and they are not interchangeable:

- **Odysseys** supplies the benchmark need and the ordinary R1–Rn rubric.
- **MatrAIx Persona** supplies the allowed behavioral dimensions and values.
- **OSWorld** supplies a reproducible computer/VM runtime when the strict
  OSWorld execution path is installed and selected.

PersonaCUABench owns the suite router, persona protocol, generated profiles,
run matrix, persona-side judges, and reports. A persona must change how a user
expresses or prioritizes the need; it must never silently rewrite the
underlying Odysseys task.

### Current runtime boundary

In the tracked implementation described by this README, `src/run.py`
drives an installed local Chrome through Playwright. It is a real-web CUA
benchmark, but it is **not** the OSWorld VM runtime. The path
`.osworld/OSWorld/.venv/bin/python` used by some repository examples selects a
convenient Python environment only; using that interpreter does not turn the
Playwright run into an OSWorld run.

A strict OSWorld result requires the separately reviewed OSWorld V1 installer,
agent adapter, VM runner, reset policy, and artifact collector. Those pieces
are not tracked in this code line. A reference implementation exists in commit
`61927ac` (`codex/personacuabench-refactor`), but its installer, adapter,
package runner, reproducibility pins, patches, schemas, and tests must be
reviewed and merged as one coherent integration. Never copy only the ignored
local `.osworld/` checkout. Do not label a result “OSWorld” until the tracked
integration is present and the run satisfies the contract in
[Section 8](#8-follow-the-osworld-contract).

## 2. Work on a scenario branch

Start from the team-agreed base branch and create a branch for one scenario or
one coherent task batch:

```bash
git switch <base-branch>
git pull --ff-only
git switch -c <name>/<scenario>-tasks
```

Do not mix unrelated scenarios, credentials, local browser state, VM images,
or result artifacts into the task change.

For the tracked Playwright pipeline, create a normal repository environment;
do not depend on another developer already having a local OSWorld checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt
.venv/bin/python src/test_pipeline.py
```

Google Chrome must also be installed for real browser runs. The `.venv/`
directory is ignored by Git.

## 3. Add and freeze task records

### Existing scenario

Add a new, predictably sorted top-level shard such as:

```text
src/task_suites/<scenario>/010-next-batch.json
```

If the suite manifest already uses
`task_suites/<scenario>/*.json`, no manifest change is needed. Keep the persona
protocol in the nested `personas/` directory so the task glob cannot mistake
it for a task shard.

### New scenario

Create this layout:

```text
src/task_suites/<scenario>/
├── README.md
├── 000-core.json
└── personas/
    └── persona_experiment.json
```

Use a lowercase, path-safe, stable scenario ID. Do not rename it after formal
results have been collected.

### Task schema

A shard is a non-empty JSON list. The router requires `task_id`,
`confirmed_task`, `level`, and at least one complete rubric:

```json
[
  {
    "task_id": "globally-unique-stable-id",
    "confirmed_task": "The complete user task, with every hard requirement.",
    "website": "https://www.google.com",
    "reference_length": 3,
    "level": "easy",
    "rubrics": {
      "R1": {
        "requirement": "One independently scorable requirement.",
        "verification": "What visible page, tab, state, or final-answer evidence proves it."
      }
    },
    "categories": ["Domain > Subdomain"],
    "num_categories": 1
  }
]
```

Rules:

- `task_id` must be globally unique and contain only letters, digits, `.`, `_`,
  or `-` after its first character;
- for an assigned Odysseys task, copy the upstream record and rubric unchanged;
- retain useful provenance fields such as `website`, `reference_length`, and
  `categories`, even though the router's minimum schema is smaller;
- never add persona preferences to `confirmed_task`; they belong in the
  persona protocol and simulated-user utterances;
- never weaken a task merely because a website is temporarily inaccessible;
- never require a purchase, message, booking, deletion, account change, or
  other irreversible action unless the benchmark and runtime explicitly
  provide a safe sandbox for it.

### Rubric review

Each rubric should be independently judgeable from retained evidence. State
both the requirement and its verification condition. Prefer visible evidence
from an open source/product page plus an attributable final answer. Avoid
rubrics that depend on private reasoning, an unstated preference, or a site
state that cannot be captured.

Before freezing a new task, manually check its named sites in the intended
runtime and region. Record DNS failures, TLS failures, blocked pages, login
requirements, CAPTCHAs, and geographic restrictions. This is feasibility
evidence, not permission to edit the task after seeing a model fail.

## 4. Register and validate routing

For a new scenario, add an entry to `src/task_suites.json`:

```json
"<scenario>": {
  "title": "Human-readable scenario title",
  "version": "1",
  "task_files": [
    "task_suites/<scenario>/*.json"
  ],
  "persona_experiment": "task_suites/<scenario>/personas/persona_experiment.json",
  "default_personas": [
    "none"
  ]
}
```

`none` is the verbatim-task control. Formal matched personas are generated from
the nested protocol, so they do not need to be enumerated in
`default_personas`.

Validate before any model call:

```bash
.venv/bin/python src/run.py --list-suites
.venv/bin/python src/run.py \
  --suite <scenario> --list-tasks
```

Use full task IDs in scripts and reports. Numeric ordinals are only a local
convenience because adding an earlier shard can change them.

## 5. Design the persona experiment

### The 6–12 rule is scenario-level

Every scenario/suite defines **3–6 matched pairs**, which produces **6–12
named personas total**. This is not 6–12 new personas per task. A task receives
only the axes that are behaviorally meaningful for it. The `none` control is
extra and does not count toward the 6–12 budget.

For every pair:

- choose one unique dimension from `src/dimensions.json`;
- choose two different values allowed by that dimension;
- begin from one shared scenario baseline;
- change exactly that one dimension between the two profiles;
- keep the display name, task, prompts, models, limits, and replicate fixed;
- make both poles affirmatively observable rather than detecting one by
  silence;
- ensure neither pole requires dropping or contradicting a hard task
  requirement;
- avoid demographic stereotypes and value judgments about which pole is
  “better.”

Examples of potentially useful axes are evidence verification, price
orientation, purchase-risk tolerance, decision style, time pressure, and
desired detail. They are examples, not a list to copy into every scenario.

### Human semantic gate

Before writing the protocol, answer yes to all of these:

1. Can each pole be stated naturally by the user on at least one task?
2. Does each pole produce evidence beyond words already inherited from the
   original task?
3. Can both poles preserve all R1–Rn requirements?
4. Could a judge distinguish the poles from user utterances alone?
5. Could the CUA reasonably adapt its search, comparison, or presentation?
6. Can contradictions for both poles be written explicitly?

Static validation cannot replace this review.

### Protocol fields

Start from the Shopping protocol but replace its task mapping and behavioral
content. The protocol must contain:

- `schema_version`, `experiment_id`, `suite_id`, and a shared `display_name`;
- `design` counts, recommended replicates, pairing controls, and invalid-pair
  conditions;
- `baseline_dimensions`, using allowed catalog values;
- `scoring`, including the 0/1/2 arm rubric, binary adherence rule, pair
  separation rule, 100% original-rubric coverage guardrail, and reporting
  policy;
- 3–6 `axes`, each with a unique ID and target dimension;
- positive and negative values, behavioral definitions, generic observables,
  and contradictions for every axis;
- exact applicable task IDs with `task_label`, `rationale`, inherited signals,
  positive observables, and negative observables.

Every suite task must map to at least one axis. The current generic validator
does not require exactly three axes per task; that is a Shopping-specific
design choice.

### Calculate the matrix before running

Let:

- `A` be the number of axes;
- `P` be the sum of applicable task counts across all axes.

Then:

```text
named personas                         = 2 × A
expected task-axis pairs per replicate = P
expected run cells per replicate       = 2 × P
```

Put those exact values in `design`. Adding one task requires updating its axis
maps and both declared matrix counts.

## 6. Generate personas; do not hand-edit them

Generate profiles from the protocol:

```bash
.venv/bin/python src/make_matched_personas.py \
  --suite <scenario>

.venv/bin/python src/make_matched_personas.py \
  --suite <scenario> --check
```

The generated location is:

```text
src/personas/<scenario>/matched_pairs/
  mp_<axis-id>_positive.yaml
  mp_<axis-id>_negative.yaml
```

The check rejects an invalid persona count, catalog value, duplicate target
dimension, uncovered or unknown task, incorrect matrix count, stale/missing
profile, any extra YAML in the generated directory, and a pair that differs in
more than its target dimension. Fix the protocol and regenerate; never patch a
generated YAML directly.

## 7. Validate, preview, and smoke-test

Run the offline regression first:

```bash
.venv/bin/python -m py_compile src/*.py
.venv/bin/python src/test_pipeline.py
```

Dry-run the whole applicability matrix:

```bash
.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id r1 --headless
```

Check that the header matches the protocol. For each newly added task, verify
its slice has `2 × mapped_axes(task)` cells:

```bash
.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id r1 \
  --task <full-task-id> --headless
```

Also check one applicable task/axis slice, one deliberately non-applicable
slice, and `r1` versus `r2`. An applicable task/axis has two cells; a
non-applicable selection must fail with `selection produced no cells`; `r2`
must reverse the two arm positions used by `r1` for the same task/axis.

Materialize and inspect a two-arm opening before launching a browser:

```bash
.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id smoke \
  --task <full-task-id> --axis <axis-id> \
  --materialize-openings -- \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1
```

Both openings must communicate every original requirement, express opposite
task-specific behavior, and avoid copying an inherited task phrase as their
only persona evidence.

Execute only after that review, using the same replicate and persona-model
configuration:

```bash
.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id smoke \
  --task <full-task-id> --axis <axis-id> --headless --execute -- \
  --model gpt-5.6-terra --provider openai \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --judge-model gpt-5.6-terra --judge-provider openai \
  --temperature 1 --max-steps 50 \
  --out artifacts/<scenario>-results
```

Do not use `run_grid.sh` for the formal matched-pair experiment. It produces a
Cartesian persona × task grid and therefore includes undeclared combinations.

## 8. Follow the OSWorld contract

### Bring in the integration before using it

The reference implementation in commit `61927ac` was validated on Apple
Silicon macOS with `uv 0.12.13` and VMware Fusion 26H1u1. It pins OSWorld,
Odysseys, Python, the resolved dependency lock, local patches, and the Ubuntu
ARM VM archive. The first real setup may need roughly 38–43 GB for the VM and
runtime data.

After that complete tracked integration has been merged, its setup and entry
points are:

```bash
./scripts/install_persona8b.sh
./integrations/osworld/install_osworld.sh

/Applications/VMware\ Fusion.app/Contents/Library/vmrun -T fusion list

.osworld/OSWorld/.venv/bin/python -m personacuabench.run \
  --task <full-task-id> --persona <persona-id> \
  --model gpt-5.6-terra
```

Fusion's EULA, privileged helper, and network permissions must first be
approved in the macOS GUI. In that reference implementation, the OSWorld
runner reads exported Azure variables or an API-key file; it does not load the
Playwright pipeline's repository `.env`. Follow the merged integration's
tracked README and reproducibility manifest rather than copying a machine's
local configuration.

The adapter keeps OSWorld's screenshot-to-prompted-PyAutoGUI interface. It is
not Azure's native computer tool. OSWorld browser state comes from the VM
snapshot/reset lifecycle, so Playwright options such as `--profile` and its
Chrome user-data directories do not apply. A single VM is a serial resource;
do not run multiple cells against it concurrently.

Adding a task also requires an explicit bridge between this suite router and
OSWorld. That bridge must:

- resolve each selected task ID to its pinned OSWorld/Odysseys VM config rather
  than handing the PersonaCUABench task shard directly to OSWorld;
- clone that VM config and replace only its user instruction with the frozen,
  cached persona opening—never its setup, reset, evaluator, or task identity;
- implement persona clarification turns without revealing the private profile
  or ordinary rubric to the CUA;
- normalize OSWorld screenshots, trajectory, open tabs, conversation, and run
  outcome into one versioned PersonaCUABench result record;
- run the pinned Odysseys full-trajectory R1–Rn scorer separately. OSWorld's
  native `result.txt` marker for these imported tasks is not by itself the
  complete ordinary-rubric score.

When the declared experiment runtime is OSWorld, the integration must preserve
all of the following:

1. **Pinned runtime.** Record the OSWorld V1 source revision, dependency lock,
   VM image identity, host architecture, and local patch hashes.
2. **Clean reset.** Reset the VM or task environment before every cell. Do not
   reuse browser history, cookies, tabs, downloads, or login state across arms.
3. **Information boundary.** The persona simulator may receive the frozen task
   and private profile. The CUA receives only the persona's utterances; it must
   not receive the profile, opposite arm, hidden rubric, or judge prompt.
4. **Native interaction.** Keep OSWorld's screenshot observation and computer
   action path. A transport adapter may change how model requests are sent, but
   must not replace the benchmark's computer interface or inject hidden task
   knowledge.
5. **Controlled pair.** Use the same task revision, CUA/persona/judge models,
   prompts, limits, reset policy, and replicate ID for both arms. Freeze pair
   order and position.
6. **Preflight timing.** If network feasibility is measured, probe from inside
   the reset guest after reset and before the first agent action. Store the raw
   DNS/HTTP evidence. Do not browse the task for the agent during preflight.
7. **No task mutation.** Site failure may support an explicit infeasible or
   availability-adjusted diagnostic. It must not modify the original task,
   rubric, or raw task score.
8. **Complete artifacts.** Preserve `traj.jsonl`, screenshots, conversation,
   final answer, open tabs, reset/runtime metadata, optional network preflight,
   model configuration, task/profile hashes, and the raw result.
9. **Separate judging.** Keep raw R1–Rn success, communication coverage,
   persona expression, CUA alignment, P1–P5 experience, and any availability
   adjustment separate. Never rename one metric as another or average them
   into a single headline score.

If the OSWorld adapter or artifact collector cannot satisfy those points, stop
at protocol validation and dry-run. Do not treat a local Playwright smoke test
as evidence that the OSWorld environment is ready.

## 9. Score and report

For the current Playwright path, add the post-hoc persona-side judges after a
completed smoke or formal run:

```bash
.venv/bin/python src/experience_judge.py \
  --results artifacts/<scenario>-results \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra

.venv/bin/python src/persona_fidelity_judge.py \
  --results artifacts/<scenario>-results \
  --judge-model gpt-5.6-terra --judge-provider openai

.venv/bin/python src/report.py \
  artifacts/<scenario>-results --suite <scenario>
```

Persona expression uses 0/1/2 per arm. A pair separates only when both arms
score 2 for their assigned opposite poles, preserve 100% of original-rubric
communication, and contain meaningfully opposite cited evidence. Otherwise it
is invalid or non-separating; do not conceal that result in an average.

## 10. Pull-request acceptance checklist

### Task and routing

- [ ] The task ID is stable, path-safe, and globally unique.
- [ ] Assigned upstream task wording and R1–Rn rubrics are unchanged.
- [ ] Every rubric has an observable verification condition.
- [ ] Task shards are top-level; the protocol is nested under `personas/`.
- [ ] Suite listing and task listing both pass without a model call.

### Persona protocol

- [ ] The scenario has 3–6 pairs / 6–12 named personas total.
- [ ] `none` is treated as an additional control.
- [ ] Every pair changes exactly one unique MatrAIx dimension.
- [ ] Both poles are affirmative, task-relevant, and stereotype-free.
- [ ] Every task maps to at least one meaningful axis.
- [ ] Matrix formulas and declared counts agree.
- [ ] `make_matched_personas.py --check` passes with no extra generated YAML.

### Execution

- [ ] Full and task-slice dry-runs match the declared matrix.
- [ ] Applicable and non-applicable task/axis selections behave correctly.
- [ ] `r2` reverses `r1` pair order for identical task/axis pairs.
- [ ] Both cached openings pass human review before browser execution.
- [ ] One paid two-cell smoke pair succeeds before full replicates begin.
- [ ] Environment failures are preserved and not scored as model failures.
- [ ] The runtime is labeled accurately as Playwright or strict OSWorld.

### Repository hygiene

- [ ] `src/test_pipeline.py` and `git diff --check` pass.
- [ ] The scenario README documents tasks, axes, commands, and known limits.
- [ ] No API key, `.env`, browser profile, VM image, opening cache, result,
      screenshot, or trajectory is committed.
- [ ] The PR contains only one coherent scenario or task batch.

For the protocol field reference, continue with
[`src/task_suites/README.md`](../../src/task_suites/README.md). For the
runner and result schema, see
[`src/README.md`](../../src/README.md).
