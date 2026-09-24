# Health pilot: saved evidence and audit

This report covers the September 22, 2026 feasibility pilot: six unchanged
Odyssey Health tasks, one persona pair per task, and twelve final responses.
Four browser stalls and one API timeout remain separate unscored attempts.

Start with the [Chinese review and per-run evidence index](health-evaluation-audit-zh.md).
The [structured audit](health-evaluation-audit.json) includes every original
rubric, original automatic verdict, review reason, and source JSON pointer.
Each linked evidence page includes the complete action directory, final tabs,
selected verbatim observations, original judge reasons, and original answer.

The automatic rubric judge awarded 31/66 points across these responses.
The assistant's later evidence review found **16 supported, 38 not met, and
12 insufficient-evidence decisions**. Insufficient evidence remains unresolved;
these counts are not a replacement score or official Odyssey evaluation.
Two originally failed Pilates R2 decisions are supported under the actual
Fresno-or-Clovis wording. Six originally passed decisions are not met; another
eleven originally passed decisions cannot be fully confirmed.

P1–P5 scores remain unchanged. Their explanations sometimes assert actions that
did not occur, such as opening both requested videos. Two same-model judges
agreeing does not validate those premises. All twelve persona-expression scores
are 2/2, but check authored opening preferences; no run called `ask_user`.

## Sources and redactions

- [Runs, task snapshots, browser observations and rubric judgments](health-pilot-results.json)
- [Original P1–P5 scores and reasons](health-experience-scores.json)
- [Original persona-expression judgments](health-persona-expression.json)
- [Original and review-copy hashes; redaction scope](redaction-manifest.json)

These are redacted review copies. Local user/workspace paths, IP addresses and
Google challenge query parameters have been removed. Local originals remain
unchanged. Evidence offsets and result hashes refer to the copies committed
here. Original model answers are audit subjects, not verified provider advice.
Markdown display copies normalize trailing whitespace; exact excerpt strings
are preserved in the JSON files.

The saved browser evidence consists of text observations and final tab lists,
not screenshots or video. Some observations are truncated. No current provider
pages were used to fill gaps in historical runs. This review was authored by
the assistant, not by a human panel or a new independent model experiment.

## Offline validation

From the repository root:

```bash
python docs/reports/health-pilot-2026-09-22/verify_audit.py
```

This checks all source hashes, 66 rubric mappings, 134 action events, excerpt
offsets, task snapshots, and the 17-attempt accounting. It does not validate the
subjective review judgments or call any model or live task website.

The [Health runbook](../../../odyssey/task_suites/health/README.md) describes
personas and reproducible new-run commands. The runtime is local
Chrome/Playwright with AWS Bedrock, not the official OSWorld evaluation setup.
