"""Persona-aware OSWorld interaction loop.

The core loop is intentionally independent of OSWorld imports.  Tests can pass
small fake agents and environments, while :func:`create_osworld_runtime` lazily
loads the pinned local OSWorld checkout for real runs.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, MutableSequence, Sequence

from personacuabench.protocol import (
    Clarification,
    ResponseKind,
    classify_response,
    compose_cua_instruction,
)


ConversationTurn = dict[str, Any]
AnswerUser = Callable[[str, list[ConversationTurn]], str]
OpenTabsCollector = Callable[[Any], Sequence[Mapping[str, Any]]]
EnvironmentPreflight = Callable[[Any], Mapping[str, Any]]


class InteractionLoopError(RuntimeError):
    """Raised when the agent/environment cannot produce a valid trial."""


@dataclass
class RunOutcome:
    """Serializable result of one Persona x task interaction."""

    status: str
    stop_reason: str
    answer: str | None
    conversation: list[ConversationTurn]
    open_tabs: list[dict[str, Any]]
    agent_turns: int
    env_actions: int
    questions_asked: int
    questions_answered: int
    max_questions: int
    osworld_result_marker: float
    trajectory_path: str
    conversation_path: str
    environment_preflight: dict[str, Any] | None = None
    screenshot_files: list[str] = field(default_factory=list)
    recording_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OSWorldRuntime:
    """Real OSWorld objects plus the process working-directory lease.

    OSWorld V1's VMware manager uses relative registry and VM paths, so its
    working directory must remain the OSWorld checkout for the runtime's entire
    lifetime.  This factory is therefore intended for the benchmark's
    single-process/single-VM launcher, not concurrent in-process use.
    """

    agent: Any
    env: Any
    osworld_root: Path
    previous_cwd: Path
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.env.close()
        finally:
            os.chdir(self.previous_cwd)
            self._closed = True

    def __enter__(self) -> "OSWorldRuntime":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _action_timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d@%H%M%S%f")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, default=str))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
    )


def _copy_conversation(conversation: Sequence[ConversationTurn]) -> list[ConversationTurn]:
    return [dict(turn) for turn in conversation]


def _append_conversation_turn(
    conversation: MutableSequence[ConversationTurn],
    conversation_path: Path,
    *,
    role: str,
    content: str,
    event_type: str,
    turn: int,
) -> ConversationTurn:
    item: ConversationTurn = {
        "role": role,
        "content": content,
        "event_type": event_type,
        "turn": turn,
    }
    conversation.append(item)
    _append_jsonl(conversation_path, item)
    return item


def _screenshot_bytes(observation: Mapping[str, Any] | None) -> bytes | None:
    if not observation:
        return None
    value = observation.get("screenshot")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str) and value.strip():
        encoded = value.strip()
        if encoded.startswith("data:") and "," in encoded:
            encoded = encoded.split(",", 1)[1]
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return None
    return None


def _save_screenshot(
    result_dir: Path,
    observation: Mapping[str, Any] | None,
    *,
    agent_turn: int,
    event_index: int,
    timestamp: str,
) -> str | None:
    screenshot = _screenshot_bytes(observation)
    if not screenshot:
        return None
    filename = f"step_{agent_turn}_{event_index}_{timestamp}.png"
    (result_dir / filename).write_bytes(screenshot)
    return filename


def _reset_agent(agent: Any, env: Any, runtime_logger: Any = None) -> None:
    reset = getattr(agent, "reset", None)
    if not callable(reset):
        return
    vm_ip = getattr(env, "vm_ip", None)
    if runtime_logger is not None:
        try:
            reset(runtime_logger, vm_ip=vm_ip)
            return
        except TypeError:
            pass
    try:
        reset(vm_ip=vm_ip)
    except TypeError:
        reset()


def _prompt_agent_history_snapshot(agent: Any) -> dict[str, list[Any]] | None:
    """Capture OSWorld PromptAgent history before a prediction attempt.

    ``PromptAgent.predict`` appends the current observation before calling the
    model.  When the transport fails it also appends an empty thought, but no
    action, leaving the three history lists out of sync.  A retry must therefore
    roll those mutations back before asking for the same observation again.

    Requiring all three list attributes avoids treating unrelated fake/custom
    agent bookkeeping (for example, a list of observations passed to predict)
    as PromptAgent history.
    """
    names = ("observations", "actions", "thoughts")
    values = [getattr(agent, name, None) for name in names]
    if not all(isinstance(value, list) for value in values):
        return None
    return {name: list(value) for name, value in zip(names, values)}


def _restore_prompt_agent_history(
    agent: Any, snapshot: Mapping[str, Sequence[Any]] | None
) -> None:
    if snapshot is None:
        return
    for name, prior in snapshot.items():
        current = getattr(agent, name, None)
        if isinstance(current, list):
            current[:] = prior
        else:
            setattr(agent, name, list(prior))


def _predict_with_retries(
    *,
    agent: Any,
    instruction: str,
    observation: Mapping[str, Any],
    retries: int,
    retry_seconds: float,
    warnings: list[str],
) -> Any:
    """Retry a prediction before any environment action has been executed.

    Only thrown prediction errors and empty model responses are retried.  A
    malformed non-empty control response remains a protocol failure so the
    benchmark never silently turns invalid output into a different turn.
    """
    history = _prompt_agent_history_snapshot(agent)
    for attempt in range(retries + 1):
        try:
            prediction = agent.predict(instruction, observation)
        except Exception as exc:
            _restore_prompt_agent_history(agent, history)
            if attempt >= retries:
                raise InteractionLoopError(
                    f"agent.predict failed after {attempt + 1} attempt(s): {exc}"
                ) from exc
            warnings.append(
                "agent prediction retry "
                f"{attempt + 1}/{retries} after {type(exc).__name__}: {exc}"
            )
        else:
            if not isinstance(prediction, (tuple, list)) or len(prediction) != 2:
                raise InteractionLoopError(
                    "agent.predict must return (response, actions)"
                )
            raw_response = prediction[0]
            is_empty = raw_response is None or (
                isinstance(raw_response, str) and not raw_response.strip()
            )
            if not is_empty:
                return prediction

            # PromptAgent has already mutated its trajectory at this point.
            _restore_prompt_agent_history(agent, history)
            if attempt >= retries:
                return prediction
            warnings.append(
                f"agent prediction retry {attempt + 1}/{retries} after empty response"
            )

        if retry_seconds > 0:
            time.sleep(retry_seconds)

    raise AssertionError("prediction retry loop exhausted unexpectedly")


def _initial_observation(
    env: Any,
    *,
    task_config: Mapping[str, Any] | None,
    initial_observation: Mapping[str, Any] | None,
    ready_wait_seconds: float,
) -> Mapping[str, Any]:
    if initial_observation is not None:
        if task_config is not None:
            raise ValueError(
                "pass either task_config or initial_observation, not both"
            )
        return initial_observation

    if task_config is None:
        reset_observation = env.reset()
    else:
        reset_observation = env.reset(task_config=dict(task_config))
    if ready_wait_seconds > 0:
        time.sleep(ready_wait_seconds)
    get_observation = getattr(env, "_get_obs", None)
    observation = get_observation() if callable(get_observation) else reset_observation
    if not isinstance(observation, Mapping):
        raise InteractionLoopError("environment did not return an observation mapping")
    return observation


def _refresh_observation_after_preflight(
    env: Any,
    current: Mapping[str, Any],
    warnings: list[str],
) -> Mapping[str, Any]:
    """Refresh a potentially stale first frame without consuming an env step."""
    get_observation = getattr(env, "_get_obs", None)
    if not callable(get_observation):
        return current
    try:
        refreshed = get_observation()
    except Exception as exc:
        warnings.append(f"post-preflight observation refresh failed: {exc}")
        return current
    if not isinstance(refreshed, Mapping):
        warnings.append("post-preflight observation refresh returned a non-mapping")
        return current
    return refreshed


def _default_open_tabs_collector(env: Any) -> Sequence[Mapping[str, Any]]:
    from desktop_env.evaluators.getters.chrome import get_open_tabs_info

    return get_open_tabs_info(env, {})


def _collect_open_tabs(
    env: Any,
    collector: OpenTabsCollector | None,
    warnings: list[str],
) -> list[dict[str, Any]]:
    # A fake/non-browser environment should not need OSWorld installed merely to
    # exercise the interaction loop.
    if collector is None and not all(
        hasattr(env, attribute) for attribute in ("vm_ip", "chromium_port")
    ):
        return []
    actual_collector = collector or _default_open_tabs_collector
    try:
        raw_tabs = actual_collector(env)
        if raw_tabs is None:
            return []
        tabs: list[dict[str, Any]] = []
        for tab in raw_tabs:
            if isinstance(tab, Mapping):
                tabs.append(dict(tab))
            else:
                tabs.append({"value": str(tab)})
        return tabs
    except Exception as exc:  # Artifact collection must not invalidate the run.
        warnings.append(f"open-tabs collection failed: {exc}")
        return []


def _evaluate_marker(env: Any, warnings: list[str]) -> float:
    evaluate = getattr(env, "evaluate", None)
    if not callable(evaluate):
        return 0.0
    try:
        marker = float(evaluate())
        if not math.isfinite(marker):
            raise ValueError(f"non-finite marker {marker!r}")
        return marker
    except Exception as exc:
        # Odysseys uses an OSWorld placeholder evaluator.  Keep a numeric
        # completion marker so its independent rubric judge can still run, but
        # preserve the evaluator failure in warnings.
        warnings.append(f"OSWorld placeholder evaluation failed: {exc}")
        return 0.0


def _prepare_artifact_paths(result_dir: Path) -> tuple[Path, Path]:
    result_dir.mkdir(parents=True, exist_ok=True)
    trajectory_path = result_dir / "traj.jsonl"
    conversation_path = result_dir / "conversation.jsonl"
    for path in (trajectory_path, conversation_path):
        if path.exists() and path.stat().st_size:
            raise FileExistsError(
                f"refusing to append a new trial to non-empty artifact: {path}"
            )
    return trajectory_path, conversation_path


def run_interaction_loop(
    *,
    agent: Any,
    env: Any,
    opening_request: str,
    answer_user: AnswerUser,
    result_dir: str | Path,
    task_config: Mapping[str, Any] | None = None,
    initial_observation: Mapping[str, Any] | None = None,
    max_steps: int = 50,
    max_questions: int = 5,
    sleep_after_execution: float = 1.0,
    ready_wait_seconds: float = 0.0,
    settle_seconds: float = 0.0,
    prediction_retries: int = 1,
    prediction_retry_seconds: float = 2.0,
    collect_open_tabs: OpenTabsCollector | None = None,
    environment_preflight: EnvironmentPreflight | None = None,
    runtime_logger: Any = None,
    reset_agent: bool = True,
) -> RunOutcome:
    """Run one Persona/CUA interaction and persist OSWorld-compatible artifacts.

    ``answer_user`` is called as ``answer_user(question, conversation)``.  The
    supplied conversation already contains the assistant's question and is a
    detached list of dictionaries, so a PersonaSession wrapper may safely keep
    its own memory.

    Agent turns, including ``ASK_USER`` turns, consume ``max_steps``.  Only real
    UI actions and the final ``DONE`` action call ``env.step``.  An ASK reuses the
    current observation.  On the sixth question with the default budget, the
    run stops with ``question_limit_exceeded`` without calling ``answer_user``.
    """

    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if max_questions < 0:
        raise ValueError("max_questions must be non-negative")
    if prediction_retries < 0:
        raise ValueError("prediction_retries must be non-negative")
    if (
        sleep_after_execution < 0
        or ready_wait_seconds < 0
        or settle_seconds < 0
        or prediction_retry_seconds < 0
    ):
        raise ValueError("sleep durations must be non-negative")
    # Validation preserves the original bytes/string for the first CUA call.
    first_instruction = compose_cua_instruction(opening_request)
    output_dir = Path(result_dir).expanduser().resolve()
    trajectory_path, conversation_path = _prepare_artifact_paths(output_dir)

    conversation: list[ConversationTurn] = []
    clarifications: list[Clarification] = []
    screenshot_files: list[str] = []
    warnings: list[str] = []
    answer: str | None = None
    stop_reason = "max_steps"
    agent_turns = 0
    env_actions = 0
    questions_asked = 0
    questions_answered = 0
    started_at = _utc_now()
    recording_started = False
    recording_finished = False
    recording_path = output_dir / "recording.mp4"
    preflight_result: dict[str, Any] | None = None

    _append_conversation_turn(
        conversation,
        conversation_path,
        role="user",
        content=opening_request,
        event_type="opening",
        turn=0,
    )

    observation = _initial_observation(
        env,
        task_config=task_config,
        initial_observation=initial_observation,
        ready_wait_seconds=ready_wait_seconds,
    )
    if reset_agent:
        _reset_agent(agent, env, runtime_logger)

    # This hook intentionally runs only after the task reset has completed: a
    # VMware reset may replace the guest controller.  It also runs before
    # recording and before the first model prediction, so the diagnostic never
    # consumes an agent step, changes the browser state, or reaches the CUA
    # prompt.  A failed diagnostic must not invalidate the raw benchmark run.
    if environment_preflight is not None:
        try:
            raw_preflight = environment_preflight(env)
            if not isinstance(raw_preflight, Mapping):
                raise TypeError("environment preflight must return a mapping")
            preflight_result = dict(raw_preflight)
        except Exception as exc:
            warnings.append(
                "environment preflight failed; availability adjustment disabled: "
                f"{type(exc).__name__}: {exc}"
            )
            preflight_result = {
                "schema_version": "persona-cua-network-preflight/v1",
                "phase": "after_reset_before_agent",
                "status": "error",
                "adjustment_eligible": False,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "started_at": _utc_now(),
                "finished_at": _utc_now(),
            }
        _write_json(output_dir / "network_preflight.json", preflight_result)
        observation = _refresh_observation_after_preflight(
            env,
            observation,
            warnings,
        )

    controller = getattr(env, "controller", None)
    start_recording = getattr(controller, "start_recording", None)
    if callable(start_recording):
        try:
            start_recording()
            recording_started = True
        except Exception as exc:
            warnings.append(f"recording could not be started: {exc}")

    try:
        for agent_turn in range(1, max_steps + 1):
            agent_turns = agent_turn
            instruction = (
                first_instruction
                if not clarifications
                else compose_cua_instruction(opening_request, clarifications)
            )
            prediction = _predict_with_retries(
                agent=agent,
                instruction=instruction,
                observation=observation,
                retries=prediction_retries,
                retry_seconds=prediction_retry_seconds,
                warnings=warnings,
            )
            raw_response, raw_actions = prediction
            parsed = classify_response(raw_response)

            if parsed.kind is ResponseKind.ASK_USER:
                if raw_actions is None:
                    raise InteractionLoopError(
                        "agent parser rejected ASK_USER (is allow_ask_user enabled?)"
                    )
                if isinstance(raw_actions, str):
                    ask_actions = [raw_actions]
                else:
                    try:
                        ask_actions = list(raw_actions)
                    except TypeError as exc:
                        raise InteractionLoopError(
                            "ASK_USER actions must be an empty iterable"
                        ) from exc
                if ask_actions:
                    raise InteractionLoopError(
                        "ASK_USER must not be accompanied by an environment action"
                    )
                questions_asked += 1
                _append_conversation_turn(
                    conversation,
                    conversation_path,
                    role="assistant",
                    content=parsed.text,
                    event_type="ask_user",
                    turn=agent_turn,
                )
                timestamp = _action_timestamp()
                screenshot_file = _save_screenshot(
                    output_dir,
                    observation,
                    agent_turn=agent_turn,
                    event_index=1,
                    timestamp=timestamp,
                )
                if screenshot_file:
                    screenshot_files.append(screenshot_file)

                if questions_answered >= max_questions:
                    _append_jsonl(
                        trajectory_path,
                        {
                            "step_num": agent_turn,
                            "event_type": "ask_user",
                            "action_timestamp": timestamp,
                            "action": "",
                            "response": raw_response,
                            "question": parsed.text,
                            "persona_answer": None,
                            "reward": 0,
                            "done": True,
                            "info": {"question_limit_exceeded": True},
                            "screenshot_file": screenshot_file,
                        },
                    )
                    stop_reason = "question_limit_exceeded"
                    break

                if not callable(answer_user):
                    raise InteractionLoopError(
                        "agent asked the user, but no answer_user callable is available"
                    )
                persona_answer = answer_user(
                    parsed.text,
                    _copy_conversation(conversation),
                )
                if not isinstance(persona_answer, str) or not persona_answer.strip():
                    raise InteractionLoopError("answer_user returned an empty answer")
                persona_answer = persona_answer.strip()
                questions_answered += 1
                clarifications.append(
                    Clarification(question=parsed.text, answer=persona_answer)
                )
                _append_conversation_turn(
                    conversation,
                    conversation_path,
                    role="user",
                    content=persona_answer,
                    event_type="user_answer",
                    turn=agent_turn,
                )
                _append_jsonl(
                    trajectory_path,
                    {
                        "step_num": agent_turn,
                        "event_type": "ask_user",
                        "action_timestamp": timestamp,
                        "action": "",
                        "response": raw_response,
                        "question": parsed.text,
                        "persona_answer": persona_answer,
                        "reward": 0,
                        "done": False,
                        "info": {},
                        "screenshot_file": screenshot_file,
                    },
                )
                # Deliberately do not call env.step: the same observation is used
                # after the persona answers.
                continue

            if parsed.kind is ResponseKind.FINAL_RESPONSE:
                answer = parsed.text
                _append_conversation_turn(
                    conversation,
                    conversation_path,
                    role="assistant",
                    content=answer,
                    event_type="final_response",
                    turn=agent_turn,
                )
                timestamp = _action_timestamp()
                observation, reward, done, info = env.step(
                    "DONE", sleep_after_execution
                )
                env_actions += 1
                screenshot_file = _save_screenshot(
                    output_dir,
                    observation,
                    agent_turn=agent_turn,
                    event_index=1,
                    timestamp=timestamp,
                )
                if screenshot_file:
                    screenshot_files.append(screenshot_file)
                _append_jsonl(
                    trajectory_path,
                    {
                        "step_num": agent_turn,
                        "event_type": "final_response",
                        "action_timestamp": timestamp,
                        "action": "DONE",
                        "response": raw_response,
                        "reward": reward,
                        "done": bool(done),
                        "info": info,
                        "screenshot_file": screenshot_file,
                    },
                )
                stop_reason = "final_response"
                break

            if raw_actions is None:
                raise InteractionLoopError("agent returned no actions")
            if isinstance(raw_actions, str):
                actions = [raw_actions]
            else:
                try:
                    actions = list(raw_actions)
                except TypeError as exc:
                    raise InteractionLoopError(
                        "agent actions must be an iterable"
                    ) from exc
            if not actions:
                raise InteractionLoopError(
                    "ordinary agent response produced an empty action list"
                )

            environment_done = False
            for event_index, action in enumerate(actions, start=1):
                timestamp = _action_timestamp()
                observation, reward, done, info = env.step(
                    action, sleep_after_execution
                )
                env_actions += 1
                screenshot_file = _save_screenshot(
                    output_dir,
                    observation,
                    agent_turn=agent_turn,
                    event_index=event_index,
                    timestamp=timestamp,
                )
                if screenshot_file:
                    screenshot_files.append(screenshot_file)
                _append_jsonl(
                    trajectory_path,
                    {
                        "step_num": agent_turn,
                        "event_type": "action",
                        "action_timestamp": timestamp,
                        "action": action,
                        "response": raw_response,
                        "reward": reward,
                        "done": bool(done),
                        "info": info,
                        "screenshot_file": screenshot_file,
                    },
                )
                if done:
                    environment_done = True
                    stop_reason = (
                        "agent_fail"
                        if action == "FAIL"
                        or (isinstance(info, Mapping) and info.get("fail"))
                        else "environment_done"
                    )
                    break
            if environment_done:
                break

        if settle_seconds > 0:
            time.sleep(settle_seconds)

        open_tabs = _collect_open_tabs(env, collect_open_tabs, warnings)
        _write_json(output_dir / "open_tabs.json", open_tabs)

        marker = _evaluate_marker(env, warnings)

        end_recording = getattr(controller, "end_recording", None)
        if recording_started and callable(end_recording):
            try:
                end_recording(str(recording_path))
                recording_finished = True
            except Exception as exc:
                warnings.append(f"recording could not be finalized: {exc}")

        outcome = RunOutcome(
            status="complete",
            stop_reason=stop_reason,
            answer=answer,
            conversation=conversation,
            open_tabs=open_tabs,
            agent_turns=agent_turns,
            env_actions=env_actions,
            questions_asked=questions_asked,
            questions_answered=questions_answered,
            max_questions=max_questions,
            osworld_result_marker=marker,
            trajectory_path=str(trajectory_path),
            conversation_path=str(conversation_path),
            environment_preflight=preflight_result,
            screenshot_files=screenshot_files,
            recording_path=str(recording_path) if recording_finished else None,
            warnings=warnings,
            started_at=started_at,
            finished_at=_utc_now(),
        )
        _write_json(output_dir / "run_outcome.json", outcome.to_dict())
        # Existing Odysseys tooling treats result.txt as the completion marker.
        # Publish it last so an interrupted artifact write is never mistaken for
        # a completed, judgeable trial.
        _atomic_write_text(output_dir / "result.txt", f"{marker}\n")
        return outcome
    finally:
        if recording_started and not recording_finished:
            end_recording = getattr(controller, "end_recording", None)
            if callable(end_recording):
                try:
                    end_recording(str(recording_path))
                except Exception:
                    pass


def create_osworld_runtime(
    *,
    model: str = "gpt-5.6-terra",
    osworld_root: str | Path | None = None,
    provider_name: str = "vmware",
    path_to_vm: str | None = None,
    headless: bool = True,
    action_space: str = "pyautogui",
    observation_type: str = "screenshot",
    screen_width: int = 1920,
    screen_height: int = 1080,
    max_tokens: int = 8192,
    max_trajectory_length: int = 3,
    top_p: float = 0.9,
    temperature: float = 1.0,
    client_password: str = "password",
    enable_proxy: bool = True,
    allow_ask_user: bool = False,
    max_questions: int = 5,
) -> OSWorldRuntime:
    """Create the real pinned OSWorld environment and Azure agent.

    Azure endpoint/key/retry/reasoning settings remain environment-driven, just
    like the existing integration adapter.  No secret or endpoint is accepted or
    persisted here.  When ``allow_ask_user`` is false, the existing non-Persona
    agent prompt is unchanged.
    """

    if max_questions < 0:
        raise ValueError("max_questions must be non-negative")
    project_root = Path(__file__).resolve().parents[1]
    resolved_osworld = Path(
        osworld_root or (project_root / ".osworld" / "OSWorld")
    ).expanduser().resolve()
    if not (resolved_osworld / "desktop_env" / "desktop_env.py").is_file():
        raise FileNotFoundError(
            f"OSWorld checkout is missing or incomplete: {resolved_osworld}"
        )

    previous_cwd = Path.cwd()
    osworld_text = str(resolved_osworld)
    if osworld_text not in sys.path:
        sys.path.insert(0, osworld_text)
    os.chdir(resolved_osworld)
    try:
        from desktop_env.desktop_env import DesktopEnv
        from mm_agents.azure_foundry_agent import AzureFoundryPromptAgent

        agent = AzureFoundryPromptAgent(
            model=model,
            max_tokens=max_tokens,
            top_p=top_p,
            temperature=temperature,
            action_space=action_space,
            observation_type=observation_type,
            max_trajectory_length=max_trajectory_length,
            client_password=client_password,
            allow_ask_user=allow_ask_user,
        )

        env = DesktopEnv(
            provider_name=provider_name,
            path_to_vm=path_to_vm,
            action_space=action_space,
            cache_dir=str(resolved_osworld / "cache"),
            screen_size=(screen_width, screen_height),
            headless=headless,
            os_type="Ubuntu",
            require_a11y_tree=observation_type
            in {"a11y_tree", "screenshot_a11y_tree", "som"},
            enable_proxy=enable_proxy,
            client_password=client_password,
        )
    except Exception:
        os.chdir(previous_cwd)
        raise

    return OSWorldRuntime(
        agent=agent,
        env=env,
        osworld_root=resolved_osworld,
        previous_cwd=previous_cwd,
    )


__all__ = [
    "AnswerUser",
    "ConversationTurn",
    "InteractionLoopError",
    "OSWorldRuntime",
    "OpenTabsCollector",
    "RunOutcome",
    "create_osworld_runtime",
    "run_interaction_loop",
]
