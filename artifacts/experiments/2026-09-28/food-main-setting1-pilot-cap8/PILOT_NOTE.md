# Superseded Food pilot — main tab cap

- Date: `2026-09-28`
- Status: stopped after 3/30 planned cells; excluded from formal r1–r3
- Configuration: `main@4a1c0f2`, `MAX_TABS=8`, otherwise the same models,
  prompts, judges, temperature, and step budget planned for Food
- Completed cells: first three `none` control tasks
- Raw scores: `1.00`, `0.75`, `0.75`

## Why this pilot was stopped

All three completed trajectories contain real `[tab limit 8 reached; close a
tab first]` tool results. The executor can issue multiple `open_tab` calls in a
single model turn, so it may hit the limit before receiving tool feedback and
before it has a chance to close or reuse a tab. This is a material protocol
capacity effect, not an isolated executor mistake.

The source meeting note specifies live Chrome “without the infra limitation.”
Continuing 90 cells under a known binding cap would not answer that setting.
The three scored records remain preserved as pilot evidence but are not merged
with the no-artificial-cap formal experiment.

Formal Food r1–r3 use the same core runner and evaluation logic with only the
tab guard disabled via `ODYSSEY_MAX_TABS=0`.
