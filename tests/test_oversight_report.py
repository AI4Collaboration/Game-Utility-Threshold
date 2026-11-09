"""Hand-check stratification, missingness, ties, and report artifacts."""

from copy import deepcopy
from fractions import Fraction as F
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gut.oversight import Oversight
from gut.oversight_report import interval, report, summarize


def fixture(repetitions=4, *, tie=False):
    game = Oversight(p=0) if tie else Oversight()
    d = F(1, 2) if tie else F(3, 10)
    condition = {"id": "defense-1", "sweep": "defense", "x": str(d), "d": str(d),
                 "parameters": {key: str(value) for key, value in game.__dict__.items()},
                 "framing": "neutral", "repetitions": repetitions}
    plan = {"protocol": "oversight-test-v1", "mode": "synthetic", "sha256": "a"*64,
            "models": [{"id": "synthetic/demo", "provider": "local"}], "conditions": [condition],
            "block_definitions": [{"block": block, "mapping": "A/B mapping", "order": "row order"} for block in range(4)]}
    rows = []
    for block in range(4):
        for repeat in range(repetitions):
            human, ai = game.payoff(d, "cooperate")
            rows.append({"id": f"b{block}-r{repeat}", "model": "synthetic/demo", "condition_id": condition["id"],
                         "block": block, "repeat": repeat, "attempted": True, "status": "valid",
                         "action": "cooperate", "theoretical_best": list(game.best_responses(d)),
                         "margin": str(game.margin(d)), "human_payoff": str(human), "ai_payoff": str(ai),
                         "regret": "0", "cost_usd": "0.001"})
    return plan, rows


def act(plan, row, action):
    condition = plan["conditions"][0]
    game, d = Oversight(**condition["parameters"]), F(condition["d"])
    human, ai = game.payoff(d, action)
    row.update(action=action, human_payoff=str(human), ai_payoff=str(ai),
               regret=str(max(game.payoff(d, a)[1] for a in ("cooperate", "attack"))-ai))


def missing(row, status="transport_error", attempted=True):
    row.update(status=status, action=None, regret=None, human_payoff=None, ai_payoff=None,
               cost_usd=None, attempted=attempted)


