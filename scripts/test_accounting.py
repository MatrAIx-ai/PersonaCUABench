"""Offline self-check for the meter, the model registry and the cost report.

No network, no API keys, no browser.

    python scripts/test_accounting.py
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import types
from pathlib import Path

# This test lives in scripts/; the code it exercises lives in src/.
REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import cost_report  # noqa: E402
import models as registry  # noqa: E402
import run as R  # noqa: E402


def fake_response(prompt=1000, completion=100, cost=None):
    usage = types.SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion,
                                  prompt_tokens_details=types.SimpleNamespace(
                                      cached_tokens=7))
    if cost is not None:
        usage.cost = cost
    return types.SimpleNamespace(usage=usage, choices=[])


def check_registry() -> None:
    # Resolution depends on what is configured, so the environment is pinned
    # here rather than inherited from whoever runs the test.
    import os

    watched = ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY",
               "AZURE_OPENAI_API_KEY_FILE", "OPENROUTER_API_KEY",
               "MINIMAX_BASE_URL", "MINIMAX_API_KEY")
    saved = {k: os.environ.get(k) for k in watched}
    try:
        for key in watched:
            os.environ.pop(key, None)
        # A raw id passes through untouched, with no route lookup at all.
        assert registry.resolve("qwen/qwen3.8-27b") == ("qwen/qwen3.8-27b", "")
        # With only OpenRouter configured, a key resolves there.
        os.environ["OPENROUTER_API_KEY"] = "k"
        assert registry.resolve("minimax-m3") == ("minimax/minimax-m3", "openrouter")
        assert registry.resolve("terra") == ("openai/gpt-5.6-terra", "openrouter")
        # Azure wins for a model deployed there, but only with credentials.
        os.environ["AZURE_OPENAI_BASE_URL"] = "https://example.invalid/openai/v1"
        os.environ["AZURE_OPENAI_API_KEY"] = "x"
        assert registry.resolve("terra") == ("gpt-5.6-terra", "openai")
        assert registry.resolve("minimax-m3") == ("minimax/minimax-m3", "openrouter")
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value
    # Prices come from the registry for either of a model's ids.
    assert registry.cost_of("minimax/minimax-m3", 1_000_000, 0) == 0.3
    assert registry.cost_of("gpt-5.6-terra", 1_000_000, 1_000_000) == 0.0
    assert registry.cost_of("not/a-model", 1_000_000, 0) is None


def check_model_routes() -> None:
    """Each model reaches its owner's endpoint first, then Azure, then OpenRouter."""
    import os

    saved = {k: os.environ.get(k) for k in
             ("GLM_BASE_URL", "GLM_API_KEY", "QWEN_BASE_URL", "QWEN_API_KEY",
              "OPENROUTER_API_KEY", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY")}

    def setenv(**values):
        for key in saved:
            os.environ.pop(key, None)
        os.environ.update({k: v for k, v in values.items() if v})

    try:
        # Nothing configured: a model must refuse, naming what is missing.
        setenv()
        try:
            registry.resolve("minimax-m3")
        except SystemExit as exc:
            assert "MINIMAX_BASE_URL" in str(exc) and "OPENROUTER_API_KEY" in str(exc)
        else:
            raise AssertionError("an unroutable model was resolved anyway")

        # Only OpenRouter: everything falls back to it.
        setenv(OPENROUTER_API_KEY="k")
        assert registry.resolve("minimax-m3") == ("minimax/minimax-m3", "openrouter")

        # The owner's own endpoint wins over the aggregator.
        setenv(OPENROUTER_API_KEY="k", MINIMAX_BASE_URL="https://vendor/v1",
               MINIMAX_API_KEY="v")
        assert registry.resolve("minimax-m3") == ("MiniMax-M3", "minimax-m3")
        key, base_url = R._provider_config("minimax-m3")
        assert (key, base_url) == ("v", "https://vendor/v1")

        # A local server may need no key at all.
        setenv(OPENROUTER_API_KEY="k", QWEN_BASE_URL="http://localhost:8000/v1")
        assert registry.resolve("qwen3.8-27b")[1] == "qwen3.8-27b"

        # Azure sits between the two for a model deployed there.
        setenv(OPENROUTER_API_KEY="k", AZURE_OPENAI_BASE_URL="https://azure/v1",
               AZURE_OPENAI_API_KEY="a")
        assert registry.resolve("gpt-6-astra") == ("gpt-6-astra", "openai")

        # An explicit provider is honoured even when unconfigured, so a forced
        # route fails loudly instead of silently using another vendor.
        assert registry.resolve("minimax-m3", "minimax-m3") == ("MiniMax-M3", "minimax-m3")
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None)
            if value is not None:
                os.environ[key] = value


def check_every_route_is_priced() -> None:
    """Every id a model can resolve to must have a price.

    price_for matched only the azure and openrouter ids, so a model reached
    through its own vendor endpoint -- the common case for a collaborator on a
    company gateway -- came back unpriced, and the report showed those cells as
    free. Qwen resolves to "Qwen/Qwen3.8-27B" and MiniMax to "MiniMax-M3";
    neither is the registry key or the OpenRouter id.
    """
    for key, entry in registry.MODELS.items():
        ids = {(entry.get("endpoint") or {}).get("model"),
               entry.get("azure"), entry.get("openrouter")} - {None}
        assert ids, f"{key} can be reached by no id at all"
        for model_id in ids:
            price = registry.price_for(model_id)
            assert price is not None, f"{key}: {model_id!r} has no price"

    # A model that needs /v1/responses for function tools must be routed to the
    # shim, or chat completions rejects the call and it looks incapable.
    assert registry.wants_responses_api("gpt-6-astra", "openai"), "Azure always"
    for key in ("gpt-6.1-sol", "gpt-6-luna"):
        model_id = registry.MODELS[key]["endpoint"]["model"]
        assert registry.wants_responses_api(model_id, key), key
    assert not registry.wants_responses_api("z-ai/anything", "openrouter")


def check_meter() -> None:
    meter = R.Meter()
    # A provider-reported charge wins over the list price.
    reported = meter.add("agent", "minimax/minimax-m3", "openrouter",
                         fake_response(cost=0.123), ms=1500)
    assert reported["cost_usd"] == 0.123 and reported["cost_source"] == "provider"
    assert reported["cached_prompt_tokens"] == 7
    # Without one, the registry prices it.
    priced = meter.add("agent", "minimax/minimax-m3", "openrouter",
                       fake_response(prompt=1_000_000, completion=0), ms=500)
    assert priced["cost_usd"] == 0.3 and priced["cost_source"] == "registry"
    # An unknown model is counted, not silently priced at zero.
    unknown = meter.add("rubric_judge", "mystery/model", "openrouter",
                        fake_response(), ms=10)
    assert unknown["cost_usd"] is None and unknown["cost_source"] == "unknown"

    # The shared Azure endpoint is not special: it is priced by the registry
    # like any other provider. It used to be zeroed as somebody else's bill,
    # which meant a whole grid's cost report read $0.00.
    azure = R.Meter().add("agent", "minimax/minimax-m3", "openai",
                          fake_response(prompt=1_000_000, completion=0), ms=100)
    assert azure["cost_usd"] == 0.3, azure
    assert azure["cost_source"] == "registry", azure

    totals = meter.totals()
    assert totals["calls"] == 3 and totals["unpriced_calls"] == 1
    assert totals["cost_usd"] == 0.423
    assert totals["model_ms"] == 2010
    assert totals["by_role"]["agent"]["calls"] == 2
    assert totals["by_role"]["rubric_judge"]["unpriced_calls"] == 1


def check_metered_call() -> None:
    """metered() times the call and asks OpenRouter to report its cost."""
    sent = {}

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    sent.update(kwargs)
                    return fake_response(cost=0.5)

    meter = R.Meter()
    resp, call = R.metered(Client(), meter, "agent", provider="openrouter",
                           model="minimax/minimax-m3", messages=[])
    assert sent["extra_body"] == {"usage": {"include": True}}
    assert call["cost_usd"] == 0.5 and call["ms"] >= 0
    # The openai/Azure provider goes through the Responses API instead, so the
    # reasoning summary reaches the stored turn; the caller still sees a chat
    # completion.
    responses_sent = {}

    class Azure:
        class responses:
            @staticmethod
            def create(**kwargs):
                responses_sent.update(kwargs)
                return types.SimpleNamespace(model_dump=lambda exclude_none=False: {
                    "output": [
                        {"type": "reasoning",
                         "summary": [{"type": "summary_text", "text": "weighing options"}]},
                        {"type": "message",
                         "content": [{"type": "output_text", "text": "ok"}]}],
                    "usage": {"input_tokens": 12, "output_tokens": 3,
                              "output_tokens_details": {"reasoning_tokens": 2}}})

    resp, call = R.metered(Azure(), R.Meter(), "agent", provider="openai",
                           model="gpt-5.6-terra", messages=[{"role": "user",
                                                             "content": "hi"}],
                           tools=R.TOOLS)
    assert responses_sent["input"] == [{"type": "message", "role": "user",
                                       "content": [{"type": "input_text",
                                                    "text": "hi"}]}]
    assert responses_sent["reasoning"] == {"summary": "auto"}
    assert responses_sent["tools"][0]["name"] == "open_tab"   # flattened schema
    assert "extra_body" not in responses_sent
    assert resp.choices[0].message.content == "ok"
    assert call["reasoning_tokens"] == 2 and call["prompt_tokens"] == 12
    assert R.dump_response(resp)["output"][0]["summary"][0]["text"] == "weighing options"

    # --no-responses-api falls back to chat completions on the same provider.
    R.RESPONSES_API = False
    try:
        sent.clear()
        R.metered(Client(), meter, "agent", provider="openai",
                  model="gpt-5.6-terra", messages=[])
        assert "extra_body" not in sent and sent["model"] == "gpt-5.6-terra"
    finally:
        R.RESPONSES_API = True


def cell_record(setting, model, task, cost, judge_cost, wall, steps=10):
    return {
        "setting": setting, "suite_id": "main-original", "level": "easy",
        "task_id": task + "0" * (40 - len(task)), "persona": "p", "replicate_id": "r1",
        "run": {"steps": steps, "arm": {"model": model, "provider": "openrouter"}},
        "judgement": {"score": 0.5},
        "accounting": {
            "cell_wall_seconds": wall, "prompt_tokens": 1000, "completion_tokens": 100,
            "cost_usd": cost + judge_cost, "unpriced_calls": 0, "per_call": [],
            "by_role": {"agent": {"cost_usd": cost, "ms": 1000},
                        "rubric_judge": {"cost_usd": judge_cost, "ms": 50}},
        },
        "experience": {"a": {"accounting": {"cost_usd": 0.01, "model_ms": 20}},
                       "b": {"accounting": {"cost_usd": 0.02, "model_ms": 30}}},
    }


def check_cache_marking() -> None:
    """Breakpoints go on the prefix providers can cache, and never accumulate."""
    history = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "help me"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "page one"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "2"}]},
        {"role": "tool", "tool_call_id": "2", "content": "page two"},
    ]
    # A provider that caches on its own is left completely alone.
    assert R.cache_marked(history, "minimax/minimax-m3") is history

    marked = R.cache_marked(history, "anthropic/claude-opus-5.5")
    breaks = [i for i, m in enumerate(marked) if isinstance(m["content"], list)]
    assert 0 in breaks, "the system prompt is always a breakpoint"
    assert len(breaks) <= R.CACHE_MAX_BREAKPOINTS, breaks
    assert 5 in breaks, "the newest tool result must be a breakpoint"
    part = marked[5]["content"][0]
    assert part == {"type": "text", "text": "page two",
                    "cache_control": {"type": "ephemeral", "ttl": R.CACHE_TTL}}
    # The originals keep plain strings, so a later step does not double-mark.
    assert all(isinstance(m["content"], (str, type(None))) for m in history)
    # An assistant turn with no text is skipped rather than marked empty.
    assert all(marked[i]["content"] is None for i in (2, 4))
    # Stripping is the inverse, for the retry after a provider refuses.
    assert R._strip_cache_control(marked)[5]["content"] == "page two"

    # A refusal disables marking for that model only, for the rest of the run.
    R._cache_refused.add("anthropic/claude-opus-5.5")
    try:
        assert R.cache_marked(history, "anthropic/claude-opus-5.5") is history
        assert R.needs_explicit_cache("qwen/qwen3.8-27b")
    finally:
        R._cache_refused.discard("anthropic/claude-opus-5.5")


