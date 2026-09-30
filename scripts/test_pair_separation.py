"""Offline self-check for pair_separation.py. No network, no API keys.

    python scripts/test_pair_separation.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# This test lives in scripts/; the code it exercises lives in src/.
REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import pair_separation as ps  # noqa: E402


def record(arm: str, *, score: int = 2, contradicted: bool = False,
           communicated: int = 6, total: int = 6, status: str = "complete",
           targets: int = 1, axis: str = "price_orientation") -> dict:
    target = {"attribute": "economic_motivation", "score": score,
              "expressed": score == 2 and not contradicted,
              "contradicted": contradicted, "evidence": f"{arm} quote"}
    return {
        "task_id": "b21a86441ddc000000000000000000000000dead",
        "suite_id": "main-original", "replicate_id": "r1",
        "run": {"user": {"persona_profile": {"matched_pair": {
            "axis_id": axis, "arm": arm, "target_value": "Cost-sensitive"}}}},
        "persona_fidelity": {
            "status": status, "targets": [target] * targets,
            "communication_guardrail": {"applicable": True,
                                        "passed": communicated == total,
                                        "communicated": communicated,
                                        "expected_total": total}},
    }


def pair(**overrides) -> dict:
    """A pair with per-arm overrides: pair(negative={"score": 1})."""
    return {arm: ps.arm_record(record(arm, **overrides.get(arm, {})))
            for arm in ps.ARMS}


def main() -> None:
    assert ps.classify(pair())[0] == "separated_pending_evidence_review"
    assert ps.classify(pair(negative={"score": 1}))[0] == "not_separated"
    assert ps.classify(pair(positive={"score": 0, "contradicted": True}))[0] == "not_separated"
    # A guardrail failure invalidates the pair even when both arms scored 2.
    assert ps.classify(pair(negative={"communicated": 4}))[0] == "invalid"
    assert ps.classify(pair(positive={"status": "error"}))[0] == "invalid"
    assert ps.classify(pair(positive={"targets": 2}))[0] == "invalid"
    assert ps.classify({"positive": ps.arm_record(record("positive"))})[0] == "incomplete"

    # A run without a matched-pair profile or without a fidelity verdict is
    # ignored rather than paired.
    plain = record("positive")
    plain["run"]["user"]["persona_profile"] = {}
    assert ps.arm_record(plain) is None
    unjudged = record("positive")
    del unjudged["persona_fidelity"]
    assert ps.arm_record(unjudged) is None

    # End to end over a results tree, including the _-prefixed archive skip.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for arm in ps.ARMS:
            out = root / "task" / f"{arm}__model__stamp"
            out.mkdir(parents=True)
            (out / "result.json").write_text(json.dumps(record(arm)), encoding="utf-8")
        archived = root / "_v1" / "old"
        archived.mkdir(parents=True)
        (archived / "result.json").write_text(
            json.dumps(record("positive", axis="ignored_axis")), encoding="utf-8")
        out = subprocess.run([sys.executable, str(SRC / "pair_separation.py"), str(root),
                              "--evidence"], capture_output=True, text=True, check=True).stdout
        assert "separated_pending_evidence_review" in out, out
        assert "ignored_axis" not in out, out
        assert "positive quote" in out and "negative quote" in out, out

    print("pair separation self-check OK")


if __name__ == "__main__":
    main()
