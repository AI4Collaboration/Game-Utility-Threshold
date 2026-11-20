from fractions import Fraction as F
from itertools import product
from random import Random
import unittest

from gut.canonical import EXAMPLES
from gut.incomplete.games import GAMES, INFORMATION, TYPES, encode, get_game
from gut.incomplete.solver import solve, is_equilibrium


def contains(component, x, ys, priors):
    a, b = component['row_c']
    if not (a < x < b if component['row_open_ends'] else a <= x <= b):
        return False
    if any(not a <= y <= b for y, (a, b) in zip(ys, component['column_c'])):
        return False
    q = sum(p*y for p, y in zip(priors, ys))
    return component['mean_column_c'][0] <= q <= component['mean_column_c'][1]


class IncompleteGameTests(unittest.TestCase):
    def test_separate_ids_and_fixed_intervention(self):
        before = repr(EXAMPLES)
        self.assertFalse(set(GAMES) & set(EXAMPLES))
        for game in GAMES.values():
            for kind in TYPES:
                for role in ('row', 'column'):
                    base, treated = game.table(role, kind), game.table(role, kind, '3/7')
                    self.assertEqual(base[0], treated[0])
                    self.assertEqual(tuple(v-F(3, 7) for v in base[1]), treated[1])
        self.assertEqual(repr(EXAMPLES), before)
        with self.assertRaises(ValueError):
            get_game('pd')

    def test_starting_game_families_and_mean_match_base(self):
        for game, key in zip(GAMES.values(), ('pd', 'stag_hunt')):
            for table in (game.row, *game.columns):
                r, s, t, p = (*table[0], *table[1])
                self.assertTrue(t > r > p > s if key == 'pd' else r > t > p > s)
            mean = tuple(tuple(sum(game.priors[k]*game.columns[k][i][j] for k in (0, 1))
                               for j in (0, 1)) for i in (0, 1))
            self.assertEqual(mean, game.row)
            self.assertEqual(game.row, tuple(tuple(cell[0] for cell in row) for row in EXAMPLES[key].baseline))

    def test_hidden_views_and_matched_revealed_payoffs(self):
        for game in GAMES.values():
            self.assertEqual(game.view('row', 'hidden', 'low', '.6'), game.view('row', 'hidden', 'high', '.6'))
            for kind in TYPES:
                for role in ('row', 'column'):
                    revealed = game.view(role, 'revealed', kind, '.6')
                    hidden = game.view(role, 'hidden', kind, '.6')
                    self.assertEqual(revealed['own_payoffs'], hidden['own_payoffs'])
                    self.assertEqual(revealed['possible_other_payoffs'], hidden['possible_other_payoffs'])
                    self.assertEqual('actual_column_profile' in hidden, role == 'column')
            self.assertEqual(game.equilibria('.3', 'hidden', 'low'), game.equilibria('.3', 'hidden', 'high'))

    def test_thresholds_and_ties_are_not_forced_choices(self):
        pd = get_game('private_pd_v1')
        self.assertEqual(pd.thresholds('row', 'low')['c_strict_above'], 1)
        self.assertEqual(pd.thresholds('column', 'low')['c_strict_above'], F(3, 4))
        self.assertEqual(pd.thresholds('column', 'high')['c_strict_above'], F(5, 4))
        self.assertTrue(pd.score_choice('row', 'low', '11/10', 'D')['strict_dominance_violation'])
        self.assertFalse(pd.score_choice('row', 'low', 1, 'D')['strict_dominance_violation'])
        self.assertFalse(pd.score_choice('row', 'low', '3/4', 'C')['strict_dominance_violation'])
        self.assertFalse(pd.score_choice('row', 'low', '3/4', 'D')['strict_dominance_violation'])

    def test_all_frozen_witnesses_satisfy_bayesian_best_responses(self):
        for game in GAMES.values():
            for z, info, kind in product(game.costs, INFORMATION, TYPES):
                eq = game.equilibria(z, info, kind)
                for component in eq['components']:
                    w = component['witness']
                    self.assertTrue(is_equilibrium(game.gaps('row', kind, z),
                        [game.gaps('column', t, z) for t in eq['types']], eq['priors'],
                        w['row_c'], w['column_c']))

    def test_stag_hunt_retains_continuum_and_both_pure_equilibria(self):
        game = get_game('private_stag_hunt_v1')
        components = game.equilibria(0, 'hidden', 'low')['components']
        self.assertTrue(any(c['row_c'] == (F(1, 3), F(3, 5)) and c['row_open_ends'] for c in components))
        self.assertTrue(any(contains(c, F(0), (F(0), F(0)), game.priors) for c in components))
        self.assertTrue(any(contains(c, F(1), (F(1), F(1)), game.priors) for c in components))

    def test_equilibrium_set_matches_direct_conditions_on_grid(self):
        rng = Random(87)
        grid = tuple(F(i, 4) for i in range(5))
        for _ in range(35):
            row = tuple(F(rng.randint(-2, 2)) for _ in range(2))
            columns = tuple(tuple(F(rng.randint(-2, 2)) for _ in range(2)) for _ in range(2))
            priors = (F(1, 3), F(2, 3))
            components = solve(row, columns, priors)
            for x, y0, y1 in product(grid, repeat=3):
                expected = is_equilibrium(row, columns, priors, x, (y0, y1))
                actual = any(contains(c, x, (y0, y1), priors) for c in components)
                self.assertEqual(actual, expected, (row, columns, x, y0, y1))

    def test_reject_invalid_inputs_and_score_orientation(self):
        game = get_game('private_pd_v1')
        for value in (True, 'nan', '-1', '21'):
            with self.assertRaises(ValueError):
                game.cost(value)
        self.assertEqual(game.outcome('high', '1/2', 'C', 'D'), {'row': F(-1, 2), 'column': F(7, 4)})
        with self.assertRaises(ValueError):
            game.outcome('high', 0, 'nonsense', 'D')
        with self.assertRaises(ValueError):
            solve((0, 0), [(0, 0), (0, 0)], (0, 1))


if __name__ == '__main__':
    unittest.main()
