import unittest

from utility_threshold.games import (
    Payoff,
    SymmetricTwoByTwoGame,
    audit_research_catalog,
    validate_game_family,
)


class GameValidationTests(unittest.TestCase):
    def test_complete_research_catalog_satisfies_every_constraint(self) -> None:
        report = audit_research_catalog()

        self.assertTrue(report.valid)
        self.assertEqual(report.failures, ())
        self.assertGreater(report.record()["check_count"], 150)

    def test_prisoners_dilemma_checks_expose_values_and_positive_margins(self) -> None:
        report = audit_research_catalog()
        checks = {
            (check.subject, check.check_id): check
            for check in report.checks
        }
        check = checks[
            ("scenario:frontier_deployment_race:canonical", "row_T_gt_R")
        ]

        self.assertEqual(check.expression, "row.T > row.R")
        self.assertEqual(check.observed, {"row.T": 5.0, "row.R": 3.0})
        self.assertEqual(check.margin, 2.0)
        self.assertTrue(check.passed)

    def test_independent_validator_rejects_mislabeled_prisoners_dilemma(self) -> None:
        game = SymmetricTwoByTwoGame(
            game_id="invalid_pd",
            name="Invalid Prisoner's Dilemma",
            family="prisoners_dilemma",
            actions=("COOPERATE", "DEFECT"),
            cooperative_action="COOPERATE",
            competitive_action="DEFECT",
            payoffs={
                ("COOPERATE", "COOPERATE"): Payoff(5.0, 5.0),
                ("COOPERATE", "DEFECT"): Payoff(0.0, 3.0),
                ("DEFECT", "COOPERATE"): Payoff(3.0, 0.0),
                ("DEFECT", "DEFECT"): Payoff(1.0, 1.0),
            },
        )

        checks = validate_game_family(game)

        self.assertFalse(all(check.passed for check in checks))
        failed_ids = {check.check_id for check in checks if not check.passed}
        self.assertIn("row_T_gt_R", failed_ids)
        self.assertIn("column_T_gt_R", failed_ids)
        self.assertIn("strict_defection_dominance", failed_ids)

    def test_scenario_specific_semantics_are_explicitly_checked(self) -> None:
        report = audit_research_catalog()
        checks = {check.check_id: check for check in report.checks}

        self.assertTrue(checks["safe_equilibrium_risk_dominant"].passed)
        self.assertTrue(checks["preferred_belief_threshold_below_half"].passed)
        self.assertTrue(checks["severity_loss_strictly_worsens_1"].passed)


if __name__ == "__main__":
    unittest.main()