def check_cache_switch() -> None:
    """--no-prompt-cache turns our breakpoints off without touching providers."""
    history = [{"role": "system", "content": "rules"},
               {"role": "user", "content": "help"}]
    assert R.PROMPT_CACHE is True
    R.PROMPT_CACHE = False
    try:
        assert R.cache_marked(history, "anthropic/claude-opus-5.5") is history
        assert not R.needs_explicit_cache("anthropic/claude-opus-5.5")
    finally:
        R.PROMPT_CACHE = True
    assert R.needs_explicit_cache("anthropic/claude-opus-5.5")


def check_cache_retry() -> None:
    """A provider that rejects cache_control gets one plain retry, not a crash."""
    seen = []

    class Picky:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    seen.append(kwargs["messages"])
                    if isinstance(kwargs["messages"][0]["content"], list):
                        raise ValueError("cache_control is not supported here")
                    return fake_response(cost=0.01)

    messages = R.cache_marked([{"role": "system", "content": "rules"}],
                              "anthropic/claude-opus-5.5")
    R._cache_refused.discard("anthropic/claude-opus-5.5")
    resp, call = R.metered(Picky(), R.Meter(), "agent", provider="openrouter",
                           model="anthropic/claude-opus-5.5", messages=messages)
    assert len(seen) == 2, seen
    assert seen[1][0]["content"] == "rules"
    assert call["cost_usd"] == 0.01
    assert "anthropic/claude-opus-5.5" in R._cache_refused
    R._cache_refused.discard("anthropic/claude-opus-5.5")


