from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

from gut.canonical import EXAMPLES, example
from gut.experiment import collect, load_run, make_plan, prompt, save_plan, summarize
from gut.game import Game
from gut.proofs import exact_table, export_proofs
from serve import canonical_state


class CanonicalTests(unittest.TestCase):
    def test_baselines_and_conditional_thresholds(self):
        expected = {
            "pd": ((1, Fraction(1, 2)), (1, Fraction(1, 2)), ((1, 1),)),
            "stag_hunt": ((Fraction(-1, 2), Fraction(1, 2)), (Fraction(-1, 2), Fraction(1, 2)), ((0, 0), (1, 1))),
            "chicken": ((Fraction(1, 2), Fraction(-1, 2)), (Fraction(1, 2), Fraction(-1, 2)), ((0, 1), (1, 0))),
            "battle_of_sexes": ((-2, 1), (-1, 2), ((0, 0), (1, 1))),
        }
        for key, (row, column, stable) in expected.items():
            game = example(key)
            self.assertEqual(game.thresholds("row"), row)
            self.assertEqual(game.thresholds("column"), column)
            self.assertEqual(game.stable_outcomes(), stable)
            with self.assertRaises(ValueError):
                game.matrix(-1)
            with self.assertRaises(ValueError):
                game.perspective("invalid")
        self.assertEqual(Game(t="0.5", s="-0.5").region(), "stag_hunt")
        self.assertEqual(Game(t="1.5", s="0.5").region(), "chicken")

    def test_payoffs_and_proofs_preserve_each_players_perspective(self):
        for key, game in EXAMPLES.items():
            for z in game.costs:
                table = game.matrix(z)
                for role, r in (("row", 0), ("column", 1)):
                    denominator, ints = exact_table(z, key, role)
                    own = game.perspective(role, z)
                    for i in range(2):
                        for j in range(2):
                            original = table[i][j] if r == 0 else table[j][i]
                            self.assertEqual(own[i][j], (original[r], original[1-r]))
                            self.assertEqual(Fraction(ints[2*i+j], denominator), original[r])
                            self.assertEqual(table[i][j][r], game.baseline[i][j][r] - (i if r == 0 else j)*Fraction(z))

    def test_battle_of_sexes_thresholds_are_distinct_and_ties_remain(self):
        game = example("battle_of_sexes")
        self.assertEqual(game.margins("row", 1), (3, 0))
        self.assertEqual(game.margins("column", 1), (2, -1))
        self.assertEqual(game.stable_outcomes(1), ((0, 0), (1, 1)))
        self.assertEqual(game.stable_outcomes("1.01"), ((0, 0),))
        self.assertEqual(game.margins("column", 2), (3, 0))

    def test_role_and_label_prompts(self):
        row = prompt(0, "row", 0, "battle_of_sexes")
        column = prompt(0, "column", 0, "battle_of_sexes")
        self.assertIn("Your action A, other action A: your points 2, other points 1", row)
        self.assertIn("Your action A, other action A: your points 1, other points 2", column)
        self.assertIn("Your action B, other action B: your points 2, other points 1", column)
        swapped = prompt(0, "column", 1, "battle_of_sexes")
        self.assertIn("Your action A, other action A: your points 2, other points 1", swapped)

    def test_pd_protocol_and_schedule_remain_unchanged(self):
        self.assertEqual(make_plan()["sha256"], "7b466c4718779df1c9733c4645732ee72b2b03125da9f4204697c6908b441475")

    def test_all_games_run_report_and_map_choices(self):
        with tempfile.TemporaryDirectory() as temp:
            for game in EXAMPLES:
                directory = Path(temp) / game
                save_plan(directory, game=game, repetitions=1)
                self.assertEqual(collect(directory), 40)
                load_run(directory)
                report = summarize(directory)
                self.assertEqual(report["game"], game)
                self.assertEqual(sum(c["valid_games"] for c in report["cells"]), 20)
                self.assertEqual(export_proofs(directory)["mapped_choices"], 40)
                if game == "battle_of_sexes":
                    self.assertTrue(all(c["cooperation_rate"] is None and "XX" in c and "CC" not in c for c in report["cells"]))
                mapping = json.loads((directory / "proofs/mapping.json").read_text())
                for record in mapping:
                    _, expected = exact_table(record["z"], game, record["role"])
                    self.assertEqual(record["payoff_integers"], expected)

    def test_known_bos_observations_do_not_pool_conflicting_preferences(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "bos"
            save_plan(directory, game="battle_of_sexes", repetitions=1)
            def choices(job, plan):
                # Both choose X in block 0; row X, column Y in block 1.
                action = "A" if job["block"] == 0 or job["role"] == "column" else "B"
                return 200, json.dumps({"model": "synthetic/demo", "choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({"final_action": action})}}]}), None
            collect(directory, transport=choices)
            baseline = summarize(directory)["cells"][0]
            self.assertEqual((baseline["XX"], baseline["XY"], baseline["YX"], baseline["YY"]), (1, 1, 0, 0))
            self.assertEqual((baseline["row_first_rate"], baseline["column_first_rate"], baseline["matching_rate"]), (1, 0.5, 0.5))
            self.assertEqual((baseline["row_mean_payoff"], baseline["column_mean_payoff"]), (1, 0.5))

    def test_canonical_api_separates_players_and_rejects_invalid_input(self):
        result = canonical_state({"game": ["battle_of_sexes"], "z": ["1"]})
        self.assertEqual(result["stable_outcomes"], ["XX", "YY"])
        self.assertEqual([c["best"] for c in result["comparisons"]], ["X", "tie", "X", "Y"])
        for query in ({"game": ["nope"], "z": ["0"]}, {"game": ["pd"], "z": ["NaN"]},
                      {"game": ["pd", "chicken"], "z": ["0"]}):
            with self.assertRaises(ValueError):
                canonical_state(query)


if __name__ == "__main__":
    unittest.main()
