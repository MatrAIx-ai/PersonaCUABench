"""Offline self-check: the whole pipeline with the LLM and the browser stubbed.

No API key, no network, no Chromium. Fails if task loading, persona injection,
the tool loop or the rubric scoring breaks.

    python odyssey/test_pipeline.py
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run as R  # noqa: E402


def test_tasks():
    # Invariants only, not the count: teammates add tasks to tasks.json.
    assert len(R.TASKS) >= 2, len(R.TASKS)
    ids = [t["task_id"] for t in R.TASKS]
    assert len(set(ids)) == len(ids), "duplicate task_id in tasks.json"
    for t in R.TASKS:
        assert t["rubrics"] and t["confirmed_task"].strip() and t["level"]
    assert R.resolve_tasks("2", False)[0]["task_id"] == R.TASKS[1]["task_id"]
    assert len(R.resolve_tasks("1,3", False)) == 2
    assert R.resolve_tasks(R.TASKS[4]["task_id"][:8], False)[0] is R.TASKS[4]
    assert len(R.resolve_tasks(None, True)) == len(R.TASKS)


def test_personas_differ():  # the profiles the persona LLM is given
    prompts = {name: R.persona_lib.persona_system_prompt(HERE / "personas" / f"{name}.yaml")
               for name in ("travel-expert", "elderly-novice")}
    assert "75-84" in prompts["elderly-novice"]
    assert "Frequent flyer" in prompts["travel-expert"]
    assert prompts["travel-expert"] != prompts["elderly-novice"]
    # The profile carries no task: the need is added separately, per task.
    for p in prompts.values():
        assert "Aurora" not in p


class _StubBrowser:
    """Records calls, returns canned page text; same surface run_agent uses."""

    def __init__(self, **_):
        self.calls = []

    def open_tab(self, url):
        self.calls.append(("open_tab", url))
        return f"tab 1 | Stub | {url}\n\nHigh 54F Low 39F"

    def open_tabs(self):
        return [{"tab_id": 1, "title": "Stub", "url": "https://example.com"}]

    def close(self):
        self.calls.append(("close", None))


def _tool_call(cid, name, args):
    return types.SimpleNamespace(
        id=cid, function=types.SimpleNamespace(name=name, arguments=json.dumps(args)))


class _StubUser:
    """Stands in for the persona LLM: a fixed opening, a canned reply."""

    def __init__(self, opening="I want to take the train to Aurora. Will it be cold?"):
        self.opening = opening
        self.transcript = [{"role": "user", "text": opening}]
        self.questions = []

    def reply(self, question):
        self.questions.append(question)
        answer = "The next three days, please."
        self.transcript += [{"role": "assistant", "text": question},
                            {"role": "user", "text": answer}]
        return answer

    def info(self):
        return {"model": "stub-user", "provider": "stub"}


class _StubClient:
    """Three turns: browse, ask the user, finish."""

    def __init__(self):
        self.turns = [
            _tool_call("c1", "open_tab", {"url": "https://www.google.com/search?q=x"}),
            _tool_call("c2", "ask_user", {"question": "How many days of forecast?"}),
            _tool_call("c3", "finish", {"summary": "High 54F, low 39F."}),
        ]
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))
        self.seen_system = None
        self.seen_first_user = None

    def _create(self, *, model, messages, tools, temperature):
        self.seen_system = messages[0]["content"]
        self.seen_first_user = messages[1]["content"]
        call = self.turns.pop(0)
        msg = types.SimpleNamespace(
            content=None, tool_calls=[call],
            model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": []})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_agent_loop(monkeypatched):
    client, user = _StubClient(), _StubUser()
    R._client = lambda model, provider="": (client, "stub")
    R.Browser = _StubBrowser
    run = R.run_agent(R.TASKS[0], user, "stub-model",
                      max_steps=5, headless=True, temperature=0.0)
    assert run["stop_reason"] == "finish", run["stop_reason"]
    assert run["answer"] == "High 54F, low 39F."
    assert [t["tool"] for t in run["trajectory"]] == ["open_tab", "ask_user", "finish"]
    assert run["open_tabs"][0]["url"] == "https://example.com"
    # ask_user reached the persona and its reply went back to the agent
    assert user.questions == ["How many days of forecast?"]
    assert "three days" in run["trajectory"][1]["result_preview"]
    assert len(run["conversation"]) == 3
    # The CUA carries no persona and never sees the hidden Odysseys text --
    # only what the user said.
    assert "75-84" not in client.seen_system
    assert client.seen_first_user == user.opening
    assert R.TASKS[0]["confirmed_task"][:60] not in client.seen_system
    return run


class _TextClient:
    """Plain-text chat stub for the persona LLM; records what it was sent."""

    def __init__(self, reply="Hi, how do I get to Aurora by train?"):
        self.reply, self.sent = reply, []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, *, model, messages, temperature=None, **kwargs):
        self.sent.append([dict(m) for m in messages])
        self.kwargs = dict(kwargs, temperature=temperature)
        msg = types.SimpleNamespace(content=self.reply, tool_calls=None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_persona_user():
    task = R.TASKS[0]
    client = _TextClient()
    R._client = lambda model, provider="": (client, "stub")

    user = R.PersonaUser(task, HERE / "personas" / "elderly-novice.yaml", "stub")
    system = client.sent[0][0]["content"]
    assert "75-84" in system                      # persona profile
    assert task["confirmed_task"] in system       # hidden need
    assert user.opening == client.reply           # said in its own words
    snapshot = user.info()["persona_profile"]
    assert snapshot["persona_id"] == "odyssey-elderly-novice"
    assert snapshot["evaluation_dimensions"]
    assert set(snapshot["evaluation_dimensions"]) == set(snapshot["evaluation_values"])
    assert len(snapshot["profile_sha256"]) == 64
    assert "75-84" in snapshot["profile_narrative"]
    assert user.reply("Which days?") == client.reply
    assert [t["role"] for t in user.transcript] == ["user", "assistant", "user"]

    # Control arm: no profile, and the opening is the Odysseys text verbatim
    # without an LLM call.
    client2 = _TextClient()
    R._client = lambda model, provider="": (client2, "stub")
    control = R.PersonaUser(task, None, "stub")
    assert control.opening == task["confirmed_task"]
    assert client2.sent == []


class _NeverFinishesClient(_StubClient):
    """Always browses, never calls finish -- the out-of-budget case."""

    def _create(self, *, model, messages, tools=None, temperature):
        self.seen_system = messages[0]["content"]
        if tools is None:  # the forced final-summary call carries no tools
            msg = types.SimpleNamespace(
                content="Partial: I found the BNSF line.", tool_calls=[],
                model_dump=lambda exclude_none=True: {"role": "assistant"})
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
        call = _tool_call("c", "open_tab", {"url": "https://example.com"})
        msg = types.SimpleNamespace(
            content=None, tool_calls=[call],
            model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": []})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_budget_exhausted_still_answers():
    R._client = lambda model, provider="": (_NeverFinishesClient(), "stub")
    R.Browser = _StubBrowser
    run = R.run_agent(R.TASKS[0], _StubUser(), "stub-model",
                      max_steps=3, headless=True, temperature=0.0)
    assert run["stop_reason"] == "max_steps_summarised", run["stop_reason"]
    assert run["answer"] == "Partial: I found the BNSF line."
    assert run["steps"] == 3


class _MuteClient(_StubClient):
    """Returns neither content nor tool calls -- the API-hiccup case."""

    def __init__(self):
        super().__init__()
        self.calls = 0

    def _create(self, *, model, messages, tools=None, temperature):
        self.calls += 1
        msg = types.SimpleNamespace(
            content=None, tool_calls=[],
            model_dump=lambda exclude_none=True: {"role": "assistant"})
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


def test_mute_model_is_not_scored_as_zero():
    client = _MuteClient()
    R._client = lambda model, provider="": (client, "stub")
    R.Browser = _StubBrowser
    real_sleep, R.time.sleep = R.time.sleep, lambda *_: None
    try:
        run = R.run_agent(R.TASKS[0], _StubUser(), "stub",
                          max_steps=10, headless=True, temperature=0.0)
    finally:
        R.time.sleep = real_sleep
    # Three retries, then give up -- and never a forced summary, which is what
    # used to turn a mute API into a confident 0.0.
    assert run["stop_reason"] == "no_model_output", run["stop_reason"]
    assert client.calls == 3, client.calls
    assert run["answer"] == "" and run["steps"] == 0


def test_judge_failure_keeps_the_run(run):
    """An unusable judge response must not throw away the browse it grades."""
    client = _TextClient(reply="")          # the judge answers with nothing
    R._client = lambda model, provider="": (client, "stub")
    R.time = types.SimpleNamespace(sleep=lambda *_: None)

    j = R.judge_run(R.TASKS[0], run, judge_model="stub", judge_provider="stub")
    assert j["score"] is None and j["met"] is None and j["error"]
    assert len(client.sent) == 3            # retried, then gave up
    R.time = __import__("time")


def test_extract_json():
    assert R.extract_json('{"R1": {"met": true}}') == {"R1": {"met": True}}
    assert R.extract_json('```json\n{"R1": {"met": false}}\n```') == {"R1": {"met": False}}
    assert R.extract_json("Here you go: {\"a\": 1} -- done") == {"a": 1}
    assert R.extract_json("") is None
    assert R.extract_json("no json here") is None
    assert R.extract_json("[1, 2]") is None


def test_azure_key_file_config():
    """Azure aliases may point at a file, so the key stays out of .env."""
    import os
    import tempfile

    names = (
        "OPENAI_API_KEY", "OPENAI_API_KEY_FILE", "OPENAI_BASE_URL",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY_FILE",
        "AZURE_OPENAI_BASE_URL",
    )
    before = {name: os.environ.get(name) for name in names}
    try:
        for name in names:
            os.environ.pop(name, None)
        with tempfile.TemporaryDirectory() as d:
            key_file = Path(d) / "azure.key"
            key_file.write_text("test-secret\n", encoding="utf-8")
            # Stale direct OpenAI settings must not be mixed with Azure.
            os.environ["OPENAI_API_KEY"] = "wrong-secret"
            os.environ["OPENAI_BASE_URL"] = "https://wrong.example/v1"
            os.environ["AZURE_OPENAI_API_KEY_FILE"] = str(key_file)
            os.environ["AZURE_OPENAI_BASE_URL"] = "https://example.test/openai/v1"
            key, base_url = R._provider_config("openai")
            assert key == "test-secret"
            assert base_url == "https://example.test/openai/v1"
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_persona_fidelity_contract():
    import copy
    import persona_fidelity_judge as fidelity

    snapshot = {
        "persona_id": "odyssey-budget-student",
        "version": "2.0",
        "profile_sha256": "a" * 64,
        "evaluation_dimensions": ["tech_savviness", "economic_motivation"],
        "evaluation_values": {
            "tech_savviness": "Digital native",
            "economic_motivation": "Cost-sensitive",
        },
    }
    record = {
        "task_id": R.TASKS[0]["task_id"],
        "task_snapshot": {
            **R.TASKS[0],
            "confirmed_task": "FROZEN KOBE TASK",
        },
        "persona": "budget-student",
        "run": {
            "answer": "stub",
            "user": {"model": "stub", "provider": "stub", "persona_profile": snapshot},
            "conversation": [
                {"role": "user", "text": "Please keep it quick and show me cheaper Kobe shoes."},
                {"role": "assistant", "text": "Do you care about size?"},
                {"role": "user", "text": "Men's 10, and I want a page I can check myself."},
            ],
        },
    }
    rendered = fidelity.build_prompt(record)
    assert '"expected_value": "Cost-sensitive"' in rendered
    assert "PERSON TURN 1: Please keep it quick" in rendered
    assert "Do you care about size?" not in rendered
    assert "FROZEN KOBE TASK" in rendered
    task, integrity = R.task_for_record(record)
    assert task["confirmed_task"] == "FROZEN KOBE TASK"
    assert integrity == "frozen_snapshot"

    parsed = {
        "targets": [
            {"attribute": "tech_savviness", "score": 1, "expressed": False,
             "contradicted": False, "confidence": 0.7,
             "evidence": "quick", "note": "weak"},
            {"attribute": "economic_motivation", "score": 2, "expressed": True,
             "contradicted": False, "confidence": 0.9,
             "evidence": "cheaper", "note": "clear"},
        ],
        "fidelity_issues": [],
        "judge_confidence": 0.8,
    }
    normalized = fidelity.normalize_verdict(
        parsed, model="stub-judge", provider="stub", snapshot=snapshot
    )
    assert normalized["expressed_target_count"] == 1
    assert normalized["total_target_count"] == 2
    assert normalized["contradicted_target_count"] == 0
    assert normalized["judge"] == {
        "model": "stub-judge", "provider": "stub", "backend": "stub"
    }
    assert normalized["profile_integrity"] == "frozen_snapshot"
    assert all(item["criterion_source"] == "declared_profile_dimension"
               for item in normalized["targets"])

    invalid_cases = []
    boolean_score = copy.deepcopy(parsed)
    boolean_score["targets"][0]["score"] = True
    invalid_cases.append(boolean_score)
    mismatch = copy.deepcopy(parsed)
    mismatch["targets"][0]["expressed"] = True
    invalid_cases.append(mismatch)
    bad_confidence = copy.deepcopy(parsed)
    bad_confidence["targets"][0]["confidence"] = 1.1
    invalid_cases.append(bad_confidence)
    boolean_confidence = copy.deepcopy(parsed)
    boolean_confidence["targets"][0]["confidence"] = True
    invalid_cases.append(boolean_confidence)
    no_evidence = copy.deepcopy(parsed)
    no_evidence["targets"][1]["evidence"] = ""
    invalid_cases.append(no_evidence)
    bad_issue = copy.deepcopy(parsed)
    bad_issue["fidelity_issues"] = [123]
    invalid_cases.append(bad_issue)
    duplicate = copy.deepcopy(parsed)
    duplicate["targets"].append(copy.deepcopy(duplicate["targets"][0]))
    invalid_cases.append(duplicate)
    missing = copy.deepcopy(parsed)
    missing["targets"].pop()
    invalid_cases.append(missing)
    for invalid in invalid_cases:
        try:
            fidelity.normalize_verdict(
                invalid, model="stub-judge", provider="stub", snapshot=snapshot
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid fidelity verdict must be rejected")


def test_experience_uses_frozen_profile():
    import experience_judge

    record = {
        "task_id": R.TASKS[0]["task_id"],
        "task_snapshot": {
            **R.TASKS[0],
            "confirmed_task": "FROZEN EXPERIENCE TASK",
        },
        "persona": "budget-student",
        "run": {
            "answer": "stub",
            "trajectory": [],
            "open_tabs": [],
            "conversation": [{"role": "user", "text": "A short request."}],
            "user": {"persona_profile": {"profile_narrative": "FROZEN PROFILE"}},
        },
    }
    rendered = experience_judge.build_prompt(record)
    assert "FROZEN PROFILE" in rendered
    assert "FROZEN EXPERIENCE TASK" in rendered
    complete = {
        "a": {dimension: {"score": 4} for dimension in experience_judge.DIMENSIONS},
        "b": {dimension: {"score": 4} for dimension in experience_judge.DIMENSIONS},
    }
    assert experience_judge.experience_complete(complete)
    complete["a"]["error"] = "transient"
    assert not experience_judge.experience_complete(complete)


def test_skip_existing_ignores_unscored(tmp: Path = Path("/tmp")):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        scored, unscored = Path(d) / "a.json", Path(d) / "b.json"
        scored.write_text(json.dumps({"judgement": {"score": 0.5}}))
        unscored.write_text(json.dumps({"judgement": {"score": None, "error": "x"}}))
        assert R._is_scored(scored)
        assert not R._is_scored(unscored)
        assert not R._is_scored(Path(d) / "missing.json")


def test_judge(run):
    task = R.TASKS[0]
    rids = list(task["rubrics"])
    # met: first two items; communicated: first three
    fake = {rid: {"met": i < 2, "communicated": i < 3, "reason": "stub"}
            for i, rid in enumerate(rids)}
    client = _TextClient(reply=json.dumps(fake))
    R._client = lambda model, provider="": (client, "stub")

    j = R.judge_run(task, run, judge_model="stub-judge", judge_provider="stub")
    # reasoning-model call shape: no temperature, max_completion_tokens
    assert client.kwargs["temperature"] is None
    assert client.kwargs["max_completion_tokens"] == 8000
    assert j["met"] == 2 and j["total"] == len(rids)
    assert j["score"] == round(2 / len(rids), 3)
    assert j["trajectory_efficiency"] == round(2 / len(rids) / run["steps"], 4)
    # score over only what the user actually communicated: 2 of those 3
    assert j["communicated"] == 3 and j["score_communicated"] == round(2 / 3, 3)


if __name__ == "__main__":
    test_tasks()
    test_personas_differ()
    run = test_agent_loop(None)
    test_persona_user()
    test_budget_exhausted_still_answers()
    test_mute_model_is_not_scored_as_zero()
    test_judge_failure_keeps_the_run(run)
    test_extract_json()
    test_azure_key_file_config()
    test_persona_fidelity_contract()
    test_experience_uses_frozen_profile()
    test_skip_existing_ignores_unscored()
    test_judge(run)
    print("odyssey pipeline self-check OK")
