import unittest

from utility_threshold.core import (
    GameParams,
    GameState,
    deterring_defense,
    normal_form_mixed_nash,
    normal_form_nash,
    safety_margin,
    solve_stackelberg,
    threshold_action,
    verify_threshold_decision,
)
from utility_threshold.agents import CUPODVerifier, DUPOCVerifier, PDUPOCVerifier


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
        self.assertTrue(solution.deterred)
        self.assertTrue(any(candidate.defense == 0.0 for candidate in solution.candidates))
        self.assertIn("stationary point", solution.optimality_basis)
        equilibria = normal_form_nash(4.0, (0.0, 4.0), self.params)
        # This parameterization has no pure simultaneous equilibrium: the human
        # wants high defense against attack but low defense against cooperation.
        self.assertEqual(equilibria, [])

        mixed = normal_form_mixed_nash(4.0, (0.0, 4.0), self.params)
        self.assertIsNotNone(mixed)
        assert mixed is not None
        self.assertAlmostEqual(mixed.high_defense_probability, 0.8)
        self.assertAlmostEqual(mixed.attack_probability, 0.4)
        self.assertAlmostEqual(mixed.human_expected_utility, -8.0)
        self.assertAlmostEqual(mixed.ai_expected_utility, 0.0)

    def test_fully_mixed_equilibrium_is_absent_outside_interior_support(self) -> None:
        self.assertIsNone(normal_form_mixed_nash(100.0, (0.0, 4.0), self.params))
        with self.assertRaisesRegex(ValueError, "distinct defense"):
            normal_form_mixed_nash(4.0, (2.0, 2.0), self.params)

    def test_stackelberg_solver_finds_non_deterring_interior_optimum(self) -> None:
        solution = solve_stackelberg(100.0, self.params)
        self.assertFalse(solution.deterred)
        self.assertAlmostEqual(solution.defense, 5.0)
        self.assertAlmostEqual(solution.human_utility, -12.5)
        self.assertGreater(solution.human_utility, -20.0)

    def test_named_verifier_variants_expose_valid_certificates(self) -> None:
        unsafe = GameState(v=4.0, d=0.0)
        safe = GameState(v=4.0, d=4.0)
        dupoc = DUPOCVerifier()
        cupod = CUPODVerifier()
        self.assertEqual(dupoc.choose(safe, self.params), "COOPERATE")
        self.assertTrue(dupoc.certificate and dupoc.certificate.valid)
        self.assertEqual(cupod.choose(unsafe, self.params), "ATTACK")
        self.assertTrue(cupod.certificate and cupod.certificate.valid)
        self.assertGreater(PDUPOCVerifier().attack_probability(unsafe, self.params), 0.5)


if __name__ == "__main__":
    unittest.main()
