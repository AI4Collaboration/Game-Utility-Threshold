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
    commands=[['run_phase_space.py','summarize'],['scripts/render_phase_space.py'],
              ['scripts/compare_phase_space_theory.py'],
              ['scripts/render_threshold_displacement.py','--analysis',str(out)],
              ['scripts/report_phase_space.py']]
    for cmd in commands:
        subprocess.run([sys.executable,*cmd,'--output',str(out)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/render_lesswrong_figures.py','--analysis',str(out),
                    '--output',str(out/'post-figures')],cwd=ROOT,check=True)
    print(f'Offline reproduction complete: {out / "post-figures/index.html"}')

if __name__=='__main__': main()
