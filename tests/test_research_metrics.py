import json
from pathlib import Path
import unittest

from utility_threshold.research_metrics import build_metric_atlas, matrix, observed_brackets

ROOT = Path(__file__).resolve().parents[1]


class ResearchMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gameplay = json.loads((ROOT / "results/model_gameplay_replication_02.json").read_text())
        cls.phase = json.loads((ROOT / "results/phase_one_model_eval_replication_02.json").read_text())
        cls.atlas = build_metric_atlas(cls.gameplay, cls.phase)

    def test_catalog_covers_every_recorded_score(self):
        self.assertTrue(set(self.gameplay["records"][0]["scores"]) <= set(self.atlas["metric_specs"]))
        self.assertTrue(set(self.phase["records"][0]["scores"]) <= set(self.atlas["phase_metric_specs"]))

    def test_complete_atlas_is_strict_json_serializable(self):
        decoded = json.loads(json.dumps(self.atlas, allow_nan=False))
        self.assertEqual(len(decoded["threshold_catalog"]), 20)
        mixed = decoded["threshold_catalog"][5]["mixed_equilibrium"]
        self.assertAlmostEqual(sum(mixed["row"].values()), 1)

    def test_nonapplicable_mechanisms_are_missing_not_failures(self):
        table = self.atlas["matrices"]["treatment:communication_honesty"]
        self.assertIsNone(table["values"][0][0])
        self.assertEqual(table["counts"][0][0], 0)
        self.assertEqual(table["eligible"][0][0], 32)
        self.assertEqual(table["counts"][-1][-1], 128)
        expected = [r["joint_outcome"]["communication_honesty"] for r in self.gameplay["records"] if r["treatment"] == "communication"]
        self.assertAlmostEqual(table["values"][-1][-1], sum(expected) / 128)

    def test_action_complements_and_joint_outcome_partition(self):
        for r in self.atlas["records"]:
            m = r["metrics"]
            self.assertEqual(m["cooperative_action_rate"] + m["second_action_rate"], 1)
            self.assertEqual(m["mutual_cooperation"] + m["mutual_competition"] + m["miscoordination"], 1)
            self.assertEqual(m["expected_payoff_nash"], int(all(role["overrides"]["best_response_rate"] for role in r["roles"])))

    def test_own_regret_is_assigned_to_the_correct_role(self):
        values = [r["joint_outcome"][f"{role}_expected_regret"] for r in self.gameplay["records"]
                  for role in ("row", "column") if r[f"{role}_provider"] == "anthropic"]
        actual = self.atlas["matrices"]["model:own_expected_regret"]["values"][0][-1]
        self.assertAlmostEqual(actual, sum(values) / len(values))

    def test_filters_preserve_ordered_pair_denominators(self):
        table = matrix(self.atlas["records"], "expected_payoff_nash", by="crossplay",
                       objective="open_ended", treatment="baseline", game="frontier_deployment_race")
        self.assertEqual(table["counts"][0], [1, 1, 1, 1, 4])
        self.assertEqual(table["counts"][-1][-1], 16)

    def test_threshold_transition_matches_existing_analysis(self):
        transitions = self.atlas["threshold_transitions"]
        self.assertEqual(transitions["transition_count"], 20)
        self.assertEqual(transitions["expected_transition_rate"], .55)

    def test_nonmonotonic_actions_do_not_become_a_threshold_estimate(self):
        rows = [dict(provider=p, defense=2, critical_v=2.5, v=v, observed=action)
                for p in self.atlas["labels"]["models"] for v, action in ((2, "ATTACK"), (3, "COOPERATE"))]
        self.assertTrue(all(not r["compatible"] for r in observed_brackets(rows)))

    def test_invalid_phase_action_is_separate_from_attack(self):
        rows = self.atlas["phase_records"]
        self.assertEqual(sum(r["metrics"]["invalid_action"] for r in rows), 1)
        for r in rows:
            self.assertEqual(r["metrics"]["safe_action"] + r["metrics"]["attack_action"] + r["metrics"]["invalid_action"], 1)

    def test_derived_thresholds_include_false_positive_penalties(self):
        pd, chicken, stag, protocol = self.atlas["contract_thresholds"]
        self.assertAlmostEqual(pd["effective_advantage"], 3.78)
        self.assertAlmostEqual(pd["target_nash_boundary"], 2.515 / .63)
        self.assertAlmostEqual(stag["target_dominance_boundary"], 17.5)
        self.assertAlmostEqual(protocol["target_dominance_boundary"], 35)
        self.assertFalse(chicken["target_actions_strictly_dominant"])

    def test_expected_value_risk_threshold_matches_direct_utility_gap(self):
        expected = {r["scenario"]: r for r in self.atlas["threshold_catalog"] if r["variant"] == "Expected"}
        for result in self.atlas["risk_thresholds"]:
            if result["criterion"] != "expected_value":
                continue
            base = expected[result["scenario"]]
            q = result["opponent_first_probability"]
            direct = max(0, q * base["against_first"] + (1-q) * base["against_second"])
            self.assertAlmostEqual(result["threshold"], direct, places=6)


if __name__ == "__main__":
    unittest.main()
