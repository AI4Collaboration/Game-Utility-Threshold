from collections import Counter
from fractions import Fraction as F
import importlib.util
import unittest

from gut.presentation import blocks, presentation
from gut.audit_game import ACTIONS, demo_game, information_benchmark
from gut.incomplete.games import GAMES


class PresentationTests(unittest.TestCase):
    def test_label_and_position_are_independently_balanced(self):
        for actions in (('C', 'D'), ACTIONS):
            observed = {a: Counter() for a in actions}
            for block in blocks(actions):
                p = presentation(actions, block)
                for action in actions:
                    label = p['labels'][action]
                    observed[action][label, p['action_order'].index(label)] += 1
            for counts in observed.values():
                self.assertEqual(len(counts), len(actions)**2)
                self.assertEqual(set(counts.values()), {1})

    def test_all_private_payoff_tables_roundtrip_under_every_presentation(self):
        for game in GAMES.values():
            for role in ('row', 'column'):
                for kind in ('low', 'high'):
                    for block in range(4):
                        p = presentation(('C', 'D'), block)
                        view = game.view(role, 'hidden', kind, F(3, 7), bool(block//2), bool(block%2))
                        table = game.table(role, kind, F(3, 7))
                        for i, action in enumerate(('C', 'D')):
                            for j, other in enumerate(('C', 'D')):
                                displayed_i = view['action_order'].index(p['labels'][action])
                                displayed_j = view['action_order'].index(p['labels'][other])
                                self.assertEqual(view['own_payoffs'][displayed_i][displayed_j], table[i][j])
                        self.assertEqual(view['costed_action'], p['labels']['D'])

    def test_audit_revelation_keeps_realized_rewards_and_coverage(self):
        game = demo_game()
        for kind in game.types:
            revealed = game.information_game('revealed', kind.name)
            self.assertEqual(revealed.types[0].unchecked, kind.unchecked)
            self.assertEqual(revealed.types[0].checked, kind.checked)
            for q in game.coverage_grid():
                actual = next(t for t in game.evaluate(q)['types'] if t['name'] == kind.name)
                for key in ('follower', 'leader', 'best_responses'):
                    self.assertEqual(revealed.evaluate(q)['types'][0][key], actual[key])
        self.assertNotEqual(demo_game('known').types[0].unchecked, game.mean_game().types[0].unchecked)

    def test_audit_grid_surrounds_exact_action_thresholds(self):
        game = demo_game()
        grid = game.coverage_grid()
        for row in game.thresholds():
            q = row['checking_probability']
            if row['target'] == 'target_b':
                q = 1-q
            self.assertIn(q, grid)
            self.assertIn(q-F(1, 50), grid)
            self.assertIn(q+F(1, 50), grid)

    def test_information_benchmark_has_real_decision_value_and_matched_rewards(self):
        game = information_benchmark()
        self.assertFalse(game.safe_region()['feasible'])
        for kind in game.types:
            revealed = game.information_game('revealed', kind.name)
            self.assertEqual(revealed.types[0].unchecked, kind.unchecked)
            self.assertTrue(revealed.safe_region()['feasible'])
            self.assertEqual(revealed.commitment().solve()['favorable']['value'], 0)
        # Independent hand calculation: q=6/13 deters type B at a tie.
        # Type A violates A and gives defender -1 + .9*(6/13) = -38/65.
        # Equal prior: -19/65. Favorable tie is explicit, not a safety guarantee.
        self.assertEqual(game.commitment().solve()['favorable']['value'], F(-19,65))
        self.assertEqual(game.commitment().solve()['favorable']['witnesses'], [F(6,13)])

    @unittest.skipUnless(importlib.util.find_spec('inspect_ai'), 'Install inspect extra')
    def test_audit_matched_schedule_and_no_hidden_profile_leak(self):
        from gut.audit_inspect import audit_samples, player_view, parse_choice
        game = demo_game()
        samples = audit_samples(game, defender_mode='model')
        self.assertEqual(len(samples), 36)
        pairs = {}
        for sample in samples:
            pairs.setdefault(sample.metadata['pair_id'], []).append(sample.metadata)
        for pair in pairs.values():
            a, b = pair
            self.assertEqual(a['private_type'], b['private_type'])
            self.assertEqual(a['seed'], b['seed'])
            self.assertEqual({a['information'], b['information']}, {'revealed', 'hidden'})
        for block in range(9):
            hidden = player_view(game, 'hidden', 'low', block, 'defender')
            self.assertEqual(hidden, player_view(game, 'hidden', 'high', block, 'defender'))
            revealed = player_view(game, 'revealed', 'low', block, 'defender')
            self.assertEqual(revealed.pop('actual_type'), 'low')
            revealed['information'] = 'hidden'
            self.assertEqual(revealed, hidden)
            for action, label in presentation(ACTIONS, block)['labels'].items():
                self.assertEqual(parse_choice('{"action":"'+label+'"}', 'action', block), action)
        with self.assertRaises(ValueError):
            audit_samples(game, defender_mode='model', coverages=[F(1, 2)])
