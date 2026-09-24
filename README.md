# PersonaCUABench

Run browser tasks with simulated user personas and evaluate task completion,
persona expression, and user experience. The [runner guide](odyssey/README.md)
describes the original main-branch workflow.

## Lifestyle — Yingtao Luo

The [Lifestyle runbook](odyssey/task_suites/lifestyle/README.md) contains six
unchanged Odysseys tasks, four controlled persona pairs (eight personas), and
reproducible validation and execution commands. The pairs vary price orientation,
decision style, purchase risk, and technology confidence only where the task
supports the comparison. There are 15 task–axis pairs and 30 cells per replicate.

This contribution is based on `main`. The original `odyssey/tasks.json`,
legacy personas, model defaults, and explicit Azure provider remain available.
Select `--suite lifestyle` for this assignment.

```bash
python odyssey/run.py --suite lifestyle --list-tasks
python odyssey/make_matched_personas.py --suite lifestyle --check
python odyssey/run_matched_pairs.py --suite lifestyle --replicate-id r1 --headless
python odyssey/test_pipeline.py
python odyssey/test_pair_separation.py
```

The last three commands are offline; the matrix command only prints a plan.
Real runs require the dependencies in `odyssey/requirements.txt`, Chrome, and
configured model access. Lifestyle's recorded runs used Vertex Gemini with
Application Default Credentials and a fresh Chrome context through Docker CDP.
See the runbook for Windows PowerShell commands.

## Saved experiment evidence

The [Lifestyle first-round report](docs/reports/lifestyle-r1-2026-09-24/README.md)
contains redacted historical results, per-attempt evidence, failure records,
and an offline integrity verifier for the first replicate only: 26 scored cells
and four unscored 403 outcomes. The [paired analysis](docs/reports/lifestyle-r1-2026-09-24/lifestyle-evaluation-audit.md)
compares all 15 task–axis pairs using quoted persona preferences and saved
answers, with per-rubric evidence reviews. This is offline evidence analysis,
not new model scoring; missing numerical persona/experience evaluations remain
explicitly missing. No second-round results are included.

An opt-in [preference-disclosure pilot](odyssey/task_suites/lifestyle/DISCLOSURE_PILOT.md)
adds controlled full/gap openings, fixed clarification replies and a neutral
baseline. Offline tests pass; new live experiments have not been executed.

These are local Playwright runs, not official OSWorld evaluation results.
Raw local artifacts, browser profiles, and credentials remain excluded from Git.
