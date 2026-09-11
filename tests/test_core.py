import unittest
from math import inf, nan

from utility_threshold.core import (
    GameParams,
    GameState,
    deterring_defense,
    human_utility,
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

    def test_invalid_parameters_and_states_fail_closed(self) -> None:
        for kwargs in (
            {"R": 0.0},
            {"p": -1.0},
            {"L": -1.0},
            {"defense_cost_scale": -0.1},
            {"g": nan},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                GameParams(**kwargs)
        for state in ((-1.0, 0.0), (1.0, -1.0), (inf, 0.0)):
            with self.subTest(state=state), self.assertRaises(ValueError):
                GameState(v=state[0], d=state[1])

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

    def test_stackelberg_certificate_dominates_dense_parameter_sweeps(self) -> None:
        for v in (1.0, 4.0, 8.0, 20.0, 100.0):
            for loss in (1.0, 20.0, 100.0):
                for cost_scale in (0.1, 0.3, 2.0):
                    for max_defense in (2.0, 10.0):
                        with self.subTest(
                            v=v,
                            loss=loss,
                            cost_scale=cost_scale,
                            max_defense=max_defense,
                        ):
                            params = GameParams(L=loss, defense_cost_scale=cost_scale)
                            solution = solve_stackelberg(v, params, max_defense=max_defense)
                            grid_best = max(
                                human_utility(
                                    threshold_action(state, params),
                                    state,
                                    params,
                                )
                                for index in range(10_001)
                                for state in [GameState(
                                    v=v,
                                    d=max_defense * index / 10_000,
                                )]
                            )
                            self.assertGreaterEqual(
                                solution.human_utility + 1e-6,
                                grid_best,
                            )

    def test_named_verifier_variants_expose_valid_certificates(self) -> None:
        unsafe = GameState(v=4.0, d=0.0)
        safe = GameState(v=4.0, d=4.0)
        dupoc = DUPOCVerifier()
        cupod = CUPODVerifier()
        self.assertEqual(dupoc.choose(safe, self.params), "COOPERATE")
        self.assertTrue(dupoc.certificate and dupoc.certificate.valid)
        self.assertEqual(cupod.choose(unsafe, self.params), "ATTACK")
        self.assertTrue(cupod.certificate and cupod.certificate.valid)
        pdupoc = PDUPOCVerifier()
        self.assertGreater(pdupoc.attack_probability(unsafe, self.params), 0.5)
        action = pdupoc.choose(unsafe, self.params)
        self.assertIsNotNone(pdupoc.certificate)
        assert pdupoc.certificate is not None
        self.assertTrue(pdupoc.certificate.valid)
        self.assertEqual(pdupoc.certificate.action, action)
        self.assertEqual(
            action == "ATTACK",
            pdupoc.certificate.draw < pdupoc.certificate.attack_probability,
        )


if __name__ == "__main__":
    unittest.main()
