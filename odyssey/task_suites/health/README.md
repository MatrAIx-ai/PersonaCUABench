# Health — Yiyang Wang

This suite contains the six tasks assigned under **Health (Yiyang Wang)** in
the PersonaCUABench task-assignment document. The records, task IDs, task
wording, and ordinary rubrics were copied unchanged from
`ljang0/Odysseys`, `data/odysseys.json`, commit
`837814633ef948479abb3d142458f0acdb73fa65`.

The recorded runs used PersonaCUABench `main-shop` at `d8a2885` as their
implementation base. This contribution is based on `main` and includes the
shared routing, matched-persona, and evidence components needed by Health.
The original `tasks.json` remains the default suite; select `--suite health`
for these six tasks. Existing main model defaults and explicit Azure routing
remain available.
The runtime is **local Google Chrome through Playwright**. It is not the
strict OSWorld VM integration.

| Level | Task | Full task ID |
|---|---|---|
| Easy | Clovis/Fresno Pilates comparison, including Title 29 | `69782bfcfdb3311496bc9048bf66915b33e692cd` |
| Easy | Coil/Tower Yoga and highest-view-count yin video | `5e09c06aa92c1e252db5106a72e8d61e59356c7e` |
| Easy | Free YouTube instructor shortlist and two yoga videos | `328ce861b58b2cf2e6da520040193710f95cfe56` |
| Medium | Exactly ten LA maternity hospitals in a CryptPad Document | `e8b73f739732f8aeb3c473d00f6219af5b8dcdb7` |
| Medium | Exactly ten NYC knee surgeons in a spreadsheet | `256342f13c0a03e080f92ee073153fe33a6881c0` |
| Medium | Tower Yoga, Blue Moon Yoga, and Fight Girl Fitness | `e1aca0ae8174c6f1847be80c82d8adc63d031b23` |

## Six personas: controlled explicit preferences

Protocol `health-matched-pairs-v3` defines three axes and six generated profiles.
All profiles share the display name Alex Rivera and the same baseline:
`cog_detail_orientation=Moderate`, `decision_style=Deliberative`,
`trust_level=Trusting`. Exactly one dimension changes within each pair.

| Pair | Values | Full applicability |
|---|---|---|
| Detail oriented / Essentials only | Very high / Low detail orientation | All six tasks |
| Analytical / Intuitive chooser | Analytical / Intuitive decision style | Four fitness tasks |
| Evidence checker / Comfortable delegating | Verifying / Trusting | Hospitals and surgeons |

Both arms keep every original requirement. Low detail removes optional background,
not required fields. Trusting delegates interpretation after all required official
verification; it does not weaken the evidence floor.

The full matrix has 12 task-axis pairs and 24 cells per replicate. Three formal
replicates would be 72 cells. The current feasibility pilot selects one pair per
task, producing 12 cells: detail for tasks 1–2, decision for tasks 3 and 6, and
evidence verification for tasks 4–5. The `none` control is additional.

### Fixed opening method

Each V3 opening is the exact `confirmed_task`, followed by that arm's
`positive_opening_preference` or `negative_opening_preference` from the protocol.
The simulator supplies LLM clarification replies only. The CUA sees user utterances,
never the profile, opposite arm or hidden ordinary rubric.

This explicitly tests CUA response to a stated preference. An opening expression
score is a check of an authored stimulus, not evidence of spontaneous persona
simulation. V1 and V2 model-generated previews sometimes omitted the assigned
preference. Failed previews are retained; V2 had no browser execution.

Never hand-edit generated YAML. Update the JSON protocol and regenerate:

```bash
.venv/bin/python odyssey/make_matched_personas.py --suite health
.venv/bin/python odyssey/make_matched_personas.py --suite health --check
.venv/bin/python odyssey/test_pipeline.py
.venv/bin/python odyssey/test_browser.py
.venv/bin/python odyssey/run_matched_pairs.py --suite health --replicate-id r1 --headless
```

The browser test uses only local HTML. It verifies visible links, visible iframe
reading/editing and enough tabs for the provider tasks. It does not guarantee
remote schedules, YouTube playback or CryptPad availability.

## AWS and the runtime

