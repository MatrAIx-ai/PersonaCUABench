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

**Cold Chrome profiles are served Google's bot wall.** `run_matched_pairs.py` gives each
cell its own isolated profile under `artifacts/chrome-profiles/matched-pairs/...`, which is
correct — no browser state should leak between arms — but it means every cell starts cold.
Measured on the contributor's machine, in the same minute and from the same IP, with only
the profile directory differing: a warm profile returned real results for 3 of 3 Google
searches, two independently created cold profiles returned `google.com/sorry/...` for 3 of 3.

This matters here because **8 of the 32 rubric items name Google** in their verification
text. Cells were therefore run with each per-cell profile pre-seeded from one identical
warm cookie template — five files (`Local State`, `Default/Cookies`, `Default/Preferences`,
`Default/Secure Preferences`, `Default/Network Persistent State`, about 900 KB against
1.6 GB for a full profile). Seeding every cell from the same source keeps the arms isolated
from each other while giving both an identical, non-cold starting state; seeding one arm
and not the other would be worse than seeding neither. A couple of scripted page visits is
**not** sufficient to warm a profile — the state that works came from a profile with hours
of real browsing behind it.

Anyone can check their own runs with `grep -rl "/sorry" <results dir>`.

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
