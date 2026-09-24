"""Persona x task score tables over benchmark results.

The default report is the catalog's default suite.  Results carry a frozen
suite/task snapshot, so historical or ad-hoc tasks are not silently dropped.

    python odyssey/report.py
    python odyssey/report.py artifacts/lifestyle-results --suite lifestyle
    python odyssey/report.py --all-suites
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import task_router  # noqa: E402

RESULTS = HERE / "results"
TaskKey = tuple[str, str, str]  # suite id, full task id, task sha256/revision
ResultKey = tuple[str, str, str, str]  # task key + arm
ResultValue = tuple[str, dict, int | None, dict | None, dict | None, str]


def _explicit_suite(record: dict) -> str | None:
    snapshot = record.get("suite_snapshot")
    values = [record.get("suite_id"), record.get("task_suite")]
    if isinstance(snapshot, dict):
        values.append(snapshot.get("id"))
    present = [value for value in values if value is not None]
    if any(not isinstance(value, str) or not value for value in present):
        raise ValueError("result has an invalid suite identity")
    if len(set(present)) > 1:
        raise ValueError("result has conflicting suite identities")
    return present[0] if present else None


def suite_for_record(record: dict, catalog: task_router.TaskCatalog) -> str:
    """Recover a suite for v1 records without blindly assuming today's default."""
    explicit = _explicit_suite(record)
    if explicit:
        return explicit
    task_id = record.get("task_id")
    try:
        _, suite = catalog.find_task(task_id)
    except task_router.TaskRoutingError:
        return "unrouted"
    return suite.suite_id


def task_version_for_record(record: dict) -> str:
    """Return a content identity without trusting a stale stored hash."""
    stored = record.get("task_sha256")
    snapshot = record.get("task_snapshot")
    if isinstance(snapshot, dict) and snapshot.get("task_id") != record.get("task_id"):
        raise ValueError("result task_snapshot does not match task_id")
    actual = (
        task_router.canonical_sha256(snapshot)
        if isinstance(snapshot, dict) else None
    )
    if stored is not None:
        if (not isinstance(stored, str) or len(stored) != 64
                or any(char not in "0123456789abcdef" for char in stored.lower())):
            raise ValueError("result has an invalid task_sha256")
        if actual and actual != stored:
            raise ValueError("result task_sha256 does not match task_snapshot")
        return stored
    return actual or "unverified"


def run_config_version(record: dict) -> str:
    stored = record.get("run_config_sha256")
    config = record.get("run_config")
    actual = task_router.canonical_sha256(config) if isinstance(config, dict) else None
    if stored is not None:
        if (not isinstance(stored, str) or len(stored) != 64
                or any(char not in "0123456789abcdef" for char in stored.lower())):
            raise ValueError("result has an invalid run_config_sha256")
        if actual and actual != stored:
            raise ValueError("result run_config_sha256 does not match run_config")
        return stored
    return actual or "legacy"


def comparison_config_version(record: dict) -> str:
    """A cross-task arm identity, excluding task-bound scheduling/cache fields."""
    exact = run_config_version(record)
    config = record.get("run_config")
    if exact == "legacy" or not isinstance(config, dict):
        return "legacy"
    comparable = copy.deepcopy(config)
    for field in (
        "persona_opening_cache_key",
        "pair_order",
        "pair_position",
    ):
        comparable.pop(field, None)
    return task_router.canonical_sha256(comparable)


def resume_config_version(record: dict) -> str:
    stored = record.get("resume_config_sha256")
    config = record.get("resume_config")
    actual = task_router.canonical_sha256(config) if isinstance(config, dict) else None
    if stored is not None:
        if (not isinstance(stored, str) or len(stored) != 64
                or any(char not in "0123456789abcdef" for char in stored.lower())):
            raise ValueError("result has an invalid resume_config_sha256")
        if actual and actual != stored:
            raise ValueError("result resume_config_sha256 does not match resume_config")
        return stored
    return actual or "legacy"