Use the normal Python environment and installed Google Chrome:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r odyssey/requirements.txt
```

The Bedrock provider reads only `AWS_BEARER_TOKEN_BEDROCK` or
`AWS_BEARER_TOKEN_BEDROCK_FILE`, plus `AWS_REGION` or `AWS_DEFAULT_REGION`.
It does not borrow OpenAI or Azure keys. Keep credentials out of source and results.
The OpenAI-compatible endpoint is derived from the selected AWS region.

The pilot uses `openai.gpt-oss-120b` through Bedrock in `us-west-2` for every model
role, temperature 1, reasoning effort low, 50 agent steps, 4,000 completion tokens
per agent response, a 60-second API deadline, and 16 tabs. Low reasoning effort
passed an actual tool-call probe. The earlier `openai.gpt-5.6-terra` probe was
rejected on this Chat Completions route despite appearing in the models list.

Runtime `playwright-visible-frames.v4` includes visible iframe text, editable controls,
real link discovery, visible text/label clicks, and keyboard input. It stops click
searching once a visible match is found, so an unnecessary lookup in a still-loading
third-party frame cannot block an available page control. It also writes an atomic
partial trajectory checkpoint after each tool result. A live Tower Yoga reproduction
confirmed that the schedule click completes with this change. The task judge
receives the retained visible tool results. It remains an LLM judge and can make
mistakes: the pilot audit found unsupported answer claims that earned raw points.
Do not silently overwrite raw scores or describe them as verified completion.

## A new controlled pair

Choose a fresh replicate ID. Preview and review both arms before executing with
identical settings. In V3 the initial openings are deterministic; credentials are
still needed for model-client initialization and later execution.

```bash
.venv/bin/python odyssey/run_matched_pairs.py \
  --suite health --replicate-id review-pilates-r1 \
  --task 69782bfcfdb3311496bc9048bf66915b33e692cd --axis detail_depth \
  --materialize-openings -- \
  --persona-model openai.gpt-oss-120b --persona-provider bedrock \
  --temperature 1 --reasoning-effort low --request-timeout 60
```

After reviewing the exact openings:

```bash
.venv/bin/python odyssey/run_matched_pairs.py \
  --suite health --replicate-id review-pilates-r1 \
  --task 69782bfcfdb3311496bc9048bf66915b33e692cd --axis detail_depth \
  --headless --execute -- \
  --model openai.gpt-oss-120b --provider bedrock \
  --persona-model openai.gpt-oss-120b --persona-provider bedrock \
  --judge-model openai.gpt-oss-120b --judge-provider bedrock \
  --temperature 1 --reasoning-effort low --request-timeout 60 \
  --max-steps 50 --agent-max-output-tokens 4000 --max-tabs 16 \
  --out artifacts/health-new-results
```

This runs two cells, not the full matrix. The packaged `run_health_pilot.py`
records the exact six selected task pairs and preserves every attempt. It uses
sequential arms and at most two independent task pairs concurrently. Do not reuse
an isolated profile across arms or relabel an unsuccessful attempt as a new result.
That driver belongs to the local historical archive; the commands above use the
checked-in runner and are the supported way to start a new pair from this PR.

## Evidence and post-hoc judging

The local archive includes `artifacts/health-pilot-v3-r1/` with the plan, opening review,
source hashes, smoke review, logs, raw results and a separate assistant evidence audit.
`artifacts/persona-openings/health/` includes cached openings and failed historical
calibration. Those runtime directories remain ignored by Git.
The PR includes a [redacted evidence bundle and audit](../../../docs/reports/health-pilot-2026-09-22/README.md)
with all 17 attempts, 12 final responses, original scores, and source-indexed
reviews of all 66 rubric decisions. Local browser profiles and credentials are excluded.

Four V3 attempts on tasks 2 and 6 stalled in `Locator.all()` while looking for click
text in an embedded frame. The complete V3 source and patch are archived alongside
those failures. After the V4 fix and regression checks, `run_health_recovery.py`
reran both blocked pairs as `health-recovery-v4-r1`: four fresh cells with exactly
the same reviewed opening text and model settings. Recovery artifacts are separate
from the initial pilot and include per-action `checkpoint.json` files.
The analytical fitness recovery timed out on an AWS request. Its unscored result
and checkpoint were preserved, and one fresh-profile retry is recorded under
`artifacts/health-recovery-v4-r1/api-retry/`. Its command and reason are in
`attempt.json`. This brings the total to 17 attempts and 12 final responses,
covering both personas on all six tasks, without erasing infrastructure failures.

`judge_health_pilot.py` adds persona-expression and P1–P5 experience scores separately.
It uses two distinct experience calls to the same model, not diverse judges. It
records low reasoning effort and prompt hashes. The original task judge's raw
scores remain unchanged.

Earlier control attempts are historical: one stalled and was interrupted, and
one bounded attempt produced an empty answer that the old runner incorrectly
scored 0/4. The current runner normally preserves empty output and API errors
as unscored outcomes. V3 also exposed a browser-cleanup hang: some Tower Yoga
schedule clicks stalled, and graceful interruption could itself hang in
Playwright. Those cells required external termination and have limited
logs/history instead of complete trajectories. They remain unscored. The
older control records are not pooled with the V3 pilot.

The user-facing `health-pilot-report.md` and `health-pilot-results.json` contain
observed outcomes. A strict OSWorld run requires the separately reviewed VM
integration described in the contributor runbook; using a Python environment
named OSWorld does not supply that integration.
