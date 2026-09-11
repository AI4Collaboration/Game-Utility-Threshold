import unittest

from run_phase_one_policy_eval import POLICIES, aggregate_policy_records


class PhaseOnePolicyRunnerTests(unittest.TestCase):
    def test_required_agent_families_are_registered(self) -> None:
        self.assertEqual(len(POLICIES), 8)
        self.assertTrue({"cooperate", "defect", "dupoc", "cupod", "pdupoc"} <= set(POLICIES))

    def test_policy_aggregation_distinguishes_certificates(self) -> None:
        records = [{
            "policy": "pdupoc",
            "scores": {"optimal_action": 1, "utility_regret": 0.0},
            "certificate": {"valid": True},
            "probabilistic_certificate": {"valid": True},
        }]
        summary = aggregate_policy_records(records)["pdupoc"]
        self.assertEqual(summary["optimal_action_rate"], 1.0)
        self.assertEqual(summary["valid_certificate_rate"], 1.0)
        self.assertEqual(summary["valid_probabilistic_certificate_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
