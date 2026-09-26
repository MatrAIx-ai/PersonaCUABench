"""The model registry: a short key resolves to a provider, an id and a price.

Azure wins whenever the model is deployed there, because that endpoint is the
collaborator's and costs this project nothing. Everything else goes to
OpenRouter, where one key covers every model under test.

    python odyssey/models.py                 # what each key resolves to now
    python odyssey/models.py --probe         # ask Azure which ids it serves
    python odyssey/models.py --estimate 30   # price 30 cells per model
"""
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = json.loads((HERE / "models.json").read_text(encoding="utf-8"))
MODELS: dict[str, dict] = REGISTRY["models"]

# One cell of measured browsing, from the qwen runs: the agent resends the whole
# history every step, so input dominates and output barely moves the bill.
CELL_INPUT_TOKENS = 600_000
CELL_OUTPUT_TOKENS = 15_000
# Of that input, the part a cache can never cover: the new page text each step
# adds. The rest is the transcript resent unchanged, which is what gets cached.
CELL_UNCACHED_INPUT_TOKENS = 85_000


def azure_configured() -> bool:
    """True when this machine has Azure credentials and an Azure endpoint."""
    if not os.environ.get("AZURE_OPENAI_BASE_URL", "").strip():
        return False
    return any(os.environ.get(name, "").strip() for name in
               ("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY_FILE"))


def resolve(spec: str, provider: str = "") -> tuple[str, str]:
    """(model id, provider) for a registry key, or the spec itself untouched.

    A raw model id still works and keeps whatever provider the caller asked
    for, so an id that is not in the registry is never silently rerouted.
    """
    entry = MODELS.get(spec)
    if entry is None:
        return spec, provider
    if provider:                          # an explicit --provider is an override
        return (entry.get("azure") or entry["openrouter"]) if provider == "openai" \
            else entry["openrouter"], provider
    if entry.get("azure") and azure_configured():
        return entry["azure"], "openai"   # Azure rides the openai-compatible path
    return entry["openrouter"], "openrouter"


def price_for(model_id: str) -> dict | None:
    """USD per million tokens for a resolved id, or None when unknown."""
    for entry in MODELS.values():
        if model_id in (entry.get("azure"), entry.get("openrouter")):
            return entry["price"]
    return None


def cell_cost(key: str, *, cached: bool = False) -> float | None:
    """What one cell of browsing costs on this model, with or without caching.

    Caching only helps the resent transcript, so the estimate prices the new
    tokens at full rate and the rest at the measured cache-read multiplier --
    a single-call "97% cheaper" number would overstate a whole cell badly.
    """
    entry = MODELS.get(key)
    if entry is None:
        return None
    model_id, provider = resolve(key)
    if provider == "openai" and entry.get("azure"):
        return 0.0                      # the collaborator's endpoint
    price = entry["price"]
    multiplier = entry.get("cache_read_multiplier")
    if not cached or multiplier is None:
        multiplier = 1.0
    cacheable = max(CELL_INPUT_TOKENS - CELL_UNCACHED_INPUT_TOKENS, 0)
    input_tokens = cacheable * multiplier + CELL_UNCACHED_INPUT_TOKENS
    return round(input_tokens / 1e6 * price["in"]
                 + CELL_OUTPUT_TOKENS / 1e6 * price["out"], 6)


def cost_of(model_id: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """What those tokens cost, from the registry price. None when unpriced."""
    price = price_for(model_id)
    if price is None:
        return None
    return round(prompt_tokens / 1e6 * price["in"]
                 + completion_tokens / 1e6 * price["out"], 6)


def _probe() -> None:
    """Ask the Azure endpoint which registry ids it actually serves."""
    import sys

    sys.path.insert(0, str(HERE))
    import run as odyssey

    odyssey.load_dotenv()
    if not azure_configured():
        raise SystemExit("no Azure credentials: set AZURE_OPENAI_BASE_URL and "
                         "AZURE_OPENAI_API_KEY_FILE (see .env.example)")
    from openai import OpenAI

    key, base_url = odyssey._provider_config("openai")
    client = OpenAI(api_key=key, base_url=base_url)
    for name, entry in MODELS.items():
        candidate = entry.get("azure") or entry["openrouter"].split("/")[-1]
        try:
            client.chat.completions.create(
                model=candidate, messages=[{"role": "user", "content": "ok"}],
                max_completion_tokens=16)
        except Exception as exc:
            served = False
            detail = f"{type(exc).__name__}"
        else:
            served, detail = True, "answers"
        flag = ""
        if served and not entry.get("azure"):
            flag = "  <- deployed on Azure; set \"azure\" to this id to stop paying"
        if not served and entry.get("azure"):
            flag = "  <- azure field is set but the deployment does not answer"
        print(f"{name:<16} {candidate:<34} {detail:<18}{flag}")


def _estimate(cells: int) -> None:
    print(f"estimated cost of {cells} cells per model "
          f"({CELL_INPUT_TOKENS/1e6:.1f}M in + {CELL_OUTPUT_TOKENS/1e3:.0f}k out each, "
          f"{CELL_UNCACHED_INPUT_TOKENS/1e3:.0f}k of the input uncacheable)\n")
    plain_total = cached_total = 0.0
    print(f"{'key':<16}{'provider':<12}{'per cell':>10}{'cached':>9}"
          f"{'total':>11}{'cached total':>14}  cache")
    for name, entry in MODELS.items():
        _, provider = resolve(name)
        plain = cell_cost(name) or 0.0
        cached = cell_cost(name, cached=True) or 0.0
        plain_total += plain * cells
        cached_total += cached * cells
        mult = entry.get("cache_read_multiplier")
        tag = "unmeasured" if mult is None else (
            "none" if mult >= 1.0 else f"{mult:.2f}x reads")
        print(f"{name:<16}{provider:<12}{plain:>10.2f}{cached:>9.2f}"
              f"{plain * cells:>11.2f}{cached * cells:>14.2f}  {tag}")
    print(f"\n{'all models':<16}{'':<12}{'':>10}{'':>9}"
          f"{plain_total:>11.2f}{cached_total:>14.2f}")


def main() -> None:
    import argparse
    import sys

    sys.path.insert(0, str(HERE))
    import run as odyssey

    odyssey.load_dotenv()          # so --probe and the display see the real keys

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="store_true",
                    help="ask the Azure endpoint which registry ids it serves")
    ap.add_argument("--estimate", type=int, metavar="CELLS",
                    help="price this many cells for every model")
    args = ap.parse_args()
    if args.probe:
        return _probe()
    if args.estimate:
        return _estimate(args.estimate)
    print(f"{'key':<16}{'resolves to':<40}{'provider':<12}{'label'}")
    for name, entry in MODELS.items():
        model_id, provider = resolve(name)
        print(f"{name:<16}{model_id:<40}{provider:<12}{entry['label']}")
    if not azure_configured():
        print("\nno Azure credentials on this machine, so every key resolves to "
              "OpenRouter; with them, keys whose azure field is set go to Azure "
              "for free.")


if __name__ == "__main__":
    main()
