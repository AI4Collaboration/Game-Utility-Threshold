"""Run the utility-threshold model evaluation across several OpenRouter models."""

from __future__ import annotations

import os

from inspect_ai import eval
from inspect_ai.model import GenerateConfig

from utility_threshold_inspect import utility_threshold_model_eval

# One model from each major provider family, all accessed through Inspect's
# native OpenRouter provider. Pin these identifiers for reproducible logs.
MODEL_MATRIX = {
    "openai": "openrouter/openai/gpt-5-mini",
    "anthropic": "openrouter/anthropic/claude-sonnet-4.5",
    "google": "openrouter/google/gemini-3-flash-preview",
    "meta": "openrouter/meta-llama/llama-3.3-70b-instruct",
}


def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required; copy .env.example to .env and add it locally.")
    eval(
        utility_threshold_model_eval(),
        model=list(MODEL_MATRIX.values()),
        model_args={"provider": {"data_collection": "deny", "allow_fallbacks": True}},
        config=GenerateConfig(temperature=0, max_tokens=8),
        display="plain",
        log_dir="./logs",
    )


if __name__ == "__main__":
    main()
