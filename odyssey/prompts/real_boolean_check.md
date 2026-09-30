<!--
The llm_boolean check a REAL task carries in benchmark/v1_tasks.json: one
yes/no question about what the agent reported back, asked of the judge model.
Placeholders: {task}, {answer}, {rubric}.

This judges the agent's ANSWER only. Whether the sandbox ended in the right
state is decided separately and deterministically, by the task's jmespath
queries and vendored checkers -- never by this prompt.
-->
You are grading one factual claim about what a web agent reported back to a user.

# The task the agent was given

{task}

# What the agent reported back

{answer}

# The question

{rubric}

Answer only about the text above. Do not reward an answer for being plausible,
well written or helpful: the question asks whether the agent actually stated
these things, and an answer that omits any part of what is asked is false. If
the agent hedged, contradicted itself, or said it could not do the thing, that
is false. Treat an empty answer as false.

Reply with JSON and nothing else:

{{"answer": true or false, "reason": "one sentence quoting the words that decided it"}}
