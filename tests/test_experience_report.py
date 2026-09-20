from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from personacuabench.detailed_report import render_report
from personacuabench.report import parse_result


DIMENSIONS = (
    "P1_asked_for",
    "P2_readable_for_them",
    "P3_actionable",
    "P4_gap_handling",
    "P5_overall",
)


def _judge(model: str, scores: tuple[object, ...], prefix: str) -> dict[str, object]:
    payload: dict[str, object] = {"model": model}
    for dimension, score in zip(DIMENSIONS, scores, strict=True):
        payload[dimension] = {
            "score": score,
            "reason": f"{prefix} evidence for {dimension}",
        }
    payload["unmet_requests"] = [f"{prefix} unmet request"]
    payload["missed_gaps"] = [f"{prefix} missed gap"]
    payload["judge_confidence"] = 0.8
    return payload


def _result() -> dict[str, object]:
    return {
        "schema_version": "2",
        "status": "complete",
        "task_id": "task-fixture",
        "task": {
            "task_id": "task-fixture",
            "confirmed_task": "Find one option.",
            "rubrics": [],
        },
        "persona": "fixture-persona",
        "run": {},
        "judgement": {
            "status": "complete",
            "score_raw": 0.8,
            "score_availability_adjusted": 1.0,
        },
    }


class ExperienceSummaryReportTests(unittest.TestCase):
    def _parse(self, payload: dict[str, object]):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "task-fixture" / "fixture-persona__run"
            run_dir.mkdir(parents=True)
            path = run_dir / "result.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return parse_result(
                path,
                root,
                {"task-fixture": 1},
                {1: "task-fixture"},
            )

    def test_current_schema_keeps_two_scores_separate(self) -> None:
        payload = _result()
        payload["experience"] = {
            "schema_version": "1",
            "status": "complete",
            "judge_a": _judge("judge-a", (5, 4, 3, "n/a", 4), "A"),
            "judge_b": _judge("judge-b", (4, 4, 2, "n/a", 3), "B"),
            "agreement": {
                "P1_asked_for": {"delta": 1, "within_one": True},
                "P3_actionable": {"delta": 1, "within_one": True},
            },
        }

        row = self._parse(payload)

        self.assertEqual(row.task_score, "0.8")
        self.assertEqual(row.adjusted_task_score, "1")
        self.assertEqual(row.experience_status, "complete")
        self.assertEqual(row.experience_p1, "A=5; B=4; within1=yes")
        self.assertEqual(row.experience_p2, "A=4; B=4")
        self.assertEqual(row.experience_p3, "A=3; B=2; within1=yes")
        self.assertEqual(row.experience_p4, "A=n/a; B=n/a")
        self.assertEqual(row.experience_p5, "A=4; B=3")

    def test_legacy_a_b_schema_is_supported(self) -> None:
        payload = _result()
        payload["experience"] = {
            "a": _judge("legacy-a", (1, 2, 3, 4, 5), "A"),
            "b": _judge("legacy-b", (3, 2, 3, 4, 5), "B"),
            "agreement": {
                "P1_asked_for": {"delta": -2, "within_one": False}
            },
        }

        row = self._parse(payload)

        self.assertEqual(row.experience_status, "complete")
        self.assertEqual(row.experience_p1, "A=1; B=3; within1=no")

    def test_result_without_experience_remains_reportable(self) -> None:
        payload = _result()
        row = self._parse(payload)

        self.assertEqual(row.experience_status, "—")
        self.assertEqual(row.experience_p1, "—")
        report = render_report(payload, Path("/tmp/run/result.json"))
        self.assertIn("Persona experience (P1–P5)", report)
        self.assertIn("Not run:", report)


class ExperienceDetailedReportTests(unittest.TestCase):
    def test_detailed_report_shows_reasons_lists_and_agreement(self) -> None:
        payload = _result()
        payload["experience"] = {
            "schema_version": "1",
            "status": "complete",
            "prompt": {"template_sha256": "a" * 64},
            "judge_a": {
                "model": "judge-a",
                "verdict": _judge("ignored-inner-model", (5, 4, 3, 2, 4), "A"),
            },
            "judge_b": _judge("judge-b", (4, 3, 3, 2, 3), "B"),
            "agreement": {
                "dimensions": {
                    "P1_asked_for": {"delta": 1, "within_one": True}
                },
                "comparable_dimensions": 5,
                "within_one_dimensions": 5,
                "within_one_rate": 1.0,
            },
        }

        report = render_report(payload, Path("/tmp/run/result.json"))

        self.assertIn("Persona experience (P1–P5)", report)
        self.assertIn(r"Judge A model:** judge\-a", report)
        self.assertIn(r"Judge B model:** judge\-b", report)
        self.assertIn("Judge A score:** 5", report)
        self.assertIn("Judge B score:** 4", report)
        self.assertIn(r"A evidence for P1\_asked\_for", report)
        self.assertIn("Within one point:** Yes", report)
        self.assertIn("A unmet request", report)
        self.assertIn("B missed gap", report)
        self.assertIn("Comparable dimensions:** 5", report)
        self.assertIn("Dimensions within one point:** 5", report)
        self.assertIn("must not be averaged", report)
        self.assertIn(r"Task score (raw / official):** 0\.8000 \(80\.0%\)", report)


if __name__ == "__main__":
    unittest.main()
