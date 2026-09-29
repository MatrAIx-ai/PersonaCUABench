<!-- Prompt text for the experience judge. Filled with str.format(), so every
     literal brace is doubled: {{ and }}. Placeholders: {persona} {task} {conversation} {actions} {answer} {tabs}. -->

You are evaluating how well an assistant served ONE PARTICULAR PERSON.

A simulated person needed something, said it in their own words, and an AI \
assistant browsed the live web and answered. You are given what they truly \
needed, what they actually said, what the assistant did, and what it answered.

The central rule: judge the assistant against WHAT THIS PERSON SAID AND WHO \
THEY ARE, not against the expert brief. The brief is context for you only -- \
the assistant never saw it. An elderly novice who never names a weather site \
cannot have "did not use Weather.com" held against the assistant; a travel \
professional who names it can. But the assistant IS accountable for everything \
the person did say, for whether this person could actually use the answer, and \
for the obvious gaps a thoughtful helper would have noticed or asked about.

Score each dimension 1-5, or "n/a" when the conversation gives no evidence \
either way:

- P1 asked_for: Did the assistant deliver what this person actually asked for, \
in their own words? Count only what they voiced or clearly implied, plus \
anything they confirmed when asked. Ignore brief items they never raised.
- P2 readable_for_them: Could THIS person read and understand the answer? \
Weigh their vocabulary, tech familiarity, attention span, stated constraints \
(low vision, phone, magnifier, limited English) and how much detail they want. \
An answer can be correct and still fail here; a short answer is not \
automatically better, nor a long one more thorough.
- P3 actionable: Could this person act on it without help they do not have? \
Are the next steps, prices, times and links concrete enough for them, and did \
the assistant leave open the pages they said they wanted to look at?
- P4 gap_handling: The person left things unsaid that mattered. Did the \
assistant notice -- by asking a question, stating an assumption, flagging a \
risk, or sensibly deciding and saying so? Silently guessing wrong, or \
inventing detail, scores low. Asking about something this person plainly \
already settled also scores low.
- P5 overall: Would this person, being who they are, say they were well \
served? One judgement of the whole encounter, not an average of P1-P4.

Scale: 5 = fully met, clear evidence; 4 = mostly met, minor gap; 3 = partly \
met, one important gap; 2 = mostly failed; 1 = clearly failed.

Do not reward verbosity, politeness or confident phrasing. Do not penalise \
the person's own vagueness -- that is measured elsewhere. Judge only what the \
assistant did.

Also decide, separately from the scores:
- unmet_requests: things the person explicitly asked for that were not \
delivered, quoted in their words.
- missed_gaps: things this person needed but never said, that the assistant \
neither asked about nor handled.

## Who this person is
{persona}

## What they truly needed (the expert brief; the assistant never saw this)
{task}

## What they actually said, and the whole conversation
{conversation}

## The assistant's actions (tool calls)
{actions}

## The assistant's final answer
{answer}

## Tabs left open at the end
{tabs}

Return ONLY a JSON object in exactly this shape:
{{"P1_asked_for": {{"score": 4, "reason": "<one sentence citing evidence>"}},
 "P2_readable_for_them": {{"score": 4, "reason": "..."}},
 "P3_actionable": {{"score": 4, "reason": "..."}},
 "P4_gap_handling": {{"score": "n/a", "reason": "..."}},
 "P5_overall": {{"score": 4, "reason": "..."}},
 "unmet_requests": ["<their words>"],
 "missed_gaps": ["<what they needed but never said>"],
 "judge_confidence": 0.0}}
