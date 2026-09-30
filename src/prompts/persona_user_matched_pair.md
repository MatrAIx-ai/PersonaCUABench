<!-- Prompt text for a controlled matched-pair persona user. Filled with
     str.format(); placeholders: {goal}. -->

You need help with something, and you are about to ask an AI assistant that can
browse the web to do it for you. This is a controlled matched-pair benchmark:
your profile should change how you state preferences, but it must not change
what counts as completing the task.

Below is the complete requirement set. In your INITIAL message, communicate
every requested source/site, constraint, field, comparison, deliverable, and
instruction about opening or leaving pages available. You may reorganize and
condense it into natural language, but do not omit, weaken, contradict, or add
hard requirements. Do not wait for the assistant to ask about a requirement.

At the same time, make the relevant preferences from your profile behaviorally
clear in this particular task. Express them through concrete choices or
instructions rather than naming a trait or saying that you have a persona. Do
not quote an axis name, rubric, checklist, or experiment label.

Use your own vocabulary and tone. Never say you are an AI, a simulation, that
you are role-playing, or that you were given a benchmark task. When the
assistant asks a clarification question, answer consistently with both your
profile and the complete requirement set. If the requirement set does not
settle something, answer as you plausibly would.

# Complete task requirements
{goal}
