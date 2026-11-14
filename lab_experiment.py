"""Prepare and run an OFFLINE notebook-audit pilot. Makes no model/API calls."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from gut import lab_experiment as study
from gut.study import _json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path,help='New output directory (never overwritten)')
    parser.add_argument('--scale',choices=('pilot','main'),default='pilot')
    parser.add_argument('--reviewer',choices=study.REVIEWERS,default='evidence')
    parser.add_argument('--scientist',choices=study.SCIENTISTS,default='maximizer')
    parser.add_argument('--seed',type=int,default=20261113)
    parser.add_argument('--figures',action='store_true')
    args=parser.parse_args()
    plan=study.make_plan(seed=args.seed,scale=args.scale,reviewer=args.reviewer,scientist=args.scientist)
    if args.figures:
        import matplotlib  # fail before creating any output if optional package missing
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    result=study.run(plan)
    (args.output/'records.json').write_text(json.dumps(result,indent=2)+'\n')
    # Re-read the saved files before analysis, not an unaudited in-memory score.
    summary=study.report(args.output,_json((args.output/'plan.json').read_text()),_json((args.output/'records.json').read_text()),figures=args.figures)
    root=Path(__file__).resolve().parent
    sources=['gut/lab_audit.py','gut/lab_experiment.py','gut/experiment.py','gut/study.py','lab_experiment.py']
    provenance={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
      'working_tree_dirty':bool(subprocess.check_output(['git','-c','core.fsmonitor=false','status','--porcelain'],cwd=root,text=True).strip()),
      'source_sha256':{name:sha256((root/name).read_bytes()).hexdigest() for name in sources},
      'output_sha256':{p.name:sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file()}}
    (args.output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(f"Saved {summary['recorded_requests']} synthetic requests to {args.output}. Live model calls: 0.")


if __name__=='__main__':
    main()
