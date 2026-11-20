"""Descriptive, block-balanced results; pilots never enter main estimates.

A sample/pair is the independent unit within a role, never two players pooled
as independent evidence. Intervals are pointwise Hoeffding bounds conditional
on valid observations and independence. Missing-data bounds remain separate.
"""
from collections import Counter, defaultdict
import csv
from fractions import Fraction as F
import html
import json
from math import log, sqrt
from pathlib import Path

from .canonical import EXAMPLES, controlled_matrix
from .incomplete.games import GAMES
from .audit_game import study_game

DIMENSIONS = ('study', 'model', 'role', 'profile', 'information', 'cost', 'cost_action', 'representation')
METRICS = ('first_action_rate', 'dominance_violation', 'abstention_rate', 'violation_rate',
           'best_response_rate', 'checking_probability', 'expected_defender_payoff', 'payoff')


def number(value):
    return float(F(str(value))) if value is not None else None


def metric_bounds(study, metadata, role, metric):
    if metric not in ('payoff', 'expected_defender_payoff'):
        return (0., 1.)
    if study in EXAMPLES:
        table = controlled_matrix(study, metadata['condition'], role)
        values = [float(c[0]) for row in table for c in row]
    elif study in GAMES:
        values = [float(v) for row in GAMES[study].table(role, metadata['private_type'], metadata['cost']) for v in row]
    else:
        game = study_game(study)
        deduction = game.punishment * game.punishment_cost
        values = [float(v-deduction) for v in (F(0), *game.defender_unchecked, *game.defender_checked)]
    return min(values), max(values)


def flatten(observations):
    rows = []
    for item in observations:
        meta, study = item['metadata'], item['study']
        record = item.get('record') or {}
        roles = ('row', 'column') if study in EXAMPLES or study in GAMES else (
            ('defender', 'attacker') if study == 'audit_information' else ('attacker',))
        for role in roles:
            condition = meta.get('condition', {})
            row = dict(job_id=item['job_id'], pair_id=meta['pair_id'], stage=item['stage'],
                       study=study, model=item['model'], role=role, profile=meta['private_type'],
                       information=meta['information'], cost=meta.get('cost', meta.get('planned_q')),
                       cost_action=condition.get('cost_action', ''),
                       representation=condition.get('representation', 'original'),
                       presentation_block=meta['presentation_block'], repetition=meta['repetition'],
                       status=item['status'], action=None, native_log=item.get('native_log'),
                       **{m: None for m in METRICS})
            if role in ('row', 'column'):
                choice = record.get('choices', {}).get(role, {})
                if choice.get('status') == 'valid':
                    row['action'] = choice['action']
                    row['first_action_rate'] = int(choice['action'] in ('C', 'X'))
                    # Only a strict dominance region makes this diagnostic applicable.
                    margins = choice.get('margins')
                    if margins is None and study in GAMES:
                        margins = GAMES[study].gaps(role, meta['private_type'], meta['cost'])
                    if margins and (min(map(number, margins)) > 0 or max(map(number, margins)) < 0):
                        row['dominance_violation'] = int(choice['strict_dominance_violation'])
                if record.get('status') == 'valid':
                    payoff = record['outcome'].get(role+'_payoff', record['outcome'].get(role))
                    row['payoff'] = number(payoff)
            else:
                if role == 'defender':
                    row['checking_probability'] = number(record.get('q'))
                if record.get('status') == 'valid':
                    if role == 'attacker':
                        row.update(action=record['action'], abstention_rate=int(record['action']=='abstain'),
                                   violation_rate=int(record['action']!='abstain'),
                                   best_response_rate=int(record['is_best_response']))
                    if role == 'defender':
                        row['expected_defender_payoff'] = number(record['expected_defender'])
            row['_metadata'] = meta
            rows.append(row)
    return rows


