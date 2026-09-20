"""Persona-side conversation adapter for an Odysseys CUA run.

The adapter deliberately keeps task execution out of the persona model.  It
uses MatrAIx-Persona-8B's official loader and ``persona_system`` renderer for
identity, then asks an OpenAI-compatible chat endpoint for only two things:
an opening request and answers to clarification questions.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


_STATE_SCHEMA = "persona-session.v1"
_SENSITIVE_NAME = re.compile(
    r"(?:api[_-]?key|authorization|credential|password|secret|token)", re.I
)

_NULLISH = frozenset(
    {
        "",
        "none",
        "n/a",
        "na",
        "null",
        "undefined",
        "none notable",
        "not applicable",
        "prefer not to say",
        "no coding activity",
        "not a developer",
        "no interest",
        "unknown",
    }
)

_LEGACY_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Identity",
        (
            "Demographic: Core",
            "Demographic: Cultural",
            "Demographic: Family",
            "Demographic: Life Events",
        ),
    ),
    (
        "Career & education",
        (
            "Professional: Career",
            "Professional: Industry",
            "Learning: Academic",
            "Learning: Style",
            "Developer:",
        ),
    ),
    (
        "Language & communication",
        ("Linguistic: Language", "Linguistic: Communication"),
    ),
    (
        "Personality & values",
        (
            "Personality: Big Five",
            "Personality: Character",
            "Personality: MBTI",
            "Personality: Relationships",
            "Values & Motivation",
            "Risk & Decision",
        ),
    ),
    ("Current interaction state", ("State: Emotional", "Behavior: Time", "Behavior: Work")),
    ("Worldview", ("Worldview: Beliefs",)),
    (
        "Interests",
        (
            "Interests: Topics",
            "Interests: Hobbies",
            "Interests: Media",
            "Interests: Culture",
            "Interests: Sports",
            "Interests: Food",
        ),
    ),
    (
        "Skills & expertise",
        ("Expertise: Domains", "Expertise: Skills", "Skills: Tools", "Skills: Programming"),
    ),
    (
        "Lifestyle & health",
        (
            "Health: Physical",
            "Health: Fitness",
            "Health: Lifestyle",
            "Behavior: Preferences",
            "Behavior: Habits",
        ),
    ),
)


class PersonaConfigurationError(ValueError):
    """Raised when persona/session configuration is invalid."""


class PersonaSessionStateError(ValueError):
    """Raised when a saved session is malformed or belongs to another run."""


class QuestionLimitExceeded(RuntimeError):
    """Raised when the CUA asks more clarification questions than allowed."""


@dataclass(frozen=True)
class PersonaProfile:
    """A loaded MatrAIx profile plus its rendered identity and eval selection."""

    path: Path
    persona: Any = field(repr=False, compare=False)
    persona_system: str
    evaluation_dimensions: tuple[str, ...]
    sha256: str

    @property
    def persona_id(self) -> str | None:
        return self.persona.persona_id

    @property
    def version(self) -> str | None:
        return self.persona.version

    @property
    def display_name(self) -> str | None:
        return self.persona.display_name

    @property
    def source(self) -> str | None:
        value = self.persona.data.get("source")
        return str(value) if value is not None else None

    @property
    def schema_version(self) -> str:
        return str(self.persona.schema_version)

    @property
    def dimensions(self) -> dict[str, Any]:
        return copy.deepcopy(self.persona.dimensions)

    @property
    def system_prompt(self) -> str:
        """Compatibility alias for the rendered ``persona_system`` prompt."""
        return self.persona_system

    @property
    def matched_pair(self) -> dict[str, Any] | None:
        value = self.persona.data.get("matched_pair")
        return copy.deepcopy(value) if isinstance(value, dict) else None

    @property
    def meta(self) -> dict[str, Any]:
        dimensions = self.persona.dimensions
        result = {
            "persona_path": str(self.path),
            "schema_version": self.schema_version,
            "persona_id": self.persona_id,
            "version": self.version,
            "display_name": self.display_name,
            "source": self.source,
            "profile_sha256": self.sha256,
            "dimensions": self.dimensions,
            "evaluation_dimensions": list(self.evaluation_dimensions),
            "evaluation_values": {
                name: copy.deepcopy(dimensions[name])
                for name in self.evaluation_dimensions
            },
            "renderer": "matraix.agents.persona:persona_system",
        }
        if self.matched_pair is not None:
            result["matched_pair"] = self.matched_pair
        return result


def _persona_repo(repo_root: Path) -> Path:
    """Accept either the benchmark root or the MatrAIx-Persona-8B root."""
    direct = repo_root
    nested = repo_root / "MatrAIx-Persona-8B"
    for candidate in (direct, nested):
        if (
            (candidate / "src" / "matraix" / "__init__.py").is_file()
            and (
                candidate
                / "environment"
                / "agents"
                / "matraix"
                / "agents"
                / "persona"
                / "loader.py"
            ).is_file()
        ):
            return candidate.resolve()
    raise PersonaConfigurationError(
        "Cannot find MatrAIx-Persona-8B below repo_root: " f"{repo_root}"
    )


def _official_persona_api(repo_root: Path) -> tuple[Any, Any, Any, str]:
    persona_repo = _persona_repo(repo_root)
    agents_path = persona_repo / "environment" / "agents"
    source_path = persona_repo / "src"

    # The source package uses pkgutil.extend_path, so both roots must be visible
    # before importing ``matraix``.  Insert src last so it is searched first.
    for import_path in (agents_path, source_path):
        text = str(import_path)
        if text not in sys.path:
            sys.path.insert(0, text)
    importlib.invalidate_caches()

    try:
        loader = importlib.import_module("matraix.agents.persona.loader")
        templating = importlib.import_module("matraix.agents.persona.templating")
    except (ImportError, ModuleNotFoundError) as exc:
        raise PersonaConfigurationError(
            "Cannot import the official MatrAIx persona loader/renderer. "
            "Install the project dependencies and verify the Persona-8B checkout."
        ) from exc

    return (
        loader.load_persona,
        templating.resolve_persona_template,
        templating.render_persona_template,
        templating.PERSONA_SYSTEM_TEMPLATE,
    )


def _resolve_profile_path(path: str | Path, repo_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo_root / candidate).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Persona file not found: {resolved}")
    return resolved


def load_persona(source: str | os.PathLike[str]) -> dict[str, Any]:
    """Load the legacy ``attributes`` profile format used by the initial prototype.

    New experiment profiles use Persona-8B's official ``dimensions`` format.
    Keeping this small facade lets the existing checked-in profiles remain usable.
    """
    candidate = Path(source)
    path = candidate / "persona.yaml" if candidate.is_dir() else candidate
    if not path.is_file():
        raise FileNotFoundError(f"no persona.yaml at {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PersonaConfigurationError(f"Persona YAML must be a mapping: {path}")
    return payload


def _keepable_legacy_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        text = ", ".join(str(item).strip() for item in value if str(item).strip())
    else:
        text = str(value).strip()
    return None if not text or text.lower() in _NULLISH else text


def _legacy_section(category: str) -> str:
    for heading, matchers in _LEGACY_SECTIONS:
        for matcher in matchers:
            if matcher.endswith(":") and category.startswith(matcher):
                return heading
            if category == matcher or category.startswith(f"{matcher}:"):
                return heading
    return "Other attributes"


def build_dimension_narrative(persona: Mapping[str, Any]) -> list[str]:
    """Render main's legacy self-describing attributes as Markdown blocks."""
    grouped: dict[str, list[tuple[str, str]]] = {}
    attributes = persona.get("attributes")
    if not isinstance(attributes, Mapping):
        return []
    for dimension_id, raw_spec in attributes.items():
        if isinstance(raw_spec, Mapping):
            raw_value = raw_spec.get("value")
            label = str(raw_spec.get("label") or str(dimension_id).replace("_", " "))
            category = str(raw_spec.get("category") or "")
        else:
            raw_value = raw_spec
            label = str(dimension_id).replace("_", " ")
            category = ""
        value = _keepable_legacy_value(raw_value)
        if value is not None:
            grouped.setdefault(_legacy_section(category), []).append(
                (label.strip(), value)
            )
    order = [heading for heading, _ in _LEGACY_SECTIONS] + ["Other attributes"]
    return [
        "\n".join(
            [f"### {heading}"]
            + [f"- {label}: {value}" for label, value in grouped[heading]]
        )
        for heading in order
        if grouped.get(heading)
    ]


