# Food main-style API / model preflight

- Date: `2026-09-28` (America/Los_Angeles)
- Branch: `codex/food-main-2026-09-28`
- Base protocol: `main@4a1c0f2`
- Provider route: configured Azure-compatible OpenAI Chat Completions endpoint
- Credential values and endpoint secrets are intentionally omitted.

## Result

| Deployment | Text call | Two-turn function-tool loop | Judge JSON | Decision |
| --- | --- | --- | --- | --- |
| `gpt-5.6-terra` | PASS (`OK`) | PASS (`check` → `finish`) | PASS (`{"ok": true}`) | Eligible for all formal roles |

The provider returned model revision `gpt-5.6-terra-2026-07-09`.

Formal Food roles are therefore frozen as follows unless a later dated
preflight records a provider-state change:

- persona simulator: Azure `gpt-5.6-terra`, temperature `1`;
- executor: Azure `gpt-5.6-terra`, temperature `1`;
- original task judge: Azure `gpt-5.6-terra`, unchanged no-temperature judge call;
- persona experience Judge A/B: two independent Azure `gpt-5.6-terra` calls,
  retained separately.

This preflight used only minimal synthetic text and function calls. It did not
include Food task text, persona utterances, or browser trajectories.