def check_judge_calls() -> None:
    """Both post-hoc judges must actually be callable, and bill what they spend.

    A NameError inside score_once once cost sixty cells their verdicts: the
    retry loop swallowed it three times per judge and wrote empty results.
    """
    import experience_judge

    class Fake:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    message = types.SimpleNamespace(
                        content='{"P5_overall": {"score": 4, "reason": "ok"}}')
                    return types.SimpleNamespace(
                        choices=[types.SimpleNamespace(message=message)],
                        usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=5,
                                                    prompt_tokens_details=None,
                                                    completion_tokens_details=None))

    saved = R._client
    R._client = lambda model, provider="": (Fake(), "openrouter")
    try:
        out = experience_judge.score_once("prompt", "minimax/minimax-m3")
        assert out["P5_overall"]["score"] == 4, out
        assert out["accounting"]["calls"] == 1 and out["accounting"]["cost_usd"] > 0

        # A programming error must surface, not be retried into an empty verdict.
        class Broken:
            class chat:
                class completions:
                    @staticmethod
                    def create(**_):
                        raise AttributeError("no attribute 'responses'")

        R._client = lambda model, provider="": (Broken(), "openrouter")
        try:
            experience_judge.score_once("prompt", "minimax/minimax-m3")
        except RuntimeError as exc:
            assert "broken" in str(exc)
        else:
            raise AssertionError("a broken judge call must raise, not retry")
    finally:
        R._client = saved


