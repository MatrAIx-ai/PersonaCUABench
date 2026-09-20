#!/usr/bin/env python3
"""Pure-offline self-test for the PersonaCUABench pipeline.

This file intentionally uses only fake model, agent, environment, and judge
objects.  It never creates a real ``DesktopEnv`` and never makes a network
request, so it is safe to run before spending a VM or model call.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from personacuabench.core import (  # noqa: E402
    DEFAULT_ODYSSEYS_DIR,
    DEFAULT_OSWORLD_DIR,
    DEFAULT_PERSONA8B_DIR,
    load_task_config,
    load_tasks,
)
from personacuabench.evaluation import (  # noqa: E402
    compute_availability_adjustment,
    EvaluationError,
    evaluate_adherence,
    evaluate_alignment,
    evaluate_communication,
    merge_task_and_communication,
    parse_json_object,
    persona_contexts,
    task_verdicts_from_standard,
)
from personacuabench.detailed_report import render_report  # noqa: E402
from personacuabench.judge import (  # noqa: E402
    _commit_judgement,
    _materialize_judge_snapshot,
    assemble_judgement,
    JudgeConfigurationError,
    load_run_artifacts,
)
from personacuabench.osworld_runner import (  # noqa: E402
    create_osworld_runtime,
    run_interaction_loop,
)
from personacuabench.network_preflight import (  # noqa: E402
    GUEST_PAYLOAD_VERSION,
    OUTPUT_SENTINEL,
    PreflightEndpoint,
    parse_controller_result,
)
from personacuabench.persona import (  # noqa: E402
    PersonaProfile,
    PersonaSession,
    QuestionLimitExceeded,
    load_profile,
    persona_system_prompt,
)
from personacuabench import run as run_module  # noqa: E402
from personacuabench.run import cached_opening_session, opening_cache_path  # noqa: E402
from personacuabench.report import parse_result  # noqa: E402
from personacuabench.protocol import (  # noqa: E402
    Clarification,
    ResponseKind,
    ResponseProtocolError,
    classify_response,
    compose_cua_instruction,
)


SECRET_SENTINEL = "OFFLINE_TEST_API_SECRET_DO_NOT_PERSIST"
RUBRIC_SENTINEL = "HIDDEN_RUBRIC_MUST_NOT_REACH_PERSONA_OR_CUA"
PROFILE_SENTINEL = "PRIVATE_PROFILE_SYSTEM_PROMPT"
SCREENSHOT_BYTES = b"\x89PNG\r\n\x1a\nOFFLINE-PIPELINE-FIXTURE"


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _eligible_preflight(
    *, task_id: str, run_id: str, affected_rubric_ids: tuple[str, ...]
) -> dict[str, Any]:
    endpoints = [
        PreflightEndpoint(
            "target_apex",
            "target",
            "https://retired.example/",
            affected_rubric_ids=affected_rubric_ids,
        ),
        PreflightEndpoint(
            "target_www",
            "target",
            "https://www.retired.example/",
            affected_rubric_ids=affected_rubric_ids,
        ),
        PreflightEndpoint("control_one", "control", "https://example.com/"),
        PreflightEndpoint("control_two", "control", "https://www.python.org/"),
    ]

    def dns_unresolved() -> dict[str, Any]:
        attempts = [
            {
                "ok": False,
                "addresses": [],
                "error_type": "gaierror",
                "error": "Name or service not known",
                "elapsed_ms": 1.0,
            }
            for _ in range(2)
        ]
        return {
            "ok": False,
            "addresses": [],
            "attempts": attempts,
            "error_type": "gaierror",
            "error": "Name or service not known",
            "elapsed_ms": 2.0,
        }

    def dns_resolved(address: str) -> dict[str, Any]:
        attempts = [
            {
                "ok": True,
                "addresses": [address],
                "error_type": None,
                "error": None,
                "elapsed_ms": 1.0,
            }
            for _ in range(2)
        ]
        return {
            "ok": True,
            "addresses": [address],
            "attempts": attempts,
            "error_type": None,
            "error": None,
            "elapsed_ms": 2.0,
        }

    def http_failure() -> dict[str, Any]:
        return {
            "response_received": False,
            "status_code": None,
            "final_host": None,
            "headers": {},
            "error_type": "gaierror",
            "error": "Name or service not known",
            "elapsed_ms": 1.0,
        }

    def http_success(code: int) -> dict[str, Any]:
        return {
            "response_received": True,
            "status_code": code,
            "final_host": "fixture.example",
            "headers": {},
            "error_type": None,
            "error": None,
            "elapsed_ms": 1.0,
        }

    probes: list[dict[str, Any]] = []
    for endpoint in endpoints[:2]:
        probes.append(
            {
                "key": endpoint.key,
                "role": endpoint.role,
                "url": endpoint.url,
                "host": endpoint.host,
                "dns": dns_unresolved(),
                "http": http_failure(),
            }
        )
    for endpoint, address, code in zip(
        endpoints[2:], ("93.184.216.34", "151.101.0.223"), (200, 301)
    ):
        probes.append(
            {
                "key": endpoint.key,
                "role": endpoint.role,
                "url": endpoint.url,
                "host": endpoint.host,
                "dns": dns_resolved(address),
                "http": http_success(code),
            }
        )
    payload = {
        "probe_payload_version": GUEST_PAYLOAD_VERSION,
        "task_id": task_id,
        "run_id": run_id,
        "phase": "after_reset_before_agent",
        "evidence_scope": "same_run",
        "started_at": "2026-09-20T20:00:00Z",
        "finished_at": "2026-09-20T20:00:01Z",
        "timeout_seconds": 4.0,
        "dns_attempts": 2,
        "network": {"default_route_present": True, "error": None},
        "probes": probes,
    }
    return parse_controller_result(
        endpoints,
        {
            "status": "success",
            "output": OUTPUT_SENTINEL + json.dumps(payload, separators=(",", ":")),
            "error": "",
            "return_code": 0,
        },
        task_id=task_id,
        run_id=run_id,
    )


def _fixture_profile() -> PersonaProfile:
    persona = SimpleNamespace(
        persona_id="offline-persona",
        version="1.0",
        display_name="Offline persona",
        schema_version="v2",
        data={"source": "synthetic:offline-test"},
        dimensions={"time_pressure": "Deadline"},
    )
    return PersonaProfile(
        path=Path("/offline/persona.yaml"),
        persona=persona,
        persona_system=PROFILE_SENTINEL,
        evaluation_dimensions=("time_pressure",),
        sha256="a" * 64,
    )


class _FakePersonaClient:
    role = "persona"
    model = "offline-model"
    provider = "offline"

    def __init__(self, responses: Sequence[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []
        # The adapter must not serialize arbitrary client attributes or metadata.
        self.api_key = SECRET_SENTINEL
        self.meta = {"api_key": SECRET_SENTINEL}

    def complete(self, messages: Sequence[Mapping[str, str]]) -> str:
        self.calls.append([dict(message) for message in messages])
        if not self.responses:
            raise AssertionError("unexpected fake persona call")
        return self.responses.pop(0)


class _ExplodingClient:
    def complete(self, _messages: Sequence[Mapping[str, str]]) -> str:
        raise AssertionError("the none control must not call a model")


class _FakeEnv:
    def __init__(self, *, marker: float = 0.75, forbid_step: bool = False) -> None:
        self.marker = marker
        self.forbid_step = forbid_step
        self.initial_observation: dict[str, Any] = {
            "screenshot": SCREENSHOT_BYTES,
            "fixture": "initial",
        }
        self.reset_configs: list[dict[str, Any] | None] = []
        self.steps: list[tuple[str, float]] = []

    def reset(self, task_config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.reset_configs.append(task_config)
        return self.initial_observation

    def step(self, action: str, pause: float) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        if self.forbid_step:
            raise AssertionError("ASK_USER must not call env.step")
        self.steps.append((action, pause))
        observation = {
            "screenshot": SCREENSHOT_BYTES,
            "fixture": f"after-{action}",
        }
        return observation, 0.0, action == "DONE", {"fixture": True}

    def evaluate(self) -> float:
        return self.marker


class _SequenceAgent:
    def __init__(self, responses: Sequence[tuple[str, Sequence[str] | None]]) -> None:
        self.responses = list(responses)
        self.instructions: list[str] = []
        self.observations: list[Mapping[str, Any]] = []
        self.reset_calls: list[dict[str, Any]] = []

    def reset(self, **kwargs: Any) -> None:
        self.reset_calls.append(kwargs)

    def predict(self, instruction: str, observation: Mapping[str, Any]) -> tuple[str, Sequence[str] | None]:
        self.instructions.append(instruction)
        self.observations.append(observation)
        if not self.responses:
            raise AssertionError("fake agent ran out of responses")
        return self.responses.pop(0)


class _AlwaysAskAgent:
    def __init__(self) -> None:
        self.instructions: list[str] = []
        self.observations: list[Mapping[str, Any]] = []

    def predict(self, instruction: str, observation: Mapping[str, Any]) -> tuple[str, list[str]]:
        self.instructions.append(instruction)
        self.observations.append(observation)
        number = len(self.instructions)
        return f"<ASK_USER>Question {number}?</ASK_USER>", []


class _FakeEvaluationJudge:
    def __init__(self, rubric_ids: Sequence[str]) -> None:
        self.rubric_ids = list(rubric_ids)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, system: str, user: str, screenshots: list[Path]) -> str:
        self.calls.append(
            {"system": system, "user": user, "screenshots": list(screenshots)}
        )
        if "communication-coverage judge" in system:
            payload = {
                "rubrics": {
                    rubric_id: {
                        "communicated": index == 0,
                        "evidence": f"offline communication evidence {rubric_id}",
                    }
                    for index, rubric_id in enumerate(self.rubric_ids)
                }
            }
            return "```json\n" + json.dumps(payload) + "\n```"
        if "persona-adherence judge" in system:
            payload = {
                "targets": [
                    {
                        "attribute": "time_pressure",
                        "expectedValue": "Deadline",
                        "score": 2,
                        "expressed": True,
                        "confidence": 0.9,
                        "evidence": "The user asked for a quick answer.",
                        "note": "offline fixture",
                    }
                ]
            }
            return json.dumps(payload)
        if "communicated preferences" in system:
            payload = {
                "persona_alignment_status": "partially_aligned",
                "persona_alignment_score": 0.75,
                "persona_preference_axis_primary": "frugality",
                "persona_signal_source": "dialog_context",
                "persona_alignment_explanation": "The communicated limit was respected.",
                "persona_constraints": [
                    {
                        "key": "budget",
                        "type": "budget",
                        "priority": "hard",
                        "status": "satisfied",
                        "source": "dialog",
                        "communicated": True,
                        "evidence": "The selected item stayed below the stated limit.",
                    }
                ],
            }
            return json.dumps(payload)
        raise AssertionError("unexpected fake judge prompt")


class ProtocolTests(unittest.TestCase):
    def test_strict_control_protocol_and_verbatim_instruction(self) -> None:
        opening = "\n  Keep these bytes — including whitespace.  \n"
        self.assertEqual(compose_cua_instruction(opening), opening)
        self.assertEqual(compose_cua_instruction(opening).encode(), opening.encode())

        ask = classify_response(" \n<ASK_USER> Which size? </ASK_USER>\t")
        self.assertIs(ask.kind, ResponseKind.ASK_USER)
        self.assertEqual(ask.text, "Which size?")
        final = classify_response("<FINAL_RESPONSE>Finished.</FINAL_RESPONSE>")
        self.assertIs(final.kind, ResponseKind.FINAL_RESPONSE)
        self.assertEqual(final.text, "Finished.")
        action_text = "```python\npyautogui.click(10, 20)\n```"
        action = classify_response(action_text)
        self.assertIs(action.kind, ResponseKind.ACTION)
        self.assertEqual(action.text, action_text)

        malformed = (
            "<ASK_USER></ASK_USER>",
            "<FINAL_RESPONSE>   </FINAL_RESPONSE>",
            "<ASK_USER>Question?</ASK_USER>\n```python\npass\n```",
            "prefix <FINAL_RESPONSE>done</FINAL_RESPONSE>",
            "<ASK_USER>one</ASK_USER><FINAL_RESPONSE>two</FINAL_RESPONSE>",
            "<ASK_USER><FINAL_RESPONSE>nested</FINAL_RESPONSE></ASK_USER>",
            "<ASK_USER>unclosed",
            "</ASK_USER>",
            "<ASK_USER >bad spelling</ASK_USER >",
        )
        for response in malformed:
            with self.subTest(response=response):
                with self.assertRaises(ResponseProtocolError):
                    classify_response(response)

        clarified = compose_cua_instruction(
            opening,
            [Clarification(question="Which size?", answer="Men's 10")],
        )
        self.assertEqual(
            clarified,
            opening + "\n\nClarifications:\nQ1: Which size?\nA1: Men's 10",
        )


class PersonaSessionTests(unittest.TestCase):
    def test_none_control_is_byte_for_byte_and_model_free(self) -> None:
        task = "\n  Exact none-control request — keep trailing space.  \n"
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "none-state.json"
            session = PersonaSession(
                task=task,
                profile=None,
                client=_ExplodingClient(),
                max_questions=0,
                state_path=state_path,
            )
            first = session.start()
            second = session.start()
            self.assertEqual(first.encode(), task.encode())
            self.assertEqual(second.encode(), task.encode())
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["exchanges"][0]["content"].encode(), task.encode())

    def test_fake_client_state_cache_limit_and_no_sensitive_leakage(self) -> None:
        task = "ORIGINAL_TASK_SENTINEL: find one suitable item."
        client = _FakePersonaClient(
            ["PERSONA_OPENING", "First answer", "Second answer"]
        )
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / "persona-state.json"
            session = PersonaSession(
                task=task,
                profile=_fixture_profile(),
                client=client,
                max_questions=2,
                state_path=state_path,
            )
            self.assertEqual(session.start(), "PERSONA_OPENING")
            self.assertEqual(session.start(), "PERSONA_OPENING")
            self.assertEqual(len(client.calls), 1, "start() must use its disk/in-memory cache")
            self.assertEqual(session.reply("First question?"), "First answer")
            self.assertEqual(session.reply("Second question?"), "Second answer")
            with self.assertRaises(QuestionLimitExceeded):
                session.reply("Forbidden third question?")
            self.assertEqual(len(client.calls), 3)
            self.assertEqual(session.questions_asked, 2)

            mode = stat.S_IMODE(state_path.stat().st_mode)
            self.assertEqual(mode, 0o600)
            state_text = state_path.read_text(encoding="utf-8")
            prompt_text = json.dumps(client.calls, ensure_ascii=False)
            for forbidden in (SECRET_SENTINEL, RUBRIC_SENTINEL):
                self.assertNotIn(forbidden, state_text)
                self.assertNotIn(forbidden, prompt_text)

            cua_instruction = compose_cua_instruction(
                "PERSONA_OPENING", session.exchanges[1:]
            )
            self.assertEqual(
                cua_instruction,
                "PERSONA_OPENING\n\nClarifications:\n"
                "Q1: First question?\nA1: First answer\n"
                "Q2: Second question?\nA2: Second answer",
            )
            for forbidden in (
                SECRET_SENTINEL,
                RUBRIC_SENTINEL,
                PROFILE_SENTINEL,
            ):
                self.assertNotIn(forbidden, cua_instruction)

            resumed_client = _FakePersonaClient([])
            resumed = PersonaSession(
                task=task,
                profile=_fixture_profile(),
                client=resumed_client,
                max_questions=2,
                state_path=state_path,
            )
            self.assertEqual(resumed.start(), "PERSONA_OPENING")
            self.assertEqual(resumed.questions_asked, 2)
            self.assertEqual(resumed_client.calls, [])
            with self.assertRaises(QuestionLimitExceeded):
                resumed.reply("Still forbidden?")

    def test_opening_cache_ignores_hidden_rubrics_and_client_secrets(self) -> None:
        task_a = {
            "task_id": "1" * 40,
            "confirmed_task": "Find one offline fixture.",
            "rubrics": {
                "R1": {
                    "requirement": "Find it",
                    "verification": RUBRIC_SENTINEL,
                }
            },
        }
        task_b = {
            **task_a,
            "rubrics": {
                "R1": {
                    "requirement": "A different hidden requirement",
                    "verification": "A different hidden verification",
                }
            },
        }
        profile = _fixture_profile()
        with tempfile.TemporaryDirectory() as temporary:
            cache_dir = Path(temporary)
            client = _FakePersonaClient(["CACHED_PERSONA_OPENING"])
            first_path = opening_cache_path(
                cache_dir=cache_dir,
                task=task_a,
                profile=profile,
                persona_model=client.model,
                provider=client.provider,
                max_questions=5,
            )
            second_path = opening_cache_path(
                cache_dir=cache_dir,
                task=task_b,
                profile=profile,
                persona_model=client.model,
                provider=client.provider,
                max_questions=5,
            )
            self.assertEqual(first_path, second_path)
            replicated_path = opening_cache_path(
                cache_dir=cache_dir,
                task=task_a,
                profile=profile,
                persona_model=client.model,
                provider=client.provider,
                max_questions=5,
                replicate_id="replicate-2",
            )
            self.assertNotEqual(first_path, replicated_path)

            _, state_path, opening = cached_opening_session(
                task=task_a,
                profile=profile,
                client=client,
                persona_model=client.model,
                max_questions=5,
                cache_dir=cache_dir,
            )
            self.assertEqual(opening, "CACHED_PERSONA_OPENING")
            self.assertEqual(state_path, first_path)
            self.assertEqual(len(client.calls), 1)
            state_text = state_path.read_text(encoding="utf-8")
            self.assertNotIn(RUBRIC_SENTINEL, state_text)
            self.assertNotIn(SECRET_SENTINEL, state_text)

            resumed_client = _FakePersonaClient([])
            _, resumed_path, resumed_opening = cached_opening_session(
                task=task_b,
                profile=profile,
                client=resumed_client,
                persona_model=resumed_client.model,
                max_questions=5,
                cache_dir=cache_dir,
            )
            self.assertEqual(resumed_path, first_path)
            self.assertEqual(resumed_opening, "CACHED_PERSONA_OPENING")
            self.assertEqual(resumed_client.calls, [])


class RunnerTests(unittest.TestCase):
    def test_preflight_refreshes_first_observation_without_environment_step(self) -> None:
        events: list[str] = []

        class RefreshEnv(_FakeEnv):
            def __init__(self) -> None:
                super().__init__(marker=1.0)
                self.page_state = "before"

            def reset(self, task_config: dict[str, Any] | None = None) -> dict[str, Any]:
                events.append("reset")
                return super().reset(task_config)

            def _get_obs(self) -> dict[str, Any]:
                events.append(f"observation:{self.page_state}")
                return {
                    "screenshot": SCREENSHOT_BYTES,
                    "fixture": self.page_state,
                }

        class RefreshAgent(_SequenceAgent):
            def predict(
                self, instruction: str, observation: Mapping[str, Any]
            ) -> tuple[str, Sequence[str] | None]:
                events.append("predict")
                return super().predict(instruction, observation)

        env = RefreshEnv()
        agent = RefreshAgent([("<FINAL_RESPONSE>Done.</FINAL_RESPONSE>", ["DONE"])])

        def preflight(actual_env: Any) -> dict[str, Any]:
            events.append("preflight")
            actual_env.page_state = "after"
            self.assertEqual(actual_env.steps, [])
            return {"status": "fixture"}

        with tempfile.TemporaryDirectory() as temporary:
            run_interaction_loop(
                agent=agent,
                env=env,
                opening_request="Opening",
                answer_user=lambda _question, _conversation: "unused",
                result_dir=Path(temporary) / "refresh",
                max_steps=1,
                max_questions=0,
                sleep_after_execution=0,
                environment_preflight=preflight,
            )

        self.assertEqual(
            events,
            ["reset", "observation:before", "preflight", "observation:after", "predict"],
        )
        self.assertEqual(agent.observations[0]["fixture"], "after")
        self.assertEqual(env.steps, [("DONE", 0)])

    def test_preflight_runs_after_reset_before_predict_without_agent_step_or_leak(self) -> None:
        events: list[str] = []

        class OrderedEnv(_FakeEnv):
            def reset(
                self, task_config: dict[str, Any] | None = None
            ) -> dict[str, Any]:
                events.append("reset")
                return super().reset(task_config)

        class OrderedAgent(_SequenceAgent):
            def predict(
                self, instruction: str, observation: Mapping[str, Any]
            ) -> tuple[str, Sequence[str] | None]:
                events.append("predict")
                return super().predict(instruction, observation)

        env = OrderedEnv(marker=1.0)
        agent = OrderedAgent(
            [("<FINAL_RESPONSE>Done.</FINAL_RESPONSE>", ["DONE"])]
        )
        preflight_sentinel = "PREFLIGHT_POLICY_MUST_NOT_REACH_CUA"

        def preflight(actual_env: Any) -> dict[str, Any]:
            events.append("preflight")
            self.assertIs(actual_env, env)
            self.assertEqual(env.steps, [])
            return {"status": "fixture", "sentinel": preflight_sentinel}

        with tempfile.TemporaryDirectory() as temporary:
            result_dir = Path(temporary) / "ordered"
            outcome = run_interaction_loop(
                agent=agent,
                env=env,
                opening_request="Original opening",
                answer_user=lambda _question, _conversation: "unused",
                result_dir=result_dir,
                max_steps=1,
                max_questions=0,
                sleep_after_execution=0,
                environment_preflight=preflight,
            )
            saved = json.loads(
                (result_dir / "network_preflight.json").read_text(encoding="utf-8")
            )

        self.assertEqual(events, ["reset", "preflight", "predict"])
        self.assertEqual(env.steps, [("DONE", 0)])
        self.assertEqual(outcome.environment_preflight, saved)
        self.assertNotIn(preflight_sentinel, "\n".join(agent.instructions))
        self.assertNotIn(
            preflight_sentinel,
            json.dumps(outcome.conversation, ensure_ascii=False),
        )

    def test_run_entrypoint_publishes_judgeable_result_and_skips_cache(self) -> None:
        task = load_tasks()[0]
        env = _FakeEnv(marker=0.0)
        agent = _SequenceAgent(
            [("<FINAL_RESPONSE>Offline result.</FINAL_RESPONSE>", ["DONE"])]
        )

        class FakeRuntime:
            def __init__(self) -> None:
                self.agent = agent
                self.env = env

            def __enter__(self) -> "FakeRuntime":
                return self

            def __exit__(self, *_args: Any) -> None:
                return None

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = SimpleNamespace(
                osworld_root=DEFAULT_OSWORLD_DIR,
                odysseys_dir=DEFAULT_ODYSSEYS_DIR,
                persona_repo=DEFAULT_PERSONA8B_DIR,
                results_dir=root / "results",
                cache_dir=root / "cache",
                model="offline-cua",
                persona_model="offline-persona",
                max_steps=3,
                max_questions=0,
                max_tokens=128,
                max_trajectory_length=1,
                replicate_id="offline-1",
                force=False,
                provider="fake",
                path_to_vm=None,
                headless=True,
                screen_width=1920,
                screen_height=1080,
                sleep_after_execution=0,
                ready_wait_seconds=0,
                settle_seconds=0,
                prediction_retries=1,
                prediction_retry_seconds=0,
            )
            with mock.patch.object(
                run_module, "create_osworld_runtime", return_value=FakeRuntime()
            ) as factory:
                first = run_module.run_task(
                    number=1,
                    task=task,
                    persona_name="none",
                    profile=None,
                    client=None,
                    args=args,
                )
                second = run_module.run_task(
                    number=1,
                    task=task,
                    persona_name="none",
                    profile=None,
                    client=None,
                    args=args,
                )

            self.assertEqual(first, second)
            self.assertEqual(factory.call_count, 1)
            payload = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "agent_complete")
            self.assertEqual(payload["judgement"], {"status": "not_run"})
            self.assertEqual(payload["run_control"]["replicate_id"], "offline-1")
            self.assertEqual(payload["run"]["answer"], "Offline result.")
            self.assertEqual(payload["run"]["opening"], task["confirmed_task"])
            self.assertEqual(payload["task"], task)
            self.assertTrue(
                payload["run"]["environment"]["network_preflight_configured"]
            )
            self.assertEqual(
                payload["run"]["environment"]["status"], "indeterminate"
            )
            preflight_path = first.parent / payload["artifacts"]["network_preflight"]
            self.assertTrue(preflight_path.is_file())
            self.assertEqual(
                hashlib.sha256(preflight_path.read_bytes()).hexdigest(),
                payload["artifacts"]["network_preflight_sha256"],
            )
            self.assertTrue(first.parent.name.endswith(task["task_id"]))
            judge_artifacts = load_run_artifacts(first)
            self.assertEqual(judge_artifacts.persona_mode, "none")
            self.assertEqual(judge_artifacts.task["task_id"], task["task_id"])
            self.assertEqual(
                judge_artifacts.network_preflight_integrity_status, "verified"
            )
            manifest = payload["artifacts"]["sha256"]
            self.assertIn("traj.jsonl", manifest)
            self.assertIn("conversation.jsonl", manifest)
            self.assertIn("result.txt", manifest)
            screenshot_name = payload["run"]["screenshots"][0]
            self.assertIn(screenshot_name, manifest)
            (first.parent / screenshot_name).write_bytes(b"tampered")
            self.assertIsNone(
                run_module.find_cached_result(
                    args.results_dir,
                    task["task_id"],
                    payload["fingerprint"],
                )
            )

    def test_ask_reuses_observation_and_final_writes_artifacts(self) -> None:
        opening = "OPENING_ONLY"
        env = _FakeEnv(marker=0.75)
        agent = _SequenceAgent(
            [
                ("<ASK_USER>Which size?</ASK_USER>", []),
                ("<FINAL_RESPONSE>Selected a suitable option.</FINAL_RESPONSE>", []),
            ]
        )
        answer_calls: list[tuple[str, list[dict[str, Any]]]] = []

        def answer_user(question: str, conversation: list[dict[str, Any]]) -> str:
            answer_calls.append((question, conversation))
            return "Men's 10"

        with tempfile.TemporaryDirectory() as temporary:
            result_dir = Path(temporary) / "run"
            outcome = run_interaction_loop(
                agent=agent,
                env=env,
                opening_request=opening,
                answer_user=answer_user,
                result_dir=result_dir,
                task_config={
                    "instruction": opening,
                    "hidden_rubric": RUBRIC_SENTINEL,
                },
                max_steps=4,
                max_questions=5,
                sleep_after_execution=0,
                collect_open_tabs=lambda _env: [
                    {"title": "Offline tab", "url": "https://example.invalid/"}
                ],
            )

            self.assertEqual(env.steps, [("DONE", 0)])
            self.assertIs(agent.observations[0], env.initial_observation)
            self.assertIs(agent.observations[1], env.initial_observation)
            self.assertEqual(agent.instructions[0], opening)
            self.assertEqual(
                agent.instructions[1],
                "OPENING_ONLY\n\nClarifications:\n"
                "Q1: Which size?\nA1: Men's 10",
            )
            self.assertEqual(answer_calls[0][0], "Which size?")
            self.assertEqual(
                [turn["event_type"] for turn in answer_calls[0][1]],
                ["opening", "ask_user"],
            )
            self.assertEqual(outcome.stop_reason, "final_response")
            self.assertEqual(outcome.answer, "Selected a suitable option.")
            self.assertEqual(outcome.agent_turns, 2)
            self.assertEqual(outcome.env_actions, 1)
            self.assertEqual(outcome.questions_asked, 1)
            self.assertEqual(outcome.questions_answered, 1)

            trajectory = _jsonl(result_dir / "traj.jsonl")
            self.assertEqual(
                [item["event_type"] for item in trajectory],
                ["ask_user", "final_response"],
            )
            self.assertEqual(trajectory[0]["action"], "")
            self.assertEqual(trajectory[1]["action"], "DONE")
            self.assertEqual(
                _jsonl(result_dir / "conversation.jsonl"), outcome.conversation
            )
            self.assertEqual(
                json.loads((result_dir / "open_tabs.json").read_text()),
                outcome.open_tabs,
            )
            saved_outcome = json.loads(
                (result_dir / "run_outcome.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved_outcome["stop_reason"], "final_response")
            self.assertEqual((result_dir / "result.txt").read_text(), "0.75\n")
            self.assertEqual(len(outcome.screenshot_files), 2)
            for filename in outcome.screenshot_files:
                self.assertEqual((result_dir / filename).read_bytes(), SCREENSHOT_BYTES)

            artifact_text = "\n".join(
                (result_dir / name).read_text(encoding="utf-8")
                for name in (
                    "traj.jsonl",
                    "conversation.jsonl",
                    "open_tabs.json",
                    "run_outcome.json",
                    "result.txt",
                )
            )
            self.assertNotIn(SECRET_SENTINEL, artifact_text)
            self.assertNotIn(RUBRIC_SENTINEL, artifact_text)

    def test_sixth_question_stops_without_persona_or_environment_call(self) -> None:
        env = _FakeEnv(marker=0.0, forbid_step=True)
        agent = _AlwaysAskAgent()
        answered: list[str] = []

        def answer_user(question: str, _conversation: list[dict[str, Any]]) -> str:
            answered.append(question)
            return f"Answer {len(answered)}"

        with tempfile.TemporaryDirectory() as temporary:
            result_dir = Path(temporary) / "limit"
            outcome = run_interaction_loop(
                agent=agent,
                env=env,
                opening_request="Question-limit opening",
                answer_user=answer_user,
                result_dir=result_dir,
                max_steps=10,
                max_questions=5,
                sleep_after_execution=0,
            )
            self.assertEqual(outcome.stop_reason, "question_limit_exceeded")
            self.assertEqual(outcome.agent_turns, 6)
            self.assertEqual(outcome.questions_asked, 6)
            self.assertEqual(outcome.questions_answered, 5)
            self.assertEqual(outcome.env_actions, 0)
            self.assertEqual(len(answered), 5)
            self.assertTrue(
                all(observation is env.initial_observation for observation in agent.observations)
            )
            trajectory = _jsonl(result_dir / "traj.jsonl")
            self.assertEqual(len(trajectory), 6)
            self.assertTrue(trajectory[-1]["done"])
            self.assertTrue(trajectory[-1]["info"]["question_limit_exceeded"])
            self.assertIsNone(trajectory[-1]["persona_answer"])
            self.assertTrue((result_dir / "result.txt").is_file())

    def test_empty_prediction_retries_without_duplicate_environment_action(self) -> None:
        class RetryAgent:
            def __init__(self) -> None:
                self.calls = 0
                self.observations: list[Mapping[str, Any]] = []
                self.actions: list[Sequence[str]] = []
                self.thoughts: list[str] = []

            def predict(
                self, instruction: str, observation: Mapping[str, Any]
            ) -> tuple[str, Sequence[str] | None]:
                self.calls += 1
                self.observations.append(observation)
                if self.calls == 1:
                    # Match PromptAgent's transport-failure mutation: it stores
                    # an observation and empty thought but no action.
                    self.thoughts.append("")
                    return "", None
                self.actions.append(["DONE"])
                self.thoughts.append("<FINAL_RESPONSE>Recovered.</FINAL_RESPONSE>")
                return "<FINAL_RESPONSE>Recovered.</FINAL_RESPONSE>", ["DONE"]

        env = _FakeEnv(marker=1.0)
        agent = RetryAgent()
        with tempfile.TemporaryDirectory() as temporary:
            outcome = run_interaction_loop(
                agent=agent,
                env=env,
                opening_request="Retry fixture",
                answer_user=lambda _question, _conversation: "unused",
                result_dir=Path(temporary) / "retry",
                max_steps=2,
                max_questions=0,
                sleep_after_execution=0,
                prediction_retries=1,
                prediction_retry_seconds=0,
            )

        self.assertEqual(agent.calls, 2)
        self.assertEqual(len(agent.observations), 1)
        self.assertEqual(len(agent.actions), 1)
        self.assertEqual(len(agent.thoughts), 1)
        self.assertEqual(env.steps, [("DONE", 0)])
        self.assertEqual(outcome.answer, "Recovered.")
        self.assertEqual(outcome.agent_turns, 1)
        self.assertEqual(outcome.env_actions, 1)
        self.assertEqual(
            outcome.warnings,
            ["agent prediction retry 1/1 after empty response"],
        )

    def test_factory_forwards_ask_flag_and_cache_dir_without_real_vm(self) -> None:
        agent_kwargs: dict[str, Any] = {}
        env_kwargs: dict[str, Any] = {}

        class FakeFactoryAgent:
            def __init__(self, **kwargs: Any) -> None:
                agent_kwargs.update(kwargs)
                self.system_message = "adapter-owned prompt"

        class FakeFactoryEnv:
            def __init__(self, **kwargs: Any) -> None:
                env_kwargs.update(kwargs)
                self.closed = False

            def close(self) -> None:
                self.closed = True

        desktop_package = types.ModuleType("desktop_env")
        desktop_package.__path__ = []  # type: ignore[attr-defined]
        desktop_module = types.ModuleType("desktop_env.desktop_env")
        desktop_module.DesktopEnv = FakeFactoryEnv  # type: ignore[attr-defined]
        agents_package = types.ModuleType("mm_agents")
        agents_package.__path__ = []  # type: ignore[attr-defined]
        agent_module = types.ModuleType("mm_agents.azure_foundry_agent")
        agent_module.AzureFoundryPromptAgent = FakeFactoryAgent  # type: ignore[attr-defined]

        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            osworld_root = Path(temporary).resolve()
            source = osworld_root / "desktop_env" / "desktop_env.py"
            source.parent.mkdir(parents=True)
            source.touch()
            modules = {
                "desktop_env": desktop_package,
                "desktop_env.desktop_env": desktop_module,
                "mm_agents": agents_package,
                "mm_agents.azure_foundry_agent": agent_module,
            }
            runtime = None
            try:
                with mock.patch.dict(sys.modules, modules):
                    runtime = create_osworld_runtime(
                        osworld_root=osworld_root,
                        allow_ask_user=True,
                        max_questions=5,
                    )
                    self.assertEqual(Path.cwd(), osworld_root)
                    self.assertIs(agent_kwargs["allow_ask_user"], True)
                    self.assertEqual(runtime.agent.system_message, "adapter-owned prompt")
                    self.assertEqual(
                        env_kwargs["cache_dir"], str(osworld_root / "cache")
                    )
                    runtime.close()
                    self.assertTrue(runtime.env.closed)
                    self.assertEqual(Path.cwd(), old_cwd)
            finally:
                if runtime is not None and not runtime._closed:
                    runtime.close()
                os.chdir(old_cwd)
                while str(osworld_root) in sys.path:
                    sys.path.remove(str(osworld_root))

        # Pin drift is caught without importing or instantiating DesktopEnv.
        desktop_source = DEFAULT_OSWORLD_DIR / "desktop_env" / "desktop_env.py"
        tree = ast.parse(desktop_source.read_text(encoding="utf-8"))
        init_parameters: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "DesktopEnv":
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__":
                        init_parameters = [argument.arg for argument in item.args.args]
        self.assertIn("cache_dir", init_parameters)


class RepositoryFixtureTests(unittest.TestCase):
    def test_tasks_match_all_pinned_odysseys_configs(self) -> None:
        tasks = load_tasks()
        self.assertEqual(len(tasks), 6)
        upstream = json.loads(
            (DEFAULT_ODYSSEYS_DIR / "data" / "odysseys.json").read_text(
                encoding="utf-8"
            )
        )
        upstream_by_id = {item["task_id"]: item for item in upstream}
        for task in tasks:
            with self.subTest(task_id=task["task_id"]):
                config = load_task_config(task, DEFAULT_ODYSSEYS_DIR)
                self.assertEqual(config["id"], task["task_id"])
                self.assertEqual(config["instruction"], task["confirmed_task"])
                self.assertEqual(task, upstream_by_id[task["task_id"]])

    def test_summary_and_detailed_reports_distinguish_raw_adjusted_and_legacy(self) -> None:
        task = load_tasks()[0]
        legacy = {
            "status": "complete",
            "task_id": task["task_id"],
            "task": task,
            "persona": "none",
            "judgement": {"status": "complete", "score": 0.8},
        }
        legacy_report = render_report(legacy, Path("/tmp/legacy/result.json"))
        self.assertIn("Task score (raw / official)", legacy_report)
        self.assertIn("Availability-adjusted task score (diagnostic)", legacy_report)
        self.assertIn("N/A", legacy_report)

        current = json.loads(json.dumps(legacy))
        current["run"] = {"environment": {"status": "partially_infeasible"}}
        current["artifacts"] = {
            "network_preflight": "network_preflight.json",
            "network_preflight_sha256": "a" * 64,
        }
        current["source_revisions"] = {
            "availability_policy_task_sha256": "b" * 64
        }
        current["judgement"] = {
            "status": "complete",
            "score": 0.8,
            "score_raw": 0.8,
            "score_availability_adjusted": 1.0,
            "scope": {"network_preflight_integrity": "verified"},
            "environment_feasibility": {"status": "partially_infeasible"},
            "task_success": {
                "availability_adjustment": {
                    "status": "adjusted",
                    "coverage": {"excluded_rubric_ids": ["R1"]},
                    "excluded_rubrics": [{"rubric_id": "R1"}],
                }
            },
        }
        current_report = render_report(current, Path("/tmp/current/result.json"))
        self.assertIn(r"1\.0000 \(100\.0%\)", current_report)
        self.assertIn("Network preflight integrity:** verified", current_report)
        self.assertIn(r"network\_preflight\.json", current_report)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / task["task_id"] / "none__fixture__run"
            run_dir.mkdir(parents=True)
            result_path = run_dir / "result.json"
            result_path.write_text(json.dumps(current), encoding="utf-8")
            row = parse_result(
                result_path,
                root,
                {task["task_id"]: 1},
                {1: task["task_id"]},
            )
        self.assertEqual(row.task_score, "0.8")
        self.assertEqual(row.adjusted_task_score, "1")
        self.assertEqual(row.environment, "partially_infeasible")
        self.assertEqual(row.run, "none__fixture__run")

    def test_three_smoke_profiles_use_official_loader(self) -> None:
        persona_dir = REPO_ROOT / "personacuabench" / "personas"
        profile_paths = sorted(persona_dir.glob("smoke_*.yaml"))
        self.assertEqual(
            [path.name for path in profile_paths],
            [
                "smoke_accessible_premium.yaml",
                "smoke_budget_mobile.yaml",
                "smoke_verification_researcher.yaml",
            ],
        )
        for path in profile_paths:
            with self.subTest(profile=path.name):
                profile = load_profile(path.resolve(), DEFAULT_PERSONA8B_DIR)
                self.assertTrue(profile.persona_id)
                self.assertTrue(profile.persona_system.strip())
                self.assertEqual(profile.schema_version, "v2")
                self.assertTrue(profile.evaluation_dimensions)
                self.assertTrue(
                    set(profile.evaluation_dimensions).issubset(profile.dimensions)
                )
                self.assertEqual(
                    set(profile.meta["evaluation_values"]),
                    set(profile.evaluation_dimensions),
                )

    def test_main_legacy_persona_remains_usable(self) -> None:
        path = REPO_ROOT / "personacuabench" / "personas" / "budget-student.yaml"
        profile = load_profile(path, DEFAULT_PERSONA8B_DIR)
        self.assertEqual(profile.schema_version, "v2")
        self.assertEqual(profile.dimensions["tech_savviness"], "Digital native")
        self.assertIn("Digital native", profile.persona_system)
        self.assertEqual(profile.evaluation_dimensions, ())
        self.assertIn("Frugal saver", persona_system_prompt(path))

    def test_six_matched_pairs_change_exactly_one_rendered_dimension(self) -> None:
        persona_dir = REPO_ROOT / "personacuabench" / "personas" / "matched_pairs"
        profile_paths = sorted(persona_dir.glob("*.yaml"))
        self.assertEqual(len(profile_paths), 12)
        tasks_by_id = {task["task_id"]: task for task in load_tasks()}
        pairs: dict[str, list[PersonaProfile]] = {}
        for path in profile_paths:
            profile = load_profile(path.resolve(), DEFAULT_PERSONA8B_DIR)
            matched_pair = profile.meta["matched_pair"]
            self.assertEqual(
                profile.evaluation_dimensions,
                (matched_pair["changed_dimension"],),
            )
            selected_task = tasks_by_id[matched_pair["applicable_task_ids"][0]]
            rubric = run_module.persona_metadata(
                profile, task=selected_task
            )["adherence_rubric"]
            self.assertEqual(
                rubric["expected_value"],
                profile.dimensions[matched_pair["changed_dimension"]],
            )
            self.assertEqual(
                rubric["task_id"],
                selected_task["task_id"],
            )
            pairs.setdefault(matched_pair["pair_id"], []).append(profile)

        self.assertEqual(len(pairs), 6)
        for pair_id, pair in pairs.items():
            with self.subTest(pair=pair_id):
                self.assertEqual(len(pair), 2)
                left, right = pair
                self.assertEqual(left.display_name, right.display_name)
                left_pair = left.meta["matched_pair"]
                right_pair = right.meta["matched_pair"]
                self.assertEqual(
                    {left_pair["arm"], right_pair["arm"]},
                    {"positive", "negative"},
                )
                self.assertEqual(
                    left_pair["changed_dimension"], right_pair["changed_dimension"]
                )
                changed = left_pair["changed_dimension"]
                differing = {
                    key
                    for key in left.dimensions
                    if left.dimensions[key] != right.dimensions[key]
                }
                self.assertEqual(differing, {changed})
                self.assertNotEqual(left.persona_system, right.persona_system)


class EvaluationTests(unittest.TestCase):
    @staticmethod
    def _task() -> dict[str, Any]:
        return {
            "task_id": "0" * 40,
            "confirmed_task": "Find an option and report it.",
            "rubrics": {
                "R1": {"requirement": "Find an option", "verification": "visible"},
                "R2": {"requirement": "Report it", "verification": "answer"},
            },
        }

    def test_fake_judges_produce_normalized_evaluation_schema(self) -> None:
        task = self._task()
        conversation = [
            {"role": "user", "content": "Please keep it under $50.", "event_type": "opening", "turn": 0},
            {"role": "assistant", "content": "Any brand?", "event_type": "ask_user", "turn": 1},
            {"role": "user", "content": "No brand preference.", "event_type": "user_answer", "turn": 1},
        ]
        judge = _FakeEvaluationJudge(task["rubrics"].keys())
        communication = evaluate_communication(
            task=task,
            conversation=conversation,
            judge=judge,
        )
        self.assertTrue(communication["judge_derived"])
        self.assertTrue(communication["rubrics"]["R1"]["communicated"])
        self.assertFalse(communication["rubrics"]["R2"]["communicated"])

        standard = {
            "rubric_results": [
                {"rubric_id": "R1", "score": 1, "final_reasoning": "met"},
                {"rubric_id": "R2", "score": 0, "final_reasoning": "not met"},
            ]
        }
        verdicts = task_verdicts_from_standard(task, standard)
        task_metrics = merge_task_and_communication(verdicts, communication)
        self.assertEqual(
            set(task_metrics),
            {
                "verdicts",
                "score",
                "score_communicated",
                "communicated_rubric_count",
                "communication_judge_derived",
            },
        )
        self.assertEqual(task_metrics["score"], 0.5)
        self.assertEqual(task_metrics["score_communicated"], 1.0)
        self.assertEqual(task_metrics["communicated_rubric_count"], 1)

        persona_meta = {
            "evaluation_dimensions": ["time_pressure"],
            "dimensions": {"time_pressure": "Deadline"},
        }
        adherence = evaluate_adherence(
            persona_meta=persona_meta,
            conversation=conversation,
            judge=judge,
            task=task,
        )
        self.assertEqual(set(adherence), {"applicable", "targets"})
        self.assertTrue(adherence["applicable"])
        self.assertEqual(adherence["targets"][0]["attribute"], "time_pressure")

        with tempfile.TemporaryDirectory() as temporary:
            screenshot = Path(temporary) / "screenshot.png"
            screenshot.write_bytes(SCREENSHOT_BYTES)
            alignment = evaluate_alignment(
                task=task,
                persona_meta=persona_meta,
                conversation=conversation,
                action_history="clicked the first result",
                final_answer="Found one under $50.",
                communication=communication,
                screenshots=[screenshot],
                judge=judge,
            )
            self.assertEqual(
                set(alignment),
                {
                    "persona_alignment_status",
                    "persona_alignment_score",
                    "persona_preference_axis_primary",
                    "persona_signal_source",
                    "persona_alignment_explanation",
                    "persona_constraints",
                },
            )
            self.assertEqual(alignment["persona_alignment_status"], "partially_aligned")
            self.assertEqual(alignment["persona_alignment_score"], 0.75)
            self.assertEqual(judge.calls[-1]["screenshots"], [screenshot])

        contexts = persona_contexts(alignment)
        self.assertEqual(contexts[0]["contextType"], "persona_alignment")
        self.assertEqual(contexts[1]["contextType"], "persona_constraint")
        self.assertEqual(contexts[1]["key"], "persona_constraint.budget")
        self.assertEqual(len(judge.calls), 3)

        def fail_if_called(_system: str, _user: str, _screenshots: list[Path]) -> str:
            raise AssertionError("none-control coverage must not need a judge")

        exact = evaluate_communication(
            task=task,
            conversation=[],
            judge=fail_if_called,
            exact_control=True,
        )
        self.assertFalse(exact["judge_derived"])
        self.assertTrue(all(item["communicated"] for item in exact["rubrics"].values()))

    def test_matched_pair_adherence_uses_task_specific_rubric(self) -> None:
        task = self._task()
        persona_meta = {
            "evaluation_dimensions": ["time_pressure"],
            "dimensions": {"time_pressure": "Deadline"},
            "adherence_rubric": {
                "dimension": "time_pressure",
                "behavioral_definition": "Prioritize required work before optional exploration.",
                "generic_observables": ["States that the decision is soon."],
                "contradictions": ["Says there is no rush."],
                "score_scale": {"0": "absent", "1": "ambiguous", "2": "clear"},
                "task_id": task["task_id"],
                "task_criterion": {
                    "inherited_task_signals": ["Report the result."],
                    "expected_observables": ["Asks for the first complete result."],
                    "opposite_observables": ["Invites optional alternatives."],
                },
            },
        }

        def matched_judge(system: str, user: str, _screenshots: list[Path]) -> str:
            self.assertIn("merely inherited", system)
            self.assertIn("inherited_task_signals", user)
            self.assertIn(task["confirmed_task"], user)
            return json.dumps(
                {
                    "targets": [
                        {
                            "attribute": "time_pressure",
                            "expectedValue": "Deadline",
                            "score": 2,
                            "expressed": True,
                            "confidence": 0.95,
                            "evidence": "The user asked for the first complete result.",
                            "note": "task-specific evidence",
                        }
                    ]
                }
            )

        judged = evaluate_adherence(
            persona_meta=persona_meta,
            conversation=[{"role": "user", "content": "Please give me the first complete result."}],
            judge=matched_judge,
            task=task,
        )
        self.assertEqual(judged["targets"][0]["score"], 2)
        self.assertEqual(
            judged["targets"][0]["criterion_source"],
            "matched_pair_task_specific",
        )

        outside_task = dict(task, task_id="1" * 40)

        def must_not_call(_system: str, _user: str, _screenshots: list[Path]) -> str:
            raise AssertionError("non-applicable matched-pair cells must not be judged")

        with self.assertRaises(EvaluationError):
            evaluate_adherence(
                persona_meta=persona_meta,
                conversation=[],
                judge=must_not_call,
                task=outside_task,
            )

    def test_availability_adjustment_preserves_raw_verdicts_and_denominators(self) -> None:
        task_id = "a" * 40
        verdicts = [
            {
                "rubric_id": f"R{index}",
                "requirement": f"Requirement {index}",
                "met": index != 1,
                "communicated": True,
                "task_evidence": f"Evidence {index}",
            }
            for index in range(1, 6)
        ]
        task_success = {
            "verdicts": verdicts,
            "score": 0.8,
            "score_communicated": 0.8,
            "communicated_rubric_count": 5,
        }
        original = json.loads(json.dumps(task_success))
        preflight = _eligible_preflight(
            task_id=task_id,
            run_id="same-run",
            affected_rubric_ids=("R1",),
        )
        adjusted = compute_availability_adjustment(
            task_success,
            preflight,
            expected_task_id=task_id,
            expected_run_id="same-run",
            artifact_integrity_verified=True,
        )
        self.assertEqual(adjusted["score_raw"], 0.8)
        self.assertEqual(adjusted["score_availability_adjusted"], 1.0)
        self.assertEqual(
            adjusted["score_communicated_availability_adjusted"], 1.0
        )
        self.assertEqual(adjusted["status"], "adjusted")
        self.assertEqual(
            adjusted["environment_feasibility"]["status"],
            "partially_infeasible",
        )
        self.assertEqual(
            adjusted["coverage"]["excluded_rubric_ids"], ["R1"]
        )
        self.assertEqual(task_success, original)
        self.assertFalse(task_success["verdicts"][0]["met"])

        unverified = compute_availability_adjustment(
            task_success,
            preflight,
            expected_task_id=task_id,
            expected_run_id="same-run",
            artifact_integrity_verified=False,
        )
        self.assertIsNone(unverified["score_availability_adjusted"])

        one_rubric = {
            "verdicts": [verdicts[0]],
            "score": 0.0,
            "score_communicated": 0.0,
            "communicated_rubric_count": 1,
        }
        all_excluded = compute_availability_adjustment(
            one_rubric,
            preflight,
            expected_task_id=task_id,
            expected_run_id="same-run",
            artifact_integrity_verified=True,
        )
        self.assertIsNone(all_excluded["score_availability_adjusted"])
        self.assertEqual(
            all_excluded["environment_feasibility"]["status"], "infeasible"
        )

        wrong_run = compute_availability_adjustment(
            task_success,
            preflight,
            expected_task_id=task_id,
            expected_run_id="different-run",
            artifact_integrity_verified=True,
        )
        self.assertIsNone(wrong_run["score_availability_adjusted"])
        self.assertIn(
            "run_id_mismatch",
            wrong_run["environment_feasibility"]["reasons"],
        )

        # The adjusted denominator is environment-defined, not outcome-defined.
        mixed = json.loads(json.dumps(task_success))
        mixed["verdicts"][0]["met"] = True
        mixed["verdicts"][1]["met"] = False
        mixed["score"] = 0.8
        mixed["score_communicated"] = 0.8
        same_denominator = compute_availability_adjustment(
            mixed,
            preflight,
            expected_task_id=task_id,
            expected_run_id="same-run",
            artifact_integrity_verified=True,
        )
        self.assertEqual(same_denominator["coverage"]["excluded_rubric_ids"], ["R1"])
        self.assertEqual(same_denominator["score_availability_adjusted"], 0.75)

    def test_invalid_fake_judge_schemas_are_rejected(self) -> None:
        task = self._task()
        conversation = [{"role": "user", "content": "hello"}]
        self.assertEqual(parse_json_object("```json\n{\"ok\": true}\n```"), {"ok": True})

        bad_communication = json.dumps(
            {"rubrics": {"R1": {"communicated": "yes"}, "R2": {"communicated": True}}}
        )
        with self.assertRaises(EvaluationError):
            evaluate_communication(
                task=task,
                conversation=conversation,
                judge=lambda _s, _u, _p: bad_communication,
            )

        bad_adherence = json.dumps(
            {
                "targets": [
                    {
                        "attribute": "time_pressure",
                        "score": 2,
                        "expressed": True,
                        "confidence": 1.5,
                    }
                ]
            }
        )
        with self.assertRaises(EvaluationError):
            evaluate_adherence(
                persona_meta={
                    "evaluation_dimensions": ["time_pressure"],
                    "dimensions": {"time_pressure": "Deadline"},
                },
                conversation=conversation,
                judge=lambda _s, _u, _p: bad_adherence,
            )

        bad_alignment = json.dumps(
            {
                "persona_alignment_status": "excellent",
                "persona_alignment_score": 1,
                "persona_constraints": [],
            }
        )
        with self.assertRaises(EvaluationError):
            evaluate_alignment(
                task=task,
                persona_meta={},
                conversation=conversation,
                action_history="",
                final_answer="",
                communication={},
                screenshots=[],
                judge=lambda _s, _u, _p: bad_alignment,
            )

    def test_unknown_alignment_constraint_type_is_auditable_other(self) -> None:
        task = self._task()
        evidence = "The user explicitly requested trustworthy sources."
        response = json.dumps(
            {
                "persona_alignment_status": "aligned",
                "persona_alignment_score": 0.9,
                "persona_preference_axis_primary": "trust",
                "persona_signal_source": "task_instruction",
                "persona_alignment_explanation": "Sources were attributed.",
                "persona_constraints": [
                    {
                        "key": "trustworthy_sources",
                        "type": "trust",
                        "priority": "hard",
                        "status": "satisfied",
                        "source": "task",
                        "communicated": True,
                        "evidence": evidence,
                    }
                ],
            }
        )
        alignment = evaluate_alignment(
            task=task,
            persona_meta={},
            conversation=[{"role": "user", "content": "Use trustworthy sources."}],
            action_history="Visited source pages.",
            final_answer="Source-attributed answer.",
            communication={},
            screenshots=[],
            judge=lambda _s, _u, _p: response,
        )
        constraint = alignment["persona_constraints"][0]
        self.assertEqual(constraint["type"], "other")
        self.assertEqual(constraint["type_original"], "trust")
        self.assertEqual(constraint["key"], "trustworthy_sources")
        self.assertEqual(constraint["evidence"], evidence)
        contexts = persona_contexts(alignment)
        constraint_type = next(
            facet["value"]
            for facet in contexts[1]["facets"]
            if facet["key"] == "persona_constraint_type"
        )
        self.assertEqual(constraint_type, "other")

        invalid_type = json.loads(response)
        invalid_type["persona_constraints"][0]["type"] = {"trust": True}
        with self.assertRaises(EvaluationError):
            evaluate_alignment(
                task=task,
                persona_meta={},
                conversation=[],
                action_history="",
                final_answer="",
                communication={},
                screenshots=[],
                judge=lambda _s, _u, _p: json.dumps(invalid_type),
            )


class JudgeAdapterTests(unittest.TestCase):
    @staticmethod
    def _task() -> dict[str, Any]:
        return {
            "task_id": "1" * 40,
            "confirmed_task": "Find an option and report it.",
            "rubrics": {
                "R1": {"requirement": "Find an option", "verification": "visible"},
                "R2": {"requirement": "Report it", "verification": "answer"},
            },
        }

    def _fixture(
        self,
        root: Path,
        *,
        persona: str,
        persona_meta: dict[str, Any],
        opening: str,
    ) -> Path:
        task = self._task()
        run_dir = root / f"{persona}__offline__{task['task_id']}"
        run_dir.mkdir()
        screenshot = run_dir / "step_1.png"
        screenshot.write_bytes(SCREENSHOT_BYTES)
        (run_dir / "traj.jsonl").write_text(
            json.dumps(
                {
                    "step_num": 1,
                    "event_type": "final_response",
                    "action": "DONE",
                    "response": "<FINAL_RESPONSE>Found one.</FINAL_RESPONSE>",
                    "screenshot_file": screenshot.name,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        conversation = [
            {"role": "user", "content": opening, "event_type": "opening", "turn": 0},
            {
                "role": "assistant",
                "content": "Found one.",
                "event_type": "final_response",
                "turn": 1,
            },
        ]
        (run_dir / "conversation.jsonl").write_text(
            "".join(json.dumps(turn) + "\n" for turn in conversation),
            encoding="utf-8",
        )
        (run_dir / "open_tabs.json").write_text("[]\n", encoding="utf-8")
        (run_dir / "result.txt").write_text("0\n", encoding="utf-8")
        result = {
            "status": "agent_complete",
            "task_id": task["task_id"],
            "task": task,
            "persona": persona,
            "persona_meta": persona_meta,
            "run": {"answer": "Found one.", "open_tabs": []},
            "judgement": {"status": "not_run"},
        }
        result_path = run_dir / "result.json"
        result_path.write_text(json.dumps(result), encoding="utf-8")
        return result_path

    @staticmethod
    def _standard() -> dict[str, Any]:
        return {
            "rubric_results": [
                {"rubric_id": "R1", "score": 1, "final_reasoning": "met"},
                {"rubric_id": "R2", "score": 0, "final_reasoning": "not met"},
            ]
        }

    def test_none_judge_is_local_na_and_atomic_commit_promotes_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = self._fixture(
                Path(temporary),
                persona="none",
                persona_meta={"mode": "none"},
                opening=self._task()["confirmed_task"],
            )
            artifacts = load_run_artifacts(result_path)

            def no_persona_call(_system: str, _user: str, _images: list[Path]) -> str:
                raise AssertionError("none must not make persona judge calls")

            judgement = assemble_judgement(
                artifacts=artifacts,
                standard_result=self._standard(),
                judge_call=no_persona_call,
                endpoint_meta={"model": "offline"},
                max_images=0,
                max_steps=0,
            )
            self.assertEqual(judgement["score"], 0.5)
            self.assertEqual(judgement["score_communicated"], 0.5)
            self.assertFalse(judgement["persona"]["adherence"]["applicable"])
            self.assertEqual(
                judgement["persona"]["alignment"]["persona_alignment_status"],
                "not_applicable",
            )
            self.assertIsNone(
                judgement["persona"]["alignment"]["persona_alignment_score"]
            )
            self.assertEqual(judgement["persona"]["contexts"], [])

            _commit_judgement(artifacts, judgement)
            committed = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(committed["status"], "complete")
            self.assertEqual(committed["agent_status"], "agent_complete")
            self.assertEqual(committed["judgement"]["status"], "complete")

    def test_judge_rejects_out_of_run_screenshot_and_detects_artifact_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = self._fixture(
                root,
                persona="none",
                persona_meta={"mode": "none"},
                opening=self._task()["confirmed_task"],
            )
            external = root / "outside.png"
            external.write_bytes(SCREENSHOT_BYTES)
            trajectory_path = result_path.parent / "traj.jsonl"
            row = json.loads(trajectory_path.read_text(encoding="utf-8"))
            row["screenshot_file"] = str(external)
            trajectory_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaises(JudgeConfigurationError):
                load_run_artifacts(result_path)

            row["screenshot_file"] = "step_1.png"
            trajectory_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            artifacts = load_run_artifacts(result_path)
            source_screenshot = result_path.parent / "step_1.png"
            with _materialize_judge_snapshot(artifacts) as snapshot:
                snapshot_bytes = snapshot.screenshots[0].read_bytes()
                source_screenshot.write_bytes(b"changed")
                self.assertEqual(snapshot.screenshots[0].read_bytes(), snapshot_bytes)
            with self.assertRaises(JudgeConfigurationError):
                _commit_judgement(artifacts, {"status": "complete"})

    def test_hashed_but_schema_invalid_preflight_is_not_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = self._fixture(
                Path(temporary),
                persona="none",
                persona_meta={"mode": "none"},
                opening=self._task()["confirmed_task"],
            )
            artifact_path = result_path.parent / "network_preflight.json"
            artifact_bytes = json.dumps(
                {
                    "schema_version": "persona-cua-network-preflight/v1",
                    "task_id": self._task()["task_id"],
                    "run_id": result_path.parent.name,
                }
            ).encode()
            artifact_path.write_bytes(artifact_bytes)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["artifacts"] = {
                "network_preflight": artifact_path.name,
                "network_preflight_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
            }
            result_path.write_text(json.dumps(result), encoding="utf-8")
            artifacts = load_run_artifacts(result_path)
            self.assertEqual(
                artifacts.network_preflight_integrity_status,
                "contract_invalid",
            )
            judgement = assemble_judgement(
                artifacts=artifacts,
                standard_result=self._standard(),
                judge_call=lambda _system, _user, _images: (_ for _ in ()).throw(
                    AssertionError("none must not call persona judge")
                ),
                endpoint_meta={"model": "offline"},
                max_images=0,
                max_steps=0,
            )
            self.assertIsNone(judgement["score_availability_adjusted"])

    def test_verified_preflight_adds_adjusted_score_without_rewriting_raw(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result_path = self._fixture(
                Path(temporary),
                persona="none",
                persona_meta={"mode": "none"},
                opening=self._task()["confirmed_task"],
            )
            preflight = _eligible_preflight(
                task_id=self._task()["task_id"],
                run_id=result_path.parent.name,
                affected_rubric_ids=("R2",),
            )
            artifact_path = result_path.parent / "network_preflight.json"
            artifact_bytes = (
                json.dumps(preflight, indent=2, ensure_ascii=False) + "\n"
            ).encode()
            artifact_path.write_bytes(artifact_bytes)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["artifacts"] = {
                "network_preflight": artifact_path.name,
                "network_preflight_sha256": hashlib.sha256(
                    artifact_bytes
                ).hexdigest(),
            }
            result_path.write_text(json.dumps(result), encoding="utf-8")

            artifacts = load_run_artifacts(result_path)
            self.assertEqual(
                artifacts.network_preflight_integrity_status, "verified"
            )
            judgement = assemble_judgement(
                artifacts=artifacts,
                standard_result=self._standard(),
                judge_call=lambda _system, _user, _images: (_ for _ in ()).throw(
                    AssertionError("none must not call persona judge")
                ),
                endpoint_meta={"model": "offline"},
                max_images=0,
                max_steps=0,
            )
            self.assertEqual(judgement["score"], 0.5)
            self.assertEqual(judgement["score_raw"], 0.5)
            self.assertEqual(judgement["score_availability_adjusted"], 1.0)
            self.assertFalse(judgement["verdicts"][1]["met"])
            self.assertEqual(
                judgement["environment_feasibility"]["status"],
                "partially_infeasible",
            )

    def test_persona_metadata_mapping_and_three_axis_judgement(self) -> None:
        persona_meta = {
            "mode": "persona",
            "persona_id": "offline-persona",
            "evaluation_dimensions": ["time_pressure"],
            "dimensions": {"time_pressure": "Deadline"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            result_path = self._fixture(
                Path(temporary),
                persona="offline-persona",
                persona_meta=persona_meta,
                opening="Please find this quickly.",
            )
            artifacts = load_run_artifacts(result_path)
            self.assertEqual(artifacts.persona_mode, "persona")
            self.assertEqual(
                artifacts.persona_meta["dimensions"]["time_pressure"], "Deadline"
            )
            judge = _FakeEvaluationJudge(self._task()["rubrics"].keys())
            judgement = assemble_judgement(
                artifacts=artifacts,
                standard_result=self._standard(),
                judge_call=judge,
                endpoint_meta={"model": "offline"},
                max_images=0,
                max_steps=0,
            )
            self.assertEqual(len(judge.calls), 3)
            self.assertTrue(judgement["persona"]["adherence"]["applicable"])
            self.assertEqual(
                judgement["persona"]["alignment"]["persona_alignment_score"], 0.75
            )
            self.assertTrue(judgement["persona"]["contexts"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
