import unittest

from utility_threshold.games import (
    BindingCommitment,
    ContractPenalty,
    Payoff,
    SidePaymentMechanism,
    as_application,
    cooperation_subsidy,
    coordination_subsidy,
    exploitation_transfer,
    prisoners_dilemma,
    battle_of_the_sexes,
    treatment_design,
    treatment_subsidy,
    zero_transfers,
)


class CommitmentAndPenaltyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = prisoners_dilemma()
        self.cooperate = self.game.cooperative_action
        self.defect = self.game.competitive_action

    def test_mutual_binding_commitment_fixes_the_safe_profile(self) -> None:
        application = BindingCommitment(self.cooperate, self.cooperate).apply(self.game)
        self.assertEqual(application.allowed_profiles, ((self.cooperate, self.cooperate),))
        self.assertEqual(application.pure_nash_equilibria(), ((self.cooperate, self.cooperate),))
        self.assertEqual(application.payoff((self.cooperate, self.cooperate)), Payoff(3.0, 3.0))
        self.assertEqual(application.mechanism_trace[0]["mechanism_id"], "binding_commitment")

    def test_one_sided_commitment_changes_only_one_action_set(self) -> None:
        application = BindingCommitment(row_action=self.cooperate).apply(self.game)
        self.assertEqual(application.permitted_actions["row"], (self.cooperate,))
        self.assertEqual(application.permitted_actions["column"], self.game.actions)
        self.assertEqual(application.pure_nash_equilibria(), ((self.cooperate, self.defect),))

    def test_noisy_contract_penalty_uses_expected_enforcement(self) -> None:
        contract = ContractPenalty(
            agreed_profile=(self.cooperate, self.cooperate),
            penalty=10.0,
            deviation_detection_probability=0.5,
            false_positive_probability=0.1,
            enforcement_probability=0.5,
        )
        application = contract.apply(self.game)
        self.assertEqual(contract.expected_deviation_penalty, 2.5)
        self.assertEqual(contract.expected_false_positive_penalty, 0.5)
        self.assertEqual(application.payoff((self.defect, self.cooperate)), Payoff(2.5, -0.5))
        self.assertEqual(
            application.best_responses("row", self.cooperate),
            (self.cooperate, self.defect),
        )

        stronger_application = ContractPenalty(
            agreed_profile=(self.cooperate, self.cooperate),
            penalty=12.0,
            deviation_detection_probability=0.5,
            false_positive_probability=0.1,
            enforcement_probability=0.5,
        ).apply(self.game)
        self.assertEqual(
            stronger_application.best_responses("row", self.cooperate),
            (self.cooperate,),
        )
        records = application.outcome_records()
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0]["payoff_delta"], {"row": -0.5, "column": -0.5})

    def test_mechanisms_compose_and_retain_ordered_trace(self) -> None:
        penalized = ContractPenalty((self.cooperate, self.cooperate), penalty=3.0).apply(self.game)
        committed = BindingCommitment(column_action=self.cooperate).apply(penalized)
        self.assertEqual([entry["mechanism_id"] for entry in committed.mechanism_trace], [
            "contract_with_penalties", "binding_commitment"
        ])
        self.assertEqual(committed.permitted_actions["column"], (self.cooperate,))


class TransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = prisoners_dilemma()
        self.cooperate = self.game.cooperative_action
        self.defect = self.game.competitive_action

    def test_exploitation_transfer_is_budget_balanced(self) -> None:
        application = exploitation_transfer(self.game, 2.0).apply(self.game)
        self.assertEqual(application.payoff((self.cooperate, self.defect)), Payoff(2.0, 3.0))
        self.assertEqual(application.payoff((self.defect, self.cooperate)), Payoff(3.0, 2.0))
        for record in application.mechanism_trace[0]["transfers"]:
            self.assertEqual(record["external_budget"], 0.0)

    def test_external_cooperation_subsidy_can_change_dominance(self) -> None:
        application = cooperation_subsidy(self.game, 2.1).apply(self.game)
        self.assertEqual(application.best_responses("row", self.cooperate), (self.cooperate,))
        self.assertEqual(application.best_responses("row", self.defect), (self.cooperate,))
        self.assertEqual(application.pure_nash_equilibria(), ((self.cooperate, self.cooperate),))

    def test_unbalanced_transfer_is_rejected_when_balance_required(self) -> None:
        transfers = zero_transfers(self.game)
        transfers[(self.cooperate, self.cooperate)] = Payoff(1.0, 1.0)
        with self.assertRaises(ValueError):
            SidePaymentMechanism(transfers, require_budget_balance=True).apply(self.game)

    def test_baseline_application_is_lossless(self) -> None:
        application = as_application(self.game)
        self.assertEqual(application.pure_nash_equilibria(), self.game.pure_nash_equilibria())
        self.assertEqual(application.outcome_records()[0]["payoff_delta"], {"row": 0.0, "column": 0.0})

    def test_neutral_coordination_subsidy_preserves_opposed_preferences(self) -> None:
        game = battle_of_the_sexes()
        application = coordination_subsidy(game, 2.0).apply(game)
        first, second = game.actions
        self.assertEqual(
            application.payoff((first, first)),
            Payoff(game.payoff((first, first)).row + 2.0, game.payoff((first, first)).column + 2.0),
        )
        self.assertEqual(application.payoff((first, second)), game.payoff((first, second)))
        self.assertGreater(application.payoff((first, first)).row, application.payoff((second, second)).row)
        self.assertGreater(application.payoff((second, second)).column, application.payoff((first, first)).column)

    def test_family_aware_treatments_balance_equilibrium_selection(self) -> None:
        game = battle_of_the_sexes()
        first = treatment_design(game, focal_index=0)
        second = treatment_design(game, focal_index=1)
        self.assertNotEqual(first.target_profile, second.target_profile)
        self.assertEqual(set(first.mediator_distribution), set(game.coordination_profiles))
        self.assertEqual(treatment_subsidy(game, 1.0).mechanism_id, "coordination_subsidy")


if __name__ == "__main__":
    unittest.main()
