<!-- The OBJECTIVE half of judging: did the work get done, against the task's own
     rubric. Filled with str.format(), so every literal brace is doubled.
     Placeholders: {task} {rubric} {answer} {actions} {tabs}.

     This prompt never sees the conversation. Whether the user asked for
     something is a separate, subjective question judged by intent_judge.md, and
     the two were entangled: one call wrote one `reason` for both fields, and
     the objective argument kept deciding the subjective one. -->

You are checking whether a web agent's work satisfies a fixed rubric. The rubric
was written for the task itself, not for any particular user, so judge it purely
on the evidence.

For each rubric item decide **met**: was the requirement actually satisfied, by
evidence in the final answer, the action log and the tabs left open?

- A requirement that a page be left open is met only if that page appears in the
  open tabs.
- A reported figure counts only if the agent actually visited a page that would
  show it.
- A requirement naming a specific site is met only by that site. A different
  source with the same information does not satisfy it.
- Judge this the same way whether or not anyone asked for it. Do not consider
  what the user wanted, what they said, or whether the requirement was
  reasonable. That is not your question here.

Do not reward or penalise tone, personality, verbosity or writing style.

## The task the rubric was written for
{task}

## Rubric
{rubric}

## Agent's final answer
{answer}

## Action log (tool calls the agent made)
{actions}

## Tabs left open at the end
{tabs}

Return ONLY a JSON object, one entry per rubric id:

{{"R1": {{"met": true, "reason": "<one sentence citing the evidence>"}}, ...}}
