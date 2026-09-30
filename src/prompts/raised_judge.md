<!-- Did THIS PERSON ask for it. Filled with str.format(); placeholders:
     {conversation} {rubric}.

     Given nothing about the agent on purpose. This question is a property of
     what the person said, so the same conversation must give the same answer no
     matter which agent was listening. When the agent's answer and action log
     were in this prompt it did not: four models handed a byte-identical request
     produced raised counts of 1, 1, 2 and 4. -->

A person asked for help in their own words. Below is everything they said.

For each item, decide **raised**: did this person make that part of what they
wanted known -- said outright, or implied clearly enough that a reasonable
assistant would act on it?

- true when their words ask for it, directly or by clear implication.
- false when they never raised it. A specific website, tool, source or figure
  they never named is not raised merely because the item mentions it.
- Read them generously but literally. "What might it cost" raises cost. It does
  not raise "which page lists the fare table".
- Where the conversation has more than one turn, anything they confirmed when
  asked is raised: it entered the conversation in their words.
- Judge the person's request, never its quality. A vague person has still raised
  what they vaguely asked for.

## Everything this person said
{conversation}

## The items
{rubric}

Return ONLY a JSON object, one entry per item id:

{{"R1": {{"raised": true, "reason": "<quote their words, or say they never raised it>"}}, ...}}
