<!-- The SUBJECTIVE half of judging: did the agent understand what THIS person
     wanted, and act on it. Filled with str.format(), so every literal brace is
     doubled. Placeholders: {rubric} {conversation} {answer} {actions}.

     Deliberately has no access to the hidden expert brief: the agent never saw
     it either, and judging intent against a brief the person never spoke is the
     mistake this whole split exists to prevent. -->

A person asked a web agent for help in their own words. You are judging, for
each item below, whether the agent **engaged with that part of what this person
wanted**.

This is a judgement about intent, not about correctness. Whether the work was
actually done right is decided separately and is not your question.

For each item decide **communicated**: did this person's own words make this
part of what they wanted known -- said outright, or implied clearly enough that
a reasonable assistant would act on it -- **and did the agent take it up**?

- true when the person asked for it, in their own words or by clear implication,
  and the agent's behaviour shows it took that up: it pursued it, or answered
  it, or asked the person about it. Whether it then got the answer right does
  not matter here.
- false when this person never raised it and the agent never asked. An agent
  that did the thing anyway is not being penalised -- doing more than was asked
  is recorded by this being false while the work still counts as done, and that
  combination is exactly what we want to see.
- Read the person generously but literally. "What might it cost" raises cost.
  It does not raise "which page lists the fare table" unless the agent's own
  behaviour shows it reasonably read the request that way.
- A specific website, tool or figure the person never named is not raised
  merely because the item mentions it.

Judge only from what the person said and what the agent did in response. Do not
reason about whether the result was correct, complete, or from the right source
-- if you find yourself writing "because it lacks" or "rather than", stop: that
is the other judge's question.

## Conversation between the person and the agent
{conversation}

## The items
{rubric}

## What the agent finally answered
{answer}

## What the agent did
{actions}

Return ONLY a JSON object, one entry per item id:

{{"R1": {{"communicated": true, "reason": "<one sentence quoting the person's own words, or saying they never raised it>"}}, ...}}
