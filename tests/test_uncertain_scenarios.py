import unittest

from utility_threshold.games import (
    AUTONOMOUS_ESCALATION,
    CROSS_LAB_INCIDENT_RESPONSE,
    FRONTIER_DEPLOYMENT_RACE,
    INCIDENT_RESPONSE_PROTOCOL,
    autonomous_escalation_uncertainty,
    cross_lab_incident_response_uncertainty,
    frontier_deployment_uncertainty,
    incident_response_protocol_uncertainty,
    uncertain_scenario_from_id,
)


class ConcreteUncertainScenarioTests(unittest.TestCase):
    def test_deployment_states_change_payoffs_and_catastrophe_probability(self) -> None:
        game = frontier_deployment_uncertainty()
        race = FRONTIER_DEPLOYMENT_RACE.competitive_action
        profile = (race, race)
        self.assertEqual([state.state_id for state in game.states], [
            "contained_competition", "major_safety_failure", "systemic_failure"
        ])
        self.assertEqual(
            [outcome.value for outcome in game.payoff_distribution(profile, "row").outcomes],
            [1.2, -2.0, -20.0],
        )
        self.assertAlmostEqual(game.catastrophe_probability(profile), 0.15)

    def test_escalation_states_make_catastrophe_a_latent_event(self) -> None:
        game = autonomous_escalation_uncertainty()
        escalate = AUTONOMOUS_ESCALATION.competitive_action
        profile = (escalate, escalate)
        self.assertEqual(
            [outcome.value for outcome in game.payoff_distribution(profile, "row").outcomes],
            [-5.0, -30.0, -100.0],
        )
        self.assertAlmostEqual(game.catastrophe_probability(profile), 0.45)
        self.assertNotIn(profile, game.states[0].game.catastrophic_profiles)

    def test_intervention_is_applied_in_every_state(self) -> None:
        baseline = frontier_deployment_uncertainty()
        adjusted = frontier_deployment_uncertainty(intervention=2.0)
        cooperative = FRONTIER_DEPLOYMENT_RACE.cooperative_action
        competitive = FRONTIER_DEPLOYMENT_RACE.competitive_action
        profile = (competitive, cooperative)
        for before, after in zip(baseline.states, adjusted.states, strict=True):
            self.assertAlmostEqual(
                before.game.payoff(profile).row - after.game.payoff(profile).row, 2.0
            )

    def test_stag_hunt_states_quantify_latent_assurance_failure(self) -> None:
        game = cross_lab_incident_response_uncertainty()
        profile = (
            CROSS_LAB_INCIDENT_RESPONSE.cooperative_action,
            CROSS_LAB_INCIDENT_RESPONSE.competitive_action,
        )
        self.assertEqual(
            [outcome.value for outcome in game.payoff_distribution(profile, "row").outcomes],
            [0.5, -8.0, -40.0],
        )
        self.assertAlmostEqual(game.catastrophe_probability(profile), 0.55)
        self.assertTrue(game.expected_game().is_symmetric)

    def test_battle_states_preserve_asymmetry_and_latent_protocol_failure(self) -> None:
        game = incident_response_protocol_uncertainty()
        first, second = INCIDENT_RESPONSE_PROTOCOL.actions
        expected = game.expected_game()
        self.assertFalse(expected.is_symmetric)
        self.assertGreater(expected.payoff((first, first)).row, expected.payoff((second, second)).row)
        self.assertGreater(expected.payoff((second, second)).column, expected.payoff((first, first)).column)
        self.assertAlmostEqual(game.catastrophe_probability((first, second)), 0.50)
        self.assertAlmostEqual(game.catastrophe_probability((second, first)), 0.50)

    def test_intervention_uses_each_scenarios_declared_semantics(self) -> None:
        stag_before = cross_lab_incident_response_uncertainty()
        stag_after = cross_lab_incident_response_uncertainty(intervention=2.0)
        cooperate, safe = CROSS_LAB_INCIDENT_RESPONSE.actions
        self.assertEqual(
            stag_after.states[0].game.payoff((cooperate, safe)).row
            - stag_before.states[0].game.payoff((cooperate, safe)).row,
            2.0,
        )
        battle_before = incident_response_protocol_uncertainty()
        battle_after = incident_response_protocol_uncertainty(intervention=2.0)
        first, second = INCIDENT_RESPONSE_PROTOCOL.actions
        self.assertEqual(
            battle_after.states[0].game.payoff((first, first)).row
            - battle_before.states[0].game.payoff((first, first)).row,
            2.0,
        )
        self.assertEqual(
            battle_after.states[0].game.payoff((first, second)).row,
            battle_before.states[0].game.payoff((first, second)).row,
        )

    def test_registry_resolves_all_scenarios(self) -> None:
        expected = {
            FRONTIER_DEPLOYMENT_RACE.scenario_id: "prisoners_dilemma",
            AUTONOMOUS_ESCALATION.scenario_id: "chicken",
            CROSS_LAB_INCIDENT_RESPONSE.scenario_id: "stag_hunt",
            INCIDENT_RESPONSE_PROTOCOL.scenario_id: "battle_of_the_sexes",
        }
        self.assertEqual(
            {
                scenario_id: uncertain_scenario_from_id(scenario_id).family
                for scenario_id in expected
            },
            expected,
        )


if __name__ == "__main__":
    unittest.main()
