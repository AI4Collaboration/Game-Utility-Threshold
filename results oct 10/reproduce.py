"""Rebuild all analysis and publication figures from archived data, with no API calls."""
from pathlib import Path
import argparse
import gzip
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'reproduced')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if out==ROOT/'data': raise SystemExit('Choose an output directory different from the source data directory.')
    existing=out/'ledger.json'
    if existing.exists() and existing.read_bytes()!=(ROOT/'data/ledger.json').read_bytes():
        raise SystemExit('Output has a different budget ledger; choose an unused output directory.')
    for source in (ROOT/'data').iterdir():
        if source.name.endswith('.gz'):
            (out/source.stem).write_bytes(gzip.decompress(source.read_bytes()))
        else:
            shutil.copy2(source,out/source.name)
    pd_command=['scripts/render_pd_regime_composition.py']
    refinement=ROOT/'data_pd_refinement'
    if refinement.exists():
        refined_out=out/'pd-refinement';refined_out.mkdir(exist_ok=True)
        for source in refinement.iterdir():
            if source.name.endswith('.gz'):
                (refined_out/source.stem).write_bytes(gzip.decompress(source.read_bytes()))
            else:shutil.copy2(source,refined_out/source.name)
        subprocess.run([sys.executable,'run_phase_space.py','summarize','--output',str(refined_out)],cwd=ROOT,check=True)
        pd_command+=['--refinement-summary',str(refined_out/'summary.json')]
    commands=[['run_phase_space.py','summarize'],['scripts/render_phase_space.py'],
              ['scripts/compare_phase_space_theory.py'],
              ['scripts/render_threshold_displacement.py','--analysis',str(out)],
              pd_command,
              ['scripts/report_phase_space.py']]
    for cmd in commands:
        destination=out/'pd-composition' if cmd[0]=='scripts/render_pd_regime_composition.py' else out
        subprocess.run([sys.executable,*cmd,'--output',str(destination)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/render_lesswrong_figures.py','--analysis',str(out),
                    '--output',str(out/'post-figures')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/report_threshold_table.py',
                    '--output',str(out/'threshold-table')],cwd=ROOT,check=True)
    print(f'Offline reproduction complete: {out / "post-figures/index.html"}')

if __name__=='__main__': main()
