"""Independent enumerations check the sequential solver and its tie handling."""
from fractions import Fraction as F
from itertools import product
import unittest

from gut.oversight import ACTIONS, DEFENSES, Oversight


class OversightTests(unittest.TestCase):
    def test_default_payoffs_and_exact_threshold(self):
        game = Oversight()
        self.assertEqual(game.payoff(0, "attack"), (-6, 3))
        self.assertEqual(game.payoff(1, "attack"), (-2, -4))
        self.assertEqual(game.payoff(F(3, 10), "cooperate"), (F(7, 5), 1))
        self.assertEqual(game.thresholds(0)["d"]["root"], F(2, 7))
        self.assertEqual(game.best_responses(F(2, 7)), ACTIONS)
        self.assertEqual(game.best_responses(F(2, 7)-F(1, 100000)), ("attack",))
        self.assertEqual(game.best_responses(F(2, 7)+F(1, 100000)), ("cooperate",))
        solution = game.equilibria()
        self.assertEqual([(x["d"], x["action"]) for x in solution["stackelberg_favorable"]],
                         [(F(3, 10), "cooperate")])

    def test_every_threshold_is_a_root_and_direction_is_correct(self):
        game = Oversight()
        for d in (F(0), F(3, 10), F(1)):
            for name, row in game.thresholds(d).items():
                root = row["root"]
                if root is not None:
                    self.assertEqual(row["intercept"]+row["slope"]*root, 0)
                if row["in_domain"]:
                    changed = {**game.__dict__, **({name: root} if name != "d" else {})}
                    self.assertEqual(Oversight(**changed).margin(root if name == "d" else d), 0)
        self.assertEqual(game.thresholds(0)["p"]["cooperate_when"], "never")
        self.assertIsNone(game.thresholds(1)["v"]["root"])
        self.assertEqual(game.thresholds(1)["v"]["cooperate_when"], "always")
        zero = Oversight(v=0, r=0, a=0, b=0, p=0)
        self.assertEqual(zero.thresholds(0)["d"]["cooperate_when"], "always_tied")
        self.assertFalse(Oversight(b=100).thresholds(0)["d"]["in_domain"])

    def test_compact_solver_matches_exhaustive_strategy_enumeration(self):
        defenses = (F(0), F(1, 2), F(1))
        # Include exact ties, zero costs, identical human payoffs, and high costs.
        for a, p, c, h in product((0, 1), (0, 2), (0, 3), (0, 4)):
            game = Oversight(v=4, r=1, a=a, p=p, b=1, w=0, h=h, c=c)
            expected = {False: {}, True: {}}
            for strategy in product(ACTIONS, repeat=len(defenses)):
                for i, d in enumerate(defenses):
                    action = strategy[i]
                    human, ai = game.payoff(d, action)
                    if any(game.payoff(d, other)[1] > ai for other in ACTIONS):
                        continue
                    if any(game.payoff(other, strategy[j])[0] > human
                           for j, other in enumerate(defenses)):
                        continue
                    key = (d, action)
                    expected[False][key] = expected[False].get(key, 0)+1
                    if all(strategy[j] in game.best_responses(other) for j, other in enumerate(defenses)):
                        expected[True][key] = expected[True].get(key, 0)+1
            result = game.equilibria(defenses)
            for credible, name in ((False, "nash"), (True, "subgame_perfect")):
                actual = {(row["d"], row["action"]): row["strategy_count"] for row in result[name]}
                self.assertEqual(actual, expected[credible], (game, name))
                for row in result[name]:
                    for j, other in enumerate(defenses):
                        self.assertLessEqual(game.payoff(other, row["witness"][j])[0], row["human"])
            self.assertTrue(result["subgame_perfect"])

    def test_stackelberg_ties_are_not_silently_favorable(self):
        game = Oversight(v=4, a=1, b=1, p=0, c=2)
        result = game.equilibria()
        self.assertEqual(result["stackelberg_favorable"][0]["d"], F(1, 2))
        self.assertEqual(result["stackelberg_unfavorable"][0]["d"], F(3, 5))
        sp = {(r["d"], r["action"]) for r in result["subgame_perfect"]}
        self.assertEqual(sp, {(F(1, 2), "cooperate"), (F(3, 5), "cooperate")})
        self.assertTrue(sp <= {(r["d"], r["action"]) for r in result["nash"]})

    def test_all_indifferent_profiles_are_preserved(self):
        game = Oversight(v=0, r=0, a=0, p=0, b=0, w=0, h=0, c=0)
        result = game.equilibria()
        self.assertEqual(sum(x["strategy_count"] for x in result["nash"]), 11*2**11)
        self.assertEqual(result["nash"], result["subgame_perfect"])
        self.assertEqual(len(result["stackelberg_unfavorable"]), 22)

    def test_baselines_and_regret(self):
        game = Oversight(v=4, a=1, b=1, p=0)
        for baseline, action in (("always_cooperate", "cooperate"), ("always_attack", "attack")):
            rows = game.simulate(DEFENSES, baseline)
            self.assertEqual({row["action"] for row in rows}, {action})
            self.assertTrue(any(row["ai_regret"] > 0 for row in rows))
        for tie_action in ACTIONS:
            rows = game.simulate(DEFENSES, "payoff_maximizer", tie_action)
            self.assertEqual(rows[5]["action"], tie_action)
            self.assertTrue(all(row["ai_regret"] == 0 for row in rows))
        self.assertEqual(game.simulate([0], "always_attack")[0]["remaining_harm"], 6)

    def test_reject_invalid_inputs(self):
        with self.assertRaises(ValueError):
            Oversight(a=-1)
        for d in (-1, 2):
            with self.assertRaises(ValueError):
                Oversight().payoff(d, "cooperate")
        for defenses in ([], [0, 0], [2]):
            with self.assertRaises(ValueError):
                Oversight().equilibria(defenses)
        with self.assertRaises(ValueError):
            Oversight().simulate([F(1, 3)], "payoff_maximizer")
        with self.assertRaises(ValueError):
            Oversight().simulate([0], "random")
        with self.assertRaises(ValueError):
            Oversight().simulate([0], "payoff_maximizer", "random")
