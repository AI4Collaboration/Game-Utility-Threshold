"""Audit a phase-space run and write a concise, self-contained research report."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_phase_space import summarize, read_records, parse_decision

LABELS={'glm':'GLM-5.3','qwen':'Qwen3.8 2.4T A95B','astra':'GPT-6 Astra','fable':'Claude Fable 5.1'}


def mean(xs):
    xs=list(xs)
    return statistics.mean(xs) if xs else None


def pct(v):
    return f'{100*v:.1f}%' if v is not None else '—'


def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join(
        '| '+' | '.join(str(x) for x in row)+' |\n' for row in rows)+'\n'


def report(out):
    data=summarize(out)
    records=read_records(out/'attempts.jsonl')
    latest={r['job_id']:r for r in records}
    manifests=[json.loads(p.read_text()) for p in sorted(out.glob('manifest_*.json'))]
    audit=[]
    expected=set()
    for m in manifests:
        ids=set(m['job_ids']);expected.update(ids)
        found=ids & latest.keys()
        audit.append({'stage':m['stage'],'replicate':m['replicate'],'expected_decisions':len(ids),
                      'recorded_decisions':len(found),'valid_decisions':sum(latest[k]['decision']['valid'] for k in found),
                      'missing_decisions':sorted(ids-latest.keys()),
                      'complete':len(found)==len(ids)})
    audit_payload={'manifests':audit,'duplicate_job_ids':len(records)-len(latest),
                   'unexpected_job_ids':sorted(latest.keys()-expected),
                   'complete':all(a['complete'] for a in audit),
                   'invalid_decisions':sum(not r['decision']['valid'] for r in latest.values()),
                   'errors':dict(Counter(r['status'] for r in latest.values() if r['status']!='success'))}
    replay_errors=[]
    identity_errors=[]
    for r in records:
        if r['status']=='success':
            content=r['response'].get('choices',[{}])[0].get('message',{}).get('content')
            if parse_decision(content,r['label_mapping']) != r['decision']:
                replay_errors.append(r['job_id'])
            if r.get('response_model') != r['model']:
                identity_errors.append(r['job_id'])
    audit_payload['parse_replay_errors']=replay_errors
    audit_payload['model_identity_mismatches']=identity_errors
    audit_payload['reported_cost_sum_usd']=sum(r.get('reported_cost_usd') or 0 for r in records)
    audit_payload['ledger_reported_cost_usd']=data['ledger'].get('reported_usd',0)
    audit_payload['cost_reconciles']=abs(audit_payload['reported_cost_sum_usd']-audit_payload['ledger_reported_cost_usd'])<1e-8
    audit_payload['accounted_cost_sum_usd']=sum(r['accounted_cost_usd'] for r in records)
    audit_payload['outstanding_reservations']=data['ledger'].get('reservations',{})
    expected_accounted=audit_payload['accounted_cost_sum_usd']+sum(audit_payload['outstanding_reservations'].values())
    audit_payload['accounted_cost_reconciles']=abs(expected_accounted-data['ledger'].get('accounted_usd',0))<1e-8
    audit_payload['within_budget']=data['ledger'].get('accounted_usd',0)<=data['ledger'].get('cap_usd',50)
    (out/'coverage_audit.json').write_text(json.dumps(audit_payload,indent=2)+'\n')
    grid=[g for g in data['games'] if g['case']['stage']=='grid']
    valid=[g for g in grid if g['scores']['valid']]
    reps=sorted({g['case']['replicate'] for g in grid})
    paid=data['ledger'].get('reported_usd',0)
    accounted=data['ledger'].get('accounted_usd',0)
    text='# Payoff phase-space experiment\n\n'
    text+=f'**{len(records):,} paid request attempts; ${paid:.4f} provider-reported cost; '
    text+=f'${accounted:.4f} conservatively accounted against the $50 cap.**\n\n'
    text+=f'The primary grid contains {len(grid):,} recorded self-play games '
    text+=f'({len(valid):,} valid), across {len(reps)} replicate blocks and four models. '
    text+='Check the coverage table for completeness. Pilots and secondary sweeps are kept separate.\n\n'
    if any(r['case']['stage']=='perspective_grid' for r in records):
        text+='**Presentation materially affects the observed choices.** An exploratory '
        text+='own-payoff control and full-grid extension are reported below. The original '
        text+='row/column results should not be interpreted as effects of payoffs alone.\n\n'
    text+='## What the article did\n\n'
    text+='[Falmagne’s SIAM article](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/) '
    text+='is an analytic map of symmetric games. It removes payoff translation and positive scaling, '
    text+='then maps twelve strict payoff orderings and their strategic properties in two dimensions. '
    text+='It does not run LLMs or prescribe binary search.\n\n'
    text+='We implement `s=(S−P)/(R−P)` and `t=(T−P)/(R−P)`, fixing normalized `R=1, P=0`. '
    text+='The existing `(T,R,P,S)=(5,3,1,0)` baseline lies at `(s,t)=(-0.5,2)`. '
    text+='Nash boundaries are `s=0` and `t=1`; the social optimum changes at `s+t=2`. '
    text+='A grid measures behavior without assuming a single monotonic switch.\n\n'
    text+='![Analytic phase space](01_analytic_phase_space.png)\n\n'
    text+='## Primary experiment\n\n'
    text+='The 13×13 grid spans −1 to 2 in steps of 0.25 on both axes. Each model plays '
    text+='against an isolated instance of itself. Both choose simultaneously to maximize their '
    text+='own numerical payoff. There are no model-vs-model cross-pairings, repeated interactions, '
    text+='institutions, or uncertain payoffs in this experiment.\n\n'
    text+='Prompts use neutral A/B labels. The mapping to analytic C/D reverses in alternating '
    text+='replicate blocks. Matrix display order reverses between row and column roles. Main calls use '
    text+='a 4,096-token total output allowance and request low reasoning effort; temperature is '
    text+='left at provider defaults because both frontier endpoints do not advertise that parameter. '
    text+='Reasoning implementations are therefore not identical across providers.\n\n'
    rows=[]
    for model,label in LABELS.items():
        gs=[g for g in valid if g['model_key']==model]
        rs=[r for r in latest.values() if r['model_key']==model and r['case']['stage']=='grid']
        rows.append([label,f'{sum(r["decision"]["valid"] for r in rs)}/{len(rs)}',len(gs),
                     pct(mean(g['scores']['cooperation_rate'] for g in gs)),
                     pct(mean(g['scores']['nash'] for g in gs)),
                     pct(mean(g['scores']['welfare_optimal'] for g in gs)),
                     f'{mean((g["scores"]["row_regret"]+g["scores"]["column_regret"])/2 for g in gs):.3f}' if gs else '—'])
    text+=table(['Model','Valid decisions','Valid games','C-choice','Pure Nash outcome','Social optimum','Mean regret'],rows)
    text+='Rates exclude invalid games; validity retains all recorded decisions in its denominator. '
    text+='Regret is the best unilateral deviation gain divided by R−P. These are descriptive '
    text+='averages over the fixed grid, not model rankings or estimates over real-world games.\n\n'
    text+='![Measured behavior](04_model_cooperation_rate.png)\n\n'
    text+='### Response diagnostics\n\n'
    diagnostics=[]
    for model,label in LABELS.items():
        rs=[r for r in latest.values() if r['model_key']==model and r['case']['stage']=='grid']
        diagnostics.append([label,len(rs),sum(r.get('finish_reason')=='length' for r in rs),
                            sum(not r['decision']['valid'] and r.get('finish_reason')!='length' for r in rs),
                            sum(r['decision'].get('schema_valid',False) for r in rs)])
    text+=table(['Model','Recorded calls','Token-limit finishes','Other invalid outputs','Full valid schema'],diagnostics)
    text+='The action parser requires a whole JSON object with an explicit A/B final_action. '
    text+='Prose surrounding JSON is a format failure under this fixed parser, even '
    text+='when a human might recover a choice. The raw trace supports alternative parsing analyses.\n\n'
    text+='## Strict Prisoner’s Dilemma subset\n\n'
    text+='Here `T>R>P>S`, so D is strictly dominant. C-choice measures deviation from the '
    text+='stated individual-utility objective in these cells, rather than a general safety score.\n\n'
    rows=[]
    for model,label in LABELS.items():
        gs=[g for g in valid if g['model_key']==model and g['case']['payoffs']['strict_pd']]
        rows.append([label,len(gs),pct(mean(g['scores']['cooperation_rate'] for g in gs)),
                     pct(mean(g['scores']['mutual_defection'] for g in gs))])
    text+=table(['Model','Valid PD games','C-choice','Mutual defection'],rows)
    text+='## Game-regime breakdown\n\n'
    rows=[]
    for regime in ['D_dominant','C_dominant','coordination','anti_coordination','boundary']:
        for model,label in LABELS.items():
            gs=[g for g in valid if g['model_key']==model and g['case']['payoffs']['regime']==regime]
            rows.append([regime,label,len(gs),pct(mean(g['scores']['cooperation_rate'] for g in gs)),
                         pct(mean(g['scores']['nash'] for g in gs))])
    text+=table(['Regime','Model','Valid games','C-choice','Pure Nash outcome'],rows)
    text+='A realized profile outside the pure Nash set is not automatically a reasoning error: '
    text+='sampling a mixed equilibrium can produce such outcomes. The declared-belief fields '
    text+='provide a separate check of utility consistency. No catastrophe labels are invented '
    text+='for these abstract payoff matrices.\n\n'
    text+='### Dominant-action checks by role\n\n'
    role_rows=[]
    for model,label in LABELS.items():
        for role in ('row','column'):
            rs=[r for r in latest.values() if r['case']['stage']=='grid' and r['model_key']==model
                and r['role']==role and r['decision']['valid']
                and r['case']['payoffs']['regime'] in ('C_dominant','D_dominant')]
            correct=[r['decision']['action']==('C' if r['case']['payoffs']['regime']=='C_dominant' else 'D') for r in rs]
            role_rows.append([label,role,len(rs),pct(mean(correct))])
    text+=table(['Model','Role','Valid dominance cases','Dominant action chosen'],role_rows)
    text+='These cells have a strict best action for every opponent belief. Role and display '
    text+='order vary together in this design, so a role difference cannot isolate its cause.\n\n'
    controls=[r for r in latest.values() if r['case']['stage']=='perspective']
    if controls:
        text+='## Exploratory payoff-perspective control\n\n'
        text+='After observing role differences, we repeated all 16 strict-PD cells and four '
        text+='other anchors using an own-payoff presentation. Payoffs and objectives are '
        text+='unchanged. This control is exploratory and changes both matrix perspective '
        text+='and display order. It cannot distinguish those two causes.\n\n'
        def pairing_key(r):
            return (r['model_key'],r['role'],r['case']['case_id'],r['case']['replicate'])
        base={pairing_key(r):r for r in latest.values() if r['case']['stage']=='grid'}
        rows=[]
        for model,label in LABELS.items():
            for role in ('row','column'):
                paired=[(base[pairing_key(r)],r) for r in controls if r['model_key']==model
                        and r['role']==role and r['case']['payoffs']['strict_pd']
                        and pairing_key(r) in base and r['decision']['valid']
                        and base[pairing_key(r)]['decision']['valid']]
                rows.append([label,role,len(paired),pct(mean(a['decision']['action']=='C' for a,b in paired)),
                             pct(mean(b['decision']['action']=='C' for a,b in paired))])
        text+=table(['Model','Role','Valid matched PD decisions','Original C-choice','Own-perspective C-choice'],rows)
        text+='![Perspective control](13_payoff_perspective_control.png)\n\n'
    perspective_grid=[g for g in data['games'] if g['case']['stage']=='perspective_grid']
    if perspective_grid:
        text+='## Exploratory full grid with own-payoff presentation\n\n'
        text+='The targeted control motivated a full 13×13 replication with own-payoff '
        text+='presentation and two counterbalanced label blocks. This is a separate '
        text+='representation experiment, not a replacement for the original observations.\n\n'
        rows=[]
        for model,label in LABELS.items():
            gs=[g for g in perspective_grid if g['model_key']==model and g['scores']['valid']]
            pd=[g for g in gs if g['case']['payoffs']['strict_pd']]
            rows.append([label,len(gs),pct(mean(g['scores']['cooperation_rate'] for g in pd)),
                         pct(mean(g['scores']['nash'] for g in gs)),
                         pct(mean(g['scores']['welfare_optimal'] for g in gs))])
        text+=table(['Model','Valid games','PD C-choice','Pure Nash outcome','Social optimum'],rows)
        text+='![Own-payoff grid](14_own_payoff_cooperation.png)\n\n'
    text+='## Changing each raw payoff\n\n'
    text+='The secondary sweeps hold three values at `(5,3,1,0)` and vary the fourth. '
    text+='Exact incentive crossings and the baseline are included. Changing R or P generally '
    text+='moves both normalized coordinates; that is why the full two-dimensional map matters.\n\n'
    text+='At the baseline the two defection incentives are `T−R=2` and `P−S=1`. '
    text+='Changing one payoff fixes at most one. To make C dominant, both must be removed. '
    text+='The existing defection-cost intervention does this by lowering T and P together: '
    text+='cost `k=2` gives weak dominance, and `k>2` gives strict dominance. These are '
    text+='game utility units, not dollar costs.\n\n'
    text+='![Raw payoff incentives](03_one_parameter_incentives.png)\n\n'
    if (out/'09_model_raw_payoff_sweeps.png').exists():
        text+='![Raw payoff model response](09_model_raw_payoff_sweeps.png)\n\n'
    directional=[]
    for name,direction in [('T',-1),('R',1),('P',-1),('S',1)]:
        for model in LABELS:
            cells=defaultdict(list)
            for r in latest.values():
                if r['case']['stage']=='transects' and r['model_key']==model and r['decision']['valid'] and r['case']['axis']==name:
                    cells[r['case']['axis_value']].append(r['decision']['action']=='C')
            values=sorted(cells)
            if not values:
                continue
            points=[{'value':v,'C_rate':mean(cells[v]),'valid_decisions':len(cells[v])} for v in values]
            reversals=[{'left':a['value'],'right':b['value'],'delta_C_rate':b['C_rate']-a['C_rate']}
                       for a,b in zip(points,points[1:]) if direction*(b['C_rate']-a['C_rate']) < -1e-9]
            directional.append({'model':model,'axis':name,'expected_direction':direction,
                                'points':points,'adjacent_reversals':reversals})
    if directional:
        (out/'directional_diagnostics.json').write_text(json.dumps(directional,indent=2)+'\n')
        reversal_count=sum(bool(d['adjacent_reversals']) for d in directional)
        text+=f'**{reversal_count} of {len(directional)} observed model/axis curves contain adjacent '
        text+='reversals relative to the fixed-belief incentive direction.** This is a descriptive '
        text+='small-sample diagnostic, not proof that the underlying choice probability is '
        text+='nonmonotonic. Beliefs, labels, and sampling can also change. It does mean a naive '
        text+='single-switch binary search is not justified by these observations. '
        text+='See [directional diagnostics](directional_diagnostics.json) for every point and denominator.\n\n'
    text+='![Joint incentive intervention](16_joint_incentive_intervention.png)\n\n'
    text+='## Affine invariance control\n\n'
    text+='Analytically, `u`, `2u+1`, `10u`, and `u+10` define the same strategic game. '
    text+='Any measured choice differences reveal prompt-scale sensitivity and/or sampling variation. '
    text+='With few repeats per condition, differences do not establish a stable causal scale effect.\n\n'
    if (out/'10_affine_invariance_control.png').exists():
        text+='![Scale control](10_affine_invariance_control.png)\n\n'
    text+='## Coverage and execution\n\n'
    text+=table(['Stage','Block','Expected calls','Recorded','Valid','Complete'],
                [[a['stage'],a['replicate'],a['expected_decisions'],a['recorded_decisions'],a['valid_decisions'],a['complete']] for a in audit])
    text+='The initial pilot used 1,024 output tokens, truncating three answers. '
    text+='The 4,096-token pilot truncated one. Pilots are excluded from primary comparisons. '
    text+='Invalid and failed calls are retained without guessed actions or replacement retries.\n\n'
    failed=[r for r in records if r['status']!='success']
    if failed:
        text+=f'{len(failed)} request(s) have no successful API completion. Their status is recorded '
        text+='in the coverage audit and their full cost reservations remain in the accounted '
        text+='total when actual cost is unknown. One stalled GLM affine-control call was '
        text+='supervisor-terminated; its intended request was reconstructed from the manifest '
        text+='and is explicitly marked, with no response or action fabricated.\n\n'
    model_rows=[]
    for model,label in LABELS.items():
        rs=[r for r in latest.values() if r['model_key']==model]
        model_rows.append([label,rs[0]['model'] if rs else '—',
                           ', '.join(sorted({r.get('provider','unknown') for r in rs})),len(rs),
                           f'${sum(r.get("reported_cost_usd") or 0 for r in rs):.4f}'])
    text+=table(['Model','Requested ID','Returned provider(s)','Calls','Reported cost'],model_rows)
    text+='The open-weight selections are current flagships within GLM and Qwen, not a claim '
    text+='that a universal “top two” ranking exists. The public catalog and each returned model '
    text+='identifier are saved. Routing/version drift remains possible.\n\n'
    text+='## Files and reproduction\n\n'
    if (out/'theory_comparison.html').exists():
        text+='[**New: per-decision and per-simulation comparison with theory**](theory_comparison.html) '
        text+='includes stated-belief best responses, raw-payoff thresholds, dominance, mixed-equilibrium benchmarks, '
        text+='and individual/collective payoff gaps. [Decision CSV](theory_decisions.csv) · '
        text+='[Simulation CSV](theory_simulations.csv). No additional paid calls.\n\n'
    text+='- [Flat results](model_results.csv) and [structured summary](summary.json)\n'
    text+='- [Raw requests and responses](attempts.jsonl)\n'
    text+='- [Coverage audit](coverage_audit.json) and [cost ledger](ledger.json)\n'
    text+='- [Analytic grid](analytic_grid.csv)\n'
    if (out/'METHODS.md').exists():
        text+='- [Full methods](METHODS.md)\n'
    if (out/'implementation.patch').exists():
        text+='- [Implementation patch](implementation.patch)\n'
    text+='\n'
    text+='All figures have editable SVG counterparts. See METHODS.md for the exact protocol '
    text+='and reproduction commands. Positive affine normalization preserves the mathematical '
    text+='game, but model invariance must be tested. We do not fit an exact empirical threshold '
    text+='from a noisy or nonmonotonic sequence.\n'
    (out/'REPORT.md').write_text(text)
    import markdown_it
    body=markdown_it.MarkdownIt('commonmark').enable('table').render(text)
    css='''body{font-family:system-ui,sans-serif;color:#182334;max-width:1100px;margin:50px auto;padding:0 24px;line-height:1.6}h1{font-size:36px;line-height:1.2}h2{margin-top:48px}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 10px;border-bottom:1px solid #d9e0e8;text-align:left}th{background:#edf2f8}a{color:#2563a5}code{background:#edf2f8;padding:2px 4px}pre{overflow:auto}'''
    referenced=set(re.findall(r'!\[[^]]*\]\(([^)]+)\)',text))
    gallery='<h2>Additional figures</h2>'+''.join(f'<p><a href="{p.stem}.svg">Editable SVG</a></p><img src="{p.name}" alt="{html.escape(p.stem)}">' for p in sorted(out.glob('*.png')) if p.name not in referenced)
    gallery+='<h2>Figure downloads</h2><ul>'+''.join(f'<li>{html.escape(p.stem)}: <a href="{p.name}">PNG</a> · <a href="{p.stem}.svg">SVG</a></li>' for p in sorted(out.glob('*.png')))+'</ul>'
    (out/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Payoff phase-space experiment</title><style>'+css+'</style></head><body>'+body+gallery+'</body></html>')
    print(json.dumps({'reported_usd':paid,'accounted_usd':accounted,'complete':audit_payload['complete'],
                      'grid_games':len(grid),'valid_grid_games':len(valid),'blocks':len(reps)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    report(Path(parser.parse_args().output))
