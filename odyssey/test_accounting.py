"""Offline self-check for the meter, the model registry and the cost report.

No network, no API keys, no browser.

    python odyssey/test_accounting.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

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
    # A raw id passes through; a key resolves to OpenRouter without Azure.
    assert registry.resolve("qwen/qwen3.8-27b") == ("qwen/qwen3.8-27b", "")
    assert registry.resolve("glm-5.3") == ("z-ai/glm-5.3", "openrouter")
    # Azure wins for a deployed model, but only with credentials present.
    import os

    saved = {k: os.environ.get(k) for k in
             ("AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_API_KEY")}
    try:
        os.environ["AZURE_OPENAI_BASE_URL"] = "https://example.invalid/openai/v1"
        os.environ["AZURE_OPENAI_API_KEY"] = "x"
        assert registry.resolve("terra") == ("gpt-5.6-terra", "openai")
        assert registry.resolve("glm-5.3") == ("z-ai/glm-5.3", "openrouter")
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    assert registry.resolve("terra") == ("openai/gpt-5.6-terra", "openrouter")
    # Prices come from the registry for either of a model's ids.
    assert registry.cost_of("z-ai/glm-5.3", 1_000_000, 0) == 0.38
    assert registry.cost_of("gpt-5.6-terra", 1_000_000, 1_000_000) == 0.0
    assert registry.cost_of("not/a-model", 1_000_000, 0) is None


def check_meter() -> None:
    meter = R.Meter()
    # A provider-reported charge wins over the list price.
    reported = meter.add("agent", "z-ai/glm-5.3", "openrouter",
                         fake_response(cost=0.123), ms=1500)
    assert reported["cost_usd"] == 0.123 and reported["cost_source"] == "provider"
    assert reported["cached_prompt_tokens"] == 7
    # Without one, the registry prices it.
    priced = meter.add("agent", "z-ai/glm-5.3", "openrouter",
                       fake_response(prompt=1_000_000, completion=0), ms=500)
    assert priced["cost_usd"] == 0.38 and priced["cost_source"] == "registry"
    # An unknown model is counted, not silently priced at zero.
    unknown = meter.add("rubric_judge", "mystery/model", "openrouter",
                        fake_response(), ms=10)
    assert unknown["cost_usd"] is None and unknown["cost_source"] == "unknown"

    totals = meter.totals()
    assert totals["calls"] == 3 and totals["unpriced_calls"] == 1
    assert totals["cost_usd"] == 0.503
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
                           model="z-ai/glm-5.3", messages=[])
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
            "cost_usd": cost + judge_cost, "unpriced_calls": 0, "calls": [],
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
    assert R.cache_marked(history, "z-ai/glm-5.3") is history

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
        out = experience_judge.score_once("prompt", "z-ai/glm-5.3")
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
            experience_judge.score_once("prompt", "z-ai/glm-5.3")
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


def check_cost_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plan = [("s1", "z-ai/glm-5.3", "aaaa", 1.0, 0.1, 600.0),
                ("s1", "x-ai/grok-4.7", "aaaa", 2.0, 0.1, 900.0),
                ("s2", "z-ai/glm-5.3", "bbbb", 0.5, 0.1, 300.0)]
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
            json.dumps(cell_record("s1", "z-ai/glm-5.3", "cccc", 99.0, 9.0, 1.0)),
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

        out = subprocess.run([sys.executable, str(HERE / "cost_report.py"), str(root),
                              "--csv", str(root / "cells.csv"), "--by", "persona"],
                             capture_output=True, text=True, check=True).stdout
        assert "by setting" in out and "by CUA model" in out and "by task" in out
        assert "99.0" not in out, "archived _v1 run leaked into the report"
        with open(root / "cells.csv", encoding="utf-8") as handle:
            assert len(list(csv.DictReader(handle))) == 3


def main() -> None:
    check_registry()
    check_meter()
    check_metered_call()
    check_cache_marking()
    check_cache_switch()
    check_cache_retry()
    check_judge_calls()
    check_progress_note_is_not_an_answer()
    check_cost_report()
    print("accounting self-check OK")


if __name__ == "__main__":
    main()
