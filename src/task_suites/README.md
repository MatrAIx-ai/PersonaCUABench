# Scenario-owner guide

`task_suites.json` is the catalog shared by the runner, matched-pair planner,
grid, and report. Each scenario owns its frozen tasks, controlled persona
protocol, generated personas, and a scenario README.

For the end-to-end contribution workflow—including task authoring, matrix
acceptance tests, environment feasibility, and the strict OSWorld execution
contract—start with
[`docs/adding-tasks/README.md`](../../docs/adding-tasks/README.md).

## Required persona budget

Every concrete scenario must define **3–6 matched pairs**, therefore **6–12
named personas**. The `none` verbatim-task control is additional and does not
count toward this limit.

This is a protocol rule, not a suggestion. It keeps the experiment reviewable
and gives every scenario the same order of magnitude. A scenario that needs
fewer than 3 or more than 6 axes must propose a new protocol version and obtain
review before collecting results.

Each matched pair must:

- target one official dimension in `src/dimensions.json`;
- use two distinct allowed values for that dimension;
- copy the same baseline and change exactly the target value;
- use the same display name and experimental metadata apart from arm identity;
- list only tasks on which the behavior is naturally observable;
- define inherited task signals, positive and negative task observables, and
  contradictions;
- retain every original task/rubric requirement in both arms;
- avoid demographic stereotypes and avoid treating one pole as preferable.

## Directory template

```text
src/task_suites/<scenario>/
├── README.md
├── 000-core.json
├── 010-next-batch.json              # optional later task shard
└── personas/
    └── persona_experiment.json

src/personas/<scenario>/matched_pairs/
└── mp_<axis>_<positive|negative>.yaml
```

Keep the protocol in a nested directory. A suite pattern such as
`task_suites/<scenario>/*.json` treats every top-level JSON file as a task
shard.

## Register the scenario

Add one manifest entry:

```json
{
  "title": "Human-readable scenario title",
  "version": "1",
  "task_files": ["task_suites/<scenario>/*.json"],
  "persona_experiment": "task_suites/<scenario>/personas/persona_experiment.json",
  "default_personas": ["none"]
}
```

Task IDs must be globally unique and path-safe. Each task keeps the upstream
Odysseys fields: `task_id`, `confirmed_task`, `level`, and a non-empty `rubrics`
object. Copy assigned upstream tasks unchanged; persona expression belongs in
the simulator protocol, not in rewritten benchmark tasks.

Validate routing without making an API call:

```bash
.osworld/OSWorld/.venv/bin/python src/run.py --list-suites
.osworld/OSWorld/.venv/bin/python src/run.py \
  --suite <scenario> --list-tasks
```

## Design the protocol

Start from the Shopping protocol schema, but choose task-relevant axes rather
than copying Shopping's six automatically. The required top-level fields are:

- `schema_version`: `personacuabench.matched-pair.v1`;
- `experiment_id`: a stable, versioned ID;
- `suite_id` and one shared `display_name` for the two arms of every pair;
- `design`: selected axis count, recommended replicates, expected task-axis
  pairs, expected run cells, pairing controls, and invalid-pair conditions;
- `baseline_dimensions`: one allowed value for every selected dimension;
- `scoring`: the 0/1/2 arm rubric, pair-separation rule, coverage guardrail,
  and reporting policy;
- `axes`: 3–6 axis definitions.

Every axis needs:

- a stable `axis_id`, label, and target `dimension`;
- `positive` and `negative` objects, each with an allowed value, behavioral
  definition, generic observables, and contradictions;
- a non-empty `tasks` map keyed by exact task ID;
- per task: a label, rationale, inherited task signals, and separate positive
  and negative observables.

“Positive” and “negative” are neutral arm identifiers. They do not encode
quality, virtue, or the expected direction of task score.

### Selecting good dimensions

Choose a dimension only when both poles can produce affirmative, observable
behavior on the task. Examples include evidence threshold, price orientation,
risk tolerance, decision style, time pressure, and desired detail. Do not use a
dimension when one arm would be detectable only by silence.

For each candidate axis, ask:

