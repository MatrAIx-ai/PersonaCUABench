# API / tool-loop preflight — science-education Setting 1

Run 2026-09-28T23:03:49Z on branch `jiashu/science-education-main`. Credentials: direct OpenAI API key and an OpenRouter key; no Azure.

## Fixed roles on gpt-5.6-terra

| role | result | sample |
|---|---|---|
| persona text | PASS | Could you help me find a grammar quiz? |
| judge JSON | PASS | {"R1":{"met":true,"communicated":true}} |

## Execution backbones — two-turn tool loop through main's own code

| backbone | provider / id | unmodified main | with reasoning_effort fix |
|---|---|---|---|
| GPT 5.6 Terra | `openai` `gpt-5.6-terra` | **FAIL** | **PASS** |
| GPT 6 Astra | `openai` `gpt-6-astra` | **FAIL** | **FAIL** |
| Claude Opus 5.5 | `openrouter` `anthropic/claude-opus-5.5` | **PASS** | **PASS** |
| Muse Spark 1.1 | `openrouter` `meta/muse-spark-1.1` | **FAIL** | **FAIL** |
| Kimi-K3 | `openrouter` `moonshotai/kimi-k3` | **PASS** | **PASS** |
| Grok 4.7 | `openrouter` `x-ai/grok-4.7` | **PASS** | **PASS** |
| MiniMax M3 | `openrouter` `minimax/minimax-m3` | **PASS** | **PASS** |
| GLM 5.3 | `openrouter` `z-ai/glm-5.3` | **PASS** | **PASS** |
| Qwen 3.8 27B | `openrouter` `qwen/qwen3.8-27b` | **PASS** | **PASS** |
| Gemini V4 Pro | — | **UNAVAILABLE** | **UNAVAILABLE** |

## Detail

- **GPT 5.6 Terra** — unmodified: BadRequestError: Error code: 400 - {'error': {'message': "Function tools with reasoning_effort are not supported for gpt-5.6-terra in /v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.", 'ty — with fix: turn 1 open_tab, turn 2 tool call finish; served as gpt-5.6-terra
- **GPT 6 Astra** — unmodified: BadRequestError: Error code: 400 - {'error': {'message': "Function tools with reasoning_effort are not supported for gpt-6-astra in /v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.", 'type — with fix: BadRequestError: Error code: 400 - {'error': {'message': "Function tools with reasoning_effort are not supported for gpt-6-astra in /v1/chat/completions. To use function tools, use /v1/responses or set reasoning_effort to 'none'.", 'type
- **Claude Opus 5.5** — unmodified: turn 1 open_tab, turn 2 tool call finish; served as anthropic/claude-opus-5.5 — with fix: turn 1 open_tab, turn 2 tool call finish; served as anthropic/claude-opus-5.5
- **Muse Spark 1.1** — unmodified: PermissionDeniedError: Error code: 403 - {'error': {'message': 'This model requires you to complete the following before use: 18+ age confirmation. Confirm at https://openrouter.ai/settings/preferences.', 'code': 403, 'metadata': {'missing_att — with fix: PermissionDeniedError: Error code: 403 - {'error': {'message': 'This model requires you to complete the following before use: 18+ age confirmation. Confirm at https://openrouter.ai/settings/preferences.', 'code': 403, 'metadata': {'missing_att
- **Kimi-K3** — unmodified: turn 1 open_tab, turn 2 tool call finish; served as moonshotai/kimi-k3 — with fix: turn 1 open_tab, turn 2 tool call finish; served as moonshotai/kimi-k3
- **Grok 4.7** — unmodified: turn 1 open_tab, turn 2 tool call finish; served as x-ai/grok-4.7 — with fix: turn 1 open_tab, turn 2 tool call finish; served as x-ai/grok-4.7
- **MiniMax M3** — unmodified: turn 1 open_tab, turn 2 final text; served as minimax/minimax-m3 — with fix: turn 1 open_tab, turn 2 final text; served as minimax/minimax-m3
- **GLM 5.3** — unmodified: turn 1 open_tab, turn 2 tool call finish; served as z-ai/glm-5.3 — with fix: turn 1 open_tab, turn 2 tool call finish; served as z-ai/glm-5.3
- **Qwen 3.8 27B** — unmodified: turn 1 open_tab, turn 2 tool call finish; served as qwen/qwen3.8-27b — with fix: turn 1 open_tab, turn 2 tool call read_page; served as qwen/qwen3.8-27b
- **Gemini V4 Pro** — no id on OpenAI or OpenRouter; newest Gemini listed is google/gemini-3.1-pro-preview. Recorded as unavailable, not substituted.

## Same two OpenAI models routed through OpenRouter, unmodified main

| backbone | provider / id | unmodified main |
|---|---|---|
| GPT 5.6 Terra | `openrouter` `openai/gpt-5.6-terra` | **PASS** — turn 1 open_tab, turn 2 final text |
| GPT 6 Astra | `openrouter` `openai/gpt-6-astra` | **PASS** — turn 1 open_tab, turn 2 finish |

Direct OpenAI rejects function tools on `/v1/chat/completions` for both models when any
`reasoning_effort` is in force. Terra accepts `"none"`, Astra does not (`low`/`medium`/…
only), so on the direct route Astra would need the Responses API, which is a runner change.
OpenRouter serves the same model ids and main's unmodified tool path works through it.

## Decision

- **Execution goes through OpenRouter for every backbone**, including Terra and Astra, so
  main's tool path runs unmodified.
- **Persona simulator, rubric judge and experience judges use `gpt-5.6-terra` on the direct
  OpenAI API.** None of them sends tools, all passed above on unmodified main, and it keeps
  the OpenRouter key (hard limit $100) for execution only.
- The maintainers' Shopping grid used one Azure `gpt-5.6-terra` deployment for every role.
  Same model id here, two routes; both are recorded per cell.
- **Formal executors: 8** — Terra, Astra, Claude Opus 5.5, Kimi-K3, Grok 4.7, MiniMax M3,
  GLM 5.3, Qwen 3.8 27B.
- **Muse Spark 1.1: blocked** — OpenRouter returns 403 until the account completes an 18+
  age confirmation in its settings. Account action, not a model failure.
- **Gemini V4 Pro: unavailable** — no such id on either provider. Not substituted.
