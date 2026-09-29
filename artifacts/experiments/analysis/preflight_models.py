#!/usr/bin/env python3
"""API / tool-loop preflight for the Setting 1 execution backbones, on main's own code.

Mirrors the check the maintainers ran before their Shopping grid: a model enters the
formal grid only if it survives main's unmodified Chat Completions function-tool path.
Everything goes through odyssey/run.py's own _client, _create_with_retry, AGENT_RULES
and TOOLS, so this measures the path the real runner uses rather than a look-alike.

Each executor gets a two-turn loop: turn 1 must return a tool call against main's real
tool schema; turn 2 feeds a synthetic tool result back and must return another tool
call or a final message without an API error.

Two modes:
  unmodified  main exactly as merged.
  patched     same, plus reasoning_effort="none" on gpt-5* tool calls -- the fix merged
              into main-shop as PR #4's first commit -- applied by monkeypatch, so the
              repo is untouched. Reports which models that fix rescues.

Also checks the two non-executor roles on gpt-5.6-terra: persona text (no tools,
temperature 1) and judge JSON (no temperature, as main's judge sends it).

    python3 work/preflight_models.py > work/preflight_<date>.md
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "repo" / "odyssey"))
import run as R  # noqa: E402  (odyssey/run.py on the current branch)

R.load_dotenv()

EXECUTORS = [
    ("GPT 5.6 Terra",   "openai",     "gpt-5.6-terra"),
    ("GPT 6 Astra",     "openai",     "gpt-6-astra"),
    ("Claude Opus 5.5", "openrouter", "anthropic/claude-opus-5.5"),
    ("Muse Spark 1.1",  "openrouter", "meta/muse-spark-1.1"),
    ("Kimi-K3",         "openrouter", "moonshotai/kimi-k3"),
    ("Grok 4.7",        "openrouter", "x-ai/grok-4.7"),
    ("MiniMax M3",      "openrouter", "minimax/minimax-m3"),
    ("GLM 5.3",         "openrouter", "z-ai/glm-5.3"),
    ("Qwen 3.8 27B",    "openrouter", "qwen/qwen3.8-27b"),
]
UNAVAILABLE = [("Gemini V4 Pro", "no id on OpenAI or OpenRouter; newest Gemini listed is "
                "google/gemini-3.1-pro-preview. Recorded as unavailable, not substituted.")]

_orig = R._create_with_retry


def _patched(client, *, attempts: int = 5, **kw):
    if kw.get("tools") and "reasoning_effort" not in kw and str(kw.get("model", "")).startswith("gpt-5"):
        kw["reasoning_effort"] = "none"
    return _orig(client, attempts=attempts, **kw)


def tool_loop(provider: str, model: str, patched: bool) -> tuple[str, str]:
    R._create_with_retry = _patched if patched else _orig
    try:
        client, _ = R._client(model, provider)
        msgs = [{"role": "system", "content": R.AGENT_RULES},
                {"role": "user", "content": "Please open https://example.com in a new tab and tell me its title."}]
        r1 = R._create_with_retry(client, model=model, messages=msgs, tools=R.TOOLS, temperature=1.0)
        m1 = r1.choices[0].message
        calls = m1.tool_calls or []
        if not calls:
            return "FAIL", "turn 1 returned no tool call: %r" % (m1.content or "")[:120]
        msgs.append(m1.model_dump(exclude_none=True))
        for c in calls:
            msgs.append({"role": "tool", "tool_call_id": c.id,
                         "content": "tab 1 | Example Domain | https://example.com/"})
        r2 = R._create_with_retry(client, model=model, messages=msgs, tools=R.TOOLS, temperature=1.0)
        m2 = r2.choices[0].message
        what = ("tool call %s" % m2.tool_calls[0].function.name) if m2.tool_calls else "final text"
        return "PASS", "turn 1 %s, turn 2 %s; served as %s" % (calls[0].function.name, what, r2.model)
    except SystemExit as e:
        return "FAIL", "config: %s" % e
    except Exception as e:  # noqa: BLE001
        return "FAIL", "%s: %s" % (type(e).__name__, str(e).replace("\n", " ")[:220])
    finally:
        R._create_with_retry = _orig


def terra_roles() -> list[tuple[str, str, str]]:
    out = []
    client, _ = R._client("gpt-5.6-terra", "openai")
    try:
        r = client.chat.completions.create(model="gpt-5.6-terra", temperature=1.0, messages=[
            {"role": "system", "content": "You are a person asking an assistant for help."},
            {"role": "user", "content": "Write one sentence asking for help finding a grammar quiz."}])
        out.append(("persona text", "PASS", (r.choices[0].message.content or "")[:80]))
    except Exception as e:  # noqa: BLE001
        out.append(("persona text", "FAIL", str(e)[:200]))
    try:
        r = client.chat.completions.create(model="gpt-5.6-terra", messages=[
            {"role": "user", "content": 'Reply with JSON only: {"R1": {"met": true, "communicated": true}}'}])
        ok = R.extract_json(r.choices[0].message.content) is not None
        out.append(("judge JSON", "PASS" if ok else "FAIL", (r.choices[0].message.content or "")[:80]))
    except Exception as e:  # noqa: BLE001
        out.append(("judge JSON", "FAIL", str(e)[:200]))
    return out


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("# API / tool-loop preflight — science-education Setting 1\n")
    print("Run %s on branch `%s`. Credentials: direct OpenAI API key and an OpenRouter key; "
          "no Azure.\n" % (now, "jiashu/science-education-main"))
    print("## Fixed roles on gpt-5.6-terra\n")
    print("| role | result | sample |\n|---|---|---|")
    for role, res, sample in terra_roles():
        print("| %s | %s | %s |" % (role, res, sample.replace("|", "/").replace("\n", " ")))
    print("\n## Execution backbones — two-turn tool loop through main's own code\n")
    print("| backbone | provider / id | unmodified main | with reasoning_effort fix |\n|---|---|---|---|")
    detail = []
    for label, prov, mid in EXECUTORS:
        u, ud = tool_loop(prov, mid, patched=False)
        p, pd = tool_loop(prov, mid, patched=True)
        print("| %s | `%s` `%s` | **%s** | **%s** |" % (label, prov, mid, u, p))
        detail.append((label, ud, pd))
        time.sleep(1)
    for label, why in UNAVAILABLE:
        print("| %s | — | **UNAVAILABLE** | **UNAVAILABLE** |" % label)
    print("\n## Detail\n")
    for label, ud, pd in detail:
        print("- **%s** — unmodified: %s — with fix: %s" % (label, ud, pd))
    for label, why in UNAVAILABLE:
        print("- **%s** — %s" % (label, why))


if __name__ == "__main__":
    main()