def check_progress_note_is_not_an_answer() -> None:
    """A tool-free turn is a nudge, not the end of the run.

    Astra pauses between tool calls to narrate ("the lecture is playing, I'll
    check the transcript next"). Treating that as the final answer closed the
    browser mid-task and scored an unfinished run as the agent's failure.
    """
    scripted = [
        ("text", "Opening the page now, I'll check the fares next."),
        ("tool", "open_tab"),
        ("text", "Loaded. Reading the timetable next."),
        ("finish", "High 54F, low 39F; BNSF fares are on the Metra page."),
    ]

    class Client:
        def __init__(self):
            self.turn = 0
            self.nudges = 0

        class chat:
            pass

        def create(self, **kwargs):
            self.nudges += sum(
                1 for m in kwargs["messages"]
                if m.get("role") == "user" and "not a tool call" in str(m.get("content")))
            kind, payload = scripted[self.turn]
            self.turn += 1
            call = None
            if kind == "tool":
                call = types.SimpleNamespace(id="c1", function=types.SimpleNamespace(
                    name=payload, arguments='{"url": "https://example.com"}'))
            elif kind == "finish":
                call = types.SimpleNamespace(id="c2", function=types.SimpleNamespace(
                    name="finish", arguments=json.dumps({"summary": payload})))
            message = types.SimpleNamespace(
                content=payload if kind == "text" else None,
                tool_calls=[call] if call else None,
                model_dump=lambda exclude_none=False: {"role": "assistant"})
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)],
                usage=types.SimpleNamespace(prompt_tokens=1, completion_tokens=1,
                                            prompt_tokens_details=None,
                                            completion_tokens_details=None))

    client = Client()
    client.chat.completions = types.SimpleNamespace(create=client.create)

    class Browser:
        def __init__(self, **_):
            pass

        def open_tab(self, url):
            return f"tab 1 | Stub | {url}"

        def open_tabs(self):
            return []

        def shot(self, *_, **__):
            return None

        def close(self):
            pass

    saved_client, saved_browser = R._client, R.Browser
    R._client = lambda model, provider="": (client, "openrouter")
    R.Browser = Browser
    try:
        run = R.run_agent(R.TASKS[0], _StubUser(), "stub", max_steps=10,
                          headless=True, temperature=1.0)
    finally:
        R._client, R.Browser = saved_client, saved_browser

    assert run["stop_reason"] == "finish", run["stop_reason"]
    assert run["answer"].startswith("High 54F"), run["answer"]
    assert client.nudges >= 1, "the model was never told to keep working"
    assert client.turn == len(scripted), "the run ended early"


