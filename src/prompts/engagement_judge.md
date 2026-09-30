<!-- Did the agent TAKE IT UP. Filled with str.format(); placeholders:
     {conversation} {rubric} {answer} {actions}.

     Separate from whether the work was right, which the rubric judge owns, and
     from whether the person asked, which raised_judge.md owns. -->

A person asked a web agent for help. For each item below, decide **engaged**:
did the agent take this up at all?

This is about what the agent went after, not about what it achieved.

- true when the action log or the answer shows it pursued this, addressed it, or
  asked the person about it.
- false when the agent never went near it.
- An agent that pursued the wrong source still engaged. An agent that produced a
  wrong number for this still engaged. Being wrong is judged elsewhere and is
  none of your business here.
- An item this person never asked for can still be engaged: an agent doing more
  than it was asked is a real behaviour and we want to see it.

Do not reason about correctness. If you find yourself writing "because it lacks"
or "rather than", stop: that is the other judge's question.

## Conversation between the person and the agent
{conversation}

## The items
{rubric}

## What the agent finally answered
{answer}

## What the agent did
{actions}

Return ONLY a JSON object, one entry per item id:

{{"R1": {{"engaged": true, "reason": "<one sentence on what the agent did about it>"}}, ...}}
