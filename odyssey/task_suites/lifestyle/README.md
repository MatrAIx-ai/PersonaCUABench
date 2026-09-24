# Lifestyle matched-pair suite

Owner: Yingtao Luo

This contribution is based on `main` and includes the shared task router,
matched-persona planner and judges needed by Lifestyle. These components were
adapted from `main-shop` at `d8a2885`; Shopping and other scenario assignments
are not included. The original main tasks, personas and model defaults remain
available. Always select `--suite lifestyle` for this assignment.

The [first-round report](../../../docs/reports/lifestyle-r1-2026-09-24/README.md)
includes all 30 saved r1 cells: 26 raw task scores and four unscored 403 outcomes.

This suite freezes the six assigned Odysseys Lifestyle tasks: three easy and
three medium. The task wording and R1–Rn rubrics in `000-core.json` are copied
unchanged from the upstream Odysseys dataset.

## Experimental design

The suite uses four controlled MatrAIx axes and eight generated named personas:

| Axis | MatrAIx dimension | Poles | Applicable tasks |
| --- | --- | --- | ---: |
| Price orientation | `economic_motivation` | Cost-sensitive / Premium-seeking | 4 |
| Decision style | `decision_style` | Analytical / Intuitive | 6 |
| Purchase risk | `risk_tolerance` | Risk-averse / Risk-tolerant | 4 |
| Technology confidence | `tech_savviness` | Digital native / Cautious adopter | 1 |

This produces 15 task-axis pairs and 30 persona cells per replicate. The
`none` arm remains a separate verbatim-task control.

The shared-journaling task already fixes privacy caution as a hard requirement.
For that reason, privacy-first versus convenience-first is intentionally not a
matched axis: the convenience pole would contradict the frozen task. Technology
confidence instead tests whether the same privacy goal is expressed through
precise technical controls or a low-complexity, plain-language setup.

## Validate

From the repository root:

```bash
python odyssey/make_matched_personas.py --suite lifestyle
python odyssey/make_matched_personas.py --suite lifestyle --check
python odyssey/run.py --list-suites
python odyssey/run.py --suite lifestyle --list-tasks
python odyssey/run_matched_pairs.py \
  --suite lifestyle --replicate-id r1 --headless
python odyssey/test_pipeline.py
```

The full dry run should report 4 axes, 8 named personas, 15 task-axis pairs,
and 30 run cells. Use `--execute` only after reviewing materialized openings
for both arms of each task-axis slice.

## Windows Docker-CDP local pilot

From the Git clone's repository root in PowerShell, with Docker Desktop running
and Vertex ADC configured (`gcloud auth application-default login`):

```powershell
python odyssey\start_docker_browser.py
$env:GOOGLE_CLOUD_PROJECT = "your-project-id"
$env:GOOGLE_CLOUD_LOCATION = "global"
python odyssey\run.py --suite lifestyle `
  --task 1,2,3 --persona none --cdp-url http://127.0.0.1:9333 --preflight-only
python odyssey\run_matched_pairs.py --suite lifestyle `
  --replicate-id r1 --task 1 --axis price_orientation -- `
  --cdp-url http://127.0.0.1:9333
```

The preflight command makes no model calls. The planner command is a two-cell **dry run**;
in CDP mode the planner omits `--profile` automatically. Add
`--materialize-openings` to review persona-user wording, then `--execute`
and explicitly specify `--model google/gemini-3.8-flash --provider vertex
--persona-model google/gemini-3.8-flash --persona-provider vertex
--judge-model google/gemini-3.8-flash --judge-provider vertex` plus a fixed
`--max-steps` and `--max-tabs 14` (the Christmas task needs more than eight
tabs). The runner checks representative live-site content before each Lifestyle
cell and marks blocked cells unscored. These checks establish browser access,
not that every requested product exists or is in stock. As of 2026-09-24,
JJ's House returns a 403 verification page in this Docker browser; the
budget-outfit task therefore cannot yield a comparable score until that source
is accessible. CDP results are local Playwright runs, not official OSWorld
screenshot/VM-reset scores.

After inspecting both-arm openings, run each replicate with the same frozen
settings. For example, one `r1` run is:

```powershell
python odyssey\run_matched_pairs.py --suite lifestyle --replicate-id r1 `
  --execute -- --cdp-url http://127.0.0.1:9333 `
  --model google/gemini-3.8-flash --provider vertex `
  --persona-model google/gemini-3.8-flash --persona-provider vertex `
  --judge-model google/gemini-3.8-flash --judge-provider vertex `
  --temperature 1 --max-steps 50 --max-tabs 14 --out artifacts/lifestyle-final-results
```

The planner stops on the first failed or unscored cell;
an unavailable required page is not a model failure. Use `--task` and `--axis`
to continue unaffected slices without changing the replicate ID. Once results
are complete, run:

```powershell
python odyssey\persona_fidelity_judge.py --results artifacts/lifestyle-final-results `
  --judge-model google/gemini-3.8-flash --judge-provider vertex
python odyssey\experience_judge.py --results artifacts/lifestyle-final-results `
  --judge-a google/gemini-3.8-flash --judge-a-provider vertex `
  --judge-b google/gemini-3.8-flash --judge-b-provider vertex
python odyssey\report.py artifacts/lifestyle-final-results --suite lifestyle
python odyssey\pair_separation.py artifacts/lifestyle-final-results --evidence
```

With only one model available, the two experience passes are independent calls
to the **same** model, not cross-model agreement. Do not call a 403-blocked cell
a CUA failure or include it in score averages.
