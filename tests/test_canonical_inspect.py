import unittest

from canonical_games_inspect import build_canonical_game_samples, parse_game_action


class CanonicalGamesInspectTests(unittest.TestCase):
    def test_dataset_covers_games_mechanisms_roles_and_opponent_actions(self) -> None:
        dataset = build_canonical_game_samples()
        self.assertEqual(len(dataset), 32)
        families = {sample.metadata["family"] for sample in dataset}
        players = {sample.metadata["player"] for sample in dataset}
        regimes = {sample.metadata["strategic_regime"] for sample in dataset}
        self.assertEqual(families, {"prisoners_dilemma", "chicken"})
        self.assertEqual(players, {"row", "column"})
        self.assertIn("boundary", regimes)
        for sample in dataset:
            self.assertEqual(len(sample.metadata["payoff_matrix"]), 4)
            self.assertIn("action_utilities", sample.metadata)
            self.assertIn("intervention_policy", sample.metadata)
            self.assertTrue(sample.target)

    def test_parser_uses_final_standalone_action(self) -> None:
        actions = ("DEESCALATE", "ESCALATE")
        self.assertEqual(parse_game_action("ESCALATE", actions), "ESCALATE")
        self.assertEqual(
            parse_game_action("ESCALATE has upside, but the best response is DEESCALATE", actions),
            "DEESCALATE",
        )
        self.assertEqual(parse_game_action("I refuse", actions), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
