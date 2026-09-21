# PersonaCUABench

The runnable benchmark on this branch lives under [`odyssey/`](odyssey/README.md).

## Task-suite router

This branch defaults to the `shopping` suite (Task 1 is the Kobe task), while
the original `main` tasks remain available as `main-original` instead of being
overwritten:

```bash
python odyssey/run.py --list-suites
python odyssey/run.py --suite shopping --list-tasks
python odyssey/run.py --suite main-original --task 1 --persona none --preview
```

Future Shopping batches can be added as another JSON shard under
`odyssey/task_suites/shopping/`; the existing manifest glob picks them up
without any runner changes. New domains get their own suite entry in
[`odyssey/task_suites.json`](odyssey/task_suites.json). See the
[`odyssey` guide](odyssey/README.md#task-suites-and-future-batches) for the
registered-suite, ad-hoc file, grid, and reporting workflows.

## Local Azure configuration

The runner reads `.env` from the repository root. It is parsed by
`odyssey/run.py`; it is not a system-wide environment file and is not created
automatically. Start from the tracked, secret-free example:

```bash
cp .env.example .env
# Copy the key from your existing secure location; do not paste it into Git.
cp /secure/path/to/azure_api_key.txt ./azure_api_key.txt
chmod 600 azure_api_key.txt
```

The local `.env` points at `azure_api_key.txt`; it does not contain the secret.
Both files are ignored by Git. Exported shell variables take precedence over
same-named dotenv values.

For the complete setup, single-task commands, P1-P5 experience grading and the
independent persona-fidelity stage, see [`odyssey/README.md`](odyssey/README.md).
