# Task suites

`task_suites.json` is the catalog. It maps a stable suite ID to one or more
task-file paths or glob patterns. `run.py`, `run_grid.sh`, and `report.py` all
use the same router, so adding a suite never requires changing pipeline code.

## Extend an existing suite

To add another Shopping batch, add a JSON list under `shopping/`, for example
`shopping/2026-q4.json`. The manifest already includes
`task_suites/shopping/*.json`, so the new shard is picked up automatically in
lexicographic filename order (`000-core.json` intentionally stays first).
Task IDs must be unique across the whole registered catalog.

## Add a new suite

Create a file (or a directory of shards) here and add one entry to
`../task_suites.json` with a title, version, task-files list, and default
personas. Each task keeps the upstream Odysseys shape: `task_id`,
`confirmed_task`, `level`, and a non-empty `rubrics` object are required.
`task_id` must be a single path-safe token (letters, numbers, `.`, `_`, `-`).

Use `python odyssey/run.py --list-suites` and
`python odyssey/run.py --suite <id> --list-tasks` to validate the catalog
without making any API calls.