def estimate(blocks, low, high):
    """Equal block weight; no complete-case reweighting of missing blocks."""
    means, ns, lower, upper = [], [], [], []
    for values in blocks.values():
        valid = [v for v in values if v is not None]
        ns.append(len(valid))
        means.append(sum(valid)/len(valid) if valid else None)
        lower.append((sum(valid)+(len(values)-len(valid))*low)/len(values))
        upper.append((sum(valid)+(len(values)-len(valid))*high)/len(values))
    b = len(blocks)
    mean = sum(means)/b if all(v is not None for v in means) else None
    half = (high-low)*sqrt(log(40)*sum(1/n for n in ns)/(2*b*b)) if mean is not None else None
    return {'planned': sum(map(len, blocks.values())), 'valid': sum(ns), 'blocks': b,
            'empty_blocks': sum(n==0 for n in ns), 'mean': mean,
            'ci_low': max(low, mean-half) if half is not None else None,
            'ci_high': min(high, mean+half) if half is not None else None,
            'missing_lower': sum(lower)/b, 'missing_upper': sum(upper)/b}


def summaries(rows):
    groups = defaultdict(list)
    for row in rows:
        if row['stage'] == 'main':
            groups[tuple(row[k] for k in DIMENSIONS)].append(row)
    cells, blocks = [], []
    for key, items in groups.items():
        study, role, meta = key[0], key[2], items[0]['_metadata']
        metrics = (('first_action_rate', 'payoff', 'dominance_violation') if study in EXAMPLES or study in GAMES else
                   ('checking_probability', 'expected_defender_payoff') if role=='defender' else
                   ('abstention_rate', 'violation_rate', 'best_response_rate'))
        for metric in metrics:
            if metric == 'dominance_violation':
                gaps = (GAMES[study].gaps(role, meta['private_type'], meta['cost']) if study in GAMES else
                        [r[0]-r[1] for r in zip(*[[c[0] for c in t] for t in controlled_matrix(study, meta['condition'], role)])])
                if not (min(gaps)>0 or max(gaps)<0):
                    continue
            values = defaultdict(list)
            for row in items:
                values[row['presentation_block']].append(row[metric])
            lo, hi = metric_bounds(study, meta, role, metric)
            base = dict(zip(DIMENSIONS, key), metric=metric)
            cells.append({**base, **estimate(values, lo, hi)})
            for block, vs in values.items():
                blocks.append({**base, 'presentation_block': block, **estimate({block:vs}, lo, hi)})
    return cells, blocks


def paired_effects(rows):
    pairs = defaultdict(dict)
    for row in rows:
        if row['stage']=='main' and row['study'] in (*GAMES, 'audit_information'):
            key = (row['pair_id'], row['role'])
            if row['information'] in pairs[key]:
                raise ValueError('Duplicate information condition in a paired observation.')
            pairs[key][row['information']] = row
    groups = defaultdict(lambda: defaultdict(list))
    bounds = {}
    dims = tuple(k for k in DIMENSIONS if k != 'information')
    for conditions in pairs.values():
        reference = next(iter(conditions.values()))
        metrics = ('first_action_rate',) if reference['study'] in GAMES else (
            ('checking_probability', 'expected_defender_payoff') if reference['role']=='defender' else ('violation_rate',))
        for metric in metrics:
            a, b = (conditions.get(i, {}).get(metric) for i in ('hidden','revealed'))
            key = (*[reference[k] for k in dims], metric)
            groups[key][reference['presentation_block']].append(a-b if a is not None and b is not None else None)
            low, high = metric_bounds(reference['study'], reference['_metadata'], reference['role'], metric)
            bounds[key] = (low-high, high-low)
    return [dict(zip((*dims, 'metric'), key), direction='hidden minus revealed',
                 **estimate(values, *bounds[key])) for key, values in groups.items()]