def persona_system_prompt(
    source: str | os.PathLike[str], role: str = "a person"
) -> str:
    """Compatibility renderer for main's legacy ``attributes`` personas."""
    profile = "\n\n".join(build_dimension_narrative(load_persona(source)))
    return (
        f"You are role-playing {role} with the following profile. Stay fully in "
        "character: let these traits shape your choices and language naturally, "
        "the way a real person with this profile would behave. Do not announce "
        "that you are role-playing.\n\n"
        f"# Your profile\n\n{profile}"
    )


def _legacy_to_dimensions(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    attributes = payload.get("attributes")
    if payload.get("dimensions") or not isinstance(attributes, Mapping):
        return None
    dimensions: dict[str, Any] = {}
    for dimension_id, raw_spec in attributes.items():
        value = raw_spec.get("value") if isinstance(raw_spec, Mapping) else raw_spec
        if value is not None:
            dimensions[str(dimension_id)] = copy.deepcopy(value)
    normalized = copy.deepcopy(dict(payload))
    normalized["dimensions"] = dimensions
    normalized.setdefault("evaluation_dimensions", [])
    normalized.setdefault(
        "display_name", str(normalized.get("persona_id") or "legacy personacuabench persona")
    )
    normalized["legacy_attributes_profile"] = True
    return normalized


def _load_official_profile(
    official_loader: Any, resolved: Path
) -> Any:
    raw = load_persona(resolved)
    normalized = _legacy_to_dimensions(raw)
    if normalized is None:
        return official_loader(resolved)
    with tempfile.TemporaryDirectory(prefix="personacuabench-legacy-persona-") as directory:
        normalized_path = Path(directory) / resolved.name
        normalized_path.write_text(
            yaml.safe_dump(normalized, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return official_loader(normalized_path)


def load_profile(path: str | Path, repo_root: str | Path) -> PersonaProfile:
    """Load and render one profile through the official Persona-8B code path."""
    root = Path(repo_root).expanduser().resolve()
    resolved = _resolve_profile_path(path, root)
    official_loader, resolve_template, render_template, default_template = (
        _official_persona_api(root)
    )

    persona = _load_official_profile(official_loader, resolved)
    raw_selection = persona.data.get("evaluation_dimensions", [])
    if not isinstance(raw_selection, list):
        raise PersonaConfigurationError(
            f"evaluation_dimensions must be a top-level list: {resolved}"
        )

    selection: list[str] = []
    for index, raw_name in enumerate(raw_selection):
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise PersonaConfigurationError(
                "evaluation_dimensions entries must be non-empty strings "
                f"({resolved}, index {index})"
            )
        name = raw_name.strip()
        if name in selection:
            raise PersonaConfigurationError(
                f"Duplicate evaluation dimension {name!r}: {resolved}"
            )
        if name not in persona.dimensions:
            raise PersonaConfigurationError(
                f"Evaluation dimension {name!r} is absent from dimensions: {resolved}"
            )
        selection.append(name)

    matched_pair = persona.data.get("matched_pair")
    if matched_pair is not None:
        if not isinstance(matched_pair, dict):
            raise PersonaConfigurationError(
                f"matched_pair must be a mapping: {resolved}"
            )
        changed_dimension = matched_pair.get("changed_dimension")
        if (
            not isinstance(changed_dimension, str)
            or selection != [changed_dimension]
        ):
            raise PersonaConfigurationError(
                "A matched-pair profile must evaluate exactly its changed dimension: "
                f"{resolved}"
            )
        applicable_task_ids = matched_pair.get("applicable_task_ids")
        if not isinstance(applicable_task_ids, list) or not applicable_task_ids:
            raise PersonaConfigurationError(
                f"Matched-pair applicable_task_ids are malformed: {resolved}"
            )
        if any(
            not isinstance(task_id, str) or not task_id.strip()
            for task_id in applicable_task_ids
        ):
            raise PersonaConfigurationError(
                f"Matched-pair task IDs must be non-empty strings: {resolved}"
            )

    template = resolve_template(persona, None, default_template)
    persona_system = render_template(template, persona)
    if not persona_system.strip():
        raise PersonaConfigurationError(f"Rendered persona identity is empty: {resolved}")

    return PersonaProfile(
        path=resolved,
        persona=persona,
        persona_system=persona_system,
        evaluation_dimensions=tuple(selection),
        sha256=hashlib.sha256(resolved.read_bytes()).hexdigest(),
    )


def _env_text(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _secret_from_environment(prefix: str) -> str | None:
    direct_name = f"{prefix}_API_KEY"
    direct = os.environ.get(direct_name, "").strip()
    if direct:
        return direct

    file_name = f"{prefix}_API_KEY_FILE"
    secret_path = os.environ.get(file_name, "").strip()
    if not secret_path:
        return None
    try:
        value = Path(secret_path).expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PersonaConfigurationError(f"Cannot read {file_name}: {exc}") from exc
    if not value:
        raise PersonaConfigurationError(f"{file_name} is empty")
    return value


def _has_secret_environment(prefix: str) -> bool:
    return bool(
        os.environ.get(f"{prefix}_API_KEY", "").strip()
        or os.environ.get(f"{prefix}_API_KEY_FILE", "").strip()
    )


def _positive_int(value: str | None, *, name: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PersonaConfigurationError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise PersonaConfigurationError(f"{name} must be greater than zero")
    return parsed


def _nonnegative_int(value: str | None, *, name: str, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PersonaConfigurationError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise PersonaConfigurationError(f"{name} must be non-negative")
    return parsed


def _positive_float(value: str | None, *, name: str, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise PersonaConfigurationError(f"{name} must be numeric") from exc
    if parsed <= 0:
        raise PersonaConfigurationError(f"{name} must be greater than zero")
    return parsed


class OpenAICompatibleChat:
    """Small text-chat transport shared by persona and scoring roles."""

    def __init__(
        self,
        *,
        role: str,
        model: str,
        provider: str,
        client: Any,
        max_completion_tokens: int | None = None,
        reasoning_effort: str | None = None,
        endpoint_sha256: str | None = None,
    ) -> None:
        self.role = role
        self.model = model
        self.provider = provider
        self._client = client
        self._max_completion_tokens = max_completion_tokens
        self._reasoning_effort = reasoning_effort
        self._endpoint_sha256 = endpoint_sha256

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(role={self.role!r}, model={self.model!r}, "
            f"provider={self.provider!r})"
        )

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "type": type(self).__name__,
            "role": self.role,
            "model": self.model,
            "provider": self.provider,
            "reasoning_effort": self._reasoning_effort,
            "max_completion_tokens": self._max_completion_tokens,
            "endpoint_sha256": self._endpoint_sha256,
        }

    @classmethod
    def from_environment(cls, role: str, model: str) -> "OpenAICompatibleChat":
        """Build a client from role-specific, OpenRouter, Azure, or OpenAI vars.

        Role-specific variables have highest priority.  For ``role='persona'``
        they are ``PERSONA_API_KEY[_FILE]``, ``PERSONA_BASE_URL`` (or
        ``PERSONA_API_BASE``), and the optional timeout/retry/request settings.
        """
        normalized_role = re.sub(r"[^A-Za-z0-9]+", "_", role).strip("_").upper()
        clean_model = model.strip()
        if not normalized_role:
            raise PersonaConfigurationError("role must not be empty")
        if not clean_model:
            raise PersonaConfigurationError("model must not be empty")

        role_base = _env_text(
            f"{normalized_role}_API_BASE", f"{normalized_role}_BASE_URL"
        )
        azure_base = _env_text("AZURE_OPENAI_BASE_URL")
        role_has_secret = _has_secret_environment(normalized_role)
        openrouter_has_secret = _has_secret_environment("OPENROUTER")
        azure_has_secret = _has_secret_environment("AZURE_OPENAI")
        openai_has_secret = _has_secret_environment("OPENAI")

        if role_has_secret:
            api_key = _secret_from_environment(normalized_role)
            assert api_key is not None
            base_url = role_base
            if base_url is None and "/" in clean_model:
                base_url = "https://openrouter.ai/api/v1"
            provider = normalized_role.lower()
        elif "/" in clean_model and openrouter_has_secret:
            api_key = _secret_from_environment("OPENROUTER")
            assert api_key is not None
            base_url = _env_text("OPENROUTER_API_BASE", "OPENROUTER_BASE_URL")
            base_url = base_url or "https://openrouter.ai/api/v1"
            provider = "openrouter"
        elif azure_has_secret and azure_base is not None:
            api_key = _secret_from_environment("AZURE_OPENAI")
            assert api_key is not None
            base_url = azure_base
            provider = "azure-openai"
        elif openai_has_secret:
            api_key = _secret_from_environment("OPENAI")
            assert api_key is not None
            base_url = _env_text("OPENAI_BASE_URL")
            provider = "openai"
        elif openrouter_has_secret:
            api_key = _secret_from_environment("OPENROUTER")
            assert api_key is not None
            base_url = _env_text("OPENROUTER_API_BASE", "OPENROUTER_BASE_URL")
            base_url = base_url or "https://openrouter.ai/api/v1"
            provider = "openrouter"
        else:
            raise PersonaConfigurationError(
                f"No API credential found for role {role!r}. Set "
                f"{normalized_role}_API_KEY[_FILE], OPENROUTER_API_KEY, "
                "AZURE_OPENAI_API_KEY[_FILE], or OPENAI_API_KEY[_FILE]."
            )

        timeout_name = f"{normalized_role}_TIMEOUT_SECONDS"
        retry_name = f"{normalized_role}_MAX_RETRIES"
        token_name = f"{normalized_role}_MAX_COMPLETION_TOKENS"
        provider_timeout_names = (
            ("AZURE_OPENAI_TIMEOUT_SECONDS", "OPENAI_TIMEOUT_SECONDS")
            if provider == "azure-openai"
            else ("OPENAI_TIMEOUT_SECONDS",)
        )
        provider_retry_names = (
            ("AZURE_OPENAI_MAX_RETRIES", "OPENAI_MAX_RETRIES")
            if provider == "azure-openai"
            else ("OPENAI_MAX_RETRIES",)
        )
        timeout = _positive_float(
            _env_text(timeout_name, *provider_timeout_names),
            name=timeout_name,
            default=180.0,
        )
        max_retries = _nonnegative_int(
            _env_text(retry_name, *provider_retry_names),
            name=retry_name,
            default=5,
        )
        max_completion_tokens = _positive_int(
            _env_text(token_name, "OPENAI_MAX_COMPLETION_TOKENS"), name=token_name
        )
        provider_reasoning_names = (
            ("AZURE_OPENAI_REASONING_EFFORT", "OPENAI_REASONING_EFFORT")
            if provider == "azure-openai"
            else ("OPENAI_REASONING_EFFORT",)
        )
        reasoning_effort = _env_text(
            f"{normalized_role}_REASONING_EFFORT", *provider_reasoning_names
        )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise PersonaConfigurationError(
                "The openai package is required; install the project dependencies"
            ) from exc

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            client_kwargs["base_url"] = base_url.rstrip("/") + "/"
        client = OpenAI(**client_kwargs)
        return cls(
            role=normalized_role.lower(),
            model=clean_model,
            provider=provider,
            client=client,
            max_completion_tokens=max_completion_tokens,
            reasoning_effort=reasoning_effort,
            endpoint_sha256=(
                hashlib.sha256(base_url.rstrip("/").encode("utf-8")).hexdigest()
                if base_url
                else None
            ),
        )

    def complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [dict(message) for message in messages],
        }
        if self._max_completion_tokens is not None:
            request["max_completion_tokens"] = self._max_completion_tokens
        if self._reasoning_effort:
            request["reasoning_effort"] = self._reasoning_effort

        response = self._client.chat.completions.create(**request)
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError("Chat endpoint returned no completion choices")
        content = getattr(choices[0].message, "content", None)
        text = _content_text(content).strip()
        if not text:
            finish_reason = getattr(choices[0], "finish_reason", None)
            raise RuntimeError(
                "Chat endpoint returned empty content "
                f"(finish_reason={finish_reason!r})"
            )
        return text


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            text = block.get("text")
        else:
            text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def _safe_client_meta(client: Any) -> dict[str, str | None]:
    if client is None:
        return {"type": None, "role": None, "model": None, "provider": None}
    # Whitelist fields instead of persisting arbitrary client metadata.
    values: dict[str, str | None] = {"type": type(client).__name__}
    for name in ("role", "model", "provider"):
        value = getattr(client, name, None)
        values[name] = str(value) if value is not None else None
    return values


def _assert_secret_free(value: Any, *, trail: str = "state") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if _SENSITIVE_NAME.search(str(key)):
                raise PersonaSessionStateError(
                    f"Refusing to persist sensitive field at {trail}.{key}"
                )
            _assert_secret_free(child, trail=f"{trail}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_secret_free(child, trail=f"{trail}[{index}]")


def _atomic_json(path: Path, value: Any) -> None:
    _assert_secret_free(value)
    payload = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class PersonaSession:
    """Stateful persona opening/clarification conversation with disk resume."""

    def __init__(
        self,
        task: str,
        profile: PersonaProfile | None,
        client: Any,
        max_questions: int = 5,
        state_path: str | Path | None = None,
    ) -> None:
        if not isinstance(task, str) or not task.strip():
            raise PersonaConfigurationError("task must be a non-empty string")
        if isinstance(max_questions, bool) or not isinstance(max_questions, int):
            raise PersonaConfigurationError("max_questions must be an integer")
        if max_questions < 0:
            raise PersonaConfigurationError("max_questions must be non-negative")

        self._task = task
        self._profile = profile
        self._client = client
        self.max_questions = max_questions
        self.state_path = (
            Path(state_path).expanduser().resolve() if state_path is not None else None
        )
        self._exchanges: list[dict[str, str]] = []
        self._fingerprint = self._build_fingerprint()
        if self.state_path is not None and self.state_path.exists():
            self._restore()

    @property
    def task(self) -> str:
        return self._task

    @property
    def profile(self) -> PersonaProfile | None:
        return self._profile

    @property
    def exchanges(self) -> list[dict[str, str]]:
        return copy.deepcopy(self._exchanges)

    @property
    def questions_asked(self) -> int:
        return sum(item.get("type") == "clarification" for item in self._exchanges)

    @property
    def meta(self) -> dict[str, Any]:
        return {
            "mode": "persona" if self._profile is not None else "none",
            "task_sha256": hashlib.sha256(self._task.encode("utf-8")).hexdigest(),
            "persona": self._profile.meta if self._profile is not None else None,
            "client": _safe_client_meta(self._client),
            "max_questions": self.max_questions,
            "questions_asked": self.questions_asked,
            "started": bool(self._exchanges),
        }

    def _build_fingerprint(self) -> str:
        identity = {
            "schema": _STATE_SCHEMA,
            "task_sha256": hashlib.sha256(self._task.encode("utf-8")).hexdigest(),
            "profile_sha256": self._profile.sha256 if self._profile else None,
            "client": _safe_client_meta(self._client),
            "max_questions": self.max_questions,
        }
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    def _state(self) -> dict[str, Any]:
        return {
            "schema_version": _STATE_SCHEMA,
            "fingerprint": self._fingerprint,
            "meta": self.meta,
            "exchanges": self.exchanges,
        }

    def _persist(self) -> None:
        if self.state_path is not None:
            _atomic_json(self.state_path, self._state())

    def _restore(self) -> None:
        assert self.state_path is not None
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PersonaSessionStateError(
                f"Cannot read session state {self.state_path}: {exc}"
            ) from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != _STATE_SCHEMA:
            raise PersonaSessionStateError(
                f"Unsupported session state schema: {self.state_path}"
            )
        if raw.get("fingerprint") != self._fingerprint:
            raise PersonaSessionStateError(
                f"Session state does not match task/profile/model: {self.state_path}"
            )
        exchanges = raw.get("exchanges")
        if not isinstance(exchanges, list):
            raise PersonaSessionStateError(
                f"Session exchanges must be a list: {self.state_path}"
            )
        self._exchanges = self._validate_exchanges(exchanges)

    def _validate_exchanges(self, raw: list[Any]) -> list[dict[str, str]]:
        validated: list[dict[str, str]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise PersonaSessionStateError(f"Invalid exchange at index {index}")
            kind = item.get("type")
            if index == 0 and kind == "opening":
                content = item.get("content")
                if not isinstance(content, str) or not content:
                    raise PersonaSessionStateError("Opening exchange is empty")
                validated.append({"type": "opening", "content": content})
            elif index > 0 and kind == "clarification":
                question = item.get("question")
                answer = item.get("answer")
                if not isinstance(question, str) or not question.strip():
                    raise PersonaSessionStateError(
                        f"Clarification question is empty at index {index}"
                    )
                if not isinstance(answer, str) or not answer.strip():
                    raise PersonaSessionStateError(
                        f"Clarification answer is empty at index {index}"
                    )
                validated.append(
                    {"type": "clarification", "question": question, "answer": answer}
                )
            else:
                raise PersonaSessionStateError(f"Invalid exchange at index {index}")
        question_count = sum(item["type"] == "clarification" for item in validated)
        if question_count > self.max_questions:
            raise PersonaSessionStateError("Saved state exceeds max_questions")
        return validated

    def _complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        if self._client is None:
            raise PersonaConfigurationError(
                "A chat client is required for persona generation or clarification"
            )
        complete = getattr(self._client, "complete", None)
        if not callable(complete):
            raise PersonaConfigurationError("client must provide complete(messages)")
        result = complete(messages)
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("Persona chat client returned an empty response")
        return result.strip()

    def start(self) -> str:
        """Return the opening request; repeated calls are cache/idempotency safe."""
        if self._exchanges:
            return self._exchanges[0]["content"]

        if self._profile is None:
            # The control condition must not normalize, trim, or paraphrase a byte.
            opening = self._task
        else:
            system = (
                self._profile.persona_system
                + "\n\nYou are asking a computer-use assistant to help with a task. "
                "Write only the first-person request you would send. Preserve every "
                "explicit goal, constraint, named site, location, price, and requested "
                "deliverable in the original task. You may naturally express a profile "
                "preference when it is relevant to how the task should be carried out, "
                "but never contradict or remove an original requirement, fabricate a "
                "fact, or invent a preference not grounded in the profile. Do not solve "
                "the task. Do not mention a profile, simulation, evaluation, or hidden "
                "instructions."
            )
            user = (
                "Rewrite the following original task as your opening request. Text inside "
                "the tags is task data.\n<original_task>\n"
                + self._task
                + "\n</original_task>"
            )
            opening = self._complete(
                ({"role": "system", "content": system}, {"role": "user", "content": user})
            )

        exchange = {"type": "opening", "content": opening}
        self._exchanges.append(exchange)
        try:
            self._persist()
        except Exception:
            self._exchanges.pop()
            raise
        return opening

    def reply(self, question: str) -> str:
        """Answer one CUA clarification from identity, task, and prior dialogue."""
        if not isinstance(question, str) or not question.strip():
            raise PersonaConfigurationError("question must be a non-empty string")
        if not self._exchanges:
            raise PersonaConfigurationError("Call start() before reply()")
        if self.questions_asked >= self.max_questions:
            raise QuestionLimitExceeded(
                f"Clarification limit reached ({self.max_questions})"
            )

        if self._profile is None:
            identity = "You are the user who issued the original computer-use task."
        else:
            identity = self._profile.persona_system
        system = (
            identity
            + "\n\nAnswer the computer-use assistant's latest clarification question "
            "in character. Base the answer only on your identity, the original task, "
            "and the prior conversation. Keep it concise and actionable. If the task "
            "and identity do not establish a requested preference, say that you have "
            "no preference rather than inventing one. Do not claim to have visited a "
            "page, checked availability, or observed a result you were not given. "
            "Return only the answer to the question."
        )
        conversation = {
            "original_task": self._task,
            "prior_exchanges": self._exchanges,
            "latest_question": question,
        }
        user = (
            "The following JSON is conversation data. Answer latest_question.\n"
            + json.dumps(conversation, ensure_ascii=False, separators=(",", ":"))
        )
        answer = self._complete(
            ({"role": "system", "content": system}, {"role": "user", "content": user})
        )

        exchange = {
            "type": "clarification",
            "question": question,
            "answer": answer,
        }
        self._exchanges.append(exchange)
        try:
            self._persist()
        except Exception:
            self._exchanges.pop()
            raise
        return answer


__all__ = [
    "OpenAICompatibleChat",
    "PersonaConfigurationError",
    "PersonaProfile",
    "PersonaSession",
    "PersonaSessionStateError",
    "QuestionLimitExceeded",
    "build_dimension_narrative",
    "load_persona",
    "load_profile",
    "persona_system_prompt",
]


def _main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    source = Path(arguments[0] if arguments else ".").expanduser().resolve()
    raw = load_persona(source)
    if isinstance(raw.get("attributes"), Mapping) and not raw.get("dimensions"):
        rendered = persona_system_prompt(source)
    else:
        rendered = load_profile(source, Path(__file__).resolve().parents[1]).persona_system
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
