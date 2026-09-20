#!/usr/bin/env python3
"""Generate three synthetic, smoke-only MatrAIx persona profiles.

These profiles exercise wiring and observable interaction differences.  They
are intentionally not research samples and must not be treated as population
representations.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

import yaml


PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "personas"
DEFAULT_SCHEMA_PATH = PACKAGE_DIR / "dimensions.json"

# Every smoke profile supplies every selected dimension.  Keep this list small
# and purposeful: it spans shopping priorities, interaction style, context,
# and enough identity background to produce visibly different conversations.
DIMENSIONS: tuple[str, ...] = (
    "age_bracket",
    "region",
    "life_stage",
    "tech_savviness",
    "risk_tolerance",
    "decision_style",
    "emotional_state",
    "intent",
    "query_complexity",
    "expertise_gap",
    "tone_expected",
    "trust_level",
    "time_pressure",
    "device_context",
    "modality_pref",
    "accessibility_needs",
    "economic_motivation",
    "cog_directness",
    "cog_detail_orientation",
    "need_for_cognition",
)

# Only behaviorally observable dimensions belong in the evaluation selection.
# Background demographics still shape the official persona rendering, but are
# not targets for judging whether the simulated user stayed in character.
EVALUATION_DIMENSIONS: tuple[str, ...] = (
    "tech_savviness",
    "risk_tolerance",
    "decision_style",
    "tone_expected",
    "trust_level",
    "time_pressure",
    "device_context",
    "modality_pref",
    "accessibility_needs",
    "economic_motivation",
    "cog_directness",
    "cog_detail_orientation",
    "need_for_cognition",
)

PROFILES: dict[str, dict[str, Any]] = {
    "smoke_budget_mobile": {
        "persona_id": "smoke-budget-mobile",
        "display_name": "Smoke example — budget-conscious mobile parent",
        "description": (
            "Synthetic smoke-only profile: a time-pressed shopper who wants concise, "
            "verifiable and cost-conscious help on a phone."
        ),
        "dimensions": {
            "age_bracket": "35-44",
            "region": "North America",
            "life_stage": "Parent of young kids",
            "tech_savviness": "Comfortable",
            "risk_tolerance": "Cautious",
            "decision_style": "Consensus-driven",
            "emotional_state": "Urgent",
            "intent": "Get task done",
            "query_complexity": "Multi-step",
            "expertise_gap": "Novice asking expert",
            "tone_expected": "Concise",
            "trust_level": "Verifying",
            "time_pressure": "Deadline",
            "device_context": "Mobile, on-the-go",
            "modality_pref": "Step-by-step",
            "accessibility_needs": "None",
            "economic_motivation": "Cost-sensitive",
            "cog_directness": "Direct",
            "cog_detail_orientation": "Moderate",
            "need_for_cognition": "Average",
        },
    },
    "smoke_verification_researcher": {
        "persona_id": "smoke-verification-researcher",
        "display_name": "Smoke example — deliberate verification shopper",
        "description": (
            "Synthetic smoke-only profile: a patient desktop researcher who wants a "
            "detailed comparison and independently checkable evidence."
        ),
        "dimensions": {
            "age_bracket": "45-54",
            "region": "North America",
            "life_stage": "Mid-life",
            "tech_savviness": "Digital native",
            "risk_tolerance": "Risk-averse",
            "decision_style": "Analytical",
            "emotional_state": "Curious",
            "intent": "Verify a claim",
            "query_complexity": "Multi-step",
            "expertise_gap": "Peer-level",
            "tone_expected": "Detailed",
            "trust_level": "Skeptical",
            "time_pressure": "No rush",
            "device_context": "Desktop, focused",
            "modality_pref": "Tabular",
            "accessibility_needs": "None",
            "economic_motivation": "Value-driven",
            "cog_directness": "Balanced",
            "cog_detail_orientation": "Very high",
            "need_for_cognition": "Very high",
        },
    },
    "smoke_accessible_premium": {
        "persona_id": "smoke-accessible-premium",
        "display_name": "Smoke example — accessibility-first premium shopper",
        "description": (
            "Synthetic smoke-only profile: an older, cautious shopper who values ease "
            "of use, visual guidance and accessibility more than the lowest price."
        ),
        "dimensions": {
            "age_bracket": "65-74",
            "region": "North America",
            "life_stage": "Retirement",
            "tech_savviness": "Cautious adopter",
            "risk_tolerance": "Risk-averse",
            "decision_style": "Deliberative",
            "emotional_state": "Anxious",
            "intent": "Decide",
            "query_complexity": "Ambiguous / underspecified",
            "expertise_gap": "Novice asking expert",
            "tone_expected": "Warm / empathetic",
            "trust_level": "Trusting",
            "time_pressure": "Moderate",
            "device_context": "Accessibility tool",
            "modality_pref": "Visual / diagram",
            "accessibility_needs": "Motor",
            "economic_motivation": "Premium-seeking",
            "cog_directness": "Indirect",
            "cog_detail_orientation": "High",
            "need_for_cognition": "Average",
        },
    },
}


HEADER = """# SMOKE EXAMPLE ONLY — synthetic fixture, not a population sample.
# Generated by personacuabench.make_personas from the official Persona-8B schema.
"""


class ProfileDefinitionError(ValueError):
    """Raised when a generated profile disagrees with the official catalog."""


def _load_catalog(path: Path) -> dict[str, set[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileDefinitionError(f"Dimension schema not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileDefinitionError(f"Invalid dimension schema {path}: {exc}") from exc
    rows = payload.get("dimensions") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ProfileDefinitionError(f"Schema has no dimensions list: {path}")
    catalog: dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        values = row.get("values")
        if not isinstance(values, list):
            continue
        catalog[str(row["id"])] = {str(value) for value in values}
    return catalog


def _profile_payload(name: str, definition: dict[str, Any]) -> dict[str, Any]:
    dimensions = definition["dimensions"]
    return {
        "persona_id": definition["persona_id"],
        "version": "1.0",
        "source": "synthetic:smoke-example",
        "display_name": definition["display_name"],
        "smoke_example": True,
        "description": definition["description"],
        # This is intentionally top-level so a scoring adapter need not infer it
        # from the full dimension map.
        "evaluation_dimensions": list(EVALUATION_DIMENSIONS),
        "dimensions": {dimension: dimensions[dimension] for dimension in DIMENSIONS},
    }


def validate_profiles(catalog: dict[str, set[str]]) -> None:
    missing_catalog = [dimension for dimension in DIMENSIONS if dimension not in catalog]
    if missing_catalog:
        raise ProfileDefinitionError(
            "Unknown DIMENSIONS entries: " + ", ".join(missing_catalog)
        )
    if not EVALUATION_DIMENSIONS:
        raise ProfileDefinitionError("EVALUATION_DIMENSIONS must not be empty")
    if len(set(EVALUATION_DIMENSIONS)) != len(EVALUATION_DIMENSIONS):
        raise ProfileDefinitionError("EVALUATION_DIMENSIONS contains duplicates")
    evaluation_unknown = [
        dimension
        for dimension in EVALUATION_DIMENSIONS
        if dimension not in DIMENSIONS
    ]
    if evaluation_unknown:
        raise ProfileDefinitionError(
            "Evaluation entries absent from DIMENSIONS: "
            + ", ".join(evaluation_unknown)
        )

    expected = set(DIMENSIONS)
    persona_ids: set[str] = set()
    for name, definition in PROFILES.items():
        persona_id = definition.get("persona_id")
        if not isinstance(persona_id, str) or not persona_id:
            raise ProfileDefinitionError(f"{name}: persona_id must be non-empty")
        if persona_id in persona_ids:
            raise ProfileDefinitionError(f"Duplicate persona_id: {persona_id}")
        persona_ids.add(persona_id)

        dimensions = definition.get("dimensions")
        if not isinstance(dimensions, dict):
            raise ProfileDefinitionError(f"{name}: dimensions must be a mapping")
        actual = set(dimensions)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ProfileDefinitionError(
                f"{name}: dimension coverage mismatch; missing={missing}, extra={extra}"
            )
        for dimension, value in dimensions.items():
            allowed = catalog[dimension]
            if value not in allowed:
                raise ProfileDefinitionError(
                    f"{name}: invalid {dimension}={value!r}; "
                    f"choose one of {sorted(allowed)!r}"
                )


def _render(payload: dict[str, Any]) -> str:
    body = yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return HEADER + body


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def generate(output_dir: Path, *, check: bool) -> list[Path]:
    paths: list[Path] = []
    mismatches: list[Path] = []
    for name, definition in PROFILES.items():
        path = output_dir / f"{name}.yaml"
        expected = _profile_payload(name, definition)
        paths.append(path)
        if check:
            try:
                actual = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, yaml.YAMLError):
                mismatches.append(path)
                continue
            if actual != expected:
                mismatches.append(path)
        else:
            _atomic_write(path, _render(expected))
    if mismatches:
        joined = "\n  ".join(str(path) for path in mismatches)
        raise ProfileDefinitionError(
            "Generated smoke profiles are missing or stale:\n  " + joined
        )
    return paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=f"official dimensions.json (default: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate definitions and confirm checked-in YAML is current",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    catalog = _load_catalog(args.schema.expanduser().resolve())
    validate_profiles(catalog)
    paths = generate(args.output_dir.expanduser().resolve(), check=args.check)
    verb = "checked" if args.check else "wrote"
    for path in paths:
        print(f"{verb}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
