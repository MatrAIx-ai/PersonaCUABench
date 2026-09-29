# science-education Setting 1 — post-hoc summary

Replicates: r1, r2, r3. Executors: openai-gpt-5.6-terra. Cells: 90.


## Executor `openai-gpt-5.6-terra`

### Raw task completion (mean over replicates)

| arm | T1 LGM study | T2 mini lesson | T3 AI explainer | T4 grad outreach | T5 law schools | T6 MH evidence | 6-task macro |
|---|---:|---:|---:|---:|---:|---:|---:|
| none (control) | 0.500 | 0.917 | 0.833 | 0.429 | 0.667 | 0.905 | **0.7083** |
| Faculty advisor | 0.500 | 0.750 | 0.889 | 0.571 | 0.833 | 0.476 | **0.6699** |
| K-12 teacher | 0.250 | 0.750 | 0.722 | 0.334 | 0.750 | 0.714 | **0.5867** |
| First-gen applicant | 0.000 | 0.583 | 0.445 | 0.238 | 0.417 | 0.333 | **0.3361** |
| Parent helper | 0.000 | 0.667 | 0.667 | 0.571 | 0.583 | 0.714 | **0.5337** |

- cell-macro completion `0.5669`; rubric micro `273/480 = 0.5687`
- communicated coverage: cell-macro `0.8516`; micro `414/480 = 0.8625`
- communicated-only: cell-macro `0.6089`

### Persona effect: paired delta vs `none` (same task, same replicate)

| persona | completion delta | coverage | communicated-only | mean asks |
|---|---:|---:|---:|---:|
| Faculty advisor | -0.038 | 0.916 | 0.701 | 0.00 |
| K-12 teacher | -0.122 | 0.830 | 0.649 | 0.00 |
| First-gen applicant | -0.372 | 0.701 | 0.390 | 0.00 |
| Parent helper | -0.175 | 0.811 | 0.584 | 0.00 |

`none` mean asks: 0.00 — the attribution baseline for persona-arm questions.

### Persona experience judge (P1–P5, 1–5), A/B are two independent Terra calls

| dimension | A mean | B mean | exact | within-one |
|---|---:|---:|---:|---:|
| P1_asked_for | 3.87 (n=90) | 3.87 (n=90) | 73/90 | 89/90 |
| P2_readable_for_them | 4.59 (n=90) | 4.56 (n=90) | 77/90 | 90/90 |
| P3_actionable | 3.97 (n=90) | 3.98 (n=90) | 70/90 | 89/90 |
| P4_gap_handling | 3.78 (n=86) | 3.77 (n=81) | 44/80 | 77/80 |
| P5_overall | 3.82 (n=90) | 3.82 (n=90) | 69/90 | 89/90 |
| **all** | | | **333/440** | **434/440** |

### P5 overall by persona (A/B mean)

| arm | P5 all cells | P5 on full-task-perfect cells (score == 1.0) |
|---|---:|---:|
| none (control) | 3.67 (n=18) | 3.88 (n=4) |
| Faculty advisor | 3.67 (n=18) | 3.88 (n=4) |
| K-12 teacher | 4.00 (n=18) | 4.00 (n=1) |
| First-gen applicant | 3.83 (n=18) | — (n=0) |
| Parent helper | 3.94 (n=18) | — (n=0) |

## Per-cell run facts and environment evidence (input to the manual audit)

