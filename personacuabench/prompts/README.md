# Prompt assets

These files are the role prompts introduced on the latest `main` branch and
are packaged with PersonaCUABench. Their leading HTML comments document the
`str.format` placeholders; `personacuabench.prompting.load_prompt()` removes
that comment before a prompt is sent to a model.

The files do not all belong to the same experimental protocol:

- `experience_judge.md` is used by the optional, explicit P1–P5 experience
  judge.
- `persona_user.md` is the natural-user protocol from the original Odyssey
  runner. It permits a persona to omit checklist details. The current matched
  pair protocol deliberately keeps every ordinary task requirement, so this
  asset is retained for provenance and is not silently substituted.
- `rubric_judge.md` is the original combined `met`/`communicated` template.
  The current pipeline instead uses the pinned Odysseys standard judge for
  task success and a separate communication judge.
- `agent.md` targets the original Playwright tools (`read_page`, `open_tab`,
  and `finish`). The OSWorld adapter uses OSWorld's native agent prompt and
  therefore does not inject this incompatible prompt.

Keeping the inactive protocol assets here makes the `main`-branch provenance
visible without changing the controlled OSWorld experiment.
