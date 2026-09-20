# Controlled persona experiment

This experiment tests whether the simulated user expresses one observable,
task-relevant attribute at a time. It does not treat demographic background as
behavioral evidence, and it does not treat either side of a pair as a better
kind of user.

The machine-readable source of truth is `persona_experiment.json`. The 12 YAML
profiles below `personacuabench/personas/matched_pairs/` are generated artifacts.

## Selected axes

- Evidence verification: `trust_level=Verifying` versus `Trusting`.
- Price orientation: `economic_motivation=Cost-sensitive` versus
  `Premium-seeking`.
- Purchase risk: `risk_tolerance=Risk-averse` versus `Risk-tolerant`.
- Decision style: `decision_style=Analytical` versus `Intuitive`.
- Time pressure: `time_pressure=Deadline` versus `No rush`.
- Detail depth: `cog_detail_orientation=Very high` versus `Low`.

Every pair has the same display name and the same six-dimension baseline. Only
the target dimension changes. Only that dimension appears in
`evaluation_dimensions`.

## Task assignment

Each of the six benchmark tasks receives three axes:

1. Kobe releases and live Nike stock: evidence verification, price orientation,
   and purchase risk.
2. Green evening dress, shoes, and ooShirts: price orientation, decision style,
   and time pressure.
3. Augusta used Toyota comparison: price orientation, purchase risk, and detail
   depth.
4. Minneapolis family-car shortlist: purchase risk, decision style, and detail
   depth.
5. UK subscription night: evidence verification, price orientation, and time
   pressure.
6. Vehicle accessory shortlist: price orientation, purchase risk, and detail
   depth.

This is 18 task-axis pairs and 36 positive/negative run cells per replicate.
Three controlled replicates are recommended.

## Scoring

Adherence is scored from simulated-user utterances only:

- `0`: absent, contradicted, or expressed by violating a hard task requirement.
- `1`: weak or ambiguous, including wording already required by the task.
- `2`: clear task-specific behavior beyond inherited task wording, with no
  contradiction.

`expressed=true` only when the score is `2`. The negative arm also requires
positive evidence—for example, explicitly delegating verification or declining
optional detail. Silence is not enough.

A pair separates only when both arms score `2` for their assigned poles and the
cited utterances show meaningfully opposite behavior. If either arm omits an
original Odysseys requirement, the pair is invalid instead of being counted as
persona expression.

Task success, persona adherence, and CUA alignment remain separate outputs.

## Regeneration

```bash
python -m personacuabench.make_matched_personas
python -m personacuabench.make_matched_personas --check
python scripts/validate_repository.py
python scripts/run_matched_pairs.py --replicate-id r1
```

The generator validates every value against the pinned MatrAIx dimensions
catalog and embeds the protocol checksum in each profile. The final command is
a dry run; add `--execute` only when the full replicate should call models and
start the VM.
