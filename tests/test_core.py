import unittest

from utility_threshold.core import (
    GameParams,
    GameState,
    deterring_defense,
    normal_form_nash,
    safety_margin,
    solve_stackelberg,
    threshold_action,
    verify_threshold_decision,
)


class UtilityThresholdGameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.params = GameParams()

    def test_threshold_switches_at_the_safety_boundary(self) -> None:
        self.assertEqual(threshold_action(GameState(v=4.0, d=0.0), self.params), "ATTACK")
        self.assertEqual(threshold_action(GameState(v=4.0, d=4.0), self.params), "COOPERATE")

    def test_minimum_deterring_defense_has_non_negative_margin(self) -> None:
        defense = deterring_defense(4.0, self.params)
        self.assertIsNotNone(defense)
        assert defense is not None
        self.assertGreaterEqual(safety_margin(GameState(v=4.0, d=defense), self.params), -1e-7)

    def test_infeasible_deterrence_is_explicit(self) -> None:
        self.assertIsNone(deterring_defense(100.0, self.params, max_defense=10.0))

    def test_proof_certificate_detects_an_incorrect_action(self) -> None:
        certificate = verify_threshold_decision(GameState(v=4.0, d=0.0), self.params, "COOPERATE")
        self.assertFalse(certificate.valid)
        self.assertIn("U_attack", certificate.inequality)

    def test_stackelberg_solution_and_normal_form_reduction(self) -> None:
        solution = solve_stackelberg(4.0, self.params)
        self.assertIsNotNone(solution.defense)
        self.assertTrue(solution.deterred)
        equilibria = normal_form_nash(4.0, (0.0, 4.0), self.params)
        # This parameterization has no pure simultaneous equilibrium: the human
        # wants high defense against attack but low defense against cooperation.
        self.assertEqual(equilibria, [])


if __name__ == "__main__":
    unittest.main()
