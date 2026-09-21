# Science and Education — matched-pair persona experiment

Suite ID `science-education`. Six Odysseys tasks from the Science and Education
assignment, three controlled persona pairs, six generated personas plus the `none`
verbatim control.

## Tasks

Copied unchanged by `task_id` from [`ljang0/Odysseys`](https://github.com/ljang0/Odysseys)
`data/odysseys.json` and verified byte-identical against upstream. 32 rubric items total.

| # | level | rubrics | task_id | content |
|---|---|---|---|---|
| 1 | easy | 4 | `65c9e7d383…` | Bing search for latent growth models, a ChatGPT prompt template, the 10015.io bionic converter, a free plagiarism checker |
| 2 | easy | 4 | `e15345ed27…` | 5th-grade grammar quiz, 8th-grade marketing worksheet, a Slidesgo template, bionic conversion of a fixed lesson intro |
| 3 | easy | 6 | `8c30f2f9ce…` | IBM's AI/ML categories page, Copilot.com, the Tom's Hardware Granite Rapids article |
| 4 | medium | 7 | `6421b906fe…` | Graduate outreach across six institutions (Lewis & Clark, Hunter Silberman, IU Kokomo, UCSF, ORU, EDF Energy) |
| 5 | medium | 4 | `4614aa0831…` | Three Maryland/DC law schools: outreach routes, an admissions event, the PIPS scholarship, a first-contact recommendation |
| 6 | medium | 7 | `976970ff5d…` | Youth mental-health evidence pack: three cited sources plus a Wikipedia track listing |

## Axes

Three pairs, six personas. Each pair changes exactly one MatrAIx dimension against a
shared baseline of `cog_detail_orientation: Moderate`, `cog_directness: Balanced`,
`decision_style: Deliberative`.

| axis_id | dimension | positive | negative | tasks |
|---|---|---|---|---|
| `detail_depth` | `cog_detail_orientation` | Very high | Low | 2, 4, 5 |
| `request_directness` | `cog_directness` | Blunt | Indirect | 1, 4, 6 |
| `decision_style` | `decision_style` | Analytical | Intuitive | 3, 5, 6 |

Matrix: 9 task-axis pairs, **18 run cells per replicate**, 6 named personas.
Every task maps to at least one axis.

## How these axes were chosen, and what did not work

This is the main methodological note for reviewers, because the result was mostly
negative and it shaped the final set.

These six tasks are densely specified — 239-311 words each, 4-7 rubric items, naming
exact sites and in three cases exact verbatim strings. The matched-pair prompt requires
the simulator to communicate every requirement and to add none. That combination leaves
very little room for a behavioural axis to express itself, and most candidates expressed
nothing.

Seven dimensions were screened against the real simulator prompt before this set was
fixed (`work/screen_axes.py` in the contributor's working tree reproduces the screen:
it renders the same profile through `persona.py` and the same
`prompts/persona_user_matched_pair.md`, then calls the same persona model). Separation
was read from the two arms' openings, using the length delta between them as the
discriminating signal:

| candidate dimension | outcome |
|---|---|
| `cog_detail_orientation` | **separates** — 96- and 67-word deltas on tasks 4 and 5 |
| `cog_directness` | separates on the long field-rich tasks only — 42-word delta on task 4, 1 word on task 3 |
| `decision_style` | weak — 11-word delta on task 5 |
| `tone_expected` | moderate, but conceptually an alias of `cog_detail_orientation`; not used |
| `trust_level` | **fails** — the tasks already demand peer review, exact quotes and real pages, so the Trusting arm only repeats inherited task wording, which scores 1 by the protocol's own rubric |
| `time_pressure` | **fails** — the Deadline arm would have to invent a deadline, which the prompt forbids as adding a requirement |
| `pref_speed_vs_accuracy` | **fails** — both arms reproduced the task's own "compare the options" |

Two general lessons that likely apply beyond this suite:

- An axis whose behaviour the task text already mandates cannot separate, because both
  poles collapse onto inherited wording. `trust_level` is the clear case here and it is
  one of Shopping's axes — it transfers to shopping tasks, which do not demand citations,
  but not to these.
- An axis whose expression requires asserting a fact absent from the task (a deadline, a
  budget, a prior attempt) cannot separate either, because the prompt forbids adding
  requirements.

`detail_depth` works because depth of the deliverable is orthogonal to coverage of the
requirements: an arm can ask for more or less around the required fields without touching
them.

`request_directness` and `decision_style` are retained to meet the 3-pair protocol
minimum and because they target genuinely distinct constructs. They are expected to
separate weakly or not at all on the short tasks. Under the protocol's scoring policy a
non-separating pair is reported as non-separating rather than dropped or averaged away.

## What replicate r1 actually measured

One replicate, 18 cells, `gpt-5.6-terra` throughout. Results are not committed
(`artifacts/` is gitignored and the acceptance checklist forbids committing them).

| | |
|---|---|
| pairs separating (both arms score 2) | **2 of 9** |
| coverage guardrail | **18/18 cells communicated 100% of rubric items** |
| truncated at the step ceiling | 2/18 |
| mean raw task score | 0.600 — **environment-depressed, see Known limits** |

Separation by axis:

| axis | positive scored 2 | negative scored 2 | pairs separating |
|---|---|---|---|
| `request_directness` | 2/3 | 3/3 | **2/3** |
| `detail_depth` | 0/3 | 0/3 | 0/3 |
| `decision_style` | 0/3 | 0/3 | 0/3 |

**The pre-run screening picked the wrong winner, and that is worth recording.** Screening
ranked candidates by the word-count delta between the two arms' openings, which made
`cog_detail_orientation` look strongest (96- and 67-word deltas) and `cog_directness`
middling. The fidelity judge inverted that: `request_directness` is the only axis that
separates at all, and `detail_depth` never scored above 1. Length delta measures how much
the arms differ in bulk; the judge scores whether an arm made a *task-specific, affirmative*
statement of its pole. Those turn out to be nearly unrelated. Anyone screening axes should
score candidate openings with the fidelity judge rather than with a text proxy.

A second, more general pattern: the `detail_depth` **negative** pole ("Low", wants only the
required fields) scored 0 with the judge recording **no evidence at all** at 0.94
confidence. When the prompt already forces the user to communicate every requirement,
asking for "only the required fields" is indistinguishable from simply stating them, so a
"less of X" pole tends to have nothing affirmative to say. That is the "detectable only by
silence" failure the runbook warns about, and it is a property of low-magnitude poles in
general rather than of this dimension. `request_directness` avoids it because both Blunt
and Indirect are affirmative ways of phrasing the same content.

## Commands

```bash
python3 odyssey/run.py --list-suites
python3 odyssey/run.py --suite science-education --list-tasks

python3 odyssey/make_matched_personas.py --suite science-education
python3 odyssey/make_matched_personas.py --suite science-education --check

# dry run the whole matrix (18 cells)
python3 odyssey/run_matched_pairs.py --suite science-education --replicate-id r1 --headless

# review both openings for a pair before executing it
python3 odyssey/run_matched_pairs.py --suite science-education --replicate-id r1 \
  --task 6421b906fe97b3799960af31c77f20ff25f756b1 --axis detail_depth \
  --materialize-openings -- \
  --persona-model gpt-5.6-terra --persona-provider openai --temperature 1

# execute
python3 odyssey/run_matched_pairs.py --suite science-education --replicate-id r1 \
  --headless --execute -- \
  --model gpt-5.6-terra --provider openai \
  --persona-model gpt-5.6-terra --persona-provider openai \
  --judge-model gpt-5.6-terra --judge-provider openai \
  --temperature 1 --max-steps 50 \
  --out artifacts/science-education-results
```

Models follow the runbook's and Shopping's worked examples (`gpt-5.6-terra` on `openai`
for CUA, persona and judge). `run_matched_pairs.py` sets no model defaults of its own and
forwards to `run.py`, whose defaults are still `qwen/qwen3.8-27b` and `gpt-5.5`; those are
deliberately overridden so this suite matches Shopping rather than the older grid path.

## Known limits

**Google walls automated search, and a warm profile is necessary but not sufficient.**
Two separate factors, and it took a full replicate to see the second one.

*Profile state.* A cold Chrome profile is walled immediately. Measured in one minute from
one IP with only the profile differing: warm profile 3/3 searches returned real results,
two independently created cold profiles returned `google.com/sorry/...` 3/3.

*Per-IP volume.* A warm profile is not a licence. After a full 18-cell replicate the same
warm profile gets roughly one search through and is then walled, and a freshly seeded
profile behaves identically — so the limit is not carried in the profile.

What that did to `r1`: the two-cell smoke pair, run first, reached Google 10 and 12 times
with zero walls. The replicate that followed exhausted the budget, and **17 of its 18 cells
never reached Google at all** (57 wall hits, 9 successful searches total). Bing was
unaffected throughout — a cold profile still searches Bing fine.

This matters because **8 of the 32 rubric items name Google** in their verification text
and cannot pass while the wall is up, so `r1`'s task-success numbers are depressed by the
environment and should not be read as agent quality.

**It does not touch the persona-side results.** `persona_fidelity_judge.py` and the
`communicated` determination both read the conversation — the simulated user's utterances —
not the browsing trajectory. Pair separation and the 100%-coverage guardrail are therefore
valid as reported; only raw task score is affected.

Cells were run with each per-cell profile pre-seeded from one identical warm cookie
template — five files (`Local State`, `Default/Cookies`, `Default/Preferences`,
`Default/Secure Preferences`, `Default/Network Persistent State`), about 900 KB against
1.6 GB for a full profile. Same seed for every cell, so arms stay isolated from each other
while neither starts cold; seeding one arm and not the other would be worse than seeding
neither. That fixes the cold-start half of the problem and not the volume half. A couple of
scripted visits will not warm a profile — the state that works came from one with hours of
real browsing behind it.

Anyone can check their own runs with `grep -rl "/sorry" <results dir>`. Getting clean
task-success numbers for a Google-heavy suite likely needs a different network, a slower
cadence, or both.

**`gpt-5.6-*` needs `reasoning_effort="none"` to use function tools.** Running the
runbook's documented command as written fails immediately on the first CUA turn:

```
400 Function tools with reasoning_effort are not supported for gpt-5.6-terra in
/v1/chat/completions. To use function tools, use /v1/responses or set
reasoning_effort to 'none'.
```

Checked across the family on this account: `gpt-5.6-terra`, `gpt-5.6-sol` and
`gpt-5.6-luna` all fail with tools and all succeed with `reasoning_effort="none"`;
`gpt-5.5` succeeds either way. The CUA turn is the only call that sends tools.
`odyssey/run.py` previously set the argument nowhere, so the model's own default applied
and was rejected. This PR adds four lines in `_create_with_retry` that set
`reasoning_effort="none"` when a `gpt-5*` call carries tools and the caller has not set it.
Without that change the model named throughout the runbook and the Shopping suite cannot
drive the agent at all. It is the only change outside this suite's own directories.

**Step and tab ceilings.** `--max-steps 50` bounds model turns; note that `run.steps` in a
result counts tool calls, one per trajectory entry, and routinely exceeds 50 without that
being truncation. Only `stop_reason` in `{max_steps, max_steps_summarised}` is truncation.
`MAX_TABS = 8` in `run.py` binds on task 4, which wants pages from six institutions plus
search pages while its rubrics require tabs to stay open.

**Task 1 and task 3 external dependencies.** Task 1 and task 2 both depend on the
10015.io bionic reading converter, a small site; task 1 additionally requires Bing rather
than Google for two steps. Task 3's Tom's Hardware article carries ad interstitials — in an
earlier pilot on the grid path, clicking through an interstitial on 10015.io and then
returning to the clean URL reloaded the page and discarded the converted output, costing
that rubric item. That is an agent failure rather than an environment one, but it is worth
knowing when reading a low score on those tasks.
