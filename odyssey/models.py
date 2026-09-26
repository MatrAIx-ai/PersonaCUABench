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
          f"({CELL_INPUT_TOKENS/1e6:.1f}M in + {CELL_OUTPUT_TOKENS/1e3:.0f}k out each)\n")
    total = 0.0
    print(f"{'key':<16}{'resolves to':<40}{'provider':<12}{'per cell':>10}{'total':>12}")
    for name in MODELS:
        model_id, provider = resolve(name)
        per_cell = cost_of(model_id, CELL_INPUT_TOKENS, CELL_OUTPUT_TOKENS) or 0.0
        if provider == "openai":
            per_cell = 0.0                # the collaborator's Azure endpoint
        total += per_cell * cells
        print(f"{name:<16}{model_id:<40}{provider:<12}"
              f"{per_cell:>10.2f}{per_cell * cells:>12.2f}")
    print(f"\n{'':<68}{'all models':>10}{total:>12.2f}")


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
