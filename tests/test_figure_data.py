import copy
import json
from pathlib import Path
import unittest

from utility_threshold.figure_data import (
    build_figure_data, game_matrix, objective_comparison, summarize_cells,
)

ROOT = Path(__file__).resolve().parents[1]


class FigureDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gameplay = json.loads((ROOT / "results/model_gameplay_replication_02.json").read_text())
        cls.phase = json.loads((ROOT / "results/phase_one_model_eval_replication_02.json").read_text())
        cls.figures = build_figure_data(cls.gameplay, cls.phase)

    def test_margins_weight_observations_not_stratum_means(self):
        table = summarize_cells(["a"], ["large", "small"], {("a", "large"): [1] * 25, ("a", "small"): [0] * 4})
        self.assertAlmostEqual(table["values"][0][-1], 25 / 29)
        self.assertEqual(table["counts"][0][-1], 29)

    def test_role_attribution_includes_both_selfplay_roles(self):
        table = self.figures["matrices"]["01_model_welfare"]
        self.assertEqual(table["counts"][0], [96] * 4 + [384])
        self.assertEqual(table["counts"][-1][-1], 1536)
        expected = sum(r["scores"]["utilitarian_optimal"] for r in self.gameplay["records"]) / 768
        self.assertAlmostEqual(table["values"][-1][-1], expected)

    def test_individual_actions_use_each_roles_action(self):
        table = game_matrix(self.gameplay["records"], "cooperative_action_rate")
        rows = self.gameplay["records"]
        expected = [r["joint_outcome"]["profile"][i] == r["first_action"]
                    for r in rows for i, role in enumerate(("row", "column")) if r[f"{role}_provider"] == "anthropic"]
        self.assertAlmostEqual(table["values"][0][-1], sum(expected) / len(expected))

    def test_missing_objective_partner_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "matched"):
            objective_comparison(self.gameplay["records"][1:], by="model")

    def test_incomplete_or_nonfinite_results_are_rejected(self):
        bad = {**self.gameplay, "records": self.gameplay["records"][1:]}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            build_figure_data(bad, self.phase)
        bad = copy.deepcopy(self.gameplay)
        bad["records"][0]["scores"]["utilitarian_optimal"] = float("nan")
        with self.assertRaisesRegex(ValueError, "finite rate"):
            build_figure_data(bad, self.phase)

    def test_threshold_accuracy_keeps_invalid_action_and_unequal_strata(self):
        table = self.figures["matrices"]["10_threshold_accuracy"]
        self.assertEqual(table["counts"][0], [25, 4, 5, 5, 39])
        self.assertEqual(table["counts"][-1][-1], 156)
        for row, provider in enumerate(("anthropic", "openai", "google", "meta")):
            self.assertAlmostEqual(table["values"][row][-1], self.phase["aggregates"]["by_provider"][provider]["optimal_action"])

    def test_thresholds_distinguish_expected_and_deterministic_games(self):
        thresholds = self.figures["11_analytic_thresholds"]
        self.assertEqual(thresholds["frontier_deployment_race"]["deterministic"]["dominance"], 2)
        self.assertAlmostEqual(thresholds["frontier_deployment_race"]["expected"]["dominance"], 2.515)
        self.assertAlmostEqual(thresholds["cross_lab_incident_response"]["expected"]["dominance"], 11.025)
        self.assertNotIn("dominance", thresholds["incident_response_protocol"]["expected"])


if __name__ == "__main__":
    unittest.main()