class _StubUser:
    opening = "I want a transit plan from downtown Chicago to Aurora."
    transcript = [{"role": "user", "text": opening}]

    def reply(self, question):
        return "whatever you think"

    def info(self):
        return {"model": "stub", "provider": "stub"}


def check_real_judging() -> None:
    """A REAL task is scored by its checkers, and a broken checker is an error."""
    import glob, os, tempfile

    real_suite = None
    for suite in (R.TASK_CATALOG.suites.values()):
        if suite.suite_id == "real":
            real_suite = suite
    assert real_suite is not None, "the real suite is not registered"
    task = real_suite.tasks[0]
    assert task["real"]["eval_scripts"], task

    # A state the checker accepts vs one it rejects: same code path, both ways.
    passing = {"orderId": "1",
               "checkoutDetails": {"charges": {"totalAmount": 20.0}},
               "cartItems": [{"name": "Large Pizza", "price": 12.0}]}
    failing = {"orderId": "1",
               "checkoutDetails": {"charges": {"totalAmount": 20.0}},
               "cartItems": [{"name": "Salad", "price": 12.0}]}
    good = R.judge_real(task, {"real_state": passing, "steps": 4})
    bad = R.judge_real(task, {"real_state": failing, "steps": 4})
    assert good["score"] == 1.0 and good["met"] == 1, good
    assert bad["score"] == 0.0 and bad["met"] == 0, bad
    assert good["judge_model"] == "real-state-checker"
    assert good["communicated"] is None, "a checker cannot judge communication"

    # No state read: unscored with a reason, never a zero.
    unread = R.judge_real(task, {"real_state": None, "steps": 4,
                                 "real_state_error": "TimeoutError: /finish"})
    assert unread["score"] is None and "TimeoutError" in unread["error"], unread

    # A missing checker is an error about the repo, not a failing agent.
    broken = {**task, "real": {**task["real"], "eval_scripts": ["eval_nope.py"]}}
    gone = R.judge_real(broken, {"real_state": passing, "steps": 4})
    assert gone["score"] is None and "missing" in gone["error"], gone

    # A checker that crashes leaves the cell unscored so a resume retries it.
    with tempfile.TemporaryDirectory() as tmp:
        crasher = Path(tmp) / "eval_crash.py"
        crasher.write_text("import sys; sys.exit(3)", encoding="utf-8")
        saved = R.REAL_EVALS
        R.REAL_EVALS = Path(tmp)
        try:
            crashed = R.judge_real({**task, "real": {**task["real"],
                                                     "eval_scripts": ["eval_crash.py"]}},
                                   {"real_state": passing, "steps": 4})
        finally:
            R.REAL_EVALS = saved
    assert crashed["score"] is None and "exit 3" in crashed["error"], crashed


