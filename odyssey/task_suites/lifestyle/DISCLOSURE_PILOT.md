# Preference disclosure pilot (not yet executed)

## Why a separate protocol

Historical r1 instructs personas to disclose all hard requirements and relevant
preferences immediately. Its original judges mark all requirements communicated
in all 26 scored records, and there are no recorded ask_user calls. Regrading
those records cannot create a missing-information experiment.

Keep r1 unchanged. This opt-in pilot asks whether an agent handles an explicitly
signalled, unresolved **soft preference**, without hiding original task rubrics.
Task completion, preference expression, clarification and preference-sensitive
selection remain different outcomes. In particular score_communicated can still
equal score here: the withheld preference is not an original task rubric.

## Fixed design

Start with Father's Day, price orientation only. Four cells per new replicate:

| Condition | Cost-sensitive | Premium-seeking |
|---|---|---|
| full | Original task + common cue + fixed preference | Same, opposite preference |
| gap | Original task + common cue; preference private | Identical public opening; opposite private preference |

The common cue says the price-versus-quality tradeoff is unresolved. Full adds
the resolution. All original sites, products, caps and deliverables stay public
and unchanged. Price orientation only applies when multiple options satisfy
the original requirements; it cannot override the Nike price check or other
requirements. There is no invented numerical budget.

An optional fifth `neutral` cell uses the same task and cue but has no private
price orientation. It is not the legacy `none` verbatim-task baseline. A neutral
arm can characterize default behavior, but there is no objectively correct
hidden preference against which to judge it.

The simulated user is deterministic, not another LLM. Questions matching the
documented English price/quality/preference trigger receive the fixed preference;
other questions receive a fixed no-additional-constraint reply. Every trigger
decision is saved. This restricted responder can miss paraphrases or disclose
on an overly broad question: audit every clarification, and mark a responder
mismatch invalid rather than blaming the agent. Do not generalize this pilot
to natural dialogue capability.

`controlled_disclosure.py` contains the exact cue, both replies and regex. Its
source hash and condition are part of run identity. No generated opening cache
is consumed; conditions cannot share scored-result resume identities. Private
metadata is saved for evaluation but is not sent to the browser agent.

## Offline checks (no Vertex)

Run in `PersonaCUABench-lifestyle-main` with the project's Python environment:

```powershell
& '../PersonaCUABench-lifestyle/.venv/Scripts/python.exe' odyssey/test_controlled_disclosure.py
foreach ($condition in @('full', 'gap')) {
  foreach ($arm in @('positive', 'negative')) {
    & '../PersonaCUABench-lifestyle/.venv/Scripts/python.exe' odyssey/run.py --suite lifestyle --task 1211fbaa --persona "mp_price_orientation_$arm" --interaction-condition $condition --replicate-id disclosure-pilot-r1 --preview
  }
}
```

Preview is scripted and makes no provider or browser calls for these conditions.
Legacy `--preview` still calls the persona model; do not confuse the two.
Execution is deliberately not started by these commands. A later live run needs
explicitly selected agent/judge providers, Docker CDP and a separate output root.
The existing environment gate, fresh-context behavior, empty-answer guard and
resume checks apply. Never mix these outputs into historical r1.

## Prespecified evidence review

For each cell record:

1. Public opening, private preference and first user-turn index disclosing it.
2. Every question and reply, trigger correctness, and whether the information
   was already available. Asking redundant questions is not automatically good.
3. Before/after search queries, filters, visited product/policy pages, compared
   prices/materials, and final selection, each with event-index references.
4. Gap handling: relevant clarification, explicit reversible assumption,
   alternatives preserving the unresolved choice, unsupported guessing, or
   not assessable. Do not require a question when a transparent assumption or
   presenting both options serves the user. Never score clairvoyance about a
   private preference as required behavior.
5. Original task score and communicated score separately from soft-preference
   fit. A missed hard requirement cannot be offset by pleasant personalized prose.

Only claim action-level adaptation when saved actions/observations support it;
answer style alone is presentation-level adaptation. Full returned tool text and
the exact observation sent to the agent are now saved separately; historical
400-character previews cannot be recovered. Full tool returns are still not a
recording of every possible webpage state or screenshots. Redact new full text
before publishing it.

Do not auto-convert this evidence review into P1–P5 scores. If numerical ratings
are added, fix the rubric and evaluation method before inspection; use n/a where
appropriate and keep raters/results distinct. Two independent judges have not
been run. A withheld persona is intentionally unexpressed at the beginning;
that is not a persona-generator failure. Evaluate expression after an eligible
question separately from successful initial disclosure in the full condition.

## What would close the empirical gap

The first four live cells only validate the mechanics. Before a larger batch,
fix repeat count, execution order and invalid-run policy; interleave conditions
and counterbalance persona order to reduce website/time confounds. Start with
three repeats as a feasibility check, not a claim of statistical power. Report
all failures, invalid responder turns and missing answers. Later choose sample
size based on the desired uncertainty and observed variance; do not stop when
an effect appears. No causal or stable-personalization conclusion follows from
the current single historical replicate or from offline unit tests.