class SummaryTests(unittest.TestCase):
    def test_equal_block_means_not_pooled_valid_requests(self):
        plan, rows = fixture()
        counts = [4, 1, 2, 3]
        for row in rows:
            if row["repeat"] >= counts[row["block"]]:
                missing(row)
            elif row["block"] in (1, 3):
                act(plan, row, "attack")
        result = summarize(plan, rows)
        cell = result["cells"][0]
        self.assertEqual(cell["valid"], 10)
        self.assertEqual(cell["cooperate_count"], 6)
        self.assertEqual(cell["cooperation_rate"], .5)  # raw 6/10 would be wrong
        radius = math.sqrt(math.log(40)/2 * sum(1/(16*n) for n in counts))
        self.assertAlmostEqual(cell["cooperation_lower_95"], max(0, .5-radius))
        self.assertAlmostEqual(cell["cooperation_upper_95"], min(1, .5+radius))
        self.assertAlmostEqual(cell["cooperation_missing_lower"], 6/16)
        self.assertAlmostEqual(cell["cooperation_missing_upper"], 12/16)
        self.assertEqual(cell["strict_disagreement_count"], 4)
        self.assertEqual(cell["strict_valid"], 10)
        self.assertEqual(cell["optimal_rate"], .5)
        self.assertAlmostEqual(cell["mean_regret"], .05)
        self.assertAlmostEqual(cell["mean_human_payoff"], -1.7)
        self.assertEqual(result["known_cost_usd"], "0.010")
        self.assertEqual(result["attempts_with_unresolved_cost"], 6)

    def test_missing_block_suppresses_combined_estimate(self):
        plan, rows = fixture()
        for row in rows:
            if row["block"] == 0:
                missing(row, "not_attempted", attempted=False)
        result = summarize(plan, rows)
        cell = result["cells"][0]
        for key in ("cooperation_rate", "optimal_rate", "mean_regret", "mean_human_payoff"):
            self.assertIsNone(cell[key])
        self.assertEqual(cell["cooperation_missing_lower"], .75)
        self.assertEqual(cell["cooperation_missing_upper"], 1)
        self.assertEqual(result["attempted"], 12)
        self.assertEqual(result["attempts_with_unresolved_cost"], 0)

    def test_empty_cell_is_retained_with_full_missing_bounds(self):
        plan, rows = fixture()
        for row in rows:
            missing(row, "not_attempted", attempted=False)
        cell = summarize(plan, rows)["cells"][0]
        self.assertEqual(cell["valid"], 0)
        self.assertIsNone(cell["cooperation_rate"])
        self.assertEqual((cell["cooperation_missing_lower"], cell["cooperation_missing_upper"]), (0, 1))
        self.assertEqual((cell["regret_missing_lower"], cell["regret_missing_upper"]), (0, .1))
        self.assertEqual((cell["human_payoff_missing_lower"], cell["human_payoff_missing_upper"]), (-4.8, 1.4))

    def test_ties_do_not_inflate_strict_agreement(self):
        plan, rows = fixture(tie=True)
        for row in rows:
            if row["block"] % 2:
                act(plan, row, "attack")
        result = summarize(plan, rows)
        cell = result["cells"][0]
        self.assertTrue(cell["is_tie"])
        self.assertEqual(cell["optimal_rate"], 1)
        self.assertEqual(cell["optimal_count"], 16)
        self.assertEqual(cell["mean_regret"], 0)
        self.assertEqual(cell["strict_valid"], 0)
        self.assertIsNone(cell["strict_agreement_rate"])
        self.assertEqual(result["model_totals"][0]["tie_valid"], 16)

    def test_coverage_and_exact_scores_are_audited(self):
        plan, rows = fixture()
        for altered in (rows[:-1], rows+[rows[0]]):
            with self.assertRaises(ValueError):
                summarize(plan, altered)
        for key, value in (("margin", "0"), ("regret", "9"), ("human_payoff", "999"),
                           ("theoretical_best", ["attack"]), ("cost_usd", "NaN")):
            altered = deepcopy(rows)
            altered[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                summarize(plan, altered)

    def test_interval_is_not_overconfident_at_all_successes(self):
        center, low, high = interval([[1]*25 for _ in range(4)])
        self.assertEqual(center, 1)
        self.assertLess(low, 1)
        self.assertEqual(high, 1)
        self.assertEqual(interval([[1], [1], [], [1]]), (None, None, None))


@unittest.skipUnless(all(importlib.util.find_spec(p) for p in ("pandas", "seaborn", "sklearn", "matplotlib")),
                     "report packages are optional")
class ArtifactTests(unittest.TestCase):
    def test_report_retains_every_observation_and_separate_2d_figures(self):
        plan, rows = fixture(repetitions=1)
        missing(rows[0])
        fake_module = SimpleNamespace(observations=lambda directory: (plan, rows))
        with tempfile.TemporaryDirectory() as temp, patch.dict(sys.modules, {"gut.oversight_experiment": fake_module}):
            result = report(temp)
            output = Path(temp) / "analysis"
            self.assertEqual(len((output / "observations.csv").read_text().splitlines()), 5)
            self.assertTrue((output / "cells.csv").is_file())
            self.assertTrue((output / "report.html").is_file())
            self.assertIn("SYNTHETIC", (output / "report.html").read_text())
            self.assertIn("scikit-learn", result["package_versions"])
            self.assertEqual(result["confusion_matrices"][0]["valid_strict"], 3)
            self.assertTrue(all((output / f["file"]).is_file() and (output / f["svg"]).is_file()
                                for f in result["figures"]))
            self.assertFalse((output / "sweep-value.png").exists())
            self.assertIsNone(json.loads((output / "summary.json").read_text())["cells"][0]["cooperation_rate"])
