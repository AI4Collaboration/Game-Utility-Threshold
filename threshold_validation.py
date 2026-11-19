"""Prepare or resume the Months 1–3 live suite with one shared dollar cap."""
import argparse
from collections import Counter
import json
from pathlib import Path

from gut import threshold_validation as study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('directory', type=Path)
    plan.add_argument('--models', required=True, type=Path)
    plan.add_argument('--budget-usd', default='45')
    run = commands.add_parser('run')
    run.add_argument('directory', type=Path)
    run.add_argument('--stage', choices=('pilot', 'main'), required=True)
    run.add_argument('--live', action='store_true')
    run.add_argument('--max-calls', type=int, required=True)
    run.add_argument('--workers', type=int, default=8)
    for command in ('status', 'materialize'):
        commands.add_parser(command).add_argument('directory', type=Path)
    audit = commands.add_parser('audit')
    audit.add_argument('directory', type=Path)
    audit.add_argument('--job-id', required=True)
    audit.add_argument('--note', required=True)
    args = vars(parser.parse_args())
    command, directory = args.pop('command'), args.pop('directory')
    if command == 'plan':
        args['models'] = json.loads(args['models'].read_text())
        plan = study.prepare(directory, **args)
        result = {'sha256': plan['sha256'], 'counts': dict(Counter(j['stage'] for j in plan['jobs']))}
    elif command == 'run':
        result = study.collect(directory, **args)
    elif command == 'audit':
        study.audit(directory, **args)
        result = {'audit_recorded': True}
    elif command == 'materialize':
        result = {'studies': len(study.materialize(directory)['studies'])}
    else:
        plan, contexts, starts, finishes, cost = study.read_ledger(directory)
        result = {'planned': dict(Counter(j['stage'] for j in plan['jobs'])), 'started': len(starts),
                  'finished': len(finishes), 'cost_plus_reservations_usd': str(cost),
                  'budget_usd': plan['budget_usd'], 'statuses': dict(Counter(
                      study.parse(contexts, j, finishes.get(j['id']))[1] for j in plan['jobs'] if j['id'] in starts))}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
