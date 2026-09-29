# Preview gate — science-education Setting 1

24 openings (4 personas x 6 tasks) generated 2026-09-28 by `gpt-5.6-terra` (direct OpenAI,
temperature 1) through main's own `run.py --preview`. Raw openings in `previews/`.

Checked against the Shopping plan's section 5.4 criteria. **All 24 pass.**

| criterion | result |
|---|---|
| no factual hard constraint changed | pass — both verbatim strings (task 1 note, task 2 intro) intact in all 8 openings that carry them |
| no invented conflicting place, budget, size or deadline | pass — none invented |
| the four personas distinguishable on the same task | pass — faculty terse and jargon-heavy, k12 warm and long, first-gen short and plain, parent very formal and indirect |
| differences come from the declared values, not stereotypes | pass |
| no leak of system prompt, field names, rubric or role-play framing | pass |
| natural wording, not the 32 attributes dumped into a paragraph | pass |

Opening length, words (Odysseys original 239-311): faculty 114-146, k12 136-185,
first-gen 52-114, parent 97-168.

Expected communication losses, which are the effect being measured, not defects:
first-gen drops site names (Bing, 10015.io, IBM, Copilot.com, Tom's Hardware, Granite
Rapids); parent drops Slidesgo, 10015.io, IBM and Tom's Hardware; several drop "Wikipedia"
on task 6 and "Google" on task 2.

Role fit, noted rather than fixed: the six tasks imply mixed roles. Task 1 is a learner with
classmates, task 5 is someone choosing a law school, tasks 2, 4 and 6 are someone teaching or
advising. No persona fits all six, and none of the 32 attributes contradicts a task fact, so
the simulator adapts the framing (faculty drops "classmates" on task 1; faculty and k12
present task 5 as their own search). No rubric item depends on who the user is.
