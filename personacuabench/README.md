# `personacuabench` package

This directory is the canonical implementation and data root for
PersonaCUABench. It contains the benchmark subset, persona protocol, run
orchestration, explicit judge, and reporting code. Do not create a parallel
runner package or a second task copy elsewhere in the repository.

It is distinct from both external checkouts:

- `.upstream/odysseys/` is the pinned, locally patched Odysseys checkout used
  by the standard rubric judge.
- `.osworld/OSWorld/` is the pinned, locally patched OSWorld checkout that owns
  the browser/VM runtime and its Python environment.

The adapter and installer connecting those checkouts live in
[`integrations/osworld/`](../integrations/osworld/README.md).

## Canonical data

- `tasks.json`: six assigned Ecommerce & Shopping tasks and their unchanged 34
  Odysseys rubrics; this is the only task source in the repository.
- `osworld_manifest.json`: the same task IDs in OSWorld execution order.
- `metadata.json`: scope, provenance, and immutable checksums.
- `availability_policies.json`: mappings from unavailable endpoints to rubrics
  that depend exclusively on them; it never changes task text or raw verdicts.
- `persona_experiment.json` and `PERSONA_EXPERIMENT.md`: the controlled
  matched-pair protocol and its rationale.
- `dimensions.json`: the pinned Persona-8B dimension catalog.
- `personas/`: legacy-compatible profiles, synthetic smoke fixtures, and
  generated matched pairs.
- `prompts/`: packaged role-prompt assets from the latest main branch, plus a
  README that records which protocol uses each one.
- `schemas/network_preflight.schema.json`: the persisted network-preflight
  contract.

## Implementation map

- `run.py`: persona opening, cache/fingerprint handling, preflight, and OSWorld
  CUA orchestration. It never performs judging implicitly.
- `persona.py`: profile loading/rendering, legacy-profile normalization, and
  persona dialogue state.
- `osworld_runner.py`: isolated OSWorld execution and artifact collection.
- `network_preflight.py` and `availability.py`: read-only guest probes and the
  policy-controlled availability decision.
- `judge.py` and `evaluation.py`: explicit ordinary-rubric and persona scoring.
- `prompting.py`, `prompts/`, and `experience_judge.py`: versioned prompt
  loading and the optional two-judge P1–P5 person-experience evaluation.
- `report.py` and `detailed_report.py`: aggregate and per-run presentation.
- `protocol.py`: matched-pair protocol validation and run-cell construction.
- `make_personas.py` and `make_matched_personas.py`: deterministic profile
  generation/checking.
- `run_grid.sh`: serial task × persona launcher for a single local VM.

## Validate and inspect

Run from the repository root after `python -m pip install -e .`:

```bash
python scripts/validate_repository.py
python -m unittest discover -s tests
python -m personacuabench.make_personas --check
python -m personacuabench.make_matched_personas --check
python scripts/run_matched_pairs.py --replicate-id r1
```

The final command prints the 36-cell controlled grid without calling a model or
starting a VM. Add `--execute` only for a configured runtime. Both arms of every
pair must preserve all ordinary task requirements; task wording alone is not
evidence that the persona actually expressed an assigned trait.

## Run lifecycle

Preview one task without starting OSWorld:

```bash
python -m personacuabench.run --task 1 --persona none --preview
python -m personacuabench.run \
  --task 1 --persona smoke_budget_mobile --preview
```

Run one cell or a selected serial grid:

```bash
.osworld/OSWorld/.venv/bin/python -m personacuabench.run \
  --task 1 --persona none --model gpt-5.6-terra --headless

PERSONAS="none smoke_budget_mobile" TASKS="1 4" \
  bash personacuabench/run_grid.sh
```

Artifacts go to `artifacts/results/`; persona openings and other reusable
inputs go to `artifacts/cache/`. A completed run is reused only when its full
fingerprint matches, including source and upstream revisions.

Judging remains an explicit second phase:

```bash
python -m personacuabench.judge artifacts/results/<task>/<run> --offline
python -m personacuabench.judge artifacts/results/<task>/<run> \
  --model gpt-5.6-terra --reasoning-effort low --max-images 0
```

Offline mode validates and prints the upload manifest without a network call or
write. In live mode, `--max-images 0` includes all selected trajectory images;
a positive value keeps only the last N.

Run the optional two-call experience evaluation separately as well:

```bash
python -m personacuabench.experience_judge \
  artifacts/results/<task>/<run> --offline
python -m personacuabench.experience_judge \
  artifacts/results/<task>/<run> \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra
```

With no positional run, `--results artifacts/results` recursively finds
eligible results. `--force` (alias `--redo`) explicitly replaces an existing
complete experience judgement.

Generate aggregate or per-run output with:

```bash
python -m personacuabench.report
python -m personacuabench.report --format csv
python -m personacuabench.detailed_report artifacts/results/<task>/<run>
```

## Scoring contract

The runner never modifies the original Odysseys task or rubrics. When enabled,
the guest-network preflight runs after reset and before the first agent action.
Its signed artifact permits a separate availability adjustment only when the
versioned policy and strict feasibility gate both allow it.

The result therefore preserves independent axes:

- raw task success is the ordinary, unchanged R1–Rn score;
- availability-adjusted task success is an optional diagnostic and may be null;
- persona adherence measures whether the simulated user expressed its assigned
  traits;
- persona alignment measures whether the CUA respected preferences actually
  communicated in the conversation;
- persona experience P1–P5 records two independent user-side judge verdicts
  for asked-for coverage, readability, actionability, gap handling, and the
  overall encounter.

Adherence and alignment are `not_applicable` for the `none` control. Experience
judge outputs remain separate from each other and from every task/persona
score; these concepts are never collapsed into one average. See the repository
[README](../README.md) for the preflight eligibility rules, API configuration,
and complete setup instructions.
