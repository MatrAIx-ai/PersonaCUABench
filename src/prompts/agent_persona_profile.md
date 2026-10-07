<!--
Appended to the agent's system prompt in the persona-profile ablation
(run.py --agent-sees-persona). {profile} is the persona's dimension narrative,
the same text the experience judge reads.

Deliberately neutral: it says who the person is, not how to adapt to them. An
instruction to tailor the work would be a second intervention riding on the
first, and the arm is meant to measure what the profile alone changes. The
request itself still reaches the agent only as the persona's own words.
-->
# The person you are working for

Below is a profile of the person you are working for. Their request reaches you in their own words in the conversation; this profile is background about who they are.

{profile}
