import unittest

from model_gameplay_inspect import (
    GAMEPLAY_SCENARIOS,
    GAMEPLAY_TREATMENTS,
    analyze_joint_outcome,
    build_gameplay_case,
    build_model_gameplay_samples,
    parse_action_decision,
    parse_public_message,
)
from utility_threshold.games import build_state_applications


class ModelGameplayInspectTests(unittest.TestCase):
    def test_dataset_is_full_factorial_and_role_order_is_counterbalanced(self) -> None:
        dataset = build_model_gameplay_samples(replicates=2)
        self.assertEqual(
            len(dataset), len(GAMEPLAY_SCENARIOS) * len(GAMEPLAY_TREATMENTS) * 2
        )
        for sample in dataset:
            self.assertNotEqual(
                sample.metadata["row_action_order"], sample.metadata["column_action_order"]
            )
            self.assertTrue(sample.metadata["observability_contract"]["role_isolation"])

    def test_utility_maximization_is_an_explicit_experimental_condition(self) -> None:
        dataset = build_model_gameplay_samples(
            scenario_ids=("frontier_deployment_race",),
            treatments=("baseline",),
            objectives=("individual_expected_utility",),
        )
        sample = dataset[0]
        self.assertEqual(sample.metadata["objective"], "individual_expected_utility")
        case = build_gameplay_case(
            "frontier_deployment_race",
            "baseline",
            objective="individual_expected_utility",
        )
        self.assertEqual(case.objective, "individual_expected_utility")

    def test_action_and_message_parsers_preserve_structured_worksheets(self) -> None:
        actions = ("DEESCALATE", "ESCALATE")
        action_text = (
            '{"strategic_reasoning_summary":"tail risk dominates",'
            '"final_action":"DEESCALATE","confidence":0.9}'
        )
        decision = parse_action_decision(action_text, actions)
        self.assertEqual(decision["action"], "DEESCALATE")
        self.assertEqual(decision["worksheet"]["confidence"], 0.9)
        message = parse_public_message(
            '{"claimed_action":"ESCALATE","public_message":"I will escalate."}', actions
        )
        self.assertTrue(message["valid"])
        self.assertEqual(message["claimed_action"], "ESCALATE")

    def test_joint_resolution_marks_pd_defection_as_nash(self) -> None:
        case = build_gameplay_case("frontier_deployment_race", "baseline")
        competitive = case.game.competitive_action
        decision = {"action": competitive, "valid": True, "confidence": 1.0}
        joint = analyze_joint_outcome(case, decision, decision)
        self.assertTrue(joint["valid_joint_action"])
        self.assertTrue(joint["is_expected_payoff_nash"])
        self.assertTrue(joint["mutual_competition"])
        self.assertAlmostEqual(joint["resolution"]["catastrophe_probability"], 0.15)

    def test_mediator_resolution_tracks_private_recommendation_compliance(self) -> None:
        case = build_gameplay_case("autonomous_escalation", "trusted_mediator")
        row_action, column_action = case.mediator_joint_recommendation
        joint = analyze_joint_outcome(
            case,
            {"action": row_action, "valid": True, "confidence": 1.0},
            {"action": column_action, "valid": True, "confidence": 1.0},
        )
        self.assertEqual(joint["mediator_compliance"], 1.0)
        self.assertEqual(joint["resolution"]["catastrophe_probability"], 0.0)
        self.assertTrue(joint["is_expected_payoff_nash"])

    def test_binding_commitment_rejects_inconsistent_profile(self) -> None:
        case = build_gameplay_case("frontier_deployment_race", "binding_commitment")
        joint = analyze_joint_outcome(
            case,
            {"action": case.game.competitive_action, "valid": False},
            {"action": case.game.cooperative_action, "valid": True},
        )
        self.assertFalse(joint["valid_joint_action"])

    def test_battle_metrics_separate_coordination_from_focal_preference(self) -> None:
        case = build_gameplay_case("incident_response_protocol", "baseline")
        first, _ = case.game.actions
        joint = analyze_joint_outcome(
            case,
            {"action": first, "valid": True, "confidence": 1.0},
            {"action": first, "valid": True, "confidence": 1.0},
        )
        self.assertTrue(joint["coordination_success"])
        self.assertTrue(joint["structural_success"])
        self.assertTrue(joint["row_preferred_coordination"])
        self.assertFalse(joint["column_preferred_coordination"])
        self.assertFalse(joint["miscoordination"])

    def test_new_game_treatments_have_family_specific_effects(self) -> None:
        stag = build_gameplay_case("cross_lab_incident_response", "binding_commitment")
        self.assertEqual(
            stag.treatment_design["target_profile"],
            (stag.game.cooperative_action, stag.game.cooperative_action),
        )
        battle = build_gameplay_case("incident_response_protocol", "side_payment")
        applications = build_state_applications(battle.game, battle.stack)
        self.assertEqual(
            applications[0][1].mechanism_trace[0]["mechanism_id"],
            "coordination_subsidy",
        )


if __name__ == "__main__":
    unittest.main()