def collect_results(
    results: Path,
    catalog: task_router.TaskCatalog,
    routes: list[task_router.TaskSuite],
    *,
    all_suites: bool = False,
    custom_selection: bool = False,
) -> tuple[dict[ResultKey, ResultValue], list[TaskKey], dict[TaskKey, str]]:
    """Collect the latest judged run and the complete ordered task row set."""
    order: list[TaskKey] = []
    level: dict[TaskKey, str] = {}
    selected_suite_ids = {suite.suite_id for suite in routes}
    selected_tasks = {
        task["task_id"]: task_router.canonical_sha256(task)
        for suite in routes for task in suite.tasks
    }
    for suite in routes:
        for task in suite.tasks:
            key = (
                suite.suite_id,
                task["task_id"],
                task_router.canonical_sha256(task),
            )
            if key not in level:
                order.append(key)
                level[key] = task["level"]

    best: dict[ResultKey, ResultValue] = {}
    resume_keys: dict[ResultKey, dict[str, ResultKey]] = {}
    for path in sorted(results.rglob("result.json")):
        try:
            relative_parts = path.relative_to(results).parts
        except ValueError:
            relative_parts = path.parts
        if any(part.startswith("_") for part in relative_parts):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        judged = record.get("judgement")
        run = record.get("run")
        task_id = record.get("task_id")
        if not isinstance(judged, dict) or not isinstance(run, dict):
            continue
        score = judged.get("score")
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(float(score)) or not 0 <= float(score) <= 1):
            continue
        if not isinstance(task_id, str) or not task_id:
            continue
        try:
            suite_id = suite_for_record(record, catalog)
            task_version = task_version_for_record(record)
            config_version = comparison_config_version(record)
            resume_version = resume_config_version(record)
        except ValueError:
            continue
        if not all_suites:
            if custom_selection:
                if selected_tasks.get(task_id) != task_version:
                    continue
                # The selected content hash is authoritative even if the file
                # was renamed or the run used another ad-hoc suite label.
                suite_id = routes[0].suite_id
            elif suite_id not in selected_suite_ids:
                continue

        arm_meta = run.get("arm") or {}
        model = arm_meta.get("model") or "unknown"
        backend = arm_meta.get("backend") or arm_meta.get("provider") or "unknown"
        config_label = "legacy" if config_version == "legacy" else config_version[:8]
        arm = f"{record.get('persona', 'unknown')}/{model}@{backend}#{config_label}"
        row_key = (suite_id, task_id, task_version)
        if row_key not in level:
            snapshot = record.get("task_snapshot")
            snapshot_level = snapshot.get("level") if isinstance(snapshot, dict) else None
            level[row_key] = str(snapshot_level or record.get("level") or "?")
            order.append(row_key)
        base_key = (suite_id, task_id, task_version, arm)
        identities = resume_keys.setdefault(base_key, {})
        key = identities.get(resume_version)
        if key is None:
            if not identities:
                key = base_key
            else:
                if len(identities) == 1 and base_key in best:
                    old_resume = next(iter(identities))
                    old_key = (
                        suite_id,
                        task_id,
                        task_version,
                        f"{arm}~profile-{old_resume[:8]}",
                    )
                    best[old_key] = best.pop(base_key)
                    identities[old_resume] = old_key
                key = (
                    suite_id,
                    task_id,
                    task_version,
                    f"{arm}~profile-{resume_version[:8]}",
                )
            identities[resume_version] = key
        stamp = path.parent.name.rsplit("__", 1)[-1]
        value: ResultValue = (
            stamp,
            judged,
            run.get("max_steps"),
            record.get("experience"),
            record.get("persona_fidelity"),
            resume_version,
        )
        if key not in best or stamp > best[key][0]:
            best[key] = value
    return best, order, level


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?", default=str(RESULTS))
    route = parser.add_mutually_exclusive_group()
    route.add_argument("--suite", help="registered suite (default: catalog default)")
    route.add_argument("--tasks-file", help="report only task IDs in an ad-hoc file")
    route.add_argument("--all-suites", action="store_true",
                       help="include every registered suite and any other frozen results")
    args = parser.parse_args()

    try:
        catalog = task_router.TaskCatalog.load()
        if args.all_suites:
            routes = list(catalog.suites.values())
        else:
            routes = [task_router.load_route(
                suite_id=args.suite,
                tasks_file=args.tasks_file,
                catalog=catalog,
            )]
    except task_router.TaskRoutingError as exc:
        raise SystemExit(f"task routing error: {exc}") from exc

    best, order, level = collect_results(
        Path(args.results),
        catalog,
        routes,
        all_suites=args.all_suites,
        custom_selection=bool(args.tasks_file),
    )

    budgets = {value[2] for value in best.values() if value[2] is not None}
    if len(budgets) > 1:
        print(f"WARNING: mixed step budgets in these results: {sorted(budgets)}\n")

    if not best:
        selected = "all suites" if args.all_suites else routes[0].suite_id
        print(f"no judged results for {selected} under {args.results}")
        return

    if any(key[2] == "unverified" for key in best):
        print("WARNING: #legacy results without a frozen task snapshot appear as "
              "version=unverified; their scores cannot be proven comparable to "
              "the current task revision.\n")

    mixed = mixed_revision_groups(best)
    if mixed:
        labels = ", ".join(f"{suite}/{task[:12]}" for suite, task in mixed)
        print("WARNING: scored results contain multiple task revisions for "
              f"{labels}. Rows stay separate; cross-task aggregates are omitted.\n")

    table(best, order, level, "score: every rubric item", "score",
          show_mean=not mixed)
    print()
    table(best, order, level, "score: communicated items only", "score_communicated",
          show_mean=not mixed)
    if mixed:
        print("\nexperience and persona-fidelity aggregates omitted because task "
              "revisions are mixed; report a single revision/result subtree instead.")
    else:
        experience(best)
        persona_fidelity(best)


