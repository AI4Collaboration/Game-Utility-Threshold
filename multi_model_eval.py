"""Run either Inspect suite across several OpenRouter model families."""

from __future__ import annotations

import argparse
import os

from inspect_ai import eval
from dotenv import load_dotenv

from canonical_games_inspect import canonical_games_model_eval
from utility_threshold_inspect import utility_threshold_model_eval

# One model from each major provider family, all accessed through Inspect's
# native OpenRouter provider. Pin these identifiers for reproducible logs.
MODEL_MATRIX = {
    "openai": "openrouter/openai/gpt-5-mini",
    "anthropic": "openrouter/anthropic/claude-sonnet-4.5",
    "google": "openrouter/google/gemini-3-flash-preview",
    "meta": "openrouter/meta-llama/llama-3.3-70b-instruct",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run cross-provider utility-threshold evaluations")
    parser.add_argument("--suite", choices=("canonical", "threshold"), default="canonical")
    parser.add_argument(
        "--provider",
        choices=tuple(MODEL_MATRIX),
        action="append",
        help="provider family to include; repeat for multiple (default: all)",
    )
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required; copy .env.example to .env and add it locally.")
    if args.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive")
    providers = args.provider or list(MODEL_MATRIX)
    inspect_task = canonical_games_model_eval() if args.suite == "canonical" else utility_threshold_model_eval()
    eval(
        inspect_task,
        model=[MODEL_MATRIX[provider] for provider in providers],
        model_args={"provider": {"data_collection": "deny", "allow_fallbacks": True}},
        temperature=0,
        max_tokens=args.max_tokens,
        reasoning_effort="minimal",
        display="plain",
        log_dir="./logs",
    )


if __name__ == "__main__":
    main()
