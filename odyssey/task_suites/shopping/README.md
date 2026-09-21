# Ecommerce & Shopping scenario

This directory is the source of truth for Defu Cao's six Shopping tasks and
their controlled persona experiment. The task text and R1–Rn rubrics live in
`000-core.json`; the persona axes, behavioral rubrics, and applicability matrix
live in `personas/persona_experiment.json`.

The formal design is fixed at **6 matched pairs / 12 named personas**. Each
task receives exactly three relevant pairs, so one replicate contains **18
task–axis pairs / 36 persona cells**. Three replicates are recommended, for 108
persona cells. A separately declared `none` control is not one of the 12.

## Files

```text
shopping/
├── README.md
├── 000-core.json
└── personas/
    └── persona_experiment.json

../../personas/shopping/matched_pairs/
└── mp_<axis>_<positive|negative>.yaml   # generated; do not hand-edit
```

The protocol is nested under `personas/` intentionally. The task-suite manifest
loads `shopping/*.json` as task shards; placing the protocol at the directory
root would make the router mistake it for a task file.

## Frozen task set

| # | Task | Stable task ID | Assigned axes |
|---:|---|---|---|
| 1 | Kobe releases and live Nike stock | `39255449e341c41a589b8a4e17f073be3a4809c9` | evidence verification; price orientation; purchase risk |
| 2 | Green evening dress, matching shoes, and ooShirts | `7cc602f239775882273921d82e181020f1769b53` | price orientation; decision style; time pressure |
| 3 | Augusta used Toyota comparison | `67ad95421a303ad78cfcd8c3f5a7f6668d2c6a75` | price orientation; purchase risk; detail depth |
| 4 | Minneapolis family-car shortlist | `63d68bb25e279fc22e6e3592d8ca59add33b6eb1` | purchase risk; decision style; detail depth |
| 5 | UK subscriptions, Wicked streaming, and PrintPigeon | `4b9850333bdd7298442df495aff3832c13b119da` | evidence verification; price orientation; time pressure |
| 6 | Vehicle accessory shortlist | `44f1e02116715d5fe313996811b358fe25bc3ee4` | price orientation; purchase risk; detail depth |

Do not rewrite a task to make a persona easier to observe. The same frozen task
and rubrics must be used for both arms and every replicate.

## Shared baseline

All 12 profiles begin with the same six values:

```json
{
  "risk_tolerance": "Balanced",
  "decision_style": "Deliberative",
  "trust_level": "Trusting",
  "time_pressure": "Moderate",
  "economic_motivation": "Value-driven",
  "cog_detail_orientation": "Moderate"
}
```

For each pair, exactly one of these values is replaced. There are no age,
gender, nationality, disability, or other demographic differences between
arms. This keeps behavioral attribution narrow and avoids stereotype-based
fidelity judgements.

## The six matched pairs

The `positive` and `negative` arm names are serialization labels only. They do
not mean that one pole is desirable and the other is undesirable.

### 1. Evidence verification

- Dimension: `trust_level`
- `positive`: `Verifying` — requests current, inspectable evidence and marks
  uncertainty.
- `negative`: `Trusting` — accepts the assistant's synthesis after the task's
  specified sources have been checked.
- Tasks: Kobe; UK subscription night.

The Verifying arm must go beyond the base task's existing source requirements,
for example by distinguishing confirmed dates from rumors or first-party
streaming inclusion from a search snippet. The Trusting arm needs affirmative
delegation; silence does not prove trust.

### 2. Price orientation

- Dimension: `economic_motivation`
- `positive`: `Cost-sensitive` — prioritizes lowest total cost and avoiding
  premiums.
- `negative`: `Premium-seeking` — accepts paying more for fit, quality,
  durability, or convenience.
- Tasks: all Shopping tasks except the Minneapolis family-car shortlist.

Both arms must keep the task's hard caps and requested price fields. A
Premium-seeking persona cannot exceed a fixed budget simply to express the pole.

### 3. Purchase risk tolerance

- Dimension: `risk_tolerance`
- `positive`: `Risk-averse` — avoids unclear stock, compatibility, condition,
  or terms.