DIMENSIONS = ("P1_asked_for", "P2_readable_for_them", "P3_actionable",
              "P4_gap_handling", "P5_overall")


def mixed_revision_groups(best: dict[ResultKey, ResultValue]) -> list[tuple[str, str]]:
    revisions: dict[tuple[str, str], set[str]] = defaultdict(set)
    for suite_id, task_id, task_version, _ in best:
        revisions[(suite_id, task_id)].add(task_version)
    return sorted(key for key, values in revisions.items() if len(values) > 1)


def dim_score(verdict: dict | None, dim: str) -> float | None:
    """One judge's 1-5 score for one dimension, or None for n/a/missing."""
    raw = ((verdict or {}).get(dim) or {}).get("score")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return float(raw) if 1 <= raw <= 5 else None


def experience(best: dict[ResultKey, ResultValue]) -> None:
    """The person's axis, kept beside the task axis and never blended into it."""
    scored = {key: value for key, value in best.items() if value[3]}
    if not scored:
        return
    arms = sorted({key[3] for key in scored})
    print("\n\nexperience 1-5 per dimension, judge A / judge B (never averaged)")
    width = max(len(arm) for arm in arms) + 2
    print(f"{'dimension':<24}" + "".join(f"{arm:<{width}}" for arm in arms))
    for dim in DIMENSIONS:
        row = f"{dim:<24}"
        for arm in arms:
            pairs = [
                (dim_score(value[3].get("a"), dim), dim_score(value[3].get("b"), dim))
                for key, value in scored.items() if key[3] == arm
            ]
            a_values = [left for left, _ in pairs if left is not None]
            b_values = [right for _, right in pairs if right is not None]
            cell = (
                f"{sum(a_values)/len(a_values):.1f} / {sum(b_values)/len(b_values):.1f}"
                if a_values and b_values else "-"
            )
            row += f"{cell:<{width}}"
        print(row)

    deltas = [
        dimension["within_one"]
        for value in scored.values()
        for dimension in (value[3].get("agreement") or {}).values()
        if dimension
    ]
    if deltas:
        print(f"\njudges within one point: {sum(deltas)}/{len(deltas)} "
              f"({sum(deltas)/len(deltas):.1%})")

    print("\nP5 among runs that did everything they were asked "
          "(score_communicated = 1.0)")
    for arm in arms:
        done = [
            value for key, value in scored.items()
            if key[3] == arm and value[1].get("score_communicated") == 1.0
        ]
        values = [
            score for value in done
            for score in (
                dim_score(value[3].get("a"), "P5_overall"),
                dim_score(value[3].get("b"), "P5_overall"),
            ) if score is not None
        ]
        total = sum(1 for key in scored if key[3] == arm)
        print(f"  {arm:<{width}}{'-' if not values else f'{sum(values)/len(values):.1f}'}"
              f"   ({len(done)} of {total} runs)")


