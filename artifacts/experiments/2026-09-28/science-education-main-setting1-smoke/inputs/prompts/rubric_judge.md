<!-- Prompt text for the rubric judge in run.py. Filled with str.format(), so every
     literal brace is doubled: {{ and }}. Placeholders: {task} {conversation} {rubric} {answer} {actions} {tabs}. -->

You are grading a web agent against a fixed rubric. A user \
asked the agent for help in their own words; the agent browsed the live \
internet and produced a final answer.

For each rubric item decide two things independently:

- met: was the requirement actually satisfied, by evidence in the final answer, \
the action log and the tabs left open? A requirement that a page be left open is \
met only if that page appears in the open tabs. A reported figure counts only if \
the agent actually visited a page that would show it. Judge this the same way \
whether or not the user asked for it.
- communicated: did the conversation make this requirement known to the agent -- \
said explicitly, or implied clearly enough that a reasonable assistant would act \
on it? A specific site or detail the user never mentioned and the agent never \
asked about is NOT communicated.

Do not reward or penalise tone, personality, verbosity or writing style.

## What the user actually needed (hidden from the agent)
{task}

## Conversation between the user and the agent
{conversation}

## Rubric
{rubric}

## Agent's final answer
{answer}

## Action log (tool calls the agent made)
{actions}

## Tabs left open at the end
{tabs}

Return ONLY a JSON object, one entry per rubric id:
{{"R1": {{"met": true, "communicated": true, "reason": "<one sentence citing the evidence>"}}, ...}}
