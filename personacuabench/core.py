"""Shared paths, validation, hashing, and atomic artifact helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_TASKS_PATH = PACKAGE_DIR / "tasks.json"
DEFAULT_RESULTS_DIR = REPO_ROOT / "artifacts" / "results"
DEFAULT_CACHE_DIR = REPO_ROOT / "artifacts" / "cache"
DEFAULT_PERSONA_DIR = PACKAGE_DIR / "personas"
DEFAULT_OSWORLD_DIR = REPO_ROOT / ".osworld" / "OSWorld"
DEFAULT_ODYSSEYS_DIR = REPO_ROOT / ".upstream" / "odysseys"
DEFAULT_PERSONA8B_DIR = REPO_ROOT / "MatrAIx-Persona-8B"


class ConfigurationError(ValueError):
    """Raised when a benchmark input or local dependency is invalid."""


def atomic_write_text(path: Path, text: str) -> None:
    """Write a UTF-8 text file atomically in its destination directory."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in {path}: {exc}") from exc


def validate_task(raw: Any, *, index: int | None = None) -> dict[str, Any]:
    prefix = f"task #{index}" if index is not None else "task"
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{prefix} must be an object")
    task_id = raw.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{40}", task_id):
        raise ConfigurationError(f"{prefix} has invalid task_id: {task_id!r}")
    instruction = raw.get("confirmed_task")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ConfigurationError(f"{prefix} is missing confirmed_task")
    rubrics = raw.get("rubrics")
    if not isinstance(rubrics, dict) or not rubrics:
        raise ConfigurationError(f"{prefix} is missing rubrics")
    for rubric_id, rubric in rubrics.items():
        if not re.fullmatch(r"R\d+", str(rubric_id)):
            raise ConfigurationError(f"{prefix} has invalid rubric id {rubric_id!r}")
        if not isinstance(rubric, dict) or not str(rubric.get("requirement", "")).strip():
            raise ConfigurationError(f"{prefix}/{rubric_id} has no requirement")
    return raw


def load_tasks(path: Path = DEFAULT_TASKS_PATH) -> list[dict[str, Any]]:
    raw = load_json(path)
    if not isinstance(raw, list) or not raw:
        raise ConfigurationError(f"Task file must contain a non-empty list: {path}")
    tasks = [validate_task(item, index=i) for i, item in enumerate(raw, start=1)]
    ids = [task["task_id"] for task in tasks]
    if len(set(ids)) != len(ids):
        raise ConfigurationError(f"Duplicate task_id in {path}")
    return tasks


def select_tasks(
    tasks: list[dict[str, Any]], *, task_number: int | None, select_all: bool
) -> list[dict[str, Any]]:
    if select_all == (task_number is not None):
        raise ConfigurationError("Choose exactly one of --all or --task N")
    if select_all:
        return tasks
    assert task_number is not None
    if task_number < 1 or task_number > len(tasks):
        raise ConfigurationError(
            f"--task must be between 1 and {len(tasks)}, got {task_number}"
        )
    return [tasks[task_number - 1]]


def task_config_path(task: dict[str, Any], odysseys_dir: Path) -> Path:
    domain = str(task.get("domain") or "mind2web_chrome")
    return (
        odysseys_dir
        / "data"
        / "odysseys_cua_final"
        / "examples"
        / domain
        / f"{task['task_id']}.json"
    )


def load_task_config(task: dict[str, Any], odysseys_dir: Path) -> dict[str, Any]:
    path = task_config_path(task, odysseys_dir)
    config = load_json(path)
    if not isinstance(config, dict):
        raise ConfigurationError(f"OSWorld task config must be an object: {path}")
    actual = config.get("instruction")
    expected = task["confirmed_task"]
    if actual != expected:
        raise ConfigurationError(
            f"Task text mismatch between {DEFAULT_TASKS_PATH} and {path}"
        )
    return config


def safe_slug(value: str, *, max_length: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return (slug or "unnamed")[:max_length]


def git_head(repo: Path) -> str | None:
    """Read a checkout's HEAD without invoking git or mutating the repository."""
    head_path = repo / ".git" / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if head.startswith("ref: "):
        ref_path = repo / ".git" / head.removeprefix("ref: ")
        try:
            return ref_path.read_text(encoding="utf-8").strip()
        except OSError:
            packed = repo / ".git" / "packed-refs"
            try:
                for line in packed.read_text(encoding="utf-8").splitlines():
                    if line and not line.startswith(("#", "^")):
                        commit, ref = line.split(" ", 1)
                        if ref == head.removeprefix("ref: "):
                            return commit
            except OSError:
                return None
            return None
    return head if re.fullmatch(r"[0-9a-f]{40}", head) else None


def build_fingerprint(
    *,
    task: dict[str, Any],
    persona_meta: dict[str, Any],
    models: dict[str, Any],
    limits: dict[str, Any],
    source_revisions: dict[str, Any],
    run_control: dict[str, Any] | None = None,
) -> str:
    return stable_sha256(
        {
            "fingerprint_schema": "persona-cua-run-fingerprint/v2",
            "task_id": task["task_id"],
            "task": task["confirmed_task"],
            "rubrics": task["rubrics"],
            "persona": persona_meta,
            "models": models,
            "limits": limits,
            "run_control": run_control or {},
            "source_revisions": source_revisions,
        }
    )


def complete_result(path: Path, fingerprint: str | None = None) -> bool:
    try:
        value = load_json(path)
    except ConfigurationError:
        return False
    if not isinstance(value, dict) or value.get("status") not in {
        "agent_complete",
        "complete",
    }:
        return False
    return fingerprint is None or value.get("fingerprint") == fingerprint


def iter_result_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.name == "result.json":
        yield root
    elif root.is_dir():
        yield from sorted(root.rglob("result.json"))
