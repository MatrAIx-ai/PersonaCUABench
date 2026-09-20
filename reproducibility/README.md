# Reproducibility pins

The commit files pin each upstream checkout used by the benchmark:

- `OSWORLD_COMMIT`: OSWorld V1 runtime;
- `ODYSSEYS_COMMIT`: source task configs and standard rubric judge;
- `PERSONA8B_COMMIT`: official MatrAIx persona loader and renderer.

The two patch files are the complete local deltas applied to the pinned OSWorld
and Odysseys checkouts. The SHA-256 files pin the resolved OSWorld lockfile and
Ubuntu ARM VM archive. These files belong in git: they contain reproducibility
metadata, not secrets or generated output.

The PersonaCUABench repository's own revision is recorded by git and embedded
in each run fingerprint; it should not be duplicated in a manually maintained
constant. Each controlled persona profile also records the SHA-256 of
`personacuabench/persona_experiment.json`, and every run records that checksum in
`source_revisions` so a changed scoring protocol cannot silently reuse a result.
`personacuabench/metadata.json` additionally pins the canonical task set, persona
experiment, availability sidecar, and network-preflight schema. The run
fingerprint includes the task-specific availability-policy hash and the source
files that implement preflight collection and adjustment.
