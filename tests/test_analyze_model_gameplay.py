import unittest

from analyze_model_gameplay import audit_summary, compare, filter_summary, summarize


def record(
    row: str,
    column: str,
    *,
    treatment: str = "baseline",
    cooperation: float = 1.0,
) -> dict:
    return {
        "sample_id": f"{row}-{column}",
        "row_provider": row,
        "column_provider": column,
        "scenario_id": "test_game",
        "treatment": treatment,
        "replicate": 0,
        "cooperative_action": "SAFE",
        "joint_outcome": {"profile": ["SAFE", "SAFE"]},
        "scores": {
            "valid_joint_action": 1,
            "cooperative_action_rate": cooperation,
            "mutual_cooperation": cooperation,
            "mutual_competition": 0,
            "catastrophic_realization": 0,
            "catastrophe_probability": 0,
            "expected_welfare": 6 * cooperation,
            "expected_payoff_nash": cooperation,
            "pareto_efficient": 1,
        },
    }


class ModelGameplayAnalysisTests(unittest.TestCase):
    def test_audit_accepts_complete_ordered_pair_factorial(self) -> None:
        payload = {
            "failed_pairs": [],
            "records": [
                record("a", "a"),
                record("a", "b"),
                record("b", "a"),
                record("b", "b"),
            ],
        }
        audit = audit_summary(payload)
        self.assertTrue(audit["complete"])
        self.assertEqual(audit["expected_record_count"], 4)
        self.assertEqual(audit["dimensions"]["objectives"], ["open_ended"])

    def test_audit_rejects_duplicate_and_invalid_cells(self) -> None:
        bad = record("a", "a")
        bad["scores"]["valid_joint_action"] = 0
        audit = audit_summary({"records": [bad, bad], "failed_pairs": []})
        self.assertFalse(audit["complete"])
        self.assertEqual(len(audit["duplicate_cells"]), 1)
        self.assertEqual(len(audit["invalid_samples"]), 2)

    def test_summarize_and_compare_compute_exact_deltas(self) -> None:
        baseline = {"records": [record("a", "a", cooperation=1.0)]}
        comparison = {"records": [record("a", "a", cooperation=0.5)]}
        self.assertEqual(summarize(baseline)["overall"]["expected_welfare"], 6.0)
        self.assertEqual(
            summarize(baseline)["by_objective"]["open_ended"]["games"], 1
        )
        self.assertEqual(
            summarize(baseline)["by_ordered_pair"]["a->a"]["games"], 1
        )
        delta = compare(baseline, comparison)
        self.assertEqual(delta["overall"]["cooperative_action_rate"], -0.5)
        self.assertEqual(delta["by_treatment"]["baseline"]["expected_welfare"], -3.0)

    def test_filter_summary_selects_matching_conditions(self) -> None:
        naturalistic = record("a", "a")
        utility = record("a", "a", treatment="communication")
        utility["objective"] = "individual_expected_utility"
        payload = {"records": [naturalistic, utility], "failed_pairs": []}

        filtered = filter_summary(
            payload,
            objectives=["individual_expected_utility"],
            scenarios=["test_game"],
        )

        self.assertEqual(filtered["records"], [utility])
        self.assertEqual(len(payload["records"]), 2)

    def test_filter_summary_rejects_empty_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected no gameplay records"):
            filter_summary(
                {"records": [record("a", "a")]}, objectives=["missing"]
            )


if __name__ == "__main__":
    unittest.main()