def check_real_manifest_checks() -> None:
    """The jmespath and llm_boolean checks the FlyUnified tasks carry.

    They have no vendored script at all, so a bug here would score every one of
    them as a pass on an empty sandbox.
    """
    flight = {"differences": {"bookedFlights": {"added": {"0": {
        "flight": {"outboundFlight": {
            "info": {"from": {"destination": {"city": "Orlando"}}},
            "selectedPrice": {"type": "Basic Economy"}}},
        "passengersInfo": [{"firstName": "John"}]}}}}}
    empty = {"differences": {"bookedFlights": {"added": {}}}}
    checks = [
        {"type": "jmespath", "expected_value": "Orlando",
         "query": 'differences.bookedFlights.added."0".flight.outboundFlight'
                  '.info.from.destination.city'},
        {"type": "jmespath", "expected_value": "Basic Economy",
         "query": 'differences.bookedFlights.added."0".flight.outboundFlight'
                  '.selectedPrice.type'},
    ]
    task = {"confirmed_task": "book the cheapest flight",
            "rubrics": {"R1": {"requirement": "x", "verification": "y"}},
            "real": {"id": "fly-unified-5", "eval_scripts": [], "checks": checks}}

    booked = R.judge_real(task, {"real_state": flight, "steps": 7, "answer": "done"})
    assert booked["score"] == 1.0, booked
    # Nothing booked: every query returns null, which must be a failure and not
    # an error -- an unbooked flight is exactly what the agent is graded on.
    nothing = R.judge_real(task, {"real_state": empty, "steps": 7, "answer": ""})
    assert nothing["score"] == 0.0 and not nothing.get("error"), nothing
    assert "FAIL" in json.loads(nothing["verdicts"]["R1"]["reason"])["jmespath[0]"]

    # One wrong value out of two is still a failure for the whole task.
    wrong = R.judge_real(
        {**task, "real": {**task["real"], "checks": [
            checks[0], {**checks[1], "expected_value": "Economy"}]}},
        {"real_state": flight, "steps": 7, "answer": "done"})
    assert wrong["score"] == 0.0, wrong

    # A malformed query is our bug: unscored with the parse error, never a zero.
    bad_query = R.judge_real(
        {**task, "real": {**task["real"],
                          "checks": [{"type": "jmespath", "query": "a]][",
                                      "expected_value": 1}]}},
        {"real_state": flight, "steps": 7, "answer": "done"})
    assert bad_query["score"] is None and bad_query["error"], bad_query

    # An llm_boolean check with no judge model must not be quietly skipped.
    llm = {"type": "llm_boolean", "expected_value": True,
           "rubric": "Did the agent say it booked the flight?"}
    unasked = R.judge_real({**task, "real": {**task["real"],
                                             "checks": [*checks, llm]}},
                           {"real_state": flight, "steps": 7, "answer": "booked it"})
    assert unasked["score"] is None and "llm_boolean" in unasked["error"], unasked

    # With a judge, the answer decides: the check passes when the judge agrees
    # with expected_value and fails when it does not, and neither is an error.
    task_llm = {**task, "real": {**task["real"], "checks": [llm]}}
    for said, want_score in ((True, 1.0), (False, 0.0)):
        reply = json.dumps({"answer": said, "reason": "because"})

        class Judge:
            class chat:
                class completions:
                    @staticmethod
                    def create(**_):
                        return types.SimpleNamespace(
                            choices=[types.SimpleNamespace(
                                message=types.SimpleNamespace(content=reply))],
                            usage=types.SimpleNamespace(
                                prompt_tokens=10, completion_tokens=5,
                                prompt_tokens_details=None,
                                completion_tokens_details=None))

        saved = R._client
        R._client = lambda model, provider="": (Judge(), "openrouter")
        try:
            got = R.judge_real(task_llm, {"real_state": flight, "steps": 7,
                                          "answer": "booked it"},
                               judge_model="stub-judge", judge_provider="stub",
                               meter=R.Meter())
        finally:
            R._client = saved
        assert got["score"] == want_score and not got.get("error"), (said, got)
        assert got["judge_model"] == "real-state-checker+stub-judge", got


