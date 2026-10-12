"""Offline independent audit of archived prompts, choices, scores, and plot cells.

The numerical oracle below reads displayed matrix cells and enumerates outcomes;
it does not call the experiment's payoff, regret, or best-response functions.
The runner is imported only to check historical request reproduction.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ACTIONS = ('C', 'D')
PROFILES = tuple(itertools.product(ACTIONS, repeat=2))


def read_bytes(path):
    return gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()


def artifact(data, name):
    return read_bytes(data / name) if (data / name).exists() else read_bytes(data / (name + '.gz'))


def close(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def displayed_matrix(record):
    """Return canonical row/column payoff tuples parsed from the actual prompt."""
    text = record['request']['messages'][0]['content']
    perspective = record['case']['stage'].startswith('perspective')
    pattern = (r'your action=([AB]), opponent action=([AB]): \(your payoff ([^,]+), opponent payoff ([^)]+)\)'
               if perspective else r'row=([AB]), column=([AB]): \(row payoff ([^,]+), column payoff ([^)]+)\)')
    cells = re.findall(pattern, text)
    require(len(cells) == 4, 'Prompt does not contain exactly four cells')
    mapping = {'A': 'C', 'B': 'D'} if record['case']['replicate'] % 2 == 0 else {'A': 'D', 'B': 'C'}
    matrix = {}
    for a, b, x, y in cells:
        a, b, x, y = mapping[a], mapping[b], float(x), float(y)
        if perspective and record['role'] == 'column':
            a, b, x, y = b, a, y, x
        require((a, b) not in matrix, 'Duplicate prompt cell')
        matrix[a, b] = (x, y)
    return matrix


def oracle_joint(matrix, row, column, scale, punishment):
    if row not in ACTIONS or column not in ACTIONS:
        return {'valid': False}
    profile = (row, column)
    utilities = matrix[profile]
    gains = (max(matrix[a, column][0] for a in ACTIONS) - utilities[0],
             max(matrix[row, a][1] for a in ACTIONS) - utilities[1])
    pareto = not any(all(v[i] >= utilities[i] for i in (0, 1)) and
                     any(v[i] > utilities[i] for i in (0, 1)) for v in matrix.values())
    return {'valid': True, 'profile': list(profile),
            'cooperation_rate': (int(row == 'C') + int(column == 'C')) / 2,
            'mutual_cooperation': row == column == 'C', 'mutual_defection': row == column == 'D',
            'nash': max(gains) <= 1e-9, 'pareto': pareto,
            'welfare_optimal': sum(utilities) >= max(map(sum, matrix.values())) - 1e-9,
            'welfare': sum(utilities), 'normalized_welfare': (sum(utilities) - 2 * punishment) / scale,
            'row_regret': gains[0] / scale, 'column_regret': gains[1] / scale}


def oracle_decision(matrix, role, action, q, scale):
    def utility(own, other):
        return matrix[own, other][0] if role == 'row' else matrix[other, own][1]
    expectations = {a: q * utility(a, 'C') + (1 - q) * utility(a, 'D') for a in ACTIONS}
    margin = (expectations['C'] - expectations['D']) / scale
    regret = (max(expectations.values()) - expectations[action]) / scale
    best = '|'.join(a for a in ACTIONS if max(expectations.values()) - expectations[a] <= 1e-9 * scale)
    return {'stated_belief_margin_normalized': margin, 'stated_belief_regret_normalized': regret,
            'stated_belief_best_response': best, 'stated_belief_action_consistent': action in best.split('|'),
            'stated_belief_tie': abs(margin) <= 1e-9}


def equal_fields(actual, expected, label):
    for key, value in expected.items():
        got = actual[key]
        if isinstance(got, str) and not isinstance(value, str):
            got = json.loads(got.lower() if got in ('True', 'False') else got) if got else None
        okay = close(got, value) if isinstance(value, (int, float)) and not isinstance(value, bool) else got == value
        require(okay, f'{label}: {key} mismatch ({got!r} versus {value!r})')


def audit(data):
    from run_phase_space import make_jobs, request_for, reservation
    records = [json.loads(line) for line in artifact(data, 'attempts.jsonl').splitlines()]
    summary = json.loads(artifact(data, 'summary.json'))
    ledger = json.loads(artifact(data, 'ledger.json'))
    catalog = json.loads(artifact(data, 'model_catalog.json'))['models']
    ds = {r['job_id']: r for r in csv.DictReader(io.StringIO(artifact(data, 'theory_decisions.csv').decode()))}
    gs = {r['simulation_id']: r for r in csv.DictReader(io.StringIO(artifact(data, 'theory_simulations.csv').decode()))}
    cells = list(csv.DictReader(io.StringIO(artifact(data, 'deviation_heatmap_cells.csv').decode())))
    require(len({r['job_id'] for r in records}) == len(records), 'Duplicate recorded request IDs')
    require(len(ds) == len(records), 'Decision export count mismatch')
    manifests = [json.loads(p.read_text()) for p in sorted(data.glob('manifest_*.json'))]
    expected = {}
    for manifest in manifests:
        jobs = make_jobs(manifest['stage'], manifest['replicate'], list(manifest['models']))
        require({j['job_id'] for j in jobs} == set(manifest['job_ids']), 'Manifest differs from generated design')
        for j in jobs:
            require(j['job_id'] not in expected, 'Overlapping manifests')
            expected[j['job_id']] = (j, manifest)
    require(set(expected) == {r['job_id'] for r in records}, 'Coverage differs from manifest union')
    groups = defaultdict(dict); decision_cells = defaultdict(list); game_cells = defaultdict(list)
    parsed = {}; matrices = {}; reported_cost = 0; accounted_cost = 0
    for r in records:
        jid = r['job_id']; case = r['case']; p = case['payoffs']; scale = p['R'] - p['P']
        job, manifest = expected[jid]
        payload, mapping = request_for(job, catalog[job['model']], manifest['max_tokens'])
        require(payload == r['request'] and mapping == r['label_mapping'] and case == job['case'], jid + ': request regeneration mismatch')
        require(close(reservation(payload, catalog[job['model']]['pricing']), r['reservation_usd']), jid + ': reservation mismatch')
        matrix = displayed_matrix(r); matrices[jid] = matrix
        intended = {('C','C'):(p['R'],p['R']), ('C','D'):(p['S'],p['T']),
                    ('D','C'):(p['T'],p['S']), ('D','D'):(p['P'],p['P'])}
        require(matrix == intended, jid + ': displayed matrix differs from scored game')
        require(close(p['s'], (p['S'] - p['P']) / scale) and close(p['t'], (p['T'] - p['P']) / scale), jid + ': normalization')
        pure = [list(profile) for profile in PROFILES if oracle_joint(matrix, *profile, scale, p['P'])['nash']]
        pareto = [list(profile) for profile in PROFILES if oracle_joint(matrix, *profile, scale, p['P'])['pareto']]
        welfare = [list(profile) for profile in PROFILES if oracle_joint(matrix, *profile, scale, p['P'])['welfare_optimal']]
        require(pure == p['pure_nash'] and pareto == p['pareto_profiles'] and welfare == p['welfare_profiles'], jid + ': analytic profile sets')
        qstar = p['mixed_cooperation_probability']
        gains = (matrix['C','C'][0]-matrix['D','C'][0], matrix['C','D'][0]-matrix['D','D'][0])
        require((qstar is not None) == (gains[0]*gains[1] < 0), jid + ': missing or extraneous interior mixed equilibrium')
        if qstar is not None:
            require(0 < qstar < 1 and close(oracle_decision(matrix, r['role'], 'C', qstar, scale)['stated_belief_margin_normalized'], 0), jid + ': mixed equilibrium')
        action = None; q = None
        if r['status'] == 'success':
            require(r['response']['model'] == r['model'] == r['response_model'], jid + ': returned model identity')
            try:
                answer = json.loads(r['response']['choices'][0]['message']['content'])
            except (ValueError, TypeError):
                answer = None
            if isinstance(answer, dict) and answer.get('final_action') in ('A','B'):
                action = 'C' if answer['final_action'] == mapping['C'] else 'D'
                belief = answer.get('belief_opponent_A')
                if type(belief) in (float, int) and math.isfinite(belief) and 0 <= belief <= 1:
                    q = belief if mapping['C'] == 'A' else 1 - belief
            usage_cost = r['response'].get('usage', {}).get('cost')
            require(usage_cost == r['reported_cost_usd'], jid + ': response cost mismatch')
        else:
            require(r['status'] == 'abandoned_timeout' and r.get('request_reconstructed_from_manifest'), jid + ': unexpected failed-call status')
        require(r['decision']['valid'] == (action is not None) and r['decision']['action'] == action, jid + ': independent action parse')
        require(r['decision'].get('belief_opponent_C') == q, jid + ': belief decoding')
        parsed[jid] = (action, q)
        row = ds[jid]
        equal_fields(row, {'valid_action': action is not None, 'action': action or ''}, jid)
        if action is not None and q is not None:
            benchmark = oracle_decision(matrix, r['role'], action, q, scale)
            equal_fields(row, benchmark, jid)
            for name in ('T','R','P','S'):
                cutoff = row[name+'_threshold_at_stated_belief']
                if (name in ('T','R') and q == 0) or (name in ('P','S') and q == 1):
                    require(cutoff == '', jid + ': payoff-independent cutoff')
                    continue
                values = {k:p[k] for k in ('T','R','P','S')};values[name]=float(cutoff)
                uc=q*values['R']+(1-q)*values['S'];ud=q*values['T']+(1-q)*values['P']
                require(close(uc,ud), jid + ': payoff cutoff not an indifference root')
            if case['stage'] == 'perspective_grid':
                decision_cells[r['model_key'], p['s'], p['t']].append((jid, benchmark))
        else:
            require(row['stated_belief_regret_normalized'] == '', jid + ': invalid decision has regret')
        cost = r['reported_cost_usd']
        require(close(r['accounted_cost_usd'], cost if cost is not None else r['reservation_usd']), jid + ': accounted cost')
        require(r['accounted_cost_usd'] <= r['reservation_usd'] + 1e-9, jid + ': cost exceeded reservation')
        reported_cost += cost or 0; accounted_cost += r['accounted_cost_usd']
        key = (case['stage'], case['replicate'], case['case_id'], r['model_key'])
        require(r['role'] not in groups[key], jid + ': duplicate role')
        groups[key][r['role']] = r
    indexed = {(g['case']['stage'],g['case']['replicate'],g['case']['case_id'],g['model_key']):g for g in summary['games']}
    require(set(indexed) == set(groups) and len(gs) == len(groups), 'Game export coverage')
    cooperation = {}; valid_games = 0
    for key, roles in groups.items():
        require(set(roles) == {'row','column'}, str(key) + ': missing role')
        r = roles['row']; c = roles['column']; p = r['case']['payoffs']; scale = p['R'] - p['P']
        require(matrices[r['job_id']] == matrices[c['job_id']], str(key) + ': players saw different games')
        result = oracle_joint(matrices[r['job_id']], parsed[r['job_id']][0], parsed[c['job_id']][0], scale, p['P'])
        equal_fields(indexed[key]['scores'], result, str(key))
        regrets=[]
        for record in roles.values():
            a,q=parsed[record['job_id']]
            if a is not None and q is not None:
                regrets.append(oracle_decision(matrices[record['job_id']],record['role'],a,q,scale)['stated_belief_regret_normalized'])
        expected_regret=statistics.mean(regrets) if regrets else None
        stored_regret=indexed[key]['belief_regret']
        require(stored_regret is None if expected_regret is None else close(stored_regret,expected_regret), str(key)+': summary belief regret')
        sid = '/'.join(map(str,key)); equal_fields(gs[sid], result, sid)
        require(gs[sid]['row_job_id'] == r['job_id'] and gs[sid]['column_job_id'] == c['job_id'], sid + ': pairing')
        if result['valid']:
            valid_games += 1
            maximum = max(map(sum,matrices[r['job_id']].values()))
            equal_fields(gs[sid], {'maximum_unilateral_regret_normalized':max(result['row_regret'],result['column_regret']),
                                  'welfare_gap_normalized':(maximum-result['welfare'])/scale},sid)
            if key[0] == 'perspective_grid':
                game_cells[key[3],p['s'],p['t']].append((sid,result))
    for cell in cells:
        key = (cell['model_key'],float(cell['s']),float(cell['t']))
        d = decision_cells[key]; g = game_cells[key]
        violations = sum(not b['stated_belief_action_consistent'] for _, b in d)
        values = {'valid_belief_decisions':len(d), 'belief_ties':sum(b['stated_belief_tie'] for _,b in d),
                  'inconsistent_decisions':violations, 'belief_violation_rate':violations/len(d) if d else None,
                  'mean_belief_regret':statistics.mean(b['stated_belief_regret_normalized'] for _,b in d) if d else None,
                  'valid_games':len(g), 'mean_maximum_realized_regret':statistics.mean(max(b['row_regret'],b['column_regret']) for _,b in g) if g else None}
        equal_fields(cell,values,str(key))
        require(set(json.loads(cell['decision_ids'])) == {jid for jid,_ in d},str(key)+': decision IDs')
        require(set(json.loads(cell['simulation_ids'])) == {sid for sid,_ in g},str(key)+': game IDs')
        cooperation[key] = statistics.mean(b['cooperation_rate'] for _,b in g) if g else None
    require(len(cells) == 4*13*13 and len({(c['model_key'],c['s'],c['t']) for c in cells}) == len(cells), 'Heatmap coverage')
    require(close(reported_cost,ledger['reported_usd']), 'Reported ledger mismatch')
    require(close(accounted_cost+sum(ledger['reservations'].values()),ledger['accounted_usd']), 'Accounted ledger mismatch')
    require(ledger['completed_attempts'] == len(records) and ledger['accounted_usd'] <= ledger['cap_usd'], 'Budget totals')
    # Check matched PD sample identities, not just bar counts.
    controls = {}
    for model in ('glm','qwen','astra','fable'):
        for role in ('row','column'):
            sets = {}; counts = {}
            for stage in ('grid','perspective'):
                selected = [r for r in records if r['case']['stage'] == stage and r['case']['replicate'] in (0,1)
                            and r['case']['payoffs']['strict_pd'] and r['model_key'] == model and r['role'] == role and parsed[r['job_id']][0] is not None]
                sets[stage] = {(r['case']['case_id'],r['case']['replicate']) for r in selected}
                counts[stage] = {'n':len(selected),'C':sum(parsed[r['job_id']][0] == 'C' for r in selected)}
            require(sets['grid'] == sets['perspective'], 'Presentation bars use different matched samples')
            controls[model+'/'+role] = counts
    return {'status':'passed','recorded_attempts':len(records),'successful_responses':sum(r['status']=='success' for r in records),
            'reconstructed_unreturned_requests':sum(bool(r.get('request_reconstructed_from_manifest')) for r in records),
            'valid_actions':sum(a is not None for a,q in parsed.values()),'paired_games':len(groups),'valid_games':valid_games,
            'heatmap_cells_checked':len(cells),'presentation_controls':controls,
            'reported_cost_usd':reported_cost,'accounted_cost_usd':accounted_cost,
            'raw_log_sha256':hashlib.sha256(artifact(data,'attempts.jsonl')).hexdigest(),
            'checks':['Manifest coverage and request regeneration','Displayed matrices for both roles and label blocks',
                      'Independent raw action/belief decoding','Independent expected utilities and joint outcome enumeration',
                      'Nash, pure Pareto and social-optimum sets','Every recorded game and theory CSV row',
                      'Every deviation heatmap cell and its source IDs','Matched presentation-control denominators','Reported and reserved costs'],
            'additional_paid_calls':0}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--data',type=Path,default=ROOT/'data');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); result=audit(args.data)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('presentation_controls','checks')}))

if __name__ == '__main__':
    main()