1. Can both poles be expressed without changing a hard task requirement?
2. Is there behavior beyond wording already present in the task?
3. Could a judge distinguish the poles from user utterances alone?
4. Could the CUA reasonably adapt its strategy or presentation?
5. Are there explicit contradictions that a judge can identify?

If any answer is no, choose a different axis or task.

## Generate and validate profiles

The shared generator reads the suite's manifest entry and produces current
runner-compatible `attributes` YAML with labels/categories from
`dimensions.json`:

```bash
.osworld/OSWorld/.venv/bin/python src/make_matched_personas.py \
  --suite <scenario>
.osworld/OSWorld/.venv/bin/python src/make_matched_personas.py \
  --suite <scenario> --check
```

The check fails when:

- the scenario has fewer than 3 or more than 6 pairs;
- a dimension/value does not exist in the pinned catalog;
- two axes target the same dimension;
- an arm lacks behavioral evidence or contradictions;
- a task ID is unknown or a task receives no axis;
- declared matrix counts differ from the task map;
- generated files are missing, stale, or extra;
- a pair differs on anything other than its target dimension.

Never fix generated YAML directly.

## Preview, smoke, and run

Preview both arms of each pair before browser execution. Then dry-run the
applicability-aware plan:

```bash
.osworld/OSWorld/.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id r1 --headless
```

The reported cell count must equal
`expected_run_cells_per_replicate`. Smoke one task/pair before scaling:

```bash
# Persona calls only: cache the exact openings for review.
.osworld/OSWorld/.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id smoke \
  --task <task-id-or-ordinal> --axis <axis-id> \
  --materialize-openings -- <persona model/provider arguments>

# Reuses those openings, then launches browser/CUA/judge.
.osworld/OSWorld/.venv/bin/python src/run_matched_pairs.py \
  --suite <scenario> --replicate-id smoke \
  --task <task-id-or-ordinal> --axis <axis-id> \
  --headless --execute -- <run.py model/provider arguments>
```

Use the same models, prompts, runtime limits, browser policy, and replicate ID
for both arms. For the formal run, repeat the exact full-matrix command with
declared replicate IDs such as `r1`, `r2`, and `r3`. The planner creates an
isolated persistent Chrome profile for each replicate/task/axis/arm cell, so an
exact retry resumes its own state without sharing cookies or history with its
counterpart. It also counterbalances positive/negative execution order and
freezes the chosen order/position in the run configuration.

Do not use `run_grid.sh` for matched-pair collection. It intentionally produces
a full persona × task Cartesian product, while a matched protocol runs only
declared axis–task combinations.

## Score and report

For every arm preserve:

- original task R1–Rn results and communicated coverage;
- persona-expression 0/1/2 verdict with cited user utterance;
- contradiction status and judge confidence;
- P1–P5 outputs from both judges;
- task, profile, protocol, configuration, and replicate identities;
- browser trajectory, final answer, and open-tab evidence.

A pair is invalid if an arm omits an original rubric, has mismatched controlled
metadata, runs on an undeclared task, or changes more than its target
dimension. A valid pair separates only when both poles score 2 and the evidence
is meaningfully opposite. Never average task success, persona expression, CUA
alignment, and user experience into one number.

## Contribution checklist

- [ ] Work on a scenario branch, not `main`.
- [ ] Copy exact assigned task IDs and rubrics.
- [ ] Register task shards and nested protocol in `task_suites.json`.
- [ ] Define 3–6 pairs / 6–12 named personas; exclude `none` from the count.
- [ ] Use one shared baseline and exactly one changed field per pair.
- [ ] Map every task only to observable axes.
- [ ] Write positive/negative observables, inherited signals, and contradictions.
- [ ] Generate profiles; `--check` passes.
- [ ] Dry plan matches declared task-axis/cell counts.
- [ ] Preview both arms and complete one paid two-cell smoke pair.
- [ ] Run `src/test_pipeline.py` offline.
- [ ] Update the scenario README.
- [ ] Commit no credentials, result artifacts, or Chrome profiles.

The Shopping suite is the complete reference implementation:
[`shopping/README.md`](shopping/README.md).
