"""The model registry: a short key resolves to a provider, an id and a price.

Azure wins whenever the model is deployed there, because that endpoint is the
collaborator's and costs this project nothing. Everything else goes to
OpenRouter, where one key covers every model under test.

    python src/models.py                 # what each key resolves to now
    python src/models.py --probe         # ask Azure which ids it serves
    python src/models.py --estimate 30   # price 30 cells per model
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


def endpoint_configured(entry: dict) -> bool:
    """True when the owner's own vendor endpoint is set up on this machine."""
    endpoint = entry.get("endpoint") or {}
    if not endpoint.get("base_url_env"):
        return False
    if not os.environ.get(endpoint["base_url_env"], "").strip():
        return False
    if endpoint.get("key_required", True):
        return bool(os.environ.get(endpoint.get("api_key_env", ""), "").strip())
    return True


def routes(key: str) -> list[tuple[str, str, bool]]:
    """Every way this model could be reached: (provider, model id, available)."""
    entry = MODELS.get(key)
    if entry is None:
        return []
    out = []
    endpoint = entry.get("endpoint") or {}
    if endpoint.get("base_url_env"):
        out.append((key, endpoint.get("model") or key, endpoint_configured(entry)))
    if entry.get("azure"):
        out.append(("openai", entry["azure"], azure_configured()))
    if entry.get("openrouter"):
        out.append(("openrouter", entry["openrouter"],
                    bool(os.environ.get("OPENROUTER_API_KEY", "").strip())))
    return out


def resolve(spec: str, provider: str = "") -> tuple[str, str]:
    """(model id, provider) for a registry key, or the spec itself untouched.

    Order: the owner's own endpoint, then the shared Azure deployment, then
    OpenRouter. Whoever owns a model usually has the better rate limit for it,
    and everyone else still reaches it through whatever they do have.

    A raw model id passes through untouched, so an id that is not in the
    registry is never silently rerouted. An explicit provider is an override
    and is honoured even when that route is not configured -- the failure then
    names the missing variable rather than quietly using another vendor.
    """
    entry = MODELS.get(spec)
    if entry is None:
        return spec, provider
    if provider:
        for name, model_id, _ in routes(spec):
            if name == provider:
                return model_id, provider
        return (entry.get("openrouter") or spec), provider
    for name, model_id, available in routes(spec):
        if available:
            return model_id, name
    wanted = [f"{name} ({_route_requirement(spec, name)})"
              for name, _, _ in routes(spec)]
    raise SystemExit(
        f"no configured route for model {spec!r}. Set up one of: "
        + "; ".join(wanted) + ". See .env.example.")


def _route_requirement(key: str, provider: str) -> str:
    entry = MODELS.get(key) or {}
    endpoint = entry.get("endpoint") or {}
    if provider == key:
        return f"{endpoint.get('base_url_env')} + {endpoint.get('api_key_env')}"
    if provider == "openai":
        return "AZURE_OPENAI_BASE_URL + AZURE_OPENAI_API_KEY_FILE"
    return "OPENROUTER_API_KEY"


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
    try:
        _, provider = resolve(key)
    except SystemExit:
        provider = "openrouter"         # price the aggregator when nothing is set up
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
    import run as pipeline

    pipeline.load_dotenv()
    if not azure_configured():
        raise SystemExit("no Azure credentials: set AZURE_OPENAI_BASE_URL and "
                         "AZURE_OPENAI_API_KEY_FILE (see .env.example)")
    from openai import OpenAI

    key, base_url = pipeline._provider_config("openai")
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
    import run as pipeline

    pipeline.load_dotenv()          # so --probe and the display see the real keys

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
    print(f"{'key':<18}{'owner':<14}{'resolves to':<34}{'provider':<12}routes")
    for name, entry in MODELS.items():
        try:
            model_id, provider = resolve(name)
        except SystemExit:
            model_id, provider = "-- no route configured --", "-"
        available = ",".join(f"{p}{'' if ok else '(x)'}" for p, _, ok in routes(name))
        print(f"{name:<18}{entry.get('owner', '?'):<14}{model_id:<34}"
              f"{provider:<12}{available}")
    print("\n(x) = that route's credentials are not set on this machine. A model "
          "with no route raises rather than silently running somewhere else.")
    if not azure_configured():
        print("\nno Azure credentials on this machine, so every key resolves to "
              "OpenRouter; with them, keys whose azure field is set go to Azure "
              "for free.")


if __name__ == "__main__":
    main()