def persona_fidelity(best: dict[ResultKey, ResultValue]) -> None:
    """Report target score distributions, separate from CUA quality."""
    scored = {
        key: value for key, value in best.items()
        if (value[4] or {}).get("status") == "complete"
    }
    if not scored:
        return
    arms = sorted({key[3] for key in scored})
    width = max(len(arm) for arm in arms) + 2
    print("\n\npersona fidelity targets: 0=no affirmative evidence, "
          "1=weak, 2=clearly expressed; contradictions reported separately")
    print(f"{'arm':<{width}}score 0   score 1   score 2   contradicted   total")
    for arm in arms:
        records = [value[4] for key, value in scored.items() if key[3] == arm]
        values = [target["score"] for record in records for target in record["targets"]]
        counts = [values.count(score) for score in (0, 1, 2)]
        contradicted = sum(
            bool(target.get("contradicted"))
            for record in records for target in record["targets"]
        )
        print(f"{arm:<{width}}{counts[0]:<10}{counts[1]:<10}{counts[2]:<10}"
              f"{contradicted:<15}{len(values)}")


def _display_ids(order: list[TaskKey]) -> dict[TaskKey, str]:
    groups: dict[str, set[str]] = defaultdict(set)
    for _, task_id, _ in order:
        groups[task_id[:12]].add(task_id)
    return {
        key: (key[1] if len(groups[key[1][:12]]) > 1 else key[1][:12])
        for key in order
    }


def table(
    best: dict[ResultKey, ResultValue],
    order: list[TaskKey],
    level: dict[TaskKey, str],
    title: str,
    field: str,
    *,
    show_mean: bool = True,
) -> None:
    scores = {}
    for key, value in best.items():
        raw = value[1].get(field)
        scores[key] = (
            float(raw)
            if (not isinstance(raw, bool) and isinstance(raw, (int, float))
                and math.isfinite(float(raw)) and 0 <= float(raw) <= 1)
            else None
        )
    arms = sorted({key[3] for key in scores})
    print(title)
    width = max(len(arm) for arm in arms) + 2
    multiple_suites = len({suite_id for suite_id, _, _ in order}) > 1
    prefix = f"{'suite':<18}" if multiple_suites else ""
    print(prefix + f"{'task':<42}{'version':<12}{'level':<8}"
          + "".join(f"{arm:<{width}}" for arm in arms))
    totals: dict[str, list[float]] = defaultdict(list)
    display_ids = _display_ids(order)
    for suite_id, task_id, task_version in order:
        row = f"{suite_id:<18}" if multiple_suites else ""
        task_key = (suite_id, task_id, task_version)
        version_label = (
            "unverified" if task_version == "unverified" else task_version[:8]
        )
        row += (f"{display_ids[task_key]:<42}{version_label:<12}"
                f"{level[task_key]:<8}")
        for arm in arms:
            score = scores.get((suite_id, task_id, task_version, arm))
            row += f"{'-' if score is None else f'{score:.2f}':<{width}}"
            if score is not None:
                totals[arm].append(score)
        print(row)
    if show_mean:
        mean = f"{'':<18}" if multiple_suites else ""
        mean += f"{'MEAN':<42}{'':<12}{'':<8}"
        for arm in arms:
            values = totals[arm]
            cell = "-" if not values else f"{sum(values) / len(values):.2f}"
            mean += cell.ljust(width)
        print(mean)


if __name__ == "__main__":
    main()
