"""Preserve OpenRouter billing receipts before Inspect computes cost estimates.

Inspect's ModelUsage.total_cost may be overwritten by its own pricing database.
The separate metadata below comes exclusively from the raw provider response.
The adapter otherwise delegates generation and native tracing to Inspect.
"""
from __future__ import annotations

import math

from inspect_ai.model import ModelOutput, modelapi
from inspect_ai.model._providers.openrouter import OpenRouterAPI


def billing_receipt(response: dict | None) -> dict:
    response = response or {}
    usage = response.get("usage") or {}
    cost = usage.get("cost")
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        cost = None
    return {"source": "openrouter_raw_response_usage.cost", "cost_usd": cost,
            "generation_id": response.get("id"), "provider": response.get("provider"),
            "returned_model": response.get("model"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "completion_tokens_details": usage.get("completion_tokens_details")}


@modelapi(name="phase_openrouter")
class MeteredOpenRouterAPI(OpenRouterAPI):
    async def generate(self, input, tools, tool_choice, config):
        result = await super().generate(input, tools, tool_choice, config)
        if isinstance(result, tuple):
            output, call = result
            if isinstance(output, ModelOutput):
                output.metadata = {**(output.metadata or {}),
                                   "phase_space_billing": billing_receipt(call.response)}
        return result
