"""Does every registered model actually run in this harness, on this machine?

Not "is it in the registry" and not "does the id exist" -- one real
tool-calling round trip per model, through the same code path a cell uses, so
a collaborator finds a broken route here for a fraction of a cent instead of
four hours into a grid.

    python scripts/check_models.py                 # every model with a route
    python scripts/check_models.py gpt-6-astra     # just yours
    python scripts/check_models.py --all           # try unrouted ones too, and fail on them
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

import run as pipeline  # noqa: E402

# Small, unambiguous, and answerable only by calling a tool: a model that
# replies in prose here cannot drive the browser either.
PROMPT = ("Open https://example.com in a browser tab. "
          "Do it by calling a tool, not by describing it.")


def explain(exc: Exception) -> str:
    """The provider's own message, and what to do about it.

    A truncated repr of an OpenAI SDK error hides the one sentence that matters:
    meta/muse-spark-1.1 returns a 403 whose body says the account needs a
    one-time age attestation, which reads like a dead model id until you see it.
    """
    text = str(exc)
    body = getattr(getattr(exc, "response", None), "text", "") or text
    for marker in ("requires you to complete", "moderation", "not a valid model",
                   "No endpoints found", "insufficient", "quota", "rate limit"):
        if marker.lower() in body.lower():
            start = body.lower().index(marker.lower())
            return f"{type(exc).__name__}: ...{body[max(0, start - 40):start + 180]}"
    return f"{type(exc).__name__}: {text[:150]}"


def check(key: str) -> dict:
    row = {"key": key, "route": "", "ms": 0, "tool": "", "ok": False, "note": ""}
    try:
        model, provider = pipeline.model_registry.resolve(key)
    except SystemExit as exc:
        row["note"] = f"no route: {str(exc).splitlines()[0][:70]}"
        return row
    client, resolved = pipeline._client(model, provider)
    row["route"] = f"{model} via {resolved}"
    meter = pipeline.Meter()
    started = time.monotonic()
    try:
        resp, _ = pipeline.metered(
            client, meter, "agent", provider=resolved, model=model,
            messages=[{"role": "system", "content": pipeline.AGENT_RULES},
                      {"role": "user", "content": PROMPT}],
            tools=pipeline.TOOLS, max_completion_tokens=2000)
    except Exception as exc:
        row["ms"] = round((time.monotonic() - started) * 1000)
        row["note"] = explain(exc)
        return row
    message = resp.choices[0].message
    calls = getattr(message, "tool_calls", None) or []
    if not calls:
        row["ms"] = round((time.monotonic() - started) * 1000)
        text = (message.content or "").strip()
        row["note"] = ("answered in prose, no tool call: "
                       + (text[:80] or "(empty response)"))
        return row
    row["tool"] = calls[0].function.name

    # Second turn: hand the tool result back and require another move. A cell is
    # dozens of these, and a model that calls a tool once but mishandles the
    # `tool` role fails on turn two, not turn one -- which is four hours in.
    history = [{"role": "system", "content": pipeline.AGENT_RULES},
               {"role": "user", "content": PROMPT},
               message.model_dump(exclude_none=True)
               if hasattr(message, "model_dump") else message,
               {"role": "tool", "tool_call_id": calls[0].id,
                "content": "tab 1 | Example Domain | https://example.com\n\n"
                           "Example Domain. This domain is for use in examples."}]
    try:
        resp2, _ = pipeline.metered(
            client, meter, "agent", provider=resolved, model=model,
            messages=history + [{"role": "user",
                                 "content": "Now finish: call finish with a one-line summary."}],
            tools=pipeline.TOOLS, max_completion_tokens=2000)
    except Exception as exc:
        row["ms"] = round((time.monotonic() - started) * 1000)
        row["note"] = "turn 2 (tool result fed back) " + explain(exc)
        return row
    row["ms"] = round((time.monotonic() - started) * 1000)
    m2 = resp2.choices[0].message
    calls2 = getattr(m2, "tool_calls", None) or []
    if not calls2 and not (m2.content or "").strip():
        row["note"] = "turn 2 returned nothing at all after the tool result"
        return row
    row["tool"] = f"{row['tool']}+{calls2[0].function.name if calls2 else 'text'}"
    row["ok"] = True
    spent = sum(c["cost_usd"] or 0.0 for c in meter.calls)
    tokens = sum(c["prompt_tokens"] for c in meter.calls)
    row["note"] = f"2 turns, {tokens} in tok, ${spent:.5f}"
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="*", help="registry keys; default is every one")
    ap.add_argument("--all", action="store_true",
                    help="also fail on models with no route here, not just skip them")
    args = ap.parse_args()
    pipeline.load_dotenv()

    keys = args.models or list(pipeline.model_registry.MODELS)
    print(f"{'model':18}{'route':46}{'ms':>7}  {'tool calls':18}note")
    failed, skipped = [], []
    for key in keys:
        row = check(key)
        mark = "ok" if row["ok"] else ("--" if not row["route"] else "FAIL")
        print(f"{row['key']:18}{(row['route'] or '-'):46}{row['ms']:>7}  "
              f"{(row['tool'] or mark):18}{row['note'][:60]}")
        if not row["ok"] and row["route"] and len(row["note"]) > 60:
            print(f"{'':20}{row['note'][60:]}")
        if row["ok"]:
            continue
        (skipped if not row["route"] else failed).append(row["key"])

    print()
    if skipped:
        print(f"{len(skipped)} model(s) have no route on this machine: {', '.join(skipped)}")
        print("  That is expected unless you own them. Fill in .env for the one you run.")
    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        print("  These have a route but did not return a tool call. A model that "
              "cannot call a tool cannot drive the browser.")
        raise SystemExit(1)
    if args.all and skipped:
        raise SystemExit(1)
    print("every routed model returned a tool call")


if __name__ == "__main__":
    main()