def csv_file(path, rows):
    fields = list(rows[0]) if rows else ['no_observations']
    with path.open('w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def draw(cells, destination, synthetic):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    panels = defaultdict(list)
    for c in cells:
        if c['metric'] not in ('first_action_rate', 'abstention_rate', 'checking_probability', 'expected_defender_payoff'):
            continue
        key = tuple(c[k] for k in ('study','model','role','profile','cost_action','representation','metric'))
        panels[key].append(c)
    figures = []
    destination.mkdir()
    for index, (key, values) in enumerate(panels.items()):
        study, model, role, profile, target, rep, metric = key
        fig, ax = plt.subplots(figsize=(6.2,3.8), layout='constrained')
        if study == 'audit_information':
            plotted = [c for c in values if c['mean'] is not None]
            for c in plotted:
                x = 0 if c['information']=='revealed' else 1
                ax.errorbar(x,c['mean'],yerr=[[c['mean']-c['ci_low']],[c['ci_high']-c['mean']]],fmt='o',capsize=3,color='#296b9f')
            ax.set_xticks([0,1],['Rewards revealed','Rewards hidden']); ax.set_xlim(-.5,1.5)
        else:
            for info in sorted({c['information'] for c in values}):
                selected = sorted([c for c in values if c['information']==info and c['mean'] is not None],key=lambda c:F(c['cost']))
                if selected:
                    ax.errorbar([number(c['cost']) for c in selected],[c['mean'] for c in selected],
                        yerr=[[c['mean']-c['ci_low'] for c in selected],[c['ci_high']-c['mean'] for c in selected]],
                        marker='o',markersize=3,linewidth=1,capsize=2,label=info)
            roots = []
            if study in EXAMPLES:
                roots = [float(v)*(1 if target==1 else -1) for v in EXAMPLES[study].thresholds(role)]
            elif study in GAMES:
                t = GAMES[study].thresholds(role,profile); roots=[float(t['against_c']),float(t['against_d'])]
            else:
                roots=[number(t['checking_probability'])*(1 if t['target']=='target_a' else -1)+(0 if t['target']=='target_a' else 1)
                       for t in study_game(study).thresholds() if t['type']==profile and t['in_domain']]
            for root in sorted(set(roots)):
                if root>=0:
                    ax.axvline(root,color='.5',linestyle=':',linewidth=.8)
            ax.set_xlabel('Checking probability q' if study=='audit_threshold' else 'Intervention cost (original points)')
            if ax.lines: ax.legend(fontsize=8)
        if metric != 'expected_defender_payoff': ax.set_ylim(-.04,1.04)
        counts = f"valid/planned = {sum(c['valid'] for c in values)}/{sum(c['planned'] for c in values)}"
        ax.set_ylabel(metric.replace('_',' ')); ax.grid(alpha=.15)
        ax.set_title(f"{'SYNTHETIC · ' if synthetic else ''}{study} · {role} · {profile}\n{model} · {rep} · cost action {target}\n{counts}", fontsize=9)
        name=f'panel-{index:03}.svg'; fig.savefig(destination/name); plt.close(fig)
        figures.append({'study':study,'model':model,'file':'figures/'+name,'label':f'{role} · {profile} · {rep} · {metric}'})
    return figures


def report(export_directory, plan, figures=True):
    directory = Path(export_directory)
    observations = [json.loads(line) for line in (directory/'observations.jsonl').read_text().splitlines()]
    rows = flatten(observations)
    cells, blocks = summaries(rows)
    effects = paired_effects(rows)
    predictions = {}
    for study in plan['studies']:
        if study in EXAMPLES:
            predictions[study] = {'thresholds_for_cost_on_second_action':{
                r:list(map(str,EXAMPLES[study].thresholds(r))) for r in ('row','column')},
                'note':'For cost on first action, negate these roots. Negative roots are outside the nonnegative sweep. Each root conditions on one opponent action; ties do not force a unique action.'}
        elif study in GAMES:
            predictions[study] = {profile:{role:GAMES[study].thresholds(role,profile)
                                           for role in ('row','column')} for profile in ('low','high')}
        else:
            game=study_game(study)
            predictions[study] = {'attacker_thresholds':game.thresholds(),
                'defender_optima':{info:{t.name:game.information_game(info,t.name).commitment().solve()
                                        for t in game.types} for info in ('revealed','hidden')},
                'note':'Defender optima assume a payoff-maximizing attacker; favorable and unfavorable ties are distinct. These are mathematical predictions, not LLM evidence.'}
    (directory/'predictions.json').write_text(json.dumps(predictions,indent=2,default=str)+'\n')
    csv_file(directory/'choices.csv', [{k:v for k,v in r.items() if not k.startswith('_')} for r in rows])
    csv_file(directory/'cells.csv', cells); csv_file(directory/'presentation-blocks.csv', blocks)
    csv_file(directory/'paired-effects.csv', effects)
    synthetic=plan['mode']=='synthetic'
    images=draw(cells,directory/'figures',synthetic) if figures else []
    summary=json.loads((directory/'summary.json').read_text())
    totals=[]
    for study in plan['studies']:
        selected=[r for r in observations if r['stage']=='main' and r['study']==study]
        counts=Counter(r['status'] for r in selected)
        totals.append({'study':study,'planned':len(selected),'valid':counts['valid'],
                       'not_started':counts['not_started'],'other':len(selected)-counts['valid']-counts['not_started']})
    csv_file(directory/'completion.csv',totals)
    esc=html.escape
    sections=[]
    for study in plan['studies']:
        cards=''.join(f'<figure><img src="{im["file"]}" alt="{esc(im["label"])}" loading="lazy"><figcaption>{esc(im["model"])} · {esc(im["label"])}</figcaption></figure>' for im in images if im['study']==study)
        sections.append(f'<details><summary>{esc(study)}</summary><div class="grid">{cards}</div></details>')
    table=''.join('<tr>'+''.join(f'<td>{esc(str(v))}</td>' for v in r.values())+'</tr>' for r in totals)
    prefix='SYNTHETIC SOFTWARE CHECK' if synthetic else 'LLM GAME STUDY'
    complete=summary['stages']['main']['attempted']==summary['stages']['main']['planned'] and not summary['unresolved_trials']
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Game study results</title><style>body{{font:16px/1.6 system-ui;max-width:1250px;margin:40px auto;padding:0 24px;color:#172c3b;background:#f5f8fa}}h1{{font-size:34px;margin-bottom:4px}}.tag{{color:#35647f;font-weight:700;letter-spacing:.1em}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}details{{background:white;padding:18px;margin:16px 0;border-radius:10px}}summary{{font-weight:700;cursor:pointer}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}}figure{{margin:12px 0}}img{{width:100%}}figcaption{{font-size:12px;color:#52626c}}a{{color:#12689b}}@media(max-width:500px){{.grid{{grid-template-columns:1fr}}}}</style>
<p class="tag">{prefix}</p><h1>When do incentives change choices?</h1><p>{'All main trials attempted' if complete else 'PARTIAL RUN — missing trials remain'}. Validity and missingness are shown below.</p>
<p>Budget: ${esc(summary['budget_usd'])}; charges plus unresolved reservations: ${esc(summary['cost_plus_reservations_usd'])}. Pilots are excluded from all main estimates.</p>
<p>PD: temptation to defect. Stag Hunt: cooperation needs trust. Chicken: both insisting is worst. Battle of the Sexes: agree despite preferring different outcomes. The private variants hide one player's reward profile. Audit: a defender chooses where to check; an attacker then violates or abstains.</p>
<table><tr><th>Study</th><th>Main planned</th><th>Valid trials</th><th>Not started</th><th>Invalid/error/interrupted</th></tr>{table}</table>
<p>Each plot is 2D. Dotted lines are exact payoff ties, not fitted behavioral thresholds. First action means C (cooperate/yield) or X in the coordination game. Both BoS directions and both roles stay separate. Display-scale checks stay separate from primary comparisons.</p>
<p>Points weight presentation blocks equally. Bars are conservative 95% pointwise Hoeffding intervals, assuming independent samples and conditioning on available valid responses. They are not simultaneous confidence bands or proof of a sharp behavioral threshold. Empty blocks have no estimated mean. Small cells are deliberately imprecise. Missing-data bounds, all planned counts and individual blocks are in the tables. Hidden-minus-revealed comparisons match actual rewards and presentations; profiles are reported separately. No unique equilibrium or safety guarantee is inferred.</p>
<p><a href="choices.csv">Individual choices</a> · <a href="cells.csv">Cell estimates and missing-data bounds</a> · <a href="presentation-blocks.csv">Presentation checks</a> · <a href="paired-effects.csv">Matched information effects</a> · <a href="predictions.json">Exact theoretical predictions</a> · <a href="observations.jsonl">Full planned observations</a> · <a href="summary.json">Budget and status</a></p>
{''.join(sections)}</html>'''
    (directory/'report.html').write_text(page)
    return {'complete':complete,'synthetic':synthetic,'cells':len(cells),'figures':len(images),'main_trials':totals}
