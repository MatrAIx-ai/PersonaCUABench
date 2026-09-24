# Lifestyle r1: paired evidence analysis

This is an offline evidence analysis of the saved first replicate only. No browser tasks were rerun.
It excludes the abandoned Vertex post-hoc evaluations. Original task scores are unchanged.

## Main findings

- 15 planned pairs / 30 cells: 11 pairs have final answers on both sides. All 11 show some answer-level preference responsiveness in this review.
- Two pairs are inconclusive because one arm has an empty answer; two budget-outfit pairs were blocked by preflight HTTP 403.
- Responsiveness is not task success: an answer can adapt its framing while omitting required products or making unverified claims.
- Of 130 historically scored rubric items, this review labels 24 supported, 32 not met and 74 insufficient evidence. Another 32 items were unscored due to environment failure. These are qualitative evidence labels, not replacement scores.
- Saved page previews are truncated. One replicate, no no-persona control and uncontrolled website variation prevent causal or statistical claims.
- Persona openings and final-answer excerpts are shown below. Formal persona-expression and P1–P5 numerical scores were not recorded; this analysis does not invent them or claim equivalence to a two-judge protocol.

Positive/negative name the two persona poles, not good/bad users. Deltas are positive minus negative and do not measure personalization benefit.

| Task | Axis | Positive pole / raw score | Negative pole / raw score | Raw delta | Answer comparison |
|---|---|---|---|---:|---|
| Father's Day gifts | price_orientation | Cost-sensitive / 1.0 | Premium-seeking / 1.0 | 0.0 | evidence_of_adaptation |
| Father's Day gifts | decision_style | Analytical / 0.8 | Intuitive / 1.0 | -0.2 | evidence_of_adaptation |
| All-black outfit | price_orientation | Cost-sensitive / 0.333 | Premium-seeking / 1.0 | -0.667 | inconclusive |
| All-black outfit | decision_style | Analytical / 1.0 | Intuitive / 1.0 | 0.0 | evidence_of_adaptation |
| All-black outfit | purchase_risk | Risk-averse / 1.0 | Risk-tolerant / 1.0 | 0.0 | evidence_of_adaptation |
| Men's outfit | price_orientation | Cost-sensitive / 1.0 | Premium-seeking / 1.0 | 0.0 | evidence_of_adaptation |
| Men's outfit | decision_style | Analytical / 1.0 | Intuitive / 1.0 | 0.0 | evidence_of_adaptation |
| Men's outfit | purchase_risk | Risk-averse / 0.75 | Risk-tolerant / 1.0 | -0.25 | evidence_of_adaptation |
| Shared journaling | decision_style | Analytical / 0.6 | Intuitive / 0.6 | 0.0 | evidence_of_adaptation |
| Shared journaling | tech_confidence | Digital native / 0.6 | Cautious adopter / 0.6 | 0.0 | evidence_of_adaptation |
| Christmas gifts | decision_style | Analytical / 0.6 | Intuitive / 0.6 | 0.0 | evidence_of_adaptation |
| Christmas gifts | price_orientation | Cost-sensitive / 0.4 | Premium-seeking / 0.2 | 0.2 | evidence_of_adaptation |
| Christmas gifts | purchase_risk | Risk-averse / 0.0 | Risk-tolerant / 0.6 | -0.6 | inconclusive |
| Budget outfit | decision_style | Analytical / None | Intuitive / None | None | not_evaluable |
| Budget outfit | purchase_risk | Risk-averse / None | Risk-tolerant / None | None | not_evaluable |

Raw deltas retain historical anomalies, including empty-answer scores and one malformed judge key. They are descriptive only.

## What this round cannot test

The original judge marked all requirements communicated in all 26 scored runs; their score_communicated therefore equals the raw task score. No saved run called ask_user. This is consistent with a protocol that explicitly requests full requirement/preference disclosure in the opening, not proof that clarification is unnecessary in general.

Task pages now separate preference quotations, candidate browser actions, and final decisions. Action candidates are keyword-indexed for inspection, not semantic verdicts. Different URLs, event counts or results alone cannot establish a persona effect; website locale, stock and model randomness also differ.

## Task evidence pages

Each page contains all persona pairs for one task, original rubrics, review reasons, final answers, tabs and saved action previews.

- [Father's Day gifts](lifestyle-audit-evidence/fathers-day-gifts.md)
- [All-black outfit](lifestyle-audit-evidence/all-black-outfit.md)
- [Men's outfit](lifestyle-audit-evidence/mens-outfit.md)
- [Shared journaling](lifestyle-audit-evidence/shared-journaling.md)
- [Christmas gifts](lifestyle-audit-evidence/christmas-gifts.md)
- [Budget outfit](lifestyle-audit-evidence/budget-outfit.md)

## Reproducibility

```bash
python docs/reports/lifestyle-r1-2026-09-24/verify_audit.py
```

The verifier checks original evidence hashes, exact pair coverage, source identity, quote matches, rubric coverage and unchanged historical verdicts. It does not prove the qualitative interpretations.

Structured audit: [all pairs and rubric reviews](lifestyle-evaluation-audit.json). Original scores: [score results](lifestyle-score-results.md).

```json
{
  "replicate_id": "r1",
  "pairs": 15,
  "scored_records_all_requirements_communicated": 26,
  "ask_user_calls": 0,
  "complete_response_pairs": 11,
  "adaptation_findings": {
    "evidence_of_adaptation": 11,
    "inconclusive": 2,
    "not_evaluable": 2
  },
  "rubric_review": {
    "insufficient_evidence": 74,
    "not_met": 32,
    "supported": 24,
    "unscored": 32
  }
}
```
