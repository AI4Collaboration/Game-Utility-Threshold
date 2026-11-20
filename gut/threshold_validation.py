"""One durable spending ledger for the bounded Months 1–3 validation suite.

Native canonical/sequential plans remain reproducible. Pilot choices never
enter main estimates. The shared ledger is authoritative; materialized native
records are an exact, checked projection for the existing analysis code.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from decimal import Decimal as D
import json
import os
from pathlib import Path
import random

from . import experiment as canonical
from . import oversight_experiment as sequential
from .canonical import EXAMPLES
from .experiment import digest, now, openrouter
from .study import _json


def construct(directory, studies, budget_usd, seed):
    budget = D(str(budget_usd))
    if not budget.is_finite() or not 0 < budget <= 50:
        raise ValueError("Suite budget must be positive and at most $50")
    if len({s['name'] for s in studies}) != len(studies):
        raise ValueError("Duplicate study")
    jobs, contexts = [], {}
    for study in studies:
        if '/' in study['name'] or study['name'] in ('.', '..'):
            raise ValueError("Invalid study name")
        path = Path(directory)/study['name']
        if study['family'] == 'canonical':
            plan = canonical.load_run(path)[0]
            native = {j['id']: j for j in plan['jobs']}
            # One paired pilot in each label/order block, alternating endpoints.
            cells = [c for c in plan['conditions'] if c['purpose'] == 'primary']
            pilots = []
            for block in range(4):
                cell = cells[0 if block%2 == 0 else -1]
                pilots.extend(j for j in plan['jobs'] if j['condition_id'] == cell['id']
                              and j['block'] == block and j['pair'].endswith('r00000'))
            selected = [('pilot', j) for j in pilots] + [('main', j) for j in plan['jobs']]
        elif study['family'] == 'sequential':
            plan = sequential.load_run(path)[0]
            native = {j['id']: j for j in plan['jobs']}
            selected = [(j['stage'], j) for j in plan['jobs']]
        else:
            raise ValueError("Unknown study family")
        if plan['mode'] != 'openrouter' or plan['sha256'] != study['sha256']:
            raise ValueError("Wrong plan identity or non-live mode")
        contexts[study['name']] = (study['family'], plan, native)
        for stage, job in selected:
            model = plan['model_spec'] if study['family'] == 'canonical' else next(m for m in plan['models'] if m['id'] == job['model'])
            reserve = sequential.reservation(model, job['request']['max_tokens'])
            if reserve > budget:
                raise ValueError("Budget cannot reserve one call")
            jobs.append({'id': f"{study['name']}/{stage}/{job['id']}", 'study': study['name'],
                         'stage': stage, 'native_id': job['id'], 'reservation_usd': str(reserve)})
    random.Random(seed).shuffle(jobs)
    plan = {'protocol': 'months1-3-controlled-live-v1', 'budget_usd': str(budget),
            'seed': seed, 'studies': studies, 'jobs': jobs}
    return {**plan, 'sha256': digest(plan)}, contexts


def prepare(directory, models, budget_usd='45', repetitions=10, control_repetitions=3,
            seed=20261119):
    directory = Path(directory)
    if (directory/'manifest.json').exists():
        raise FileExistsError('Never overwrite an existing suite')
    directory.mkdir(parents=True, exist_ok=True)
    studies = []
    for mi, model in enumerate(models):
        for game in EXAMPLES:
            name = f'{game}-m{mi}'
            plan = canonical.save_plan(directory/name, version='v2', game=game,
                       mode='openrouter', model=model['id'], provider=model['provider'],
                       model_spec=model, repetitions=repetitions, control_repetitions=control_repetitions,
                       seed=seed+mi, temperature=.7, max_tokens=128)
            studies.append({'name': name, 'family': 'canonical', 'sha256': plan['sha256']})
    manifest, _ = construct(directory, studies, budget_usd, seed)
    (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def read_ledger(directory):
    directory = Path(directory)
    stored = _json((directory/'manifest.json').read_text())
    plan, contexts = construct(directory, stored['studies'], stored['budget_usd'], stored['seed'])
    if stored != plan:
        raise ValueError('Suite schedule differs from frozen plans')
    jobs = {j['id']: j for j in plan['jobs']}
    starts, finishes = {}, {}
    path = directory/'ledger.jsonl'
    for line in path.read_text().splitlines() if path.exists() else ():
        event = _json(line)
        job = jobs.get(event['id'])
        if job is None or event['plan_sha256'] != plan['sha256']:
            raise ValueError('Foreign ledger event')
        native = contexts[job['study']][2][job['native_id']]
        if event['event'] == 'started':
            if event['id'] in starts or event['request'] != native['request'] or event['reservation_usd'] != job['reservation_usd']:
                raise ValueError('Repeated or altered request')
            starts[event['id']] = event
        elif event['event'] == 'finished':
            if event['id'] not in starts or event['id'] in finishes or event['utc'] < starts[event['id']]['utc']:
                raise ValueError('Orphaned, repeated, or out-of-order finish')
            if type(event['http_status']) is not int or not isinstance(event['body'], str) or not isinstance(event['error'], (str, type(None))):
                raise ValueError('Invalid response envelope')
            finishes[event['id']] = event
        else:
            raise ValueError('Unknown ledger event')
    committed = sum((sequential.cost_from_body(finishes[jid]['body'])
                     if jid in finishes and sequential.cost_from_body(finishes[jid]['body']) is not None
                     else D(start['reservation_usd'])) for jid, start in starts.items())
    return plan, contexts, starts, finishes, D(committed)


def parse(contexts, job, finish):
    family, plan, jobs = contexts[job['study']]
    return (canonical.decision if family == 'canonical' else sequential.parse_choice)(plan, jobs[job['native_id']], finish)


def needs_audit(contexts, job, finish):
    if finish is None:
        return True
    cost = sequential.cost_from_body(finish['body'])
    return (finish['http_status'] != 200 or bool(finish['error']) or cost is None
            or cost > D(job['reservation_usd']) or parse(contexts, job, finish)[1] in
            ('model_mismatch', 'provider_mismatch', 'response_error', 'synthetic_in_live'))


def audit(directory, job_id, note):
    directory = Path(directory)
    if (directory/'.collect.lock').exists():
        raise ValueError('Stop collection before auditing')
    plan, contexts, starts, finishes, _ = read_ledger(directory)
    job = next(j for j in plan['jobs'] if j['id'] == job_id)
    if job_id not in starts or not needs_audit(contexts, job, finishes.get(job_id)) or len(note.strip()) < 20:
        raise ValueError('Identify an attempted failure and explain the audit')
    cost = sequential.cost_from_body(finishes[job_id]['body']) if job_id in finishes else None
    if cost is not None and cost > D(job['reservation_usd']):
        raise ValueError('Price ceiling violated; cannot resume this protocol')
    with (directory/'audits.jsonl').open('a') as out:
        out.write(json.dumps({'id': job_id, 'plan_sha256': plan['sha256'], 'utc': now(),
                              'finish_sha256': digest(finishes.get(job_id)), 'note': note})+'\n')
        out.flush(); os.fsync(out.fileno())


def collect(directory, stage, *, live=False, max_calls=100, workers=8, transport=None):
    if not live or stage not in ('pilot', 'main') or type(max_calls) is not int or max_calls < 1 or type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Require --live, explicit stage/call cap, and 1..16 workers')
    directory = Path(directory)
    manifest = _json((directory/'manifest.json').read_text())
    if any(s['family'] != 'canonical' for s in manifest['studies']):
        raise ValueError('This suite contains an unapproved custom prototype. Paid collection is on hold pending a published-design mapping; create a new canonical-only plan. See docs/design-sources.md.')
    key = sequential.local_key() if transport is None else None
    lock = directory/'.collect.lock'
    with lock.open('x') as out:
        out.write(str(os.getpid()))
    try:
        plan, contexts, starts, finishes, committed = read_ledger(directory)
        by_id = {j['id']: j for j in plan['jobs']}
        audited = set()
        path = directory/'audits.jsonl'
        for line in path.read_text().splitlines() if path.exists() else ():
            event = _json(line)
            if event['plan_sha256'] != plan['sha256'] or event['finish_sha256'] != digest(finishes.get(event['id'])):
                raise ValueError('Audit no longer matches the recorded failure')
            audited.add(event['id'])
        if any(jid not in audited and needs_audit(contexts, by_id[jid], finishes.get(jid)) for jid in starts):
            raise ValueError('Unresolved cost/transport/identity failure requires audit')
        if stage == 'main' and any(parse(contexts, j, finishes.get(j['id']))[1] != 'valid' for j in plan['jobs'] if j['stage'] == 'pilot'):
            raise ValueError('Every separate compatibility pilot must pass before main collection')
        jobs = [j for j in plan['jobs'] if j['stage'] == stage and j['id'] not in starts]
        count, index, stop = 0, 0, None
        with (directory/'ledger.jsonl').open('a') as stream, ThreadPoolExecutor(max_workers=workers) as pool:
            def append(event):
                stream.write(json.dumps({**event, 'plan_sha256': plan['sha256'], 'utc': now()}, allow_nan=False)+'\n')
                stream.flush(); os.fsync(stream.fileno())

            def call(job):
                native = contexts[job['study']][2][job['native_id']]
                try:
                    return transport(native, contexts[job['study']][1]) if transport else openrouter(native, key)
                except Exception as exc:
                    return 0, '', type(exc).__name__

            pending = {}
            last_report = 0
            while pending or (index < len(jobs) and count < max_calls and not stop):
                while not stop and index < len(jobs) and count < max_calls and len(pending) < workers:
                    job = jobs[index]
                    reserve = D(job['reservation_usd'])
                    if committed+reserve > D(plan['budget_usd']):
                        if not pending:
                            stop = 'budget_cap'
                        break
                    append({'event': 'started', 'id': job['id'], 'reservation_usd': str(reserve),
                            'request': contexts[job['study']][2][job['native_id']]['request']})
                    committed += reserve
                    pending[pool.submit(call, job)] = job
                    index += 1; count += 1
                if not pending:
                    break
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    job = pending.pop(future)
                    status, body, error = future.result()
                    if key:
                        body = body.replace(key, '[REDACTED_API_KEY]')
                    finish = {'event': 'finished', 'id': job['id'], 'http_status': status, 'body': body, 'error': error}
                    append(finish)
                    cost = sequential.cost_from_body(body)
                    if cost is not None:
                        committed += cost-D(job['reservation_usd'])
                    if needs_audit(contexts, job, finish):
                        stop = f"audit_required:{job['id']}:{parse(contexts, job, finish)[1]}"
                if count-last_report >= 100 or stop:
                    print(json.dumps({'stage': stage, 'dispatched': count, 'in_flight': len(pending),
                                      'cost_plus_reservations_usd': str(committed), 'stop': stop}), flush=True)
                    last_report = count
        return {'stage': stage, 'attempted_now': count, 'cost_plus_reservations_usd': str(committed), 'stop': stop}
    finally:
        lock.unlink()


def materialize(directory):
    """Rebuild analysis inputs, never replacing a different native record file."""
    directory = Path(directory)
    plan, contexts, starts, finishes, _ = read_ledger(directory)
    events = {s['name']: [] for s in plan['studies']}
    for job in plan['jobs']:
        family, native_plan, _ = contexts[job['study']]
        if family == 'canonical' and job['stage'] == 'pilot':
            continue
        for source in (starts, finishes):
            if job['id'] in source:
                event = {**source[job['id']], 'id': job['native_id'], 'plan_sha256': native_plan['sha256']}
                events[job['study']].append(event)
    for name, rows in events.items():
        path = directory/name/'records.jsonl'
        content = ''.join(json.dumps(row, allow_nan=False)+'\n' for row in sorted(rows, key=lambda e: e['utc']))
        if path.exists() and path.read_text() != content:
            raise ValueError('Existing native records differ; retain original and investigate')
        if not path.exists():
            path.write_text(content)
    return plan
