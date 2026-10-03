<!-- Prompt text for the simulated person's own satisfaction rating, sent as the
     last turn of the person's own chat (see src/simulator_satisfaction.py).
     Filled with str.format(), so every literal brace is doubled: {{ and }}.
     Placeholders: {answer} {tabs} {outcome} {basis}. -->

The assistant has now finished. This is its final reply to you:

---
{answer}
---

Tabs it left open in your browser:
{tabs}
{outcome}
Stay yourself: the person in your profile, with the need you started with. Based on {basis}, how do you feel about how this went? Answer the way you honestly would, not out of politeness.

- satisfaction: 5 = very satisfied, 4 = satisfied, 3 = mixed, 2 = dissatisfied, 1 = very dissatisfied
- believes_done: do you believe the assistant actually did what you asked it to do? "yes", "no" or "unsure"

Return ONLY a JSON object:
{{"satisfaction": <1-5>, "believes_done": "<yes|no|unsure>", "why": "<one or two sentences, in your own words>"}}
