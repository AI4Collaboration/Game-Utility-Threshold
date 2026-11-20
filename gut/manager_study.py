"""Fixed operator workflow: prepare -> pilot -> main -> report -> handoff ZIP."""
from collections import Counter
from datetime import datetime, timezone
import getpass
from hashlib import sha256
from importlib.metadata import distributions
import json
import os
from pathlib import Path
import re
import signal
import sys
import zipfile

from . import inspect_study as S
from .experiment import digest
from .manager_report import report

CONFIG = S.ROOT/'configs/manager-study-v1.json'
SECRET = re.compile(rb'sk-or-v1-[A-Za-z0-9_-]{16,}')


class GracefulStop(Exception):
    pass


def environment():
    return {'python':sys.version.split()[0], 'packages':dict(sorted(
        (d.metadata['Name'].lower(),d.version) for d in distributions() if d.metadata['Name']))}


def configuration():
    return S.read_json(CONFIG)


def prepare(directory, smoke=False):
    directory=Path(directory)
    config=configuration()
    mode='synthetic' if smoke else 'openrouter'
    if (directory/'plan.json').exists():
        plan=S.load_plan(directory)
        if plan['mode']!=mode:
            raise ValueError('Use separate live and smoke directories.')
        operator=S.read_json(directory/'operator.json')
        if (operator['config_sha256']!=digest(config) or operator['plan_sha256']!=plan['sha256']
                or operator['environment']!=environment()):
            raise ValueError('Frozen configuration or environment changed. Send the existing results; do not start over.')
        return plan
    settings={k:config[k] for k in ('budget_usd','seed','max_tokens','temperature','repetitions','control_repetitions')}
    settings.update(repetitions_by_study=config['repetitions_by_study'], mode=mode,
                    models=None if smoke else config['models'], model_settings=None if smoke else config['model_settings'])
    if smoke:
        settings.update(repetitions=1, control_repetitions=1,
                        repetitions_by_study={s:1 for s in config['repetitions_by_study']})
    plan=S.prepare(directory,list(config['repetitions_by_study']),**settings)
    if smoke:
        # Exercise every planned pilot plus one main trial per game. Never relabel as live evidence.
        chosen={}
        for job in plan['jobs']:
            if job['stage']=='main': chosen.setdefault(job['study'],job['id'])
        plan['jobs']=[j for j in plan['jobs'] if j['stage']=='pilot' or chosen[j['study']]==j['id']]
        plan['design']['smoke']='All compatibility blocks + one main trial per study; software check only.'
        plan['sha256']=digest({k:v for k,v in plan.items() if k!='sha256'})
        # No attempts exist; replace the unpublished preparation manifest atomically.
        temporary=directory/'smoke-plan.json'
        S.atomic_json(temporary,plan); os.replace(temporary,directory/'plan.json')
    S.atomic_json(directory/'operator.json',{'config_sha256':digest(config),'plan_sha256':plan['sha256'],
                                           'environment':environment(),'mode':mode})
    source=directory/'frozen-source'
    for name, expected in plan['provenance']['files'].items():
        data=(S.ROOT/name).read_bytes()
        if sha256(data).hexdigest()!=expected:
            raise ValueError('Source changed during preparation.')
        target=source/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    # Include the bootstrap and operating guide alongside the exact source.
    for name in ('scripts/run_manager_study.sh','docs/manager-handoff.md'):
        target=source/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes((S.ROOT/name).read_bytes())
    S.atomic_json(directory/'frozen-source'/'environment.json', environment())
    counts=Counter(j['stage'] for j in plan['jobs'])
    print(json.dumps({'mode':mode,'trials':counts,'maximum_model_calls':sum(len(j['roles']) for j in plan['jobs']),
                      'budget_usd':plan['budget_usd'],'plan_sha256':plan['sha256']},indent=2),flush=True)
    return plan


