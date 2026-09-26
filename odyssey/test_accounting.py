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
    # Other providers are called unchanged.
    sent.clear()
    R.metered(Client(), meter, "agent", provider="openai", model="gpt-5.6-terra",
              messages=[])
    assert "extra_body" not in sent


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
    check_cost_report()
    print("accounting self-check OK")


if __name__ == "__main__":
    main()
