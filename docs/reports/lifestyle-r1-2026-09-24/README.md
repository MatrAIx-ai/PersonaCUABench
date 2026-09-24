# Lifestyle: first replicate (r1)

Owner: Yingtao Luo. This report includes only the 30 saved cells from the first
replicate of the Lifestyle matrix collected on September 24, 2026. There are
26 records with automatic task scores and four unscored access failures.
All six assigned tasks and all 15 applicable task–axis pairs are represented.
No recorded 429 outcome was found among these r1 records.

## Results and evidence

The [results table](RESULTS.md) lists every cell and links to its JSON evidence.
Each review copy retains the original task/rubrics, configuration fingerprints,
persona metadata, environment checks, saved conversation and action previews,
final tabs, final response and original automatic judgements where available.
The [structured summary](summary.json) contains the same per-task counts and
mean raw scores. Unscored cells are excluded from means, never assigned zero.

| Task | Scored / planned cells | Mean raw task score |
|---|---:|---:|
| Father's Day gifts | 4 / 4 | 0.950 |
| All-black outfit | 6 / 6 | 0.889 |
| Men's outfit | 6 / 6 | 0.958 |
| Shared journaling | 4 / 4 | 0.600 |
| Christmas gifts | 6 / 6 | 0.400 |
| Budget outfit | 0 / 4 | unscored |

All four budget-outfit cells stopped at the required JJ's House preflight:
HTTP 403 and a security-verification page. Their JSON records preserve the
failed URL, HTTP status, page sample and missing expected content. These are
environment failures; they do not establish a model success or failure.

Two scored records reached 50 steps with an empty final answer: all-black outfit
`mp_price_orientation_positive` (raw 2/6), and Christmas gifts
`mp_purchase_risk_positive` (raw 0/5). Thus only 24 cells have a non-empty final
response. Their historical scores are preserved and flagged in the cell table;
they are not described as successful completion. The current runner now leaves
empty-answer runs unscored and does not skip them when resuming.

One original judge output also has a malformed field: men's outfit
`mp_purchase_risk_positive`, R1, contains `" met": true` with a leading space.
The historical scorer looked for `met` and counted that item as false, yielding
3/4. The raw object and score are retained; the report does not silently fix the
key or infer a corrected score. This is a judge-formatting anomaly requiring
review, not evidence that the underlying browsing succeeded or failed.

## Configuration and provenance

- Six unchanged Lifestyle tasks; four matched axes and eight personas.
- Agent, persona user and task judge: `google/gemini-3.8-flash`, provider `vertex`.
- Local Playwright browser through Docker Chrome/CDP; fresh context per cell;
  50 agent steps and a 14-tab limit.
- Recorded temperature argument: 1.0. The Gemini adapter sends reasoning effort
  `medium` for agent/persona calls and `low` for the judge, and does not send a
  temperature parameter. The recorded argument is not an effective temperature.
- Model-generated persona openings, cached per cell; the agent sees user
  utterances, not the private profile or expert rubrics.

These are historical results from the Lifestyle implementation developed on
`main-shop` at `d8a2885`. They were not rerun with this main-based PR. Each record
contains task, profile, prompt, environment-plan and run-configuration hashes;
it does not contain a complete source-tree hash, so exact historical executable
provenance cannot be reconstructed from those fingerprints alone. The historical
collection continued after blocked cells; the checked-in planner now stops at
the first failed or unscored cell, so unaffected slices must be selected explicitly.

## Interpretation and missing measurements

The numbers above are original LLM rubric scores, not independently audited
completion. Saved tool outputs are only the first 400 characters per action;
the historical task judge received still shorter action excerpts. Screenshots,
video and complete page observations were not saved. A high automatic score
therefore cannot independently prove that every product, price or action was
correct. No current website content has been substituted into these records.

These r1 records do not contain post-hoc persona-expression or P1–P5 experience
scores. Those measurements are **missing**, not zero; persona separation and
alignment cannot be concluded from task scores. There is no `none` control in
this report. One replicate does not establish a stable persona effect, and the
unscored budget task prevents a complete six-task performance comparison.

The runtime is local Chrome/Playwright, not the official OSWorld execution and
screenshot evaluation setup. These scores should not be presented as official
Odysseys leaderboard results.

## Redaction and offline verification

The [manifest](manifest.json) records each source-relative path, original file
SHA-256 and review-copy SHA-256. The export removes local user paths, IP
addresses, GCP project IDs and Google challenge URLs. Raw local originals are
unchanged; the committed copies do not include credentials or browser profiles.

From the repository root:

```bash
python docs/reports/lifestyle-r1-2026-09-24/evidence.py verify
```

This checks all 30 review-copy hashes, exact matrix coverage, task snapshots,
configuration hashes, original score arithmetic, 26/4 accounting and generated
tables. It does not validate the judge's interpretation of website evidence.
No model API or website is called. To regenerate from the private archive, use
`evidence.py export --archive <artifacts-directory>`; selection is fixed to
`lifestyle-final-results`, suite `lifestyle`, replicate `r1`.
