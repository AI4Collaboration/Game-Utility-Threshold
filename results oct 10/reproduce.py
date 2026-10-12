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
    args=p.parse_args();out=args.output.resolve()
    if out == ROOT or out == ROOT/'data' or ROOT/'data' in out.parents:
        raise SystemExit('Choose an output directory outside the source data and bundle root.')
    out.mkdir(parents=True,exist_ok=True)
    existing=out/'ledger.json'
    if existing.exists() and existing.read_bytes()!=(ROOT/'data/ledger.json').read_bytes():
        raise SystemExit('Output has a different budget ledger; choose an unused output directory.')
    raw = out/'attempts.jsonl'
    archived_raw = gzip.decompress((ROOT/'data/attempts.jsonl.gz').read_bytes())
    if raw.exists() and raw.read_bytes() != archived_raw:
        raise SystemExit('Output has different raw records; choose an unused output directory.')
    for source in (ROOT/'data').iterdir():
        if source.name.endswith('.gz'):
            (out/source.stem).write_bytes(gzip.decompress(source.read_bytes()))
        else:
            shutil.copy2(source,out/source.name)
    shutil.copy2(ROOT/'docs/phase-space-experiment.md', out/'METHODS.md')
    commands=[['run_phase_space.py','summarize'],['scripts/render_phase_space.py'],
              ['scripts/compare_phase_space_theory.py'],['scripts/report_phase_space.py']]
    for cmd in commands:
        subprocess.run([sys.executable,*cmd,'--output',str(out)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/render_lesswrong_figures.py','--analysis',str(out),
                    '--output',str(out/'post-figures')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/audit_experiment.py','--data',str(out),
                    '--output',str(out/'independent_audit.json')],cwd=ROOT,check=True)
    print(f'Offline reproduction complete: {out / "post-figures/index.html"}')

if __name__=='__main__': main()
