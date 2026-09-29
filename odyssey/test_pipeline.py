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
               for name in ("event-pro", "older-city-visitor")}
    assert "65-74" in prompts["older-city-visitor"]
    assert "Experienced" in prompts["event-pro"]
    assert prompts["event-pro"] != prompts["older-city-visitor"]
    # The profile carries no task: the need is added separately, per task.
    for p in prompts.values():
        assert "Baltimore" not in p


def test_persona_assignments():
    assignments = json.loads((HERE / "persona_assignments.json").read_text())
    assert {t["task_id"] for t in R.TASKS if "real" not in t} <= assignments.keys()
    # REAL tasks get their personas later; any already assigned must exist.
    for t in R.TASKS:
        for name in assignments.get(t["task_id"], []) if "real" in t else []:
            assert (HERE / "personas" / f"{name}.yaml").is_file(), name
    assert {"clawbench-v1-794", "clawbench-v2-1102"} <= assignments.keys()
    names = [name for group in assignments.values() for name in group]
    assert len(names) == len(set(names)) == 24
    assert all(len(group) == 3 for group in assignments.values())
    assert all((HERE / "personas" / f"{name}.yaml").is_file() for name in names)


def test_provider_clients():
    keys = ("QWEN_BASE_URL", "QWEN_API_KEY", "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY")
    old = {key: R.os.environ.get(key) for key in keys}
    try:
        R.os.environ.update({
            "QWEN_BASE_URL": "http://qwen.test/v1",
            "QWEN_API_KEY": "",
            "AZURE_OPENAI_ENDPOINT": "https://judge.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
        })
        qwen, qwen_provider = R._client("qwen", "qwen")
        azure, azure_provider = R._client("judge", "azure")
        assert qwen_provider == "qwen" and str(qwen.base_url) == "http://qwen.test/v1/"
        assert azure_provider == "azure"
        assert str(azure.base_url) == "https://judge.openai.azure.com/openai/v1/"
        qwen.close()
        azure.close()
    finally:
        for key, value in old.items():
            if value is None:
                R.os.environ.pop(key, None)
            else:
                R.os.environ[key] = value


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
    assert "65-74" not in client.seen_system
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

    user = R.PersonaUser(task, HERE / "personas" / "older-city-visitor.yaml", "stub")
    system = client.sent[0][0]["content"]
    assert "65-74" in system                      # persona profile
    assert task["confirmed_task"] in system       # hidden need
    assert user.opening == client.reply           # said in its own words
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


def test_skip_existing_ignores_unscored(tmp: Path = Path("/tmp")):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        scored, unscored = Path(d) / "a.json", Path(d) / "b.json"
        scored.write_text(json.dumps({"judgement": {"score": 0.5}}))
        unscored.write_text(json.dumps({"judgement": {"score": None, "error": "x"}}))
        assert R._is_scored(scored)
        assert not R._is_scored(unscored)
        assert not R._is_scored(Path(d) / "missing.json")


def test_complete_run_can_be_judged_later(tmp: Path = Path("/tmp")):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        complete = Path(d) / "complete.json"
        failed = Path(d) / "failed.json"
        complete.write_text(json.dumps({"run": {"answer": "done", "stop_reason": "finish"}}))
        failed.write_text(json.dumps({"run": {"answer": "", "stop_reason": "no_model_output"}}))
        assert R._is_complete_run(complete)
        assert not R._is_complete_run(failed)


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
    test_persona_assignments()
    test_provider_clients()
    run = test_agent_loop(None)
    test_persona_user()
    test_budget_exhausted_still_answers()
    test_mute_model_is_not_scored_as_zero()
    test_judge_failure_keeps_the_run(run)
    test_extract_json()
    test_skip_existing_ignores_unscored()
    test_complete_run_can_be_judged_later()
    test_judge(run)
    print("odyssey pipeline self-check OK")
