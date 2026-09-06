import unittest

from utility_threshold.games import (
    AUTONOMOUS_ESCALATION,
    FRONTIER_DEPLOYMENT_RACE,
    autonomous_escalation_uncertainty,
    frontier_deployment_uncertainty,
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

    def test_registry_resolves_both_scenarios(self) -> None:
        self.assertEqual(
            uncertain_scenario_from_id(FRONTIER_DEPLOYMENT_RACE.scenario_id).family,
            "prisoners_dilemma",
        )
        self.assertEqual(
            uncertain_scenario_from_id(AUTONOMOUS_ESCALATION.scenario_id).family,
            "chicken",
        )


if __name__ == "__main__":
    unittest.main()
