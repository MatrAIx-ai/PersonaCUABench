# PersonaCUABench

Run browser tasks with simulated user personas and review task completion and
user-experience evaluations. The [original runner guide](odyssey/README.md)
describes the main-branch tasks.

## Health tasks and personas

The [Health runbook](odyssey/task_suites/health/README.md) covers six unchanged
Odyssey tasks and three controlled persona pairs:

- Detail oriented / Essentials only
- Analytical / Intuitive chooser
- Evidence checker / Comfortable delegating

Task routing keeps the existing `odyssey/tasks.json` as the default. Select
`--suite health` for the Health assignments. The shared matched-pair planner
supports fixed task text plus an authored preference and records task/profile
snapshots for later evidence review.

```bash
python odyssey/run.py --list-suites
python odyssey/run.py --suite health --list-tasks
python odyssey/make_matched_personas.py --suite health --check
```

For AWS Bedrock, supply `AWS_REGION` or `AWS_DEFAULT_REGION` and either
`AWS_BEARER_TOKEN_BEDROCK` or `AWS_BEARER_TOKEN_BEDROCK_FILE`. Select `bedrock`
explicitly for the agent, persona and judge roles. The Health runbook includes
complete commands, model settings and the local Chrome requirement. Existing
OpenRouter, OpenAI and explicit Azure provider options remain available.

## Evaluation results

The [Health evaluation report](docs/reports/health-pilot-2026-09-22/README.md)
includes source-indexed evidence, all twelve final responses, separately retained
incomplete runs, original scores, and a review of all 66 rubric decisions.
Review categories are distinct from the original automatic scores.

```bash
python odyssey/test_pipeline.py
python odyssey/test_browser.py
python docs/reports/health-pilot-2026-09-22/verify_audit.py
```

The browser regression uses local HTML; it does not call model APIs or task
websites. The recorded task runs used local Chrome/Playwright, not OSWorld.
