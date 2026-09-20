"""Load versioned prompt assets shipped with PersonaCUABench."""

from __future__ import annotations

import re
from pathlib import Path

from personacuabench.core import ConfigurationError


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_NAMES = frozenset(
    {
        "agent",
        "experience_judge",
        "persona_user",
        "rubric_judge",
    }
)


def prompt_path(name: str) -> Path:
    """Return the packaged path for a known prompt name."""
    if name not in PROMPT_NAMES:
        choices = ", ".join(sorted(PROMPT_NAMES))
        raise ConfigurationError(f"Unknown prompt {name!r}; expected one of: {choices}")
    return PROMPTS_DIR / f"{name}.md"


def load_prompt(name: str) -> str:
    """Read a prompt and remove its non-model-facing leading HTML comment."""
    path = prompt_path(name)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Cannot read prompt asset {path}: {exc}") from exc
    prompt = re.sub(r"\A<!--.*?-->\s*", "", text, flags=re.DOTALL).strip()
    if not prompt:
        raise ConfigurationError(f"Prompt asset is empty: {path}")
    return prompt
