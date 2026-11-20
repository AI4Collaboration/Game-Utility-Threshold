"""Prepare, collect, resume and export budgeted native Inspect game studies.

Preparation never calls a model. Live preparation reads public endpoint prices.
Run the same command again to resume; attempted trials are never resent.
See docs/inspect-studies.md for configuration and the recovery procedure.
"""
import argparse
import json
from pathlib import Path

from gut import inspect_study as study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('directory', type=Path)
    prepare.add_argument('--studies', nargs='+', choices=study.STUDIES, required=True)
    prepare.add_argument('--repetitions', type=int, required=True)
    prepare.add_argument('--budget-usd', required=True)
    prepare.add_argument('--mode', choices=('synthetic', 'openrouter'), default='synthetic')
    prepare.add_argument('--models', type=Path, help='JSON list of public id/provider pairs; no API keys.')
    prepare.add_argument('--seed', type=int, default=2026)
    prepare.add_argument('--max-tokens', type=int, default=512)
    prepare.add_argument('--temperature', type=float, default=.7)
    run = commands.add_parser('run')
    run.add_argument('directory', type=Path)
    run.add_argument('--stage', choices=('pilot', 'main'), required=True)
    run.add_argument('--max-trials', type=int, required=True)
    run.add_argument('--live', action='store_true')
    status = commands.add_parser('status')
    status.add_argument('directory', type=Path)
    review = commands.add_parser('review')
    review.add_argument('directory', type=Path)
    review.add_argument('--job', required=True)
    review.add_argument('--note', required=True)
    export = commands.add_parser('export')
    export.add_argument('directory', type=Path)
    export.add_argument('destination', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        models = study.read_json(args.models) if args.models else None
        plan = study.prepare(args.directory, args.studies, repetitions=args.repetitions,
                             budget_usd=args.budget_usd, models=models, mode=args.mode,
                             seed=args.seed, max_tokens=args.max_tokens, temperature=args.temperature)
        result = {'plan_sha256': plan['sha256'], 'planned_trials': len(plan['jobs']),
                  'maximum_role_calls': sum(len(j['roles']) for j in plan['jobs']),
                  'mode': plan['mode'], 'budget_usd': plan['budget_usd'], 'design': plan['design']}
    elif args.command == 'run':
        result = study.run(args.directory, stage=args.stage, max_trials=args.max_trials, live=args.live,
                           on_progress=lambda row: print(json.dumps(row), flush=True))
    elif args.command == 'review':
        result = study.review(args.directory, args.job, args.note)
    elif args.command == 'export':
        result = study.export(args.directory, args.destination)
    else:
        result = study.status(args.directory)
    print(json.dumps(result, indent=2))
    if args.command == 'run' and result['stop'] in ('review_required', 'pilot_failed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