def check_judge_b_is_optional() -> None:
    """A collaborator with only the shared Azure endpoint must still get scores.

    experience_judge resolved judge B inside score_once, outside its try, so a
    machine with no OpenRouter route lost the whole pass to a SystemExit on the
    first cell -- every cell then had no experience score at all.
    """
    import experience_judge as exp

    a = {d: {"score": 4, "reason": "ok"} for d in exp.DIMENSIONS}
    # A null B means "never configured here": complete, so a re-run does not
    # spend judge A's calls again to get the same null.
    assert exp.experience_complete({"a": a, "b": None, "agreement": None}) is True
    # A B that ran and failed is still incomplete, so a re-run retries it.
    assert exp.experience_complete({"a": a, "b": {"error": "boom"}}) is False
    assert exp.experience_complete({"a": {"error": "boom"}, "b": None}) is False
    # The guard must build the client, not just resolve the name: resolve()
    # hands back a raw vendor id with an empty provider and never touches
    # credentials, so a machine with only Azure configured used to sail past
    # this check and die inside the first cell instead.
    import run as pipeline
    model, provider = pipeline.model_registry.resolve("anthropic/claude-opus-4.8")
    assert provider == "", (model, provider)      # resolve alone raises nothing
    saved = dict(os.environ)
    try:
        for name in ("OPENROUTER_API_KEY", "OPENROUTER_API_KEY_FILE"):
            os.environ.pop(name, None)
        try:
            pipeline._client(model, provider)
        except SystemExit:
            pass                                   # what the guard relies on
        else:
            raise AssertionError("a missing OpenRouter key must raise at _client")
    finally:
        os.environ.clear()
        os.environ.update(saved)

    # agreement() is never called with a null B; when it is called it reports
    # per-dimension gaps and never an average.
    agreed = exp.agreement(a, {d: {"score": 5} for d in exp.DIMENSIONS})
    assert all(v["within_one"] for v in agreed.values()), agreed
    assert set(agreed) == set(exp.DIMENSIONS)


def check_harness_failure_rate() -> None:
    """The harness's own failure rate, per tool, is what the report must show.

    type_text once failed 45% of calls against click's 12% and nothing counted
    it, so a defect in our tool surface read as model weakness for weeks.
    """
    assert cost_report._rate(9, 20) == "9/20 45%", cost_report._rate(9, 20)
    assert cost_report._rate(0, 7) == "0/7 0%"
    # A tool a cell never used must not read as a clean 0%.
    assert cost_report._rate(0, 0) == "-"

    run = {"trajectory": [
        {"tool": "type_text", "result_preview": "typing failed: nothing matches"},
        {"tool": "type_text", "result_preview": "typed into f5; tab 1 now at ..."},
        {"tool": "click", "result_preview": "click failed: no visible element"},
        {"tool": "click", "result_preview": "clicked 'Next'; tab 1 now at ..."},
        {"tool": "read_page", "result_preview": "tab 1 | ..."},
    ]}
    record = {"accounting": {"per_call": [], "by_role": {}, "cell_wall_seconds": 1.0},
              "run": run, "task_id": "t" * 12, "judgement": {"score": 1.0}}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "result.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        row = next(iter(cost_report.cells(Path(tmp))))
    assert (row["typing_tried"], row["typing_failures"]) == (2, 1), row
    assert (row["clicks_tried"], row["click_failures"]) == (2, 1), row