- `negative`: `Risk-tolerant` — accepts bounded uncertainty when it is disclosed.
- Tasks: Kobe; Augusta used Toyota; Minneapolis family car; accessories.

Risk tolerance changes the treatment of uncertainty, not whether uncertainty
is hidden. Both arms must report material unknowns.

### 4. Decision style

- Dimension: `decision_style`
- `positive`: `Analytical` — compares criteria explicitly and explains
  trade-offs.
- `negative`: `Intuitive` — once hard requirements are met, prefers the option
  with the best overall fit or feel.
- Tasks: Theory evening outfit; Minneapolis family car.

An Intuitive arm still needs the fields and evidence required by the original
rubric; it may not substitute an unsupported vibe for task completion.

### 5. Time pressure

- Dimension: `time_pressure`
- `positive`: `Deadline` — prioritizes required items and minimizes optional
  searching.
- `negative`: `No rush` — welcomes further comparison and alternatives.
- Tasks: Theory evening outfit; UK subscription night.

The Deadline arm can deprioritize only optional exploration. It cannot omit an
R1–Rn requirement.

### 6. Detail depth

- Dimension: `cog_detail_orientation`
- `positive`: `Very high` — asks for extra specifications, costs, condition,
  compatibility, and reasoning.
- `negative`: `Low` — asks for only the required decision fields in a concise
  result.
- Tasks: Augusta used Toyota; Minneapolis family car; accessories.

The Low arm must remain complete against the base rubric. Concision is measured
through presentation and optional detail, never by deleting required facts.

## Generated persona names

The generator creates these 12 suite-scoped profiles:

```text
mp_evidence_verification_positive   mp_evidence_verification_negative
mp_price_orientation_positive      mp_price_orientation_negative
mp_purchase_risk_positive           mp_purchase_risk_negative
mp_decision_style_positive          mp_decision_style_negative
mp_time_pressure_positive           mp_time_pressure_negative
mp_detail_depth_positive            mp_detail_depth_negative
```

The same filenames can safely exist in another suite because the runner first
looks under `odyssey/personas/<suite>/matched_pairs/`.

Each generated YAML freezes:

- the experiment, pair, axis, arm, and counterpart IDs;
- protocol path and SHA-256;
- target and opposite values;
- generic observables and contradictions;
- applicable task IDs and task-specific criteria;
- the six rendered MatrAIx attributes;
- only the changed dimension in `evaluation_dimensions`.

Generated profiles also select `matched_pair_full_coverage.v1`. That protocol
uses `prompts/persona_user_matched_pair.md`, which requires every original
rubric to be communicated while the target preference is expressed naturally.
Legacy exploratory personas continue to use `prompts/persona_user.md`, where
natural omission is allowed; those two interaction protocols must not be mixed
inside a formal matched pair.

## Validate and regenerate

Run from the repository root:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/make_matched_personas.py \
  --suite shopping --check
```

Expected summary:

```text
checked 12 personas across 6 matched pairs for suite 'shopping'
matrix: 18 task-axis pairs / 36 cells per replicate
```

If the protocol was intentionally edited:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/make_matched_personas.py \
  --suite shopping
.osworld/OSWorld/.venv/bin/python odyssey/make_matched_personas.py \
  --suite shopping --check
```

Never edit a generated YAML to repair a failing check. Change the protocol,
regenerate all 12, and review the entire pair diff.

## Preview checklist

Previewing calls only the persona model; it does not launch Chrome or the CUA.

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run.py \
  --suite shopping --task 1 \
  --persona mp_evidence_verification_positive \
  --replicate-id smoke-kobe --preview \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1
```

Before approving a pair, check both openings:

- every original task requirement is still communicated;
- only the target behavioral pole differs;
- evidence is not merely copied from task wording;
- neither arm invents a new hard constraint;
- the negative arm has affirmative behavioral evidence rather than silence;
- no private profile, axis label, rubric, or role-play instruction leaks into
  the user message.

Preview and execution must use the same replicate ID and persona-model
configuration. The runner stores a content-addressed opening cache below
`artifacts/persona-openings/`; execution then reuses the exact inspected
opening instead of sampling a replacement.

## Dry-run the matrix

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --headless
```

This must report 36 cells. Useful slices are:

```bash
# All six applicable persona arms for Kobe
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 --task 1 --headless

# Both evidence-verification arms on both applicable tasks
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id r1 \
  --axis evidence_verification --headless
```

The formal experiment must use this applicability-aware planner. A Cartesian
product of 12 personas × 6 tasks is not the registered design.

## Execute a smoke pair

Materialize both exact openings first (persona-model calls only):

```bash
.osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
  --suite shopping --replicate-id smoke-kobe \
  --task 1 --axis evidence_verification \
  --materialize-openings -- \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --temperature 1
```

After reviewing them, execute with the same replicate and persona settings:

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

This makes two paid cells. Inspect both result directories before scaling up:

- persona opening and clarification turns;
- browser trajectory and final answer;
- open tabs and visible evidence;
- R1–R5 score and communication coverage;
- identical controlled settings and replicate ID;
- no environment-only failure such as DNS, captcha, 403, or empty page.

## Execute formal replicates

```bash
# Persona-model calls only: freeze and review the exact r1–r3 openings.
for replicate in r1 r2 r3; do
  .osworld/OSWorld/.venv/bin/python odyssey/run_matched_pairs.py \
    --suite shopping --replicate-id "$replicate" \
    --materialize-openings -- \
    --persona-model gpt-5.6-terra --persona-provider openai \
    --temperature 1 || break
done

# Only after approval, execute the browser/CUA/judge cells.
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

The planner passes `--skip-existing`, so rerunning the exact command resumes a
replicate. `--replicate-id` participates in the run hash: `r1`, `r2`, and `r3`
remain separate even when every other setting is identical. It also assigns a
separate Chrome profile under
`artifacts/chrome-profiles/matched-pairs/<suite>/<replicate>/<task>/<axis>/<arm>`
to prevent browser state from leaking across formal cells.

Within each task–axis pair, arm order is deterministically counterbalanced and
stored as `pair_order` plus `pair_position`. `r2` reverses the order used by
`r1`; `r3` repeats the first pattern, giving a 2/1 balance with three
replicates. This prevents `positive` from always running earlier on a live web.

## Evaluation and reporting

The main runner produces two R1–Rn views:

- `score`: requirements met divided by all original rubric items;
- `score_communicated`: requirements met divided by items the persona actually
  communicated.

Then run the independent persona-side judges:

```bash
.osworld/OSWorld/.venv/bin/python odyssey/experience_judge.py \
  --results artifacts/shopping-results \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra

.osworld/OSWorld/.venv/bin/python odyssey/persona_fidelity_judge.py \
  --results artifacts/shopping-results \
  --judge-model gpt-5.6-terra --judge-provider openai

.osworld/OSWorld/.venv/bin/python odyssey/report.py \
  artifacts/shopping-results --suite shopping
```

Fidelity uses the frozen task-specific rubric from the generated profile:

- `0`: absent, contradicted, or achieved by breaking the task;
- `1`: weak, ambiguous, stylistic, or inherited from the base task;
- `2`: clear, task-specific expression with no contradiction.

Report each arm's score and cited utterance. A pair is valid only when its two
runs share the controlled configuration and both communicate every original
rubric. It separates only when both assigned poles score 2 and their evidence
is meaningfully opposite. Keep task success, P1–P5, persona adherence, and CUA
alignment as separate result families. The current `report.py` shows arm-level
task, P1–P5, and fidelity outputs; pair separation and standalone CUA alignment
are not yet emitted as automatic judge fields and must not be inferred by
renaming one of those other scores. The generic report also shows replicates as
separate configuration-hash columns; it does not silently aggregate `r1`–`r3`.

## Protocol-change checklist

Any change to an axis, value, task mapping, or observable must include all of
the following in one review:

- rationale for why the behavior is observable in the assigned task;
- proof that the value exists in `dimensions.json`;
- regenerated 6–12 profiles and a passing `--check`;
- exactly one changed dimension within every pair;
- updated declared task-axis and cell counts;
- dry-run output matching those counts;
- previews for both arms of every changed pair;
- updated README mapping;
- offline `odyssey/test_pipeline.py` passing.

Do not change the six-task Shopping protocol during a formal collection unless
you intentionally start a new experiment version. The protocol hash exists to
make that boundary auditable.
