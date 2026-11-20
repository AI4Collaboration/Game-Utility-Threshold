"""Separate Design 1 runner. No paid calls; commands use native Inspect mocks.

python private_games.py run runs/private-check --game all --figures
python private_games.py export web/private-games.json
inspect view --log-dir runs/private-check/logs
"""

import argparse
from fractions import Fraction as F
import json
from pathlib import Path
from random import Random

from gut.incomplete.games import GAMES, INFORMATION, SCHEMA, TYPES, encode, get_game


def catalogue():
    return {'schema': SCHEMA, 'evidence': 'exact theory only; no live LLM results',
            'games': {key: {'config': game.config(), 'config_hash': game.fingerprint(),
                'conditions': [game.state(z, info, kind) for z in game.costs for info in INFORMATION for kind in TYPES]}
                for key, game in GAMES.items()}}


def mock_models(game, baseline='equilibrium', seed=2026):
    from inspect_ai.model import ModelOutput, get_model
    if baseline not in ('equilibrium', 'always_c', 'always_d', 'uniform'):
        raise ValueError('Unknown scripted baseline.')
    models = {}
    for index, role in enumerate(('row', 'column')):
        def callback(role=role, rng=Random(seed+index)):
            def respond(messages, *args):
                view = json.loads(messages[-1].text.split('\n')[-1])
                kind = view.get('actual_column_profile', 'low')
                if baseline == 'equilibrium':
                    eq = game.equilibria(view['cost'], view['information'], kind)
                    witness = eq['components'][0]['witness']
                    p = witness['row_c'] if role == 'row' else witness['column_c'][eq['types'].index(kind)]
                else:
                    p = F({'always_c': 1, 'always_d': 0, 'uniform': '1/2'}[baseline])
                action = 0 if rng.randrange(p.denominator) < p.numerator else 1
                labels = [a for a in ('A', 'B') if a != view['costed_action']] + [view['costed_action']]
                return ModelOutput.from_content(f'mockllm/{role}', json.dumps({'action': labels[action]}))
            return respond
        models[role] = get_model(f'mockllm/{role}', custom_outputs=callback())
    return models


def export_logs(logs, destination):
    from inspect_ai.log import read_eval_log
    records = []
    for path in logs:
        log = read_eval_log(path)
        for sample in log.samples or []:
            record = sample.metadata.get('record')
            records.append({'sample_id': sample.id, 'epoch': sample.epoch,
                            'status': 'error' if sample.error else (record or {}).get('status', 'incomplete'),
                            'record': record, 'error': sample.error.model_dump(mode='json') if sample.error else None,
                            'native_log': str(path)})
    with Path(destination).open('x') as stream:
        for row in records:
            stream.write(json.dumps(row)+'\n')
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('export', help='Regenerate exact UI theory, without Inspect or model calls.')
    export.add_argument('output', type=Path)
    run = commands.add_parser('run', help='Run paired synthetic games through native Inspect.')
    run.add_argument('output', type=Path)
    run.add_argument('--game', choices=['all', *GAMES], default='all')
    run.add_argument('--cost', nargs='+', help='Optional separate pilot subset; frozen game cost grid is the default.')
    run.add_argument('--baseline', choices=('equilibrium','always_c','always_d','uniform'), default='equilibrium')
    run.add_argument('--repetitions', type=int, default=1)
    run.add_argument('--seed', type=int, default=2026)
    run.add_argument('--figures', action='store_true')
    args = parser.parse_args()
    if args.command == 'export':
        args.output.write_text(encode(catalogue())+'\n')
        print(f'Exported exact theory: {args.output}')
        return
    from inspect_ai import eval as inspect_eval
    from gut.incomplete.inspect_task import private_task
    from gut.incomplete.report import report
    tasks = []
    for game in (GAMES.values() if args.game == 'all' else [get_game(args.game)]):
        task = private_task(game, mock_models(game, args.baseline, args.seed), args.cost, args.repetitions, args.seed)
        task.metadata.update(baseline=args.baseline,
                             equilibrium_selection='First exact component witness; arbitrary scripted convention, not an LLM prediction.')
        tasks.append(task)
    args.output.mkdir(parents=True, exist_ok=False)
    logs = inspect_eval(tasks, model=None, log_dir=str(args.output/'logs'), display='none',
                        max_retries=0, max_tokens=500, max_samples=1, max_tasks=1, log_model_api=True)
    records = export_logs([log.location for log in logs], args.output/'observations.jsonl')
    summary = report(records, args.output, args.figures)
    print(json.dumps(summary, indent=2))
    expected = sum(len(task.dataset) for task in tasks)
    if len(records) != expected or summary['valid_pairs'] != expected or any(log.status != 'success' for log in logs):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