def check_accounting_is_complete() -> None:
    """Every model call must survive into the record, not just its totals.

    per_call once shared the name "calls" with the totals' count, and the count
    won: every cell's per-call detail was silently replaced by an integer.
    """
    meter = R.Meter()
    meter.add("agent", "minimax/minimax-m3", "openrouter", fake_response(cost=0.2), ms=10)
    meter.add("rubric_judge", "minimax/minimax-m3", "openrouter", fake_response(cost=0.1), ms=20)
    accounting = {"cell_wall_seconds": 1.0, "per_call": meter.calls, **meter.totals()}
    assert isinstance(accounting["per_call"], list), accounting["per_call"]
    assert len(accounting["per_call"]) == accounting["calls"] == 2
    for call in accounting["per_call"]:
        for field in ("role", "model", "provider", "ms", "prompt_tokens",
                      "completion_tokens", "cached_prompt_tokens",
                      "cache_write_tokens", "reasoning_tokens", "cost_usd",
                      "cost_source", "list_cost_usd"):
            assert field in call, f"{field} is missing from a recorded call"
    for field in ("calls", "by_role", "prompt_tokens", "completion_tokens",
                  "model_ms", "retries", "cost_usd", "list_cost_usd",
                  "unpriced_calls"):
        assert field in accounting, f"{field} is missing from the totals"


def check_cost_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = [("s1", "minimax/minimax-m3", "aaaa", 1.0, 0.1, 600.0),
                ("s1", "x-ai/grok-4.7", "aaaa", 2.0, 0.1, 900.0),
                ("s2", "minimax/minimax-m3", "bbbb", 0.5, 0.1, 300.0)]
        for i, (setting, model, task, cost, judge, wall) in enumerate(plan):
            cell = root / setting / f"cell{i}"
            cell.mkdir(parents=True)
            (cell / "result.json").write_text(
                json.dumps(cell_record(setting, model, task, cost, judge, wall)),
                encoding="utf-8")
        # An archived run must not be counted.
        archived = root / "_v1" / "old"
        archived.mkdir(parents=True)
        (archived / "result.json").write_text(
            json.dumps(cell_record("s1", "minimax/minimax-m3", "cccc", 99.0, 9.0, 1.0)),
            encoding="utf-8")
        # A pre-accounting run is skipped rather than counted as free.
        legacy = root / "s1" / "legacy"
        legacy.mkdir(parents=True)
        (legacy / "result.json").write_text(json.dumps({"task_id": "d" * 40}),
                                            encoding="utf-8")

        rows = list(cost_report.cells(root))
        assert len(rows) == 3, rows
        assert {r["setting"] for r in rows} == {"s1", "s2"}
        # judge cost = the run's judge roles plus both experience judges
        assert rows[0]["judge_cost"] == 0.13, rows[0]
        assert rows[0]["total_cost"] == 1.13, rows[0]

        by_setting = cost_report.group(rows, "setting")
        assert by_setting["s1"]["cells"] == 2
        assert round(by_setting["s1"]["agent_cost"], 6) == 3.0
        assert round(by_setting["s2"]["total_cost"], 6) == 0.63

        out = subprocess.run([sys.executable, str(SRC / "cost_report.py"), str(root),
                              "--csv", str(root / "cells.csv"), "--by", "persona"],
                             capture_output=True, text=True, check=True).stdout
        assert "by setting" in out and "by CUA model" in out and "by task" in out
        assert "99.0" not in out, "archived _v1 run leaked into the report"
        with open(root / "cells.csv", encoding="utf-8") as handle:
            assert len(list(csv.DictReader(handle))) == 3


def main() -> None:
    check_registry()
    check_model_routes()
    check_every_route_is_priced()
    check_meter()
    check_metered_call()
    check_cache_marking()
    check_cache_switch()
    check_cache_retry()
    check_judge_calls()
    check_progress_note_is_not_an_answer()
    check_real_judging()
    check_real_manifest_checks()
    check_judge_b_is_optional()
    check_harness_failure_rate()
    check_accounting_is_complete()
    check_cost_report()
    print("accounting self-check OK")


if __name__ == "__main__":
    main()
