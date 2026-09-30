"""Load, validate, and select versioned task suites.

The router keeps task assignment data out of the runner.  A suite can contain
multiple JSON shards, so adding another batch of tasks does not require editing
``run.py`` or replacing the shared legacy ``tasks.json`` file.

    python src/task_router.py suites
    python src/task_router.py tasks --suite shopping
    python src/task_router.py selectors --suite shopping
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "task_suites.json"
LEGACY_TASKS = HERE / "tasks.json"
MANIFEST_SCHEMA = "personacuabench.task-suites.v1"
RESULT_SCHEMA = "personacuabench.result.v2"
SUITE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PERSONA_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class TaskRoutingError(ValueError):
    """A task catalog, suite, selector, or task file is invalid."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_suite_id(value: object, *, where: str) -> str:
    if not isinstance(value, str) or not SUITE_ID_RE.fullmatch(value):
        raise TaskRoutingError(
            f"{where} must match {SUITE_ID_RE.pattern!r}; got {value!r}"
        )
    return value


def _validate_tasks(tasks: object, *, source: Path) -> list[dict]:
    if not isinstance(tasks, list) or not tasks:
        raise TaskRoutingError(f"{source}: top-level tasks must be a non-empty list")
    checked: list[dict] = []
    seen: set[str] = set()
    for index, task in enumerate(tasks, 1):
        where = f"{source}: task {index}"
        if not isinstance(task, dict):
            raise TaskRoutingError(f"{where} must be an object")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
            raise TaskRoutingError(
                f"{where} task_id must be one path-safe token; got {task_id!r}"
            )
        if task_id in seen:
            raise TaskRoutingError(f"{source}: duplicate task_id {task_id!r}")
        seen.add(task_id)
        if not isinstance(task.get("confirmed_task"), str) or not task["confirmed_task"].strip():
            raise TaskRoutingError(f"{where} has no non-empty confirmed_task")
        if not isinstance(task.get("level"), str) or not task["level"].strip():
            raise TaskRoutingError(f"{where} has no non-empty level")
        rubrics = task.get("rubrics")
        if not isinstance(rubrics, dict) or not rubrics:
            raise TaskRoutingError(f"{where} has no rubric object")
        for rubric_id, rubric in rubrics.items():
            if not isinstance(rubric_id, str) or not rubric_id.strip():
                raise TaskRoutingError(f"{where} has an invalid rubric id")
            if not isinstance(rubric, dict):
                raise TaskRoutingError(f"{where} rubric {rubric_id!r} must be an object")
            if not isinstance(rubric.get("requirement"), str) or not rubric["requirement"].strip():
                raise TaskRoutingError(f"{where} rubric {rubric_id!r} has no requirement")
            if not isinstance(rubric.get("verification"), str) or not rubric["verification"].strip():
                raise TaskRoutingError(f"{where} rubric {rubric_id!r} has no verification")
        checked.append(task)
    return checked


def _validate_personas(value: object, *, where: str) -> list[str]:
    if (not isinstance(value, list) or not value
            or any(not isinstance(item, str) or not PERSONA_ID_RE.fullmatch(item)
                   for item in value)):
        raise TaskRoutingError(
            f"{where} must be a non-empty list of path-safe persona IDs"
        )
    if len(value) != len(set(value)):
        raise TaskRoutingError(f"{where} contains duplicate persona IDs")
    return list(value)


