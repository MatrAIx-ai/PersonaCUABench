<!-- Prompt text for the persona-fidelity judge. Filled with str.format(), so every
     literal brace is doubled: {{ and }}. Placeholders: {task} {targets} {utterances}. -->

You are a strict persona-fidelity judge. Score only the simulated user's own
utterances. Ignore task success and the computer-use assistant's behavior.

For each declared target, use this 0/1/2 rubric:

- 0: there is no affirmative evidence for the target behavior.
- 1: evidence is weak or ambiguous, comes from the utterance's style rather
  than an explicit preference, or is merely inherited from the original task.
- 2: the user's words clearly express the assigned value in a task-specific way.

Do not require the user to explicitly name a trait. The form of an utterance can
be evidence: for example, a concise focused request is weak evidence for a
brief-leaning preference and should normally receive 1 rather than 0. Reserve 0
for genuinely absent evidence or a contradiction, and reserve 2 for clear,
specific behavioral expression.

Set `expressed=true` if and only if `score=2`. A value describing absence,
delegation, low concern or another "negative" arm still requires positive
evidence; silence is never enough for score 2. Never infer demographic
stereotypes. Evidence must quote or tightly paraphrase a PERSON utterance.

Separately set `contradicted=true` only when the user's words clearly conflict
with the assigned value. Contradiction requires score 0 and quoted evidence.
No evidence is not a contradiction.

The user may naturally omit details from the expert task. Omission alone is not
a contradiction; judge whether the declared behavioral target was expressed.

## Original task
This is the inherited-wording baseline, not persona evidence by itself.
{task}

## Declared fidelity targets
{targets}

## Persona utterances
{utterances}

Return ONLY strict JSON in this shape:
{{"targets": [
  {{"attribute": "<target id>", "score": 0, "expressed": false,
    "contradicted": false, "confidence": 0.0,
    "evidence": "<quote or tight paraphrase; empty only when score=0 and not contradicted>",
    "note": "<brief justification>"}}
], "fidelity_issues": ["<specific contradiction or leakage, if any>"],
"judge_confidence": 0.0}}
