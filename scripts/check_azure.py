#!/usr/bin/env python3
"""Smoke-test the configured Azure Foundry Responses API.

Put your API key (one line, no quotes) in azure_api_key.txt, then:

    .venv/bin/python scripts/check_azure.py
"""

import os
from pathlib import Path

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = (
    "https://matraixwild.services.ai.azure.com/api/projects/"
    "MatrAIxWild/openai/v1"
)


def load_api_key() -> str:
    direct = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
    if direct:
        return direct
    key_file_value = os.environ.get("AZURE_OPENAI_API_KEY_FILE", "").strip()
    key_file = Path(key_file_value).expanduser() if key_file_value else ROOT / "azure_api_key.txt"
    if not key_file.exists():
        raise SystemExit(f"Missing API key file: {key_file}")
    key = key_file.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"API key file is empty: {key_file}")
    return key


def main() -> None:
    base_url = os.environ.get("AZURE_OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("CUA_MODEL", "gpt-5.6-terra")
    client = OpenAI(base_url=base_url, api_key=load_api_key())
    response = client.responses.create(
        model=model,
        input="What is the capital of France?",
    )
    answer = getattr(response, "output_text", None) or response.output[0]
    print("status: ok")
    print(f"model: {model}")
    print(f"answer: {answer}")


if __name__ == "__main__":
    main()