def _read_task_file(path: Path, *, expected_suite: str | None = None) -> tuple[list[dict], dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TaskRoutingError(f"cannot read task file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TaskRoutingError(f"invalid JSON in task file {path}: {exc}") from exc

    metadata: dict = {}
    if isinstance(payload, dict):
        metadata = {key: payload[key] for key in (
            "suite_id", "title", "version", "default_personas"
        ) if key in payload}
        tasks = payload.get("tasks")
        declared = payload.get("suite_id")
        if declared is not None:
            declared = _validate_suite_id(declared, where=f"{path} suite_id")
            if expected_suite and declared != expected_suite:
                raise TaskRoutingError(
                    f"{path}: suite_id {declared!r} does not match {expected_suite!r}"
                )
    else:
        tasks = payload
    return _validate_tasks(tasks, source=path), metadata


def _safe_task_files(root: Path, patterns: object, *, suite_id: str) -> list[Path]:
    if not isinstance(patterns, list) or not patterns:
        raise TaskRoutingError(f"suite {suite_id!r} needs a non-empty task_files list")
    files: list[Path] = []
    root_resolved = root.resolve()
    for raw_pattern in patterns:
        if not isinstance(raw_pattern, str) or not raw_pattern.strip():
            raise TaskRoutingError(f"suite {suite_id!r} has an invalid task_files entry")
        pattern_path = Path(raw_pattern)
        if pattern_path.is_absolute() or ".." in pattern_path.parts:
            raise TaskRoutingError(
                f"suite {suite_id!r} task path must stay under {root}: {raw_pattern!r}"
            )
        matches = sorted(path for path in root.glob(raw_pattern) if path.is_file())
        if not matches:
            raise TaskRoutingError(
                f"suite {suite_id!r} task_files pattern matched nothing: {raw_pattern!r}"
            )
        for path in matches:
            resolved = path.resolve()
            try:
                resolved.relative_to(root_resolved)
            except ValueError as exc:
                raise TaskRoutingError(
                    f"suite {suite_id!r} task file escapes {root}: {path}"
                ) from exc
            if resolved.suffix.lower() != ".json":
                raise TaskRoutingError(f"suite {suite_id!r} task file is not JSON: {path}")
            if resolved in files:
                raise TaskRoutingError(
                    f"suite {suite_id!r} includes the same task file twice: {path}"
                )
            files.append(resolved)
    return files


def _display_path(path: Path, *, root: Path = HERE) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


@dataclass
class TaskSuite:
    suite_id: str
    title: str
    version: str
    default_personas: list[str]
    tasks: list[dict]
    sources: list[Path]
    task_sources: dict[str, Path]
    persona_experiment: Path | None = None

    @property
    def sha256(self) -> str:
        return canonical_sha256({
            "suite_id": self.suite_id,
            "version": self.version,
            "tasks": self.tasks,
        })

    def resolve(self, spec: str | None, run_all: bool = False) -> list[dict]:
        if run_all or not spec:
            return list(self.tasks)
        picked: list[dict] = []
        picked_ids: set[str] = set()
        for raw_token in spec.split(","):
            token = raw_token.strip()
            if not token:
                raise TaskRoutingError("empty task selector")
            exact = [task for task in self.tasks if task["task_id"] == token]
            # Short decimal tokens are ordinals.  Long decimal strings are
            # allowed as SHA-like ID prefixes (Kobe begins with "39255449").
            ordinal_token = token.isdigit() and len(token) <= max(
                3, len(str(len(self.tasks)))
            )
            if exact:
                task = exact[0]
            elif ordinal_token:
                ordinal = int(token)
                if not 1 <= ordinal <= len(self.tasks):
                    raise TaskRoutingError(
                        f"task ordinal {ordinal} is outside 1..{len(self.tasks)} "
                        f"for suite {self.suite_id!r}"
                    )
                task = self.tasks[ordinal - 1]
            else:
                hits = [
                    task for task in self.tasks if task["task_id"].startswith(token)
                ]
                if not hits:
                    raise TaskRoutingError(
                        f"no task matching {token!r} in suite {self.suite_id!r}"
                    )
                if len(hits) > 1:
                    matches = ", ".join(task["task_id"] for task in hits[:5])
                    raise TaskRoutingError(
                        f"ambiguous task prefix {token!r} in suite {self.suite_id!r}: "
                        f"{matches}"
                    )
                task = hits[0]
            if task["task_id"] in picked_ids:
                raise TaskRoutingError(f"task {task['task_id']!r} was selected twice")
            picked_ids.add(task["task_id"])
            picked.append(task)
        return picked

    def task_snapshot(self, task: dict) -> dict:
        task_id = task["task_id"]
        return {
            "id": self.suite_id,
            "title": self.title,
            "version": self.version,
            "suite_sha256": self.sha256,
            "task_source": _display_path(self.task_sources[task_id]),
            "task_index": next(
                index for index, item in enumerate(self.tasks, 1)
                if item["task_id"] == task_id
            ),
        }


class TaskCatalog:
    def __init__(self, suites: dict[str, TaskSuite], default_suite_id: str):
        if default_suite_id not in suites:
            raise TaskRoutingError(f"unknown default_suite {default_suite_id!r}")
        self.suites = suites
        self.default_suite_id = default_suite_id
        owners: dict[str, str] = {}
        for suite_id, suite in suites.items():
            for task in suite.tasks:
                task_id = task["task_id"]
                if task_id in owners:
                    raise TaskRoutingError(
                        f"task_id {task_id!r} is present in both "
                        f"{owners[task_id]!r} and {suite_id!r}; registered task IDs "
                        "must be globally unique"
                    )
                owners[task_id] = suite_id

    @property
    def default_suite(self) -> TaskSuite:
        return self.suites[self.default_suite_id]

    def get_suite(self, suite_id: str | None = None) -> TaskSuite:
        suite_id = suite_id or self.default_suite_id
        try:
            return self.suites[suite_id]
        except KeyError as exc:
            choices = ", ".join(self.suites)
            raise TaskRoutingError(
                f"unknown task suite {suite_id!r}; available: {choices}"
            ) from exc

    def find_task(self, task_id: str, suite_id: str | None = None) -> tuple[dict, TaskSuite]:
        suites = [self.get_suite(suite_id)] if suite_id else list(self.suites.values())
        hits = [
            (task, suite)
            for suite in suites
            for task in suite.tasks
            if task["task_id"] == task_id
        ]
        if not hits:
            where = f" in suite {suite_id!r}" if suite_id else " in any registered suite"
            raise TaskRoutingError(f"task {task_id!r} was not found{where}")
        if len(hits) > 1:
            raise TaskRoutingError(f"task {task_id!r} is ambiguous across suites")
        return hits[0]

    @classmethod
    def load_retired(cls, suite_id: str,
                     manifest_path: Path = MANIFEST) -> "TaskSuite":
        """One suite from the manifest's `retired_suites`, on its own.

        A retired suite holds task ids that a live suite now owns -- v1 is the
        source of truth and its Odysseys entries are the same tasks -- so
        loading it into the catalog would trip the global-uniqueness check.
        It is still real data with its own protocol and personas, so it stays
        loadable one at a time, for tests and for reading old results.
        """
        manifest_path = Path(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        retired = manifest.get("retired_suites") or {}
        spec = retired.get(suite_id)
        if not isinstance(spec, dict):
            available = sorted(k for k, v in retired.items() if isinstance(v, dict))
            raise TaskRoutingError(
                f"no retired suite {suite_id!r}; available: {available}")
        single = {"schema_version": manifest.get("schema_version"),
                  "default_suite": suite_id, "suites": {suite_id: spec}}
        scratch = manifest_path.parent / f".retired-{suite_id}.json"
        scratch.write_text(json.dumps(single), encoding="utf-8")
        try:
            return cls.load(manifest_path=scratch).get_suite(suite_id)
        finally:
            scratch.unlink(missing_ok=True)

    @classmethod
    def load(
        cls,
        manifest_path: Path = MANIFEST,
        legacy_tasks_path: Path = LEGACY_TASKS,
    ) -> "TaskCatalog":
        manifest_path = Path(manifest_path)
        legacy_tasks_path = Path(legacy_tasks_path)
        if not manifest_path.is_file():
            tasks, _ = _read_task_file(legacy_tasks_path, expected_suite="legacy")
            source = legacy_tasks_path.resolve()
            suite = TaskSuite(
                suite_id="legacy",
                title="Legacy tasks.json",
                version="legacy",
                default_personas=["none", "travel-expert", "travel-senior"],
                tasks=tasks,
                sources=[source],
                task_sources={task["task_id"]: source for task in tasks},
            )
            return cls({"legacy": suite}, "legacy")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TaskRoutingError(f"cannot load task manifest {manifest_path}: {exc}") from exc
        if not isinstance(manifest, dict):
            raise TaskRoutingError(f"{manifest_path}: manifest must be an object")
        if manifest.get("schema_version") != MANIFEST_SCHEMA:
            raise TaskRoutingError(
                f"{manifest_path}: schema_version must be {MANIFEST_SCHEMA!r}"
            )
        default_suite_id = _validate_suite_id(
            manifest.get("default_suite"), where=f"{manifest_path} default_suite"
        )
        specs = manifest.get("suites")
        if not isinstance(specs, dict) or not specs:
            raise TaskRoutingError(f"{manifest_path}: suites must be a non-empty object")

        root = manifest_path.resolve().parent
        suites: dict[str, TaskSuite] = {}
        for raw_suite_id, spec in specs.items():
            suite_id = _validate_suite_id(raw_suite_id, where="suite id")
            if not isinstance(spec, dict):
                raise TaskRoutingError(f"suite {suite_id!r} config must be an object")
            files = _safe_task_files(root, spec.get("task_files"), suite_id=suite_id)
            title = spec.get("title", suite_id)
            version = spec.get("version", "1")
            personas = spec.get("default_personas", [
                "none", "travel-expert", "travel-senior"
            ])
            experiment_path = None
            raw_experiment = spec.get("persona_experiment")
            if raw_experiment is not None:
                if not isinstance(raw_experiment, str) or not raw_experiment.strip():
                    raise TaskRoutingError(
                        f"suite {suite_id!r} has an invalid persona_experiment"
                    )
                relative_experiment = Path(raw_experiment)
                if relative_experiment.is_absolute() or ".." in relative_experiment.parts:
                    raise TaskRoutingError(
                        f"suite {suite_id!r} persona_experiment must stay under {root}"
                    )
                experiment_path = (root / relative_experiment).resolve()
                try:
                    experiment_path.relative_to(root)
                except ValueError as exc:
                    raise TaskRoutingError(
                        f"suite {suite_id!r} persona_experiment escapes {root}"
                    ) from exc
                if experiment_path.suffix.lower() != ".json" or not experiment_path.is_file():
                    raise TaskRoutingError(
                        f"suite {suite_id!r} persona_experiment is not a JSON file: "
                        f"{experiment_path}"
                    )
            if not isinstance(title, str) or not title.strip():
                raise TaskRoutingError(f"suite {suite_id!r} has an invalid title")
            if not isinstance(version, (str, int, float)) or isinstance(version, bool):
                raise TaskRoutingError(f"suite {suite_id!r} has an invalid version")
            personas = _validate_personas(
                personas, where=f"suite {suite_id!r} default_personas"
            )
            tasks: list[dict] = []
            sources_by_id: dict[str, Path] = {}
            for path in files:
                shard, _ = _read_task_file(path, expected_suite=suite_id)
                for task in shard:
                    task_id = task["task_id"]
                    if task_id in sources_by_id:
                        raise TaskRoutingError(
                            f"suite {suite_id!r} has duplicate task_id {task_id!r} "
                            f"in {_display_path(sources_by_id[task_id], root=root)} and "
                            f"{_display_path(path, root=root)}"
                        )
                    sources_by_id[task_id] = path
                    tasks.append(task)
            suites[suite_id] = TaskSuite(
                suite_id=suite_id,
                title=title.strip(),
                version=str(version),
                default_personas=personas,
                tasks=tasks,
                sources=files,
                task_sources=sources_by_id,
                persona_experiment=experiment_path,
            )
        return cls(suites, default_suite_id)


def suite_from_file(path: Path) -> TaskSuite:
    path = Path(path).expanduser().resolve()
    tasks, metadata = _read_task_file(path)
    raw_id = metadata.get("suite_id")
    if raw_id is None:
        # Content-derived identity stays stable if a draft file is renamed and
        # changes when its task/rubric contents change.
        raw_id = f"adhoc-{canonical_sha256(tasks)[:12]}"
    suite_id = _validate_suite_id(raw_id, where=f"{path} suite_id")
    title = metadata.get("title", f"Ad hoc: {path.name}")
    version = metadata.get("version", "adhoc")
    personas = metadata.get(
        "default_personas", ["none", "travel-expert", "travel-senior"]
    )
    if not isinstance(title, str) or not title.strip():
        raise TaskRoutingError(f"{path}: title must be a non-empty string")
    personas = _validate_personas(personas, where=f"{path} default_personas")
    return TaskSuite(
        suite_id=suite_id,
        title=title.strip(),
        version=str(version),
        default_personas=personas,
        tasks=tasks,
        sources=[path],
        task_sources={task["task_id"]: path for task in tasks},
    )


def load_route(
    *,
    suite_id: str | None = None,
    tasks_file: str | Path | None = None,
    catalog: TaskCatalog | None = None,
) -> TaskSuite:
    if suite_id and tasks_file:
        raise TaskRoutingError("--suite and --tasks-file are mutually exclusive")
    if tasks_file:
        custom = suite_from_file(Path(tasks_file))
        active_catalog = catalog or TaskCatalog.load()
        if custom.suite_id in active_catalog.suites:
            raise TaskRoutingError(
                f"ad-hoc suite_id {custom.suite_id!r} conflicts with a registered suite; "
                "use --suite for the registered suite or choose another suite_id"
            )
        return custom
    return (catalog or TaskCatalog.load()).get_suite(suite_id)


def format_suites(catalog: TaskCatalog) -> list[str]:
    lines = []
    for suite_id, suite in catalog.suites.items():
        marker = "*" if suite_id == catalog.default_suite_id else " "
        lines.append(
            f"{marker} {suite_id:<18} {len(suite.tasks):>3} tasks  "
            f"v{suite.version}  {suite.title}"
        )
    return lines


def format_tasks(suite: TaskSuite) -> list[str]:
    lines = []
    for index, task in enumerate(suite.tasks, 1):
        text = " ".join(task["confirmed_task"].split())
        lines.append(
            f"{index:>3}\t{task['task_id']}\t{task['level']}\t{text[:100]}"
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("suites", help="list registered suites; * marks the default")
    for name, help_text in (
        ("tasks", "list tasks with ordinal, full id, level, and request"),
        ("selectors", "print stable full task IDs, one per line"),
        ("personas", "print the suite's default persona IDs, one per line"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        route = command.add_mutually_exclusive_group()
        route.add_argument("--suite")
        route.add_argument("--tasks-file")
    args = parser.parse_args()
    try:
        catalog = TaskCatalog.load()
        if args.command == "suites":
            print("\n".join(format_suites(catalog)))
            return
        suite = load_route(
            suite_id=getattr(args, "suite", None),
            tasks_file=getattr(args, "tasks_file", None),
            catalog=catalog,
        )
        if args.command == "tasks":
            print("\n".join(format_tasks(suite)))
        elif args.command == "selectors":
            print("\n".join(task["task_id"] for task in suite.tasks))
        else:
            print("\n".join(suite.default_personas))
    except TaskRoutingError as exc:
        raise SystemExit(f"task routing error: {exc}") from exc


if __name__ == "__main__":
    main()
