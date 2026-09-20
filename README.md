# PersonaCUABench

PersonaCUABench evaluates a computer-use agent on a fixed six-task Ecommerce &
Shopping subset of [Odysseys](https://odysseysbench.com/), with an optional
MatrAIx persona acting as the user. The subset contains three easy tasks, three
medium tasks, and the 34 unchanged Odysseys rubrics.

The evaluation boundary is deliberate:

1. The persona simulator receives the original task and its private profile.
2. The CUA receives only the persona's opening request and later clarification
   answers. It never receives the profile, hidden rubrics, or judge prompt.
3. Judging is a separate, explicit command. A CUA run never silently uploads
   cached artifacts to a judge.

`none` is the control condition. It sends the original `confirmed_task` to the
CUA byte-for-byte, without a persona rewrite.

## Repository layout

```text
personacuabench/          installed package; canonical tasks, personas, runner, judge, reports
integrations/osworld/     Azure CUA adapter and reproducible OSWorld installer only
reproducibility/          upstream commit pins, local patches, and artifact checksums
scripts/                  repository validation and experiment helpers
tests/                    offline unit and integration tests
artifacts/                local run results and caches (gitignored)

.upstream/odysseys/       pinned, locally patched Odysseys checkout (gitignored)
.osworld/OSWorld/         pinned, locally patched OSWorld runtime and venv (gitignored)
MatrAIx-Persona-8B/       pinned persona renderer checkout (gitignored)
```

These directories are intentionally different. [`personacuabench/`](personacuabench/README.md)
is this repository's source of truth. `.upstream/odysseys/` supplies the pinned
upstream rubric scorer; it is not imported as the PersonaCUABench package.
`.osworld/OSWorld/` owns the VM runtime, browser controller, and its isolated
Python environment. [`integrations/osworld/`](integrations/osworld/README.md)
only installs and connects those external components.

The canonical benchmark data is [`personacuabench/tasks.json`](personacuabench/tasks.json).
It contains exactly six task records and all 34 original rubrics. Its immutable
SHA-256 is recorded in [`personacuabench/metadata.json`](personacuabench/metadata.json);
there is no second task copy under another top-level package.

The latest-main role prompts are preserved under
[`personacuabench/prompts/`](personacuabench/prompts/README.md) and shipped in
the installed package. `experience_judge.md` powers the optional P1–P5
person-centered evaluation. The other three files document the earlier
Playwright/natural-user protocol; they are not silently injected into the
OSWorld matched-pair pipeline because doing so would change its tools and
experimental treatment.

## Reproducible environment

This project uses OSWorld V1. Exact OSWorld, Odysseys, and Persona-8B commits,
the local patch set, the resolved OSWorld lockfile hash, and the Ubuntu ARM VM
archive hash are recorded in [`reproducibility/`](reproducibility/README.md).
Upstream checkouts, virtual environments, VM images, API keys, caches,
screenshots, videos, and results remain local and are ignored by git.

Create the project environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Install the pinned Persona-8B renderer, then install the pinned OSWorld and
Odysseys checkouts:

```bash
./scripts/install_persona8b.sh
./integrations/osworld/install_osworld.sh
```

The OSWorld installer requires Apple Silicon macOS, `git`, `uv 0.12.13`, and a
working VMware Fusion installation. Fusion's EULA, privileged helper, and
network permissions must be approved through the macOS UI. See the
[OSWorld integration guide](integrations/osworld/README.md) for details.

Validate code and repository invariants without starting a VM or calling an
API:

```bash
.venv/bin/python scripts/validate_repository.py
.venv/bin/python -m unittest discover -s tests
```

## API configuration

Put the Azure key in `azure_api_key.txt` as one unquoted line and restrict its
permissions. The file is gitignored and its contents are never copied into a
run artifact.

```bash
chmod 600 azure_api_key.txt
export AZURE_OPENAI_API_KEY_FILE="$PWD/azure_api_key.txt"
export AZURE_OPENAI_BASE_URL="https://matraixwild.services.ai.azure.com/api/projects/MatrAIxWild/openai/v1"
export AZURE_OPENAI_REASONING_EFFORT=low
```

Role-specific `PERSONA_*` and `JUDGE_*` variables may point the simulator and
judge to different OpenAI-compatible endpoints. Check the configured endpoint
with one small Responses API request:

```bash
.venv/bin/python scripts/check_azure.py
```

The two experience-judge slots reuse the configured judge/Azure credentials.
Set `EXPERIENCE_JUDGE_A_MODEL` and `EXPERIENCE_JUDGE_B_MODEL` (or pass
`--judge-a` and `--judge-b`) when the endpoint exposes different deployments;
otherwise both use the common configured judge model, with `gpt-5.6-terra` as
the fallback, and run as separate calls.

## Personas and controlled pairs

The checked-in `smoke_*` profiles are synthetic wiring fixtures, not research
samples or demographic representations. They are validated and rendered by the
pinned MatrAIx-Persona-8B code.

```bash
.venv/bin/python -m personacuabench.make_personas --check
.venv/bin/python -m personacuabench.make_matched_personas --check
```

The controlled experiment uses six task-relevant axes: evidence verification,
price orientation, purchase-risk tolerance, decision style, time pressure, and
detail depth. Each positive/negative pair changes exactly one official MatrAIx
dimension while keeping the display name and every other dimension fixed. The
task mapping and scoring evidence live in
[`personacuabench/persona_experiment.json`](personacuabench/persona_experiment.json),
and generated profiles live in `personacuabench/personas/matched_pairs/`.

Each task has three applicable axes, producing 36 cells per replicate. Use at
least three independent replicate IDs. Inspect one complete replicate without
calling a model or starting a VM:

```bash
.venv/bin/python scripts/run_matched_pairs.py --replicate-id r1
```

Add `--execute` only when the runtime is ready. Both arms of a pair must use the
same task, models, prompts, runtime limits, and replicate ID. Both arms must
still communicate every original rubric, and task wording alone cannot earn
full persona-adherence credit.

## Preview and run

Preview the control condition without starting VMware or calling a model:

```bash
.venv/bin/python -m personacuabench.run \
  --task 1 \
  --persona none \
  --preview
```

A named-persona preview calls the persona endpoint only when its opening cache
is missing:

```bash
.venv/bin/python -m personacuabench.run \
  --task 1 \
  --persona smoke_budget_mobile \
  --preview
```

Run one real control cell with the OSWorld environment:

```bash
.osworld/OSWorld/.venv/bin/python -m personacuabench.run \
  --task 1 \
  --persona none \
  --model gpt-5.6-terra \
  --headless
```

Run selected task × persona cells serially:

```bash
PERSONAS="none smoke_budget_mobile" TASKS="1 4" \
  ./personacuabench/run_grid.sh
```

Only one VM is used at a time. Repeating a command skips a completed cell when
the task, persona, model, limits, replicate ID, source fingerprint, and upstream
revisions are unchanged. Use `--force` only when the completed artifact should
be replaced.

## Availability preflight and dual scores

The original task text, R1–Rn rubrics, and upstream task JSON are never
rewritten. Endpoint availability rules live separately in
[`personacuabench/availability_policies.json`](personacuabench/availability_policies.json).
For configured tasks, the runner performs a read-only guest-network preflight
after the VM reset and before the first CUA prediction. It does not navigate the
browser, consume an agent step, or enter the persona/CUA prompt.

The preflight is persisted as `network_preflight.json`; its hash is recorded in
`result.json` and its contract is defined by
[`personacuabench/schemas/network_preflight.schema.json`](personacuabench/schemas/network_preflight.schema.json).
The DNS-only v1 gate permits an adjustment only when every target alias fails
repeated resolution, the guest has a default route, and at least two independent
controls both resolve and return HTTP 2xx/3xx. WAF/403 pages, 404 responses, TLS
failures, timeouts, and general connectivity failures remain indeterminate.
Disable the diagnostic with `--no-network-preflight`; the adjusted score will
then remain null.

The probe does not follow redirects, rejects local/private target addresses,
isolates DNS and HTTP operations behind hard deadlines, and uses a 20-second
guest watchdog below OSWorld's controller timeout. The checked-in Kobe policy
maps only R1 to the Sole Collector aliases: composite R5 also depends on other
sites and the final synthesis, so removing all of R5 would over-credit unrelated
missing work.

This is additive scoring, not a task modification:

- `judgement.score` / `judgement.score_raw` remains the original R1–Rn score;
- `judgement.score_availability_adjusted` is a separately labeled diagnostic;
- original `met: false` verdicts remain false;
- only policy-mapped rubrics that depend exclusively on a proven unavailable
  endpoint leave the adjusted denominator;
- if every rubric would be excluded, the adjusted score is null, not 1.0.

Historical runs without an eligible after-reset, before-agent preflight are not
retroactively adjusted.

## Judge and report

First inspect exactly what a judge call would upload; offline mode makes no API
calls and writes no judgement:

```bash
.osworld/OSWorld/.venv/bin/python -m personacuabench.judge \
  artifacts/results/<task-id>/<run-directory> \
  --offline
```

Then opt in to judging:

```bash
.osworld/OSWorld/.venv/bin/python -m personacuabench.judge \
  artifacts/results/<task-id>/<run-directory> \
  --model gpt-5.6-terra \
  --reasoning-effort low \
  --max-images 0
```

`--max-images 0` sends all selected trajectory screenshots; a positive value
sends only the last N. Normal judging also sends the task/rubric text, actions,
conversation, open tabs, and final answer.

The optional person-experience judge is another explicit phase. Preview one
run without an API call or write, then request two independent P1–P5 verdicts:

```bash
.osworld/OSWorld/.venv/bin/python -m personacuabench.experience_judge \
  artifacts/results/<task-id>/<run-directory> --offline

.osworld/OSWorld/.venv/bin/python -m personacuabench.experience_judge \
  artifacts/results/<task-id>/<run-directory> \
  --judge-a gpt-5.6-terra --judge-b gpt-5.6-terra
```

Omit the run argument and add `--results artifacts/results` to process every
eligible result recursively. The two judge outputs and their per-dimension
agreement are retained independently; the pipeline never averages them. This
phase sends persona traits plus task, conversation, action, answer, and final
tab text twice, but sends no screenshots.

The recorded scoring axes stay separate. In the `none` control, persona
adherence/alignment are not applicable; the optional experience phase can
still evaluate the encounter because the control user sent the full task
verbatim.

- `task_success.score_raw`: original Odysseys task success;
- `task_success.score_availability_adjusted`: optional environment diagnostic;
- `persona.adherence`: for a named persona, whether the simulated user
  expressed assigned traits;
- `persona.alignment`: for a named persona, whether the CUA respected
  preferences communicated by that user;
- `experience.judge_a` and `experience.judge_b`: optional user-side P1–P5
  verdicts for asked-for coverage, readability, actionability, gap handling,
  and overall experience.

These scores are never averaged together. Summarize all runs or render a
detailed report for one run with:

```bash
.venv/bin/python -m personacuabench.report
.venv/bin/python -m personacuabench.detailed_report \
  artifacts/results/<task-id>/<run-directory> \
  --output artifacts/report.md
```

Each run directory retains `traj.jsonl`, `conversation.jsonl`, screenshots,
`open_tabs.json`, optional `network_preflight.json`, recording metadata, persona
session state, OSWorld's numeric `result.txt` marker, and an atomic `result.json`.
