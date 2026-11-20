"""One fixed study for an operator with an OpenRouter key; no model-selection flags."""
import argparse
from pathlib import Path
from gut import manager_study as manager
from gut import inspect_study as study
import json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('run','smoke','status','report'))
    args=parser.parse_args()
    directory=Path('runs/manager-study-smoke' if args.command=='smoke' else 'runs/manager-study-v1')
    if args.command in ('run','smoke'):
        return manager.execute(directory,smoke=args.command=='smoke')
    if args.command=='status':
        print(json.dumps(study.status(directory),indent=2))
    else:
        manager.collect_results(directory)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