| rep | task | arm | model | score | comm | steps | asks | stop | google ok/sorry | 403 | denied | captcha/CF | dns | timeout | empty reads |
|---|---|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| r1 | 1 | none | openai-gpt-5.6-terra | 0.500 | 4/4 | 31 | 0 | finish | 4/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 1 | faculty-advisor | openai-gpt-5.6-terra | 0.500 | 4/4 | 39 | 0 | finish | 13/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 1 | k12-teacher | openai-gpt-5.6-terra | 0.250 | 0/4 | 38 | 0 | finish | 10/0 | 0 | 0 | 0 | 1 | 1 | 0 |
| r1 | 1 | first-gen-applicant | openai-gpt-5.6-terra | 0.000 | 4/4 | 8 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 1 | parent-helper | openai-gpt-5.6-terra | 0.000 | 3/4 | 31 | 0 | finish | 7/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 2 | none | openai-gpt-5.6-terra | 1.000 | 4/4 | 68 | 0 | finish | 14/0 | 0 | 0 | 2 | 0 | 2 | 0 |
| r1 | 2 | faculty-advisor | openai-gpt-5.6-terra | 0.750 | 4/4 | 31 | 0 | finish | 10/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 2 | k12-teacher | openai-gpt-5.6-terra | 0.750 | 1/4 | 39 | 0 | no_tool_call | 10/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 2 | first-gen-applicant | openai-gpt-5.6-terra | 0.750 | 4/4 | 43 | 0 | finish | 8/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 2 | parent-helper | openai-gpt-5.6-terra | 0.750 | 0/4 | 34 | 0 | finish | 8/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 3 | none | openai-gpt-5.6-terra | 0.833 | 6/6 | 7 | 0 | no_tool_call | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 3 | faculty-advisor | openai-gpt-5.6-terra | 1.000 | 5/6 | 12 | 0 | finish | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 3 | k12-teacher | openai-gpt-5.6-terra | 0.833 | 6/6 | 6 | 0 | finish | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 3 | first-gen-applicant | openai-gpt-5.6-terra | 0.167 | 2/6 | 26 | 0 | no_tool_call | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 3 | parent-helper | openai-gpt-5.6-terra | 0.667 | 5/6 | 7 | 0 | finish | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 4 | none | openai-gpt-5.6-terra | 0.571 | 7/7 | 53 | 0 | no_tool_call | 15/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 4 | faculty-advisor | openai-gpt-5.6-terra | 0.429 | 7/7 | 84 | 0 | max_steps_summarised | 19/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 4 | k12-teacher | openai-gpt-5.6-terra | 0.286 | 7/7 | 60 | 0 | finish | 16/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 4 | first-gen-applicant | openai-gpt-5.6-terra | 0.429 | 7/7 | 81 | 0 | no_tool_call | 22/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 4 | parent-helper | openai-gpt-5.6-terra | 0.714 | 7/7 | 76 | 0 | finish | 18/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 5 | none | openai-gpt-5.6-terra | 0.750 | 4/4 | 39 | 0 | no_tool_call | 7/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 5 | faculty-advisor | openai-gpt-5.6-terra | 1.000 | 4/4 | 55 | 0 | finish | 16/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r1 | 5 | k12-teacher | openai-gpt-5.6-terra | 0.500 | 4/4 | 36 | 0 | no_tool_call | 9/0 | 0 | 0 | 0 | 0 | 4 | 0 |
| r1 | 5 | first-gen-applicant | openai-gpt-5.6-terra | 0.500 | 3/4 | 50 | 0 | finish | 10/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 5 | parent-helper | openai-gpt-5.6-terra | 0.500 | 4/4 | 38 | 0 | finish | 9/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r1 | 6 | none | openai-gpt-5.6-terra | 1.000 | 7/7 | 27 | 0 | finish | 5/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r1 | 6 | faculty-advisor | openai-gpt-5.6-terra | 0.714 | 6/7 | 18 | 0 | finish | 5/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 6 | k12-teacher | openai-gpt-5.6-terra | 0.714 | 7/7 | 44 | 0 | no_tool_call | 5/0 | 0 | 0 | 2 | 0 | 0 | 0 |
| r1 | 6 | first-gen-applicant | openai-gpt-5.6-terra | 0.714 | 6/7 | 18 | 0 | finish | 4/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r1 | 6 | parent-helper | openai-gpt-5.6-terra | 0.714 | 6/7 | 22 | 0 | no_tool_call | 7/0 | 0 | 0 | 1 | 0 | 0 | 0 |
| r2 | 1 | none | openai-gpt-5.6-terra | 0.500 | 4/4 | 28 | 0 | no_tool_call | 5/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 1 | faculty-advisor | openai-gpt-5.6-terra | 0.500 | 4/4 | 26 | 0 | no_tool_call | 6/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r2 | 1 | k12-teacher | openai-gpt-5.6-terra | 0.500 | 4/4 | 22 | 0 | no_tool_call | 4/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r2 | 1 | first-gen-applicant | openai-gpt-5.6-terra | 0.000 | 4/4 | 7 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 1 | parent-helper | openai-gpt-5.6-terra | 0.000 | 4/4 | 26 | 0 | no_tool_call | 4/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 2 | none | openai-gpt-5.6-terra | 0.750 | 4/4 | 25 | 0 | finish | 8/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 2 | faculty-advisor | openai-gpt-5.6-terra | 1.000 | 2/4 | 35 | 0 | finish | 11/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r2 | 2 | k12-teacher | openai-gpt-5.6-terra | 0.750 | 1/4 | 20 | 0 | finish | 4/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 2 | first-gen-applicant | openai-gpt-5.6-terra | 0.500 | 0/4 | 28 | 0 | finish | 9/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 2 | parent-helper | openai-gpt-5.6-terra | 0.500 | 3/4 | 20 | 0 | finish | 7/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 3 | none | openai-gpt-5.6-terra | 0.833 | 6/6 | 7 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 3 | faculty-advisor | openai-gpt-5.6-terra | 0.833 | 6/6 | 7 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 3 | k12-teacher | openai-gpt-5.6-terra | 0.667 | 5/6 | 6 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 3 | first-gen-applicant | openai-gpt-5.6-terra | 0.667 | 5/6 | 4 | 0 | no_tool_call | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 3 | parent-helper | openai-gpt-5.6-terra | 0.500 | 6/6 | 7 | 0 | finish | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 4 | none | openai-gpt-5.6-terra | 0.429 | 7/7 | 52 | 0 | finish | 19/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r2 | 4 | faculty-advisor | openai-gpt-5.6-terra | 0.571 | 7/7 | 56 | 0 | finish | 19/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r2 | 4 | k12-teacher | openai-gpt-5.6-terra | 0.429 | 7/7 | 83 | 0 | finish | 23/0 | 0 | 0 | 0 | 1 | 1 | 0 |
| r2 | 4 | first-gen-applicant | openai-gpt-5.6-terra | 0.000 | 1/7 | 32 | 0 | finish | 10/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 4 | parent-helper | openai-gpt-5.6-terra | 0.571 | 7/7 | 80 | 0 | finish | 18/0 | 0 | 0 | 0 | 1 | 3 | 0 |
| r2 | 5 | none | openai-gpt-5.6-terra | 1.000 | 4/4 | 62 | 0 | finish | 15/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 5 | faculty-advisor | openai-gpt-5.6-terra | 1.000 | 4/4 | 33 | 0 | no_tool_call | 10/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r2 | 5 | k12-teacher | openai-gpt-5.6-terra | 1.000 | 4/4 | 32 | 0 | finish | 10/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r2 | 5 | first-gen-applicant | openai-gpt-5.6-terra | 0.500 | 4/4 | 31 | 0 | no_tool_call | 9/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 5 | parent-helper | openai-gpt-5.6-terra | 0.750 | 4/4 | 48 | 0 | no_tool_call | 8/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r2 | 6 | none | openai-gpt-5.6-terra | 0.857 | 7/7 | 32 | 0 | finish | 7/0 | 0 | 0 | 1 | 0 | 1 | 0 |
| r2 | 6 | faculty-advisor | openai-gpt-5.6-terra | 0.429 | 7/7 | 23 | 0 | finish | 3/0 | 0 | 0 | 1 | 0 | 0 | 0 |
| r2 | 6 | k12-teacher | openai-gpt-5.6-terra | 0.571 | 6/7 | 38 | 0 | finish | 6/0 | 0 | 0 | 1 | 0 | 0 | 0 |
| r2 | 6 | first-gen-applicant | openai-gpt-5.6-terra | 0.143 | 4/7 | 29 | 0 | finish | 5/0 | 0 | 0 | 1 | 0 | 0 | 0 |
| r2 | 6 | parent-helper | openai-gpt-5.6-terra | 0.857 | 5/7 | 22 | 0 | finish | 5/0 | 0 | 0 | 3 | 0 | 0 | 0 |
| r3 | 1 | none | openai-gpt-5.6-terra | 0.500 | 4/4 | 30 | 0 | no_tool_call | 8/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r3 | 1 | faculty-advisor | openai-gpt-5.6-terra | 0.500 | 4/4 | 33 | 0 | no_tool_call | 8/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 1 | k12-teacher | openai-gpt-5.6-terra | 0.000 | 3/4 | 7 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 1 | first-gen-applicant | openai-gpt-5.6-terra | 0.000 | 2/4 | 10 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 1 | parent-helper | openai-gpt-5.6-terra | 0.000 | 1/4 | 18 | 0 | finish | 3/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 2 | none | openai-gpt-5.6-terra | 1.000 | 4/4 | 37 | 0 | finish | 11/0 | 0 | 0 | 2 | 0 | 2 | 0 |
| r3 | 2 | faculty-advisor | openai-gpt-5.6-terra | 0.500 | 3/4 | 20 | 0 | finish | 8/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r3 | 2 | k12-teacher | openai-gpt-5.6-terra | 0.750 | 4/4 | 33 | 0 | finish | 9/0 | 0 | 0 | 0 | 0 | 4 | 0 |
| r3 | 2 | first-gen-applicant | openai-gpt-5.6-terra | 0.500 | 3/4 | 16 | 0 | finish | 6/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 2 | parent-helper | openai-gpt-5.6-terra | 0.750 | 3/4 | 33 | 0 | finish | 9/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r3 | 3 | none | openai-gpt-5.6-terra | 0.833 | 6/6 | 8 | 0 | finish | 4/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 3 | faculty-advisor | openai-gpt-5.6-terra | 0.833 | 5/6 | 8 | 0 | finish | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 3 | k12-teacher | openai-gpt-5.6-terra | 0.667 | 6/6 | 8 | 0 | no_tool_call | 1/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 3 | first-gen-applicant | openai-gpt-5.6-terra | 0.500 | 4/6 | 12 | 0 | finish | 1/0 | 3 | 2 | 0 | 0 | 2 | 0 |
| r3 | 3 | parent-helper | openai-gpt-5.6-terra | 0.833 | 5/6 | 11 | 0 | finish | 4/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 4 | none | openai-gpt-5.6-terra | 0.286 | 7/7 | 54 | 0 | no_tool_call | 22/0 | 0 | 0 | 0 | 0 | 2 | 0 |
| r3 | 4 | faculty-advisor | openai-gpt-5.6-terra | 0.714 | 7/7 | 78 | 0 | no_tool_call | 23/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 4 | k12-teacher | openai-gpt-5.6-terra | 0.286 | 7/7 | 57 | 0 | no_tool_call | 16/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r3 | 4 | first-gen-applicant | openai-gpt-5.6-terra | 0.286 | 7/7 | 68 | 0 | no_tool_call | 17/0 | 0 | 0 | 0 | 0 | 1 | 0 |
| r3 | 4 | parent-helper | openai-gpt-5.6-terra | 0.429 | 7/7 | 106 | 0 | no_tool_call | 27/0 | 0 | 0 | 0 | 2 | 2 | 0 |
| r3 | 5 | none | openai-gpt-5.6-terra | 0.250 | 4/4 | 56 | 0 | finish | 12/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r3 | 5 | faculty-advisor | openai-gpt-5.6-terra | 0.500 | 4/4 | 28 | 0 | no_tool_call | 4/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 5 | k12-teacher | openai-gpt-5.6-terra | 0.750 | 4/4 | 33 | 0 | no_tool_call | 7/0 | 0 | 0 | 0 | 0 | 3 | 0 |
| r3 | 5 | first-gen-applicant | openai-gpt-5.6-terra | 0.250 | 2/4 | 45 | 0 | finish | 10/0 | 0 | 0 | 0 | 0 | 5 | 0 |
| r3 | 5 | parent-helper | openai-gpt-5.6-terra | 0.500 | 4/4 | 49 | 0 | no_tool_call | 8/0 | 0 | 0 | 0 | 0 | 4 | 0 |
| r3 | 6 | none | openai-gpt-5.6-terra | 0.857 | 7/7 | 19 | 0 | finish | 5/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 6 | faculty-advisor | openai-gpt-5.6-terra | 0.286 | 5/7 | 34 | 0 | finish | 4/0 | 0 | 0 | 2 | 0 | 0 | 0 |
| r3 | 6 | k12-teacher | openai-gpt-5.6-terra | 0.857 | 7/7 | 33 | 0 | finish | 6/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 6 | first-gen-applicant | openai-gpt-5.6-terra | 0.143 | 5/7 | 9 | 0 | finish | 2/0 | 0 | 0 | 0 | 0 | 0 | 0 |
| r3 | 6 | parent-helper | openai-gpt-5.6-terra | 0.571 | 6/7 | 26 | 0 | no_tool_call | 5/0 | 0 | 0 | 0 | 0 | 0 | 0 |
