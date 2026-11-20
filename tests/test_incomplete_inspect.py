import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

if importlib.util.find_spec('inspect_ai'):
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log
    from inspect_ai.model import ContentReasoning, ContentText, ModelOutput, get_model
    from gut.incomplete.games import get_game
    from gut.incomplete.inspect_task import paired_samples, parse_action, private_task
    from gut.incomplete.report import report
    from private_games import export_logs, mock_models


@unittest.skipUnless(importlib.util.find_spec('inspect_ai'), 'Install the inspect extra')
class PrivateInspectTests(unittest.TestCase):
    def run_task(self, task, folder):
        logs = inspect_eval(task, model=None, log_dir=folder, display='none', max_retries=0, max_samples=1, max_tokens=400)
        return read_eval_log(logs[0].location), logs[0].location

    def test_pairs_and_information_boundaries_in_native_logs(self):
        game, prompts = get_game('private_pd_v1'), {'row': [], 'column': []}
        def callback(role):
            def respond(messages, *args):
                prompts[role].append(messages[-1].text)
                return ModelOutput.from_content(f'mockllm/{role}', [ContentReasoning(reasoning='PRIVATE_'+role),
                                                ContentText(text='{"action":"A"}')])
            return respond
        models = {r: get_model('mockllm/'+r, custom_outputs=callback(r)) for r in prompts}
        task = private_task(game, models, costs=['1/2'])
        with tempfile.TemporaryDirectory() as folder:
            log, path = self.run_task(task, folder)
            self.assertEqual(log.status, 'success')
            self.assertEqual(len(log.samples), 8)
            pairs = {}
            for sample in log.samples:
                record = sample.metadata['record']
                pairs.setdefault(record['pair_id'], []).append(record)
                events = [e for e in sample.events if e.event == 'model']
                self.assertEqual([e.role for e in events], ['row', 'column'])
                for event in events:
                    self.assertEqual(event.output.message.content[0].type, 'reasoning')
                self.assertNotIn('PRIVATE_row', events[1].input[0].text)
            for pair in pairs.values():
                self.assertEqual(len(pair), 2)
                self.assertEqual(pair[0]['seed'], pair[1]['seed'])
                self.assertEqual(pair[0]['theory']['tables'], pair[1]['theory']['tables'])
            hidden = [json.loads(p.split('\n')[-1]) for p in prompts['row'] if '"information": "hidden"' in p]
            self.assertTrue(all('actual_column_profile' not in v for v in hidden))
            for label in ('A','B'):
                same = [v for v in hidden if v['costed_action']==label]
                self.assertEqual(same[0], same[1])
            records = export_logs([path], Path(folder)/'observations.jsonl')
            summary = report(records, folder)
            self.assertEqual(summary['both_conditions_valid'], 4)

    def test_invalid_and_provider_failures_are_retained(self):
        game = get_game('private_stag_hunt_v1')
        for failure in ('invalid','error'):
            def respond(*args):
                if failure == 'error':
                    raise RuntimeError('synthetic provider failure')
                return ModelOutput.from_content('mockllm/row', '{"action":"invalid"}')
            models = mock_models(game)
            models['row'] = get_model('mockllm/row', custom_outputs=respond)
            task = private_task(game, models, costs=[0])
            with tempfile.TemporaryDirectory() as folder:
                log, path = self.run_task(task, folder)
                rows = export_logs([path], Path(folder)/'observations.jsonl')
                self.assertTrue(all(r['status']==failure for r in rows))
                self.assertTrue(all('outcome' not in r['record'] for r in rows))
                summary = report(rows, folder)
                self.assertEqual(summary['both_conditions_valid'], 0)
                self.assertEqual(summary['errors' if failure=='error' else 'invalid_pairs'], 8)

    def test_baselines_respect_labels_and_strict_bounds(self):
        game = get_game('private_pd_v1')
        for baseline in ('always_c','always_d','equilibrium','uniform'):
            with tempfile.TemporaryDirectory() as folder:
                log, _ = self.run_task(private_task(game, mock_models(game, baseline), costs=['3/2']), folder)
                for sample in log.samples:
                    row = sample.metadata['record']
                    self.assertEqual(row['status'], 'valid')
                    if baseline != 'uniform':
                        for choice in row['choices'].values():
                            self.assertEqual(choice['action'], 'D' if baseline=='always_d' else 'C')
                            self.assertEqual(choice['strict_dominance_violation'], baseline=='always_d')

    def test_validation_and_deterministic_pairing(self):
        game = get_game('private_pd_v1')
        self.assertEqual([s.id for s in paired_samples(game)], [s.id for s in paired_samples(game)])
        with self.assertRaises(ValueError):
            private_task(game, {})
        for text in ('{"action":"C"}', '{"action":"A","action":"B"}', '{"action":true}', 'A'):
            with self.assertRaises(ValueError):
                parse_action(text, False)
        self.assertEqual(parse_action('{"action":"B"}', True), 'C')


if __name__ == '__main__':
    unittest.main()
