"""Offline tests for the optional two-judge person-experience phase."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from personacuabench.experience_judge import (
    DIMENSIONS,
    ExperienceJudgeError,
    _commit_experience,
    agreement,
    assemble_experience,
    build_prompt,
    main,
    validate_judge_output,
)
from personacuabench.judge import JudgeConfigurationError, RunArtifacts


def _payload(*, base_score: int = 4, p4: int | str = "n/a") -> dict:
    scores: dict[str, int | str] = {
        "P1_asked_for": base_score,
        "P2_readable_for_them": base_score,
        "P3_actionable": base_score,
        "P4_gap_handling": p4,
        "P5_overall": base_score,
    }
    return {
        dimension: {
            "score": scores[dimension],
            "reason": f"Evidence for {dimension}.",
        }
        for dimension in DIMENSIONS
    } | {
        "unmet_requests": ["show me the product page"],
        "missed_gaps": [],
        "judge_confidence": 0.8,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifacts(root: Path) -> RunArtifacts:
    run_dir = root / "persona__model__run"
    run_dir.mkdir(parents=True)
    result_path = run_dir / "result.json"
    result = {
        "status": "agent_complete",
        "task_id": "1" * 40,
        "run": {
            "open_tabs": [
                {"title": "A product", "url": "https://shop.example/item"}
            ]
        },
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    trajectory_path = run_dir / "traj.jsonl"
    trajectory_path.write_text('{"step_num": 1, "action": "click"}\n', encoding="utf-8")
    conversation_path = run_dir / "conversation.jsonl"
    conversation_path.write_text(
        '{"role": "user", "content": "Please keep it concise."}\n'
        '{"role": "assistant", "content": "Here is the result."}\n',
        encoding="utf-8",
    )
    screenshot = run_dir / "step_1.png"
    screenshot.write_bytes(b"offline-png")
    manifest = {
        "traj.jsonl": _sha256(trajectory_path),
        "conversation.jsonl": _sha256(conversation_path),
        "step_1.png": _sha256(screenshot),
    }
    return RunArtifacts(
        result_path=result_path,
        result=result,
        source_result_sha256=_sha256(result_path),
        run_dir=run_dir,
        task={
            "task_id": "1" * 40,
            "confirmed_task": "Find a green evening dress and open its page.",
            "rubrics": {"R1": {"requirement": "Find one dress"}},
        },
        persona_name="concise-shopper",
        persona_mode="persona",
        persona_meta={
            "persona_id": "concise-shopper",
            "display_name": "Concise shopper",
            "persona_path": "/Users/example/private/persona.yaml",
            "profile_sha256": "a" * 64,
            "renderer": "private.renderer:name",
            "evaluation_dimensions": ["tone_expected"],
            "dimensions": {"tone_expected": "Concise"},
        },
        trajectory_path=trajectory_path,
        trajectory=[{"step_num": 1, "action": "click"}],
        conversation_path=conversation_path,
        conversation=[
            {"role": "user", "content": "Please keep it concise."},
            {"role": "assistant", "content": "Here is the result."},
        ],
        screenshots=[screenshot],
        network_preflight_path=None,
        network_preflight=None,
        network_preflight_integrity_status="absent",
        source_artifact_sha256=manifest,
        action_history="STEP 1: action=click",
        final_answer="One green dress is ready to order.",
    )


class ExperienceOutputValidationTests(unittest.TestCase):
    def test_accepts_exact_fenced_json_and_na(self) -> None:
        payload = _payload()
        parsed = validate_judge_output(
            "```json\n" + json.dumps(payload) + "\n```"
        )
        self.assertEqual(parsed["P4_gap_handling"]["score"], "n/a")
        self.assertEqual(parsed["judge_confidence"], 0.8)

    def test_rejects_extra_keys_and_fractional_scores(self) -> None:
        extra = _payload()
        extra["average"] = 4
        with self.assertRaisesRegex(ExperienceJudgeError, "unexpected average"):
            validate_judge_output(extra)

        floating = _payload()
        floating["P1_asked_for"]["score"] = 4.5
        with self.assertRaisesRegex(ExperienceJudgeError, "integer 1-5"):
            validate_judge_output(floating)

        integral_float = _payload()
        integral_float["P1_asked_for"]["score"] = 4.0
        self.assertEqual(
            validate_judge_output(integral_float)["P1_asked_for"]["score"], 4
        )

        boolean_confidence = _payload()
        boolean_confidence["judge_confidence"] = True
        with self.assertRaisesRegex(ExperienceJudgeError, "finite number"):
            validate_judge_output(boolean_confidence)


class ExperienceJudgePipelineTests(unittest.TestCase):
    def test_prompt_and_two_independent_non_averaged_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = _artifacts(Path(temporary))
            prompt = build_prompt(artifacts)
            self.assertIn("concise-shopper", prompt)
            self.assertIn("Please keep it concise.", prompt)
            self.assertIn("https://shop.example/item", prompt)
            self.assertIn("One green dress is ready to order.", prompt)
            self.assertNotIn("<!--", prompt)
            self.assertNotIn("/Users/example", prompt)
            self.assertNotIn("profile_sha256", prompt)
            self.assertNotIn("private.renderer", prompt)

            calls_a: list[tuple[str, str, list[Path]]] = []
            calls_b: list[tuple[str, str, list[Path]]] = []
            responses_a = ["not JSON", json.dumps(_payload(base_score=4))]
            responses_b = [json.dumps(_payload(base_score=2, p4="n/a"))]

            def judge_a(system: str, user: str, images: list[Path]) -> str:
                calls_a.append((system, user, images))
                return responses_a.pop(0)

            def judge_b(system: str, user: str, images: list[Path]) -> str:
                calls_b.append((system, user, images))
                return responses_b.pop(0)

            result = assemble_experience(
                artifacts=artifacts,
                judge_a=judge_a,
                judge_b=judge_b,
                endpoint_a={"model": "judge-a", "provider": "offline"},
                endpoint_b={"model": "judge-b", "provider": "offline"},
            )

            self.assertEqual(len(calls_a), 2, "invalid A output should be retried")
            self.assertEqual(len(calls_b), 1)
            self.assertTrue(all(call[2] == [] for call in calls_a + calls_b))
            self.assertEqual(result["judge_a"]["validation_attempts"], 2)
            self.assertEqual(result["judge_b"]["validation_attempts"], 1)
            self.assertEqual(result["judge_a"]["P1_asked_for"]["score"], 4)
            self.assertEqual(result["judge_b"]["P1_asked_for"]["score"], 2)
            self.assertFalse(result["protocol"]["scores_averaged"])
            self.assertEqual(result["agreement"]["P1_asked_for"]["delta"], 2)
            self.assertFalse(result["agreement"]["P1_asked_for"]["within_one"])
            self.assertIsNone(result["agreement"]["P4_gap_handling"]["delta"])
            for forbidden in ("average", "mean", "combined_score"):
                self.assertNotIn(forbidden, result)

    def test_agreement_counts_only_comparable_dimensions(self) -> None:
        a = _payload(base_score=5, p4="n/a")
        b = _payload(base_score=4, p4=2)
        compared = agreement(a, b)
        self.assertEqual(compared["comparable_dimensions"], 4)
        self.assertEqual(compared["within_one_dimensions"], 4)
        self.assertEqual(compared["within_one_rate"], 1.0)
        self.assertIsNone(compared["P4_gap_handling"]["within_one"])
        self.assertFalse(compared["scores_averaged"])

    def test_commit_is_atomic_additive_and_rejects_a_changed_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = _artifacts(Path(temporary))
            experience = {
                "schema_version": "persona-cua-experience.v1",
                "status": "complete",
            }
            _commit_experience(artifacts, experience)
            written = json.loads(artifacts.result_path.read_text(encoding="utf-8"))
            self.assertEqual(written["status"], "agent_complete")
            self.assertEqual(written["experience"], experience)

            stale = _artifacts(Path(temporary) / "other")
            changed = copy.deepcopy(stale.result)
            changed["concurrent_change"] = True
            stale.result_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ExperienceJudgeError, "changed while"):
                _commit_experience(stale, experience)
            self.assertNotIn(
                "experience",
                json.loads(stale.result_path.read_text(encoding="utf-8")),
            )

    def test_offline_cli_makes_no_endpoint_call_and_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = _artifacts(Path(temporary))
            before = artifacts.result_path.read_bytes()
            stdout = io.StringIO()
            with (
                mock.patch(
                    "personacuabench.experience_judge.load_run_artifacts",
                    return_value=artifacts,
                ),
                mock.patch(
                    "personacuabench.experience_judge.endpoint_from_environment",
                    side_effect=AssertionError("offline mode requested an endpoint"),
                ),
                mock.patch(
                    "personacuabench.experience_judge.OpenAIJudgeCall",
                    side_effect=AssertionError("offline mode created a judge"),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                self.assertEqual(main([str(artifacts.result_path), "--offline"]), 0)
            preview = json.loads(stdout.getvalue())
            self.assertTrue(preview["offline"])
            self.assertEqual(preview["api_calls_made"], 0)
            self.assertEqual(preview["result_writes"], 0)
            self.assertEqual(preview["evidence"]["screenshots_sent"], 0)
            self.assertEqual(artifacts.result_path.read_bytes(), before)

    def test_results_scan_skips_ineligible_runs_but_explicit_run_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = _artifacts(root)
            bad = root / "bad" / "result.json"
            good = artifacts.result_path
            error = JudgeConfigurationError("run status is failed")

            with (
                mock.patch(
                    "personacuabench.experience_judge._result_paths",
                    return_value=[bad, good],
                ),
                mock.patch(
                    "personacuabench.experience_judge.load_run_artifacts",
                    side_effect=[error, artifacts],
                ),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
            ):
                self.assertEqual(main(["--results", str(root), "--offline"]), 0)
            self.assertIn("Skipping ineligible result", stderr.getvalue())

            with (
                mock.patch(
                    "personacuabench.experience_judge._result_paths",
                    return_value=[bad],
                ),
                mock.patch(
                    "personacuabench.experience_judge.load_run_artifacts",
                    side_effect=error,
                ),
                self.assertRaises(JudgeConfigurationError),
            ):
                main([str(bad), "--offline"])


if __name__ == "__main__":
    unittest.main()
