import json
from unittest.mock import AsyncMock, patch

import pytest

from phase_space_provider import MeteredOpenRouterAPI, billing_receipt
from run_phase_space import (BudgetLedger, Runtime, build_cases, call_ceiling,
                             labels, outcome_records, parse_decision, prompt_for)


def test_plan_and_counterbalance():
    cases = build_cases(["m1", "m2"], "self_play", 4)
    assert len(cases) == 70 * 2 * 4
    assert len({c["sample_id"] for c in cases}) == len(cases)
    assert cases == build_cases(["m1", "m2"], "self_play", 4)
    cell = [c for c in cases if c["model"] == "m1" and (c["s"], c["t"]) == (-.5, 1.5)]
    assert sum(labels(c, "row")["C"] == "A" for c in cell) == 2
    assert sum(labels(c, "column")["C"] == "A" for c in cell) == 2
    assert all("Prisoner" not in prompt_for(c, "row") for c in cell)


def test_cross_play_and_fixed_beliefs():
    cross = build_cases(["a", "b", "c", "d"], "cross_play", 2)
    assert len(cross) == 5 * 12 * 2
    assert all(c["model"] != c["opponent_model"] for c in cross)
    fixed = build_cases(["m"], "fixed_belief", 4)
    assert len(fixed) == 60
    assert all(c["opponent_model"] is None for c in fixed)


@pytest.mark.parametrize("raw", ["", "A", '{"action":"C"}', '[]', '{"action":null}'])
def test_invalid_parse_not_cooperation(raw):
    decision = parse_decision(raw, {"C": "A", "D": "B"})
    assert not decision["valid"] and decision["action"] is None


def test_parse_labels_and_probability_validation():
    parsed = parse_decision('```json\n{"action":"A","confidence":true,"opponent_probability_A":2}\n```', {"C": "B", "D": "A"})
    assert parsed["action"] == "D" and parsed["valid"]
    assert parsed["confidence"] is None and parsed["opponent_probability_A"] is None


def test_visible_preamble_is_not_a_parse_failure_but_ambiguity_is():
    mapping = {"C": "A", "D": "B"}
    parsed = parse_decision('Here is my choice.\n{"action":"B"}', mapping)
    assert parsed["valid"] and parsed["action"] == "D" and not parsed["json_format_exact"]
    assert not parse_decision('{"action":"A"}\n{"action":"B"}', mapping)["valid"]
    assert not parse_decision('{"action":"A"} But actually choose B.', mapping)["valid"]


def test_role_payoffs_regrets_and_nash():
    case = build_cases(["m"], "smoke", 1)[0]
    records = outcome_records(case, {"row": {"action": "C", "valid": True},
                                     "column": {"action": "D", "valid": True}})
    assert [r["expected_utility"] for r in records] == [-.5, 1.5]
    assert [r["regret"] for r in records] == [.5, 0]
    assert all(r["joint_welfare"] == 1 and not r["pure_nash"] for r in records)
    dd = outcome_records(case, {"row": {"action": "D", "valid": True},
                                "column": {"action": "D", "valid": True}})
    assert all(r["pure_nash"] and r["regret"] == 0 for r in dd)


def test_fixed_belief_boundary_and_invalid_partner():
    case = build_cases(["m"], "fixed_belief", 1)[0]
    case.update(s=-.5, t=.5, opponent_cooperation_probability=.5)
    record = outcome_records(case, {"row": {"action": "C", "valid": True}})[0]
    assert record["regret"] == 0 and record["expected_utility"] == .25
    assert record["pure_nash"] is None and record["joint_welfare"] is None
    case = build_cases(["m"], "smoke", 1)[0]
    records = outcome_records(case, {"row": {"action": "C", "valid": True},
                                     "column": {"action": None, "valid": False}})
    assert all(r["regret"] is None and r["pure_nash"] is None for r in records)


def test_budget_reserves_before_spending_and_persists(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = BudgetLedger(path, 1)
    try:
        index = ledger.reserve("a", "model", .8)
        assert ledger.reserve("b", "model", .3) is None
        ledger.settle(index, .2, "returned")
        assert ledger.committed == .2
        ledger.reserve("c", "model", .5)
    finally:
        ledger.close()
    resumed = BudgetLedger(path, 100)
    try:
        assert resumed.data["cap_usd"] == 1
        assert resumed.committed == .7
        assert resumed.summary()["unpriced_calls"] == 1
        with pytest.raises(BlockingIOError):
            BudgetLedger(path, 1)
    finally:
        resumed.close()


def test_pair_budget_is_atomic(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json", .04)
    pricing = {"prompt": 1e-6, "completion": 1e-4}
    runtime = Runtime({"preflight": {"models": {"m": {"price_ceiling_per_token": pricing}}}},
                      tmp_path / "run.json", ledger, 256)
    try:
        case = build_cases(["m"], "smoke", 1)[0]
        assert runtime.reserve_episode(case, ["row", "column"]) is None
        assert ledger.committed == 0 and not ledger.data["calls"]
    finally:
        ledger.close()


def test_batch_does_not_reuse_loop_bound_clients(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.json", 1)
    runtime = Runtime({"records": ["preserved"]}, tmp_path / "run.json", ledger, 256)
    try:
        runtime.models["old"] = object()
        runtime.begin_batch()
        assert not runtime.models
        assert runtime.payload["records"] == ["preserved"]
        assert runtime.ledger is ledger
    finally:
        ledger.close()


def test_raw_receipt_not_inspect_estimate():
    assert billing_receipt({"usage": {"total_cost": .001}})["cost_usd"] is None
    assert billing_receipt({"usage": {"cost": .23}})["cost_usd"] == .23
    for value in [-1, float("nan"), True, "0.1"]:
        assert billing_receipt({"usage": {"cost": value}})["cost_usd"] is None


def test_adapter_preserves_raw_cost_without_real_network():
    import asyncio
    from inspect_ai.model import GenerateConfig, ModelOutput
    from inspect_ai.model._model_call import ModelCall
    output = ModelOutput.from_content("m", '{"action":"A"}')
    call = ModelCall(request={}, response={"id": "test-id", "usage": {"cost": .25}})
    # The Inspect decorator returns a registered constructor, not a type.
    api = MeteredOpenRouterAPI("test-model", api_key="test-not-a-real-key", max_retries=0)
    with patch("phase_space_provider.OpenRouterAPI.generate", new=AsyncMock(return_value=(output, call))):
        result, _ = asyncio.run(api.generate([], [], "none", GenerateConfig()))
    assert result.metadata["phase_space_billing"]["cost_usd"] == .25


def test_prompt_budget_is_conservative():
    assert call_ceiling("abc", 100, {"prompt": .001, "completion": .01}) > 2