def bundle(directory, output, destination):
    """Allowlist study artifacts only; never archive a checkout, .env or credentials."""
    directory, output, destination=map(Path,(directory,output,destination))
    files={}
    for name in ('plan.json','operator.json'):
        if (directory/name).exists(): files['study/'+name]=directory/name
    for prefix in ('attempts','logs','frozen-source'):
        for path in sorted((directory/prefix).rglob('*')):
            if path.is_file() and not path.is_symlink() and not path.name.startswith('.'):
                files['study/'+str(path.relative_to(directory))]=path
    for path in sorted(output.rglob('*')):
        if path.is_file(): files['results/'+str(path.relative_to(output))]=path
    temporary=destination.with_suffix('.tmp.zip')
    checksums={}
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,path in files.items():
                data=path.read_bytes()
                if SECRET.search(data):
                    raise ValueError('Credential-shaped text detected; no shareable bundle created.')
                if path.suffix=='.eval':
                    with zipfile.ZipFile(path) as native:
                        if any(SECRET.search(native.read(member)) for member in native.namelist()):
                            raise ValueError('Credential-shaped text detected in a native log; bundle withheld.')
                checksums[name]=sha256(data).hexdigest()
                archive.writestr(name,data)
            archive.writestr('SHA256.json',json.dumps(checksums,indent=2)+'\n')
            archive.writestr('START-HERE.txt','Open results/report.html. Raw Inspect logs are under study/logs/.\n'
                              'The frozen configuration and source accompany the data. API keys are not included.\n'
                              'Incomplete runs remain incomplete; never merge pilots into main estimates.\n')
        os.replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def collect_results(directory, figures=True):
    directory=Path(directory)
    plan=S.load_plan(directory,check_code=False)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output=directory/'reports'/stamp
    S.export(directory,output)
    result=report(output,plan,figures=figures)
    destination=bundle(directory,output,directory/'results.zip')
    print(json.dumps({'report':str(output/'report.html'),'send_this_file':str(destination),**result},indent=2),flush=True)
    return result


def execute(directory, smoke=False):
    directory=Path(directory)
    plan=prepare(directory,smoke)
    live=not smoke
    state=S.status(directory)
    if not state['remaining']:
        collect_results(directory)
        return 0 if not state['unresolved_trials'] and not state['budget_breach'] else 2
    if live and state['remaining'] and not os.environ.get('OPENROUTER_API_KEY'):
        if not sys.stdin.isatty():
            raise ValueError('Run in a terminal to enter the key privately, or set OPENROUTER_API_KEY in the environment.')
        key=getpass.getpass('OpenRouter key (hidden; used only in this process): ').strip()
        if not key:
            raise ValueError('No key supplied. The frozen study is saved; run the same command again.')
        os.environ['OPENROUTER_API_KEY']=key
    requested=False
    previous=signal.getsignal(signal.SIGINT)
    def stop(signum,frame):
        nonlocal requested
        if requested: raise KeyboardInterrupt
        requested=True
        print('\nStopping after the current trial is safely saved. Please wait; a second Ctrl-C interrupts it.',flush=True)
    def progress(row):
        print(json.dumps(row),flush=True)
        if requested: raise GracefulStop
    signal.signal(signal.SIGINT,stop)
    code=0
    try:
        for stage in ('pilot','main'):
            # Fixed schedule, no scientific choices or sample-size overrides for the operator.
            result=S.run(directory,stage=stage,max_trials=len(plan['jobs']),live=live,on_progress=progress)
            print(json.dumps({'stage_finished':stage,**result}),flush=True)
            if result['stop']!='complete':
                print('Collection stopped. Send results.zip back; do not change models, counts, or start a new folder.',flush=True)
                code=2; break
    except GracefulStop:
        print('Paused between trials. Run the same command to continue.',flush=True)
        code=130
    except (Exception,KeyboardInterrupt) as exc:
        # Do not echo arbitrary SDK error text: the native logs retain diagnostic evidence.
        print(f'Collection stopped ({type(exc).__name__}). Results will show the incomplete trial. Send results.zip back.',flush=True)
        code=2
    finally:
        signal.signal(signal.SIGINT,previous)
        collect_results(directory)
    return code
