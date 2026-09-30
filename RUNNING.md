# Running your model

You have been assigned one execution model. This is everything you do with it,
start to finish. Nothing here needs another collaborator's keys.

The overview of what the benchmark measures is in [`README.md`](README.md); the
detail of how a cell works is in [`src/README.md`](src/README.md).

## 1. Set up

```bash
git clone <this repo> && cd PersonaCUABench
git checkout <this branch>
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
```

You also need **Google Chrome** installed. Without root, put
`CHROME_CHANNEL=chromium` in `.env` and run
`python -m playwright install chromium` instead.

```bash
cp .env.example .env
```

Fill in **two things**:

1. **The shared Azure endpoint.** This runs the persona simulator, the rubric
   judge and experience judge A — the same for everyone, so your results are
   comparable with everyone else's. Haoming sends you the key; put it in
   `azure_api_key.txt` (gitignored) and leave
   `AZURE_OPENAI_API_KEY_FILE=azure_api_key.txt` as it is.
2. **Your own model's endpoint and key.**

| model | owner | key to pass | variables to fill |
|---|---|---|---|
| Claude Opus 5.5 | Yiyang | `opus-5.5` | `CLAUDE_BASE_URL` + `CLAUDE_API_KEY` |
| GPT 6 Astra | Haoming | `gpt-6-astra` | `GPT6_BASE_URL` + `GPT6_API_KEY` |
| Muse Spark 1.1 | Xu Hu | `muse-spark-1.1` | `MUSE_BASE_URL` + `MUSE_API_KEY` |
| Gemini 3.8 Flash | Sherry | `gemini-3.8-flash` | `GEMINI_BASE_URL` + `GEMINI_API_KEY` |
| Kimi K3 | Sherry | `kimi-k3` | `KIMI_BASE_URL` + `KIMI_API_KEY` |
| Grok 4.7 | Defu | `grok-4.7` | `GROK_BASE_URL` + `GROK_API_KEY` |
| MiniMax M3 | Charles | `minimax-m3` | `MINIMAX_BASE_URL` + `MINIMAX_API_KEY` |
| GLM 5.3 | Charles | `glm-5.3` | `GLM_BASE_URL` + `GLM_API_KEY` |
| Qwen 3.8 27B | Xu Hu | `qwen3.8-27b` | `QWEN_BASE_URL` + `QWEN_API_KEY` |

`OPENROUTER_API_KEY` is optional. It buys experience judge **B**, a second
vendor whose agreement with judge A is what licenses the P1–P5 numbers. Without
it the run says so once and judge A still scores every cell; whoever collects
the results can add the second judge later.

Your model id must be the one **your provider** uses. Check
`src/models.json` → your key → `endpoint.model` against your provider's docs
before a paid run, and tell Haoming if it needs changing.

## 2. Check before you spend

```bash
bash scripts/check_all.sh     # 8 offline checks: no keys, no network, no browser
python src/models.py          # does your model have a route on this machine?
```

`check_all.sh` must print `all offline checks passed`. `models.py` must show
your key resolving to your own endpoint (or to Azure/OpenRouter as a fallback);
`(x)` means that route's credentials are missing here.

## 3. One cell first

```bash
python src/run.py --suite odysseys --task 1 --persona none \
  --model <your key> --headless
```

A few cents and a couple of minutes. It should print a `score` line and a path
under `src/results/`. Open that `result.json` and look at it once — that is the
unit of everything that follows.

Then one of each of the other two shapes:

```bash
python src/run.py --suite real --task 1 --persona none --model <your key> --headless
python src/run.py --suite odysseys --task 1 --persona travel-senior --model <your key> --headless
```

The `real` one runs against a sandbox replica of a real site and is scored by a
deterministic checker, not a model. The `travel-senior` one is the real thing: a
persona model rewrites the task as that person would ask it, and your model only
ever sees what they said.

If any of these three fails, stop and tell Haoming what it printed. Do not start
the grid.

## 4. The grid

```bash
SETTING=s1 MODELS="<your key>" JOBS=4 bash src/run_all.sh
```

**370 cells** — 74 tasks × (4 personas + 1 `none` control), over both suites —
then the judges and the reports. Expect roughly **8–14 hours at `JOBS=4`**.

- `DRY_RUN=1` in front lists every cell and runs nothing. Do this first.
- `JOBS=N` runs N cells at once, each in its own Chrome profile. Budget about
  **1.5 GB of RAM per worker** — Chrome, not the model, is what runs a machine
  out of memory.
- **Safe to re-run.** Finished cells are skipped and judged runs are not
  re-judged, so an interrupted night resumes by running the same command again.
- Per-cell logs are in `logs/cells/`, the summary in `logs/s1-*.log`.
- One cell of `gpt-6-astra` averaged **$3.10** over a sample of four (one task
  read enough live pages to cost $9.68 on its own). Your model's price differs;
  measure with `python src/cost_report.py src/results/s1` after a handful of
  cells before committing to the whole grid.

## 5. The proactivity ablation

The benchmark's second question is whether an agent **asks** when the person
left something out, or guesses. `ask_user` is always available to your model (up
to 5 questions per cell). The ablation adds a paragraph to its system prompt
telling it to prefer asking:

```bash
NUDGE=both SETTING=s1 MODELS="<your key>" JOBS=4 bash src/run_all.sh
```

`NUDGE=off` (the default) is the plain arm, `on` is nudged, `both` runs each
cell **twice**, once each way — so `both` is 740 cells and twice the money. The
flag is part of every cell's identity, so the two arms never overwrite each
other, and the comparison comes out as:

```bash
python src/cost_report.py src/results/s1 --by proactive_nudge
```

**Run `NUDGE=off` first and finish it.** Only start the nudged arm once the
plain grid is complete and Haoming has confirmed the budget.

## 6. Send the results

Everything is under `src/results/` — **gitignored on purpose**. Never commit it.

```bash
python src/report.py src/results/s1 --suite odysseys
python src/report.py src/results/s1 --suite real
python src/cost_report.py src/results/s1 --csv cells.csv
```

Then upload the whole `src/results/` directory to the Google Drive folder
Haoming gives you, together with `logs/` and `cells.csv`. Keep the directory
structure as it is — the judges and reports are re-run over it centrally.

Each cell's `result.json` holds the task as it was at run time with its hash,
the persona's profile, every model turn including its reasoning, every tool call
with its arguments and full result, a screenshot of every step, the judgements,
and every call's tokens, latency and cost. That is what makes a result
re-judgeable months later, so please do not prune it.

## If something goes wrong

| symptom | what it means |
|---|---|
| `models.py` shows `(x)` on your route | that route's `_BASE_URL`/`_API_KEY` is not set in `.env` |
| a model with no route raises | deliberate: it will not quietly run somewhere else |
| `UNJUDGED (...)` on a cell | the run is saved and fine; the judge could not score it. The reason is in the line. Re-runnable with `python src/judge_all.py` |
| `UNSCORED: model returned no output` | your model returned nothing usable three times. Keep the record and tell Haoming |
| a REAL cell says the state was never read | the sandbox did not answer; re-run that cell |
| Chrome dies under `JOBS=4` | lower `JOBS`; each worker needs ~1.5 GB |

Anything you cannot explain in ten minutes: send the per-cell log from
`logs/cells/` and the `result.json`. Do not "fix" a cell by editing a result.
