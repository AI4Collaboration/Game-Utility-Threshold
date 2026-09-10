import json
import unittest

from uncertainty_mechanisms_inspect import (
    RISK_CRITERIA,
    TREATMENTS,
    _analytic_worksheet,
    build_research_case,
    build_uncertainty_mechanism_samples,
    parse_structured_decision,
)


class StructuredInspectTaskTests(unittest.TestCase):
    def test_dataset_crosses_games_treatments_roles_beliefs_and_risk(self) -> None:
        dataset = build_uncertainty_mechanism_samples()
        self.assertEqual(len(dataset), 4 * len(TREATMENTS) * 2 * 2 * len(RISK_CRITERIA))
        metadata = [sample.metadata for sample in dataset]
        self.assertEqual({item["treatment"] for item in metadata}, set(TREATMENTS))
        self.assertEqual({item["risk_criterion"] for item in metadata}, set(RISK_CRITERIA))
        self.assertEqual({item["player"] for item in metadata}, {"row", "column"})
        self.assertEqual(
            {item["scenario_id"] for item in metadata},
            {
                "frontier_deployment_race",
                "autonomous_escalation",
                "cross_lab_incident_response",
                "incident_response_protocol",
            },
        )
        self.assertTrue(all(item["observability_contract"]["does_not_claim"] for item in metadata))

    def test_structured_parser_handles_fenced_and_prefaced_json(self) -> None:
        payload = {"final_action": "DEESCALATE", "confidence": 0.8}
        text = "worksheet follows\n```json\n" + json.dumps(payload) + "\n```"
        self.assertEqual(parse_structured_decision(text), payload)
        self.assertIsNone(parse_structured_decision("no structured object"))

    def test_analytic_worksheet_contains_exact_scores_and_catastrophe_fields(self) -> None:
        case = build_research_case(
            "autonomous_escalation",
            "contract_penalty",
            "row",
            0.75,
            "lower_tail_cvar",
        )
        worksheet = _analytic_worksheet(case)
        self.assertEqual(worksheet["final_action"], case.choice.action)
        self.assertEqual(set(worksheet["action_calculations"]), set(case.applications[0][1].permitted_actions["row"]))
        for values in worksheet["action_calculations"].values():
            self.assertIn("risk_score", values)
            self.assertIn("catastrophe_probability", values)

    def test_treatments_have_executable_effects(self) -> None:
        communication = build_research_case(
            "frontier_deployment_race", "communication", "row", 0.75, "expected_value"
        )
        self.assertLess(
            communication.decision_belief.probability(communication.uncertain_game.competitive_action),
            0.75,
        )
        commitment = build_research_case(
            "frontier_deployment_race", "binding_commitment", "row", 0.75, "expected_value"
        )
        self.assertEqual(len(commitment.choice.action_evaluations), 1)
        mediator = build_research_case(
            "autonomous_escalation", "trusted_mediator", "row", 0.25, "expected_value"
        )
        self.assertTrue(mediator.mediator_analysis["is_correlated_equilibrium"])
        self.assertTrue(mediator.choice.obeyed_mediator)

        battle_first = build_research_case(
            "incident_response_protocol", "trusted_mediator", "row", 0.25, "expected_value",
            mediator_profile_index=0,
        )
        battle_second = build_research_case(
            "incident_response_protocol", "trusted_mediator", "row", 0.25, "expected_value",
            mediator_profile_index=1,
        )
        self.assertNotEqual(
            battle_first.treatment_design["target_profile"],
            battle_second.treatment_design["target_profile"],
        )
        self.assertTrue(battle_first.mediator_analysis["is_correlated_equilibrium"])

    def test_battle_side_payment_is_neutral_coordination_assurance(self) -> None:
        case = build_research_case(
            "incident_response_protocol", "side_payment", "column", 0.75, "expected_value"
        )
        trace = case.applications[0][1].mechanism_trace[0]
        self.assertEqual(trace["mechanism_id"], "coordination_subsidy")

    def test_mediator_target_and_risk_optimum_are_both_auditable(self) -> None:
        case = build_research_case(
            "incident_response_protocol",
            "trusted_mediator",
            "row",
            0.25,
            "expected_value",
            mediator_profile_index=1,
        )
        record = case.choice.record()
        self.assertIn("optimal_actions", record)
        self.assertEqual(record["action"], case.mediator_recommendation)


if __name__ == "__main__":
    unittest.main()
