"""Frozen native-Inspect studies with one durable budget and at-most-once trials.

Serial trial execution is intentional: reserve every possible role call before
dispatch, disable all retry layers, then reconcile from the provider's raw cost.
Unknown charges keep the full reservation. Never resend an ambiguous trial.
"""
from contextlib import contextmanager
from decimal import Decimal as D, InvalidOperation
import fcntl
from hashlib import sha256
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
from random import Random
import sys
import urllib.request
from urllib.parse import quote
from uuid import uuid4

from .experiment import digest, now
from .audit_game import study_game
from .incomplete.games import GAMES

PROTOCOL = 'gut-inspect-study-v1'
STUDIES = (*GAMES, 'audit_threshold', 'audit_information')
ROOT = Path(__file__).resolve().parents[1]


def money(value):
    if isinstance(value, bool):
        raise ValueError('Money must be a finite nonnegative decimal.')
    try:
        result = D(str(value))
    except InvalidOperation as exc:
        raise ValueError('Money must be a finite nonnegative decimal.') from exc
    if not result.is_finite() or result < 0:
        raise ValueError('Money must be a finite nonnegative decimal.')
    return result


def atomic_json(path, value):
    """Create only; a crash leaves either a complete record or an ignored temp."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.'+path.name+'.'+uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as out:
            json.dump(value, out, sort_keys=True, allow_nan=False, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.link(temporary, path)  # fails rather than overwriting a saved record
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('Duplicate JSON keys.')
            obj[key] = value
        return obj
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON.')))


@contextmanager
def study_lock(directory):
    """OS lock releases on crashes; no unsafe deletion of stale PID files."""
    with (Path(directory)/'.study.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another process owns this study.') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def provenance():
    files = [*sorted((ROOT/'gut').rglob('*.py')),
             *(ROOT/p for p in ('inspect_study.py', 'audit_experiment.py', 'private_games.py', 'pyproject.toml'))]
    return {'files': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files},
            'python': sys.version.split()[0],
            'packages': {p: version(p) for p in ('inspect-ai', 'openai', 'agent-client-protocol')}}


def endpoint_spec(model_id, provider):
    """Public, non-billable metadata; no key is read or sent."""
    if (not isinstance(model_id, str) or model_id.count('/') != 1 or ':' in model_id
            or model_id.startswith('openrouter/') or not isinstance(provider, str) or not provider):
        raise ValueError('Specify an OpenRouter author/model ID and an exact endpoint tag.')
    url = 'https://openrouter.ai/api/v1/models/'+quote(model_id, safe='/')+'/endpoints'
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)['data']
    matches = [e for e in data['endpoints'] if e['tag'] == provider]
    if len(matches) != 1:
        raise ValueError('Select one exact endpoint tag from the public OpenRouter endpoints response.')
    endpoint = matches[0]
    prices = endpoint['pricing']
    context = endpoint.get('max_prompt_tokens') or endpoint['context_length']
    accepted = {model_id, endpoint['model_id']}
    advertised = endpoint['name'].split('|')[-1].strip()
    if '/' in advertised:
        accepted.add(advertised)
    result = {'id': model_id, 'provider': provider, 'provider_name': endpoint['provider_name'],
              'accepted_response_models': sorted(accepted), 'context_length': context,
              'max_completion_tokens': endpoint.get('max_completion_tokens'),
              'prompt_price': str(money(prices['prompt'])),
              'completion_price': str(money(prices['completion'])),
              'request_price': str(money(prices.get('request', '0'))),
              'source_url': url}
    if type(context) is not int or context < 4096:
        raise ValueError('Endpoint context is missing or too small for these tasks.')
    return result


def reserve(model, max_tokens, roles):
    if model['id'] == 'synthetic/baselines':
        return D('0.01') * len(roles)  # testable simulated reservation; actual cost is zero
    return len(roles) * (money(model['prompt_price'])*model['context_length'] +
                        money(model['completion_price'])*max_tokens + money(model['request_price']))


def samples_for(study, repetitions, seed, pilot=False):
    from .audit_inspect import audit_samples
    from .incomplete.inspect_task import paired_samples
    if study in GAMES:
        game = GAMES[study]
        return paired_samples(game, costs=[game.costs[len(game.costs)//2]] if pilot else None,
                              repetitions=repetitions, seed=seed)
    return audit_samples(study_game(study), coverages=['1/2'] if pilot and study == 'audit_threshold' else None,
                         defender_mode='model' if study == 'audit_information' else 'fixed',
                         repetitions=repetitions, seed=seed)


def roles_for(study):
    return ('row', 'column') if study in GAMES else (
        ('defender', 'attacker') if study == 'audit_information' else ('attacker',))


def prepare(directory, studies, *, repetitions, budget_usd, models=None, mode='synthetic',
            seed=2026, max_tokens=512, temperature=0.7):
    studies = tuple(studies)
    if not studies or len(set(studies)) != len(studies) or any(s not in STUDIES for s in studies):
        raise ValueError('Select distinct supported studies.')
    if mode not in ('synthetic', 'openrouter') or type(repetitions) is not int or not 1 <= repetitions <= 1000:
        raise ValueError('Specify synthetic/openrouter and 1..1000 repetitions per cell/block.')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('Seed must be an integer in [0, 2^32).')
    if type(max_tokens) is not int or not 16 <= max_tokens <= 32768:
        raise ValueError('max_tokens must be 16..32768.')
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError('Temperature must be finite and in [0,2].')
    budget = money(budget_usd)
    if not 0 < budget <= 50:
        raise ValueError('Use a total study budget greater than zero and no more than the authorized $50.')
    if mode == 'synthetic':
        if models:
            raise ValueError('Synthetic plans use only local scripted models.')
        specs = [{'id': 'synthetic/baselines'}]
    else:
        if not models or any(set(m) != {'id', 'provider'} for m in models):
            raise ValueError('Supply public model identifiers and endpoint tags only, never credentials.')
        if len({(m['id'], m['provider']) for m in models}) != len(models):
            raise ValueError('Duplicate models/endpoints.')
        specs = [endpoint_spec(m['id'], m['provider']) for m in models]
        if any(m['max_completion_tokens'] is not None and max_tokens > m['max_completion_tokens'] for m in specs):
            raise ValueError('Output cap exceeds the selected endpoint limit.')
    jobs = []
    for model_index, spec in enumerate(specs):
        for study in studies:
            roles = roles_for(study)
            reservation = reserve(spec, max_tokens, roles)
            if reservation > budget:
                raise ValueError('The budget cannot reserve even one complete trial for this endpoint.')
            for stage in ('pilot', 'main'):
                for sample in samples_for(study, 1 if stage == 'pilot' else repetitions, seed, stage == 'pilot'):
                    metadata = dict(sample.metadata)
                    prefix = f'm{model_index}:{study}:{stage}:'
                    metadata['pair_id'] = prefix+metadata['pair_id']
                    item = {'study': study, 'model_index': model_index, 'stage': stage,
                            'sample_id': prefix+str(sample.id), 'metadata': metadata,
                            'roles': list(roles), 'reservation_usd': str(reservation)}
                    jobs.append({'id': digest(item)[:24], **item})
    Random(seed).shuffle(jobs)
    plan = {'protocol': PROTOCOL, 'mode': mode, 'budget_usd': str(budget), 'studies': list(studies),
            'models': specs, 'repetitions': repetitions, 'seed': seed,
            'generation': {'max_tokens': max_tokens, 'temperature': temperature, 'max_retries': 0,
                           'timeout': 90, 'cache': False, 'cache_prompt': False, 'num_choices': 1},
            'design': {'private_games': 'Only public D cost is swept; same actual rewards revealed/hidden.',
                       'audit_threshold': 'Only q is swept; penalty=1/2, reward spread=3/10, equal prior.',
                       'audit_information': 'Only information is varied; q is a defender outcome. Fixed target-preference profiles, penalty=0, equal prior.',
                       'presentation': 'Independent cyclic label/order rotations: 4 private-game or 9 audit blocks.',
                       'pilot': 'Separate compatibility trials, never pooled with main results.'},
            'game_configs': json.loads(json.dumps({s: GAMES[s].config() if s in GAMES else study_game(s).defender_view()
                                                   for s in studies}, default=str)),
            'provenance': provenance(), 'jobs': jobs}
    plan['sha256'] = digest(plan)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory/'plan.json', plan)
    return plan


def load_plan(directory, check_code=True):
    plan = read_json(Path(directory)/'plan.json')
    if plan.get('protocol') != PROTOCOL or digest({k: v for k, v in plan.items() if k != 'sha256'}) != plan['sha256']:
        raise ValueError('Study manifest changed or is unsupported.')
    if check_code and plan['provenance'] != provenance():
        raise ValueError('Code or dependencies changed. Restore the frozen version or create a separate study.')
    if len({j['id'] for j in plan['jobs']}) != len(plan['jobs']):
        raise ValueError('Duplicate trial identities.')
    return plan


class Ledger:
    """Immutable start/finish/review records, always associated with one manifest."""
    def __init__(self, directory, plan):
        self.directory, self.plan = Path(directory), plan
        self.jobs = {j['id']: j for j in plan['jobs']}
        self.starts, self.finishes, self.reviews = {}, {}, {}
        for path in sorted((self.directory/'attempts').glob('*/*.json')):
            job_id = path.parent.name
            if job_id not in self.jobs:
                raise ValueError('Foreign attempt directory.')
            row = read_json(path)
            if digest({k: v for k, v in row.items() if k != 'sha256'}) != row.get('sha256'):
                raise ValueError('Ledger record changed or is incomplete.')
            if row['plan_sha256'] != plan['sha256'] or row['id'] != job_id:
                raise ValueError('Record does not match this study.')
            target = {'start.json': self.starts, 'finish.json': self.finishes, 'review.json': self.reviews}.get(path.name)
            if target is None:
                raise ValueError('Unknown ledger record.')
            target[job_id] = row
        for job_id, row in self.starts.items():
            if row['job_sha256'] != digest(self.jobs[job_id]) or row['reservation_usd'] != self.jobs[job_id]['reservation_usd']:
                raise ValueError('Reservation or trial identity changed.')
        if (set(self.finishes) | set(self.reviews)) - set(self.starts):
            raise ValueError('Completion/review without a reservation.')
        for job_id, row in self.finishes.items():
            if row['actual_cost_usd'] is not None:
                money(row['actual_cost_usd'])
            if row.get('native_log'):
                log = self.directory/row['native_log']
                if not log.resolve().is_relative_to(self.directory.resolve()) or sha256(log.read_bytes()).hexdigest() != row['log_sha256']:
                    raise ValueError('Native log moved, missing, or changed.')
        for job_id, row in self.reviews.items():
            if row['finish_sha256'] != digest(self.finishes.get(job_id)):
                raise ValueError('Review no longer matches the recorded attempt.')

    @property
    def committed(self):
        return sum((money(self.finishes[j]['actual_cost_usd'])
                    if j in self.finishes and self.finishes[j]['actual_cost_usd'] is not None
                    else max(money(start['reservation_usd']), money(self.finishes.get(j, {}).get('reported_cost_usd', '0'))))
                   for j, start in self.starts.items())

    @property
    def blockers(self):
        return [j for j in self.starts if
                (j not in self.finishes or self.finishes[j]['needs_review']) and j not in self.reviews]

    @property
    def breached(self):
        return any(f.get('budget_breach') for f in self.finishes.values())

    def write(self, job, kind, data):
        row = {'id': job['id'], 'plan_sha256': self.plan['sha256'], 'utc': now(), **data}
        row['sha256'] = digest(row)
        atomic_json(self.directory/'attempts'/job['id']/(kind+'.json'), row)
        {'start': self.starts, 'finish': self.finishes, 'review': self.reviews}[kind][job['id']] = row
        return row

    def start(self, job):
        if job['id'] in self.starts:
            raise ValueError('An attempted trial must never be dispatched again.')
        if self.committed + money(job['reservation_usd']) > money(self.plan['budget_usd']):
            return False
        self.write(job, 'start', {'job_sha256': digest(job), 'reservation_usd': job['reservation_usd']})
        return True

    def summary(self):
        return {'mode': self.plan['mode'], 'planned': len(self.jobs), 'attempted': len(self.starts),
                'recorded': len(self.finishes), 'remaining': len(self.jobs)-len(self.starts),
                'valid': sum(f['status'] == 'valid' for f in self.finishes.values()),
                'budget_usd': self.plan['budget_usd'], 'cost_plus_reservations_usd': str(self.committed),
                'unresolved_trials': self.blockers, 'budget_breach': self.breached,
                'stages': {stage: {'planned': sum(j['stage']==stage for j in self.jobs.values()),
                                  'attempted': sum(self.jobs[j]['stage']==stage for j in self.starts),
                                  'valid': sum(self.jobs[j]['stage']==stage and f['status']=='valid'
                                               for j, f in self.finishes.items())}
                           for stage in ('pilot', 'main')}}


def provider_options(spec):
    return {'only': [spec['provider']], 'allow_fallbacks': False, 'require_parameters': True,
            'max_price': {'prompt': float(money(spec['prompt_price'])*1000000),
                          'completion': float(money(spec['completion_price'])*1000000),
                          'request': float(money(spec['request_price']))}}


def make_task(plan, job):
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.model import GenerateConfig, ModelCost, ModelInfo, get_model, set_model_info
    from .audit_inspect import audit_task
    from .incomplete.inspect_task import private_task
    from audit_experiment import mock_attacker, mock_defender
    from private_games import mock_models
    study = job['study']
    if plan['mode'] == 'synthetic':
        models = (mock_models(GAMES[study], seed=job['metadata']['seed']) if study in GAMES else
                  {'attacker': mock_attacker(study_game(study))})
        if study == 'audit_information':
            models['defender'] = mock_defender(study_game(study))
    else:
        spec = plan['models'][job['model_index']]
        zero = ModelCost(input=0, output=0, input_cache_read=0, input_cache_write=0)
        set_model_info('none/none', ModelInfo(cost=zero))
        models = {}
        for role in job['roles']:
            model = get_model('openrouter/'+spec['id'], config=GenerateConfig(**plan['generation']),
                              provider=provider_options(spec), stream=False, max_retries=0)
            # Inspect retries AND its underlying OpenAI SDK retries must be off.
            if model.api.client.max_retries != 0:
                raise ValueError('The underlying provider SDK must not retry requests.')
            set_model_info(str(model), ModelInfo(context_length=spec['context_length'], cost=ModelCost(
                input=float(money(spec['prompt_price'])*1000000),
                output=float(money(spec['completion_price'])*1000000),
                input_cache_read=float(money(spec['prompt_price'])*1000000),
                input_cache_write=float(money(spec['prompt_price'])*1000000))))
            models[role] = model
    limit = None if plan['mode'] == 'synthetic' else max(1e-9, float(money(job['reservation_usd'])))
    if study in GAMES:
        task = private_task(GAMES[study], models, costs=[job['metadata']['cost']], cost_limit=limit)
    else:
        task = audit_task(study_game(study), models, cost_limit=limit,
                          defender_mode='model' if study == 'audit_information' else 'fixed',
                          coverages=[job['metadata']['planned_q']] if study == 'audit_threshold' else None)
    task.dataset = MemoryDataset([Sample(id=job['sample_id'], input='One-round game', metadata=job['metadata'])])
    task.metadata.update(study_sha256=plan['sha256'], job_id=job['id'], stage=job['stage'],
                         budget_reservation_usd=job['reservation_usd'])
    return task


def assess_log(plan, job, log):
    """Only provider-reported USD releases reservations; Inspect estimates do not."""
    samples = log.samples or []
    if len(samples) != 1 or str(samples[0].id) != job['sample_id']:
        raise ValueError('Native log has the wrong trial identity.')
    if log.eval.metadata.get('study_sha256') != plan['sha256'] or log.eval.metadata.get('job_id') != job['id']:
        raise ValueError('Native log belongs to a different study/trial.')
    sample = samples[0]
    record = sample.metadata.get('record')
    status = 'error' if sample.error else (record or {}).get('status', 'incomplete')
    events = [e for e in sample.events if e.event == 'model']
    seen = [e.role for e in events]
    expected = job['roles']
    diagnostics = []
    if seen != expected[:len(seen)] or len(seen) > len(expected):
        diagnostics.append('unexpected_role_calls')
    if any(e.retries or e.cache for e in events):
        diagnostics.append('retry_or_cached_response')
    if status == 'valid' and len(seen) != len(expected):
        diagnostics.append('missing_role_call')
    cost = D(0)
    if plan['mode'] == 'synthetic':
        if not all(e.model.startswith('mockllm/') for e in events):
            diagnostics.append('non_mock_in_synthetic')
    else:
        spec = plan['models'][job['model_index']]
        if not events:
            diagnostics.append('missing_usage')
        for event in events:
            raw = event.call.response if event.call and event.call.response else {}
            try:
                cost += money(raw['usage']['cost'])
            except (KeyError, TypeError, ValueError):
                diagnostics.append('missing_usage')
            if raw.get('model') not in spec['accepted_response_models'] or raw.get('provider') != spec['provider_name']:
                diagnostics.append('model_or_provider_mismatch')
            if event.error:
                diagnostics.append('provider_error')
    if log.status != 'success' or sample.error:
        diagnostics.append('incomplete_or_error_log')
    if status not in ('valid', 'invalid', 'invalid_defender', 'invalid_attacker'):
        diagnostics.append('unfinished_record')
    unknown = bool(diagnostics)  # retain ceiling even for identity / unexpected-call anomalies
    breach = cost > money(job['reservation_usd'])
    return {'status': status, 'actual_cost_usd': str(cost) if not unknown else None,
            'reported_cost_usd': str(cost),
            'needs_review': unknown or breach, 'budget_breach': breach,
            'diagnostics': sorted(set(diagnostics)), 'record': record,
            'error': sample.error.model_dump(mode='json') if sample.error else None}


def recover(directory, plan, ledger):
    """Adopt finished native logs after a crash; never repeat a started trial."""
    from inspect_ai.log import read_eval_log
    for job_id in list(ledger.starts):
        if job_id in ledger.finishes:
            continue
        job = ledger.jobs[job_id]
        logs = sorted((Path(directory)/'logs'/job_id).glob('*.eval'))
        result = None
        if len(logs) == 1:
            try:
                log = read_eval_log(str(logs[0]))
            except Exception:
                log = None  # incomplete archive: no charge is released
            if log is not None:
                result = assess_log(plan, job, log)
                result.update(native_log=str(logs[0].relative_to(directory)),
                              log_sha256=sha256(logs[0].read_bytes()).hexdigest())
        if result is None:
            result = {'status': 'interrupted', 'actual_cost_usd': None, 'needs_review': True,
                      'budget_breach': False, 'diagnostics': ['ambiguous_attempt_no_complete_native_log'],
                      'record': None, 'error': None, 'native_log': None, 'log_sha256': None}
        ledger.write(job, 'finish', result)


def run(directory, *, stage, max_trials, live=False, on_progress=None):
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log
    directory = Path(directory).resolve()
    if stage not in ('pilot', 'main') or type(max_trials) is not int or max_trials < 1:
        raise ValueError('Specify pilot/main and a positive per-invocation trial cap.')
    with study_lock(directory):
        plan = load_plan(directory)
        if (plan['mode'] == 'openrouter') != live:
            raise ValueError('A live plan requires --live; synthetic plans must omit it.')
        ledger = Ledger(directory, plan)
        recover(directory, plan, ledger)
        if ledger.breached or ledger.blockers:
            raise ValueError('Unresolved attempts require review; a price-ceiling breach stops this study permanently.')
        if stage == 'main' and any(j['id'] not in ledger.finishes or ledger.finishes[j['id']]['status'] != 'valid'
                                   or ledger.finishes[j['id']]['needs_review']
                                   for j in plan['jobs'] if j['stage'] == 'pilot'):
            raise ValueError('Every separate compatibility pilot must pass before main collection.')
        if live:
            if not os.environ.get('OPENROUTER_API_KEY'):
                raise ValueError('Set OPENROUTER_API_KEY in your local environment; never put it in the plan.')
            for spec in plan['models']:
                if endpoint_spec(spec['id'], spec['provider']) != spec:
                    raise ValueError('Endpoint prices, limits or identity changed. Prepare a separate reviewed study.')
        attempted, stop = 0, 'complete'
        for job in plan['jobs']:
            if job['stage'] != stage or job['id'] in ledger.starts:
                continue
            if attempted >= max_trials:
                stop = 'invocation_limit'
                break
            task = make_task(plan, job)  # local validation before reserving anything
            if not ledger.start(job):
                stop = 'budget_cap'
                break
            attempted += 1
            logs = inspect_eval(task, model=None, log_dir=str(directory/'logs'/job['id']),
                                display='none', max_samples=1, max_tasks=1, epochs=1, retry_on_error=0,
                                log_model_api=True, **plan['generation'])
            if len(logs) != 1:
                raise RuntimeError('Expected one native log; reservation retained until recovery.')
            path = Path(logs[0].location).resolve()
            result = assess_log(plan, job, read_eval_log(str(path)))
            result.update(native_log=str(path.relative_to(directory)), log_sha256=sha256(path.read_bytes()).hexdigest())
            ledger.write(job, 'finish', result)
            if on_progress is not None:
                on_progress({'job': job['id'], 'stage': stage, 'status': result['status'],
                             'cost_plus_reservations_usd': str(ledger.committed)})
            if result['needs_review']:
                stop = 'review_required'
                break
            if stage == 'pilot' and result['status'] != 'valid':
                stop = 'pilot_failed'
                break
        return {**ledger.summary(), 'attempted_now': attempted, 'stop': stop}


def review(directory, job_id, note):
    if not isinstance(note, str) or len(note.strip()) < 20:
        raise ValueError('Record a substantive explanation of the unresolved attempt.')
    with study_lock(directory):
        plan = load_plan(directory)
        ledger = Ledger(directory, plan)
        recover(Path(directory).resolve(), plan, ledger)
        if ledger.breached:
            raise ValueError('Cannot continue a study whose cost ceiling was breached.')
        if job_id not in ledger.blockers:
            raise ValueError('Select one unresolved trial.')
        ledger.write(ledger.jobs[job_id], 'review', {'note': note,
                     'finish_sha256': digest(ledger.finishes.get(job_id))})
        return ledger.summary()


def status(directory):
    with study_lock(directory):
        plan = load_plan(directory, check_code=False)
        return Ledger(directory, plan).summary()


def export(directory, destination):
    """Include every planned trial, including not-started/failed observations."""
    directory, destination = Path(directory), Path(destination)
    with study_lock(directory):
        plan = load_plan(directory, check_code=False)
        ledger = Ledger(directory, plan)
        rows = []
        for job in plan['jobs']:
            finish = ledger.finishes.get(job['id'], {})
            rows.append({'job_id': job['id'], 'study': job['study'], 'stage': job['stage'],
                         'model': plan['models'][job['model_index']]['id'],
                         'sample_id': job['sample_id'], 'metadata': job['metadata'],
                         'status': finish.get('status', 'interrupted' if job['id'] in ledger.starts else 'not_started'),
                         'record': finish.get('record'), 'native_log': finish.get('native_log'),
                         'diagnostics': finish.get('diagnostics', []),
                         'error': finish.get('error'), 'needs_review': finish.get('needs_review', False),
                         'reservation_usd': job['reservation_usd'] if job['id'] in ledger.starts else '0',
                         'actual_cost_usd': finish.get('actual_cost_usd'),
                         'reported_cost_usd': finish.get('reported_cost_usd')})
        destination.mkdir(parents=True, exist_ok=False)
        atomic_json(destination/'summary.json', ledger.summary())
        with (destination/'observations.jsonl').open('x') as out:
            for row in rows:
                out.write(json.dumps(row, allow_nan=False)+'\n')
        return ledger.summary()
