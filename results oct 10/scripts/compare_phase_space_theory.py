"""Replay saved decisions against analytic theory and export audits and figures.

Reads local artifacts only. Never imports or invokes the paid runner's run().
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utility_threshold.games.phase_space import SymmetricPayoffs, axis_values
from utility_threshold.games.theory_comparison import decision_benchmark, joint_benchmark, TOL
from scripts.render_phase_space import style, save, LABELS, COLORS
from scripts.report_phase_space import table, pct
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

STAGES = [('grid','Original matrix','#D47C3B'),
          ('perspective_grid','Own-payoff matrix','#2777B4')]


def mean(xs):
    xs=list(xs)
    return statistics.mean(xs) if xs else None


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})


def deviation_cells(ds,gs):
    """Aggregate within payoff cells, preserving denominators and tie counts."""
    decisions=defaultdict(list);games=defaultdict(list)
    for r in ds:
        if r['stage']=='perspective_grid' and r['stated_belief_action_consistent'] is not None:
            decisions[(r['model_key'],r['s'],r['t'])].append(r)
    for g in gs:
        if g['stage']=='perspective_grid' and g['valid']:
            games[(g['model_key'],g['s'],g['t'])].append(g)
    rows=[]
    for model in LABELS:
        for t in axis_values():
            for s in axis_values():
                rs=decisions[(model,s,t)];js=games[(model,s,t)]
                violations=sum(not r['stated_belief_action_consistent'] for r in rs)
                rows.append({'model_key':model,'s':s,'t':t,'R':1,'P':0,
                             'valid_belief_decisions':len(rs),'belief_ties':sum(r['stated_belief_tie'] for r in rs),
                             'inconsistent_decisions':violations,
                             'belief_violation_rate':violations/len(rs) if rs else None,
                             'mean_belief_regret':mean(r['stated_belief_regret_normalized'] for r in rs),
                             'valid_games':len(js),
                             'mean_maximum_realized_regret':mean(g['maximum_unilateral_regret_normalized'] for g in js),
                             'decision_ids':[r['job_id'] for r in rs],
                             'simulation_ids':[g['simulation_id'] for g in js]})
    assert sum(r['valid_belief_decisions'] for r in rows)==sum(len(v) for v in decisions.values())
    assert sum(r['valid_games'] for r in rows)==sum(len(v) for v in games.values())
    return rows


def deviation_maps(out,ds,gs):
    cells=deviation_cells(ds,gs)
    write_csv(out/'deviation_heatmap_cells.csv',cells)
    definitions=[
        ('22_belief_deviation_heatmap','belief_violation_rate','Where choices disagree with the stated-belief best response',
         'Fraction of decisions choosing a suboptimal action',1.,'valid_belief_decisions',4),
        ('23_expected_regret_heatmap','mean_belief_regret','How much expected utility those choices leave on the table',
         'Mean expected payoff loss / (R − P)',None,'valid_belief_decisions',4),
        ('24_realized_regret_heatmap','mean_maximum_realized_regret','Where realized outcomes allow a profitable unilateral switch',
         'Mean maximum unilateral regret / (R − P)',None,'valid_games',2)]
    cmap=LinearSegmentedColormap.from_list('deviation',['#FFFFFF','#FBC5B4','#E96555','#A31635','#4E0523'])
    cmap.set_bad('#B5BDC9')
    edges=np.arange(-1.125,2.126,.25)
    for filename,metric,title,colorlabel,maximum,count_field,expected in definitions:
        if maximum is None:
            maximum=max(.25,np.ceil(max(c[metric] or 0 for c in cells)*4)/4)
        fig,axes=plt.subplots(2,2,figsize=(11,10),layout='constrained')
        for ax,(model,label) in zip(axes.flat,LABELS.items()):
            selected=[c for c in cells if c['model_key']==model]
            z=np.array([np.nan if c[metric] is None else c[metric] for c in selected]).reshape(13,13)
            im=ax.pcolormesh(edges,edges,z,cmap=cmap,vmin=0,vmax=maximum,rasterized=False)
            ax.axvline(0,color='#636975',lw=.8,ls='--');ax.axhline(1,color='#636975',lw=.8,ls='--')
            partial=[c for c in selected if 0<c[count_field]<expected]
            ax.scatter([c['s'] for c in partial],[c['t'] for c in partial],s=12,c='#172333',marker='o')
            ax.set(xlim=(edges[0],edges[-1]),ylim=(edges[0],edges[-1]),
                   xlabel='Normalized S',ylabel='Normalized T',
                   title=f'{label} · n={sum(c[count_field] for c in selected)}')
        fig.colorbar(im,ax=list(axes.flat),shrink=.75,label=colorlabel)
        fig.suptitle(title,x=.02,ha='left',fontsize=17)
        footer='Own-payoff presentation · R=1, P=0 · two label blocks · '
        footer+=('up to 4 decisions/cell' if expected==4 else 'up to 2 games/cell')
        footer+='\nWhite = zero gap; darker red = larger gap; gray = no usable data; dot = reduced count. Dashed: regime boundaries.'
        footer+=('\nBest response uses each decision’s stated belief; either action is accepted at indifference. Beliefs may be inaccurate.'
                 if expected==4 else '\nRealized regret holds the opponent’s action fixed. Positive regret can occur under valid mixed-equilibrium play.')
        fig.supxlabel(footer,fontsize=9)
        save(fig,out,filename)


def build_rows(records):
    decisions=[];groups=defaultdict(dict)
    for r in records:
        c=r['case'];p=SymmetricPayoffs(**{k:c['payoffs'][k] for k in ('T','R','P','S')})
        d=r['decision'];action=d.get('action') if d.get('valid') else None
        q=d.get('belief_opponent_C')
        base={'model_key':r['model_key'],'model':r['model'],'stage':c['stage'],
              'replicate':c['replicate'],'case_id':c['case_id'],
              'axis':c.get('axis'),'axis_value':c.get('axis_value'),
              **{k:c['payoffs'][k] for k in ('T','R','P','S','s','t','regime')}}
        decisions.append({**base,'job_id':r['job_id'],'role':r['role'],
                          'valid_action':action is not None,'status':r['status'],'action':action,
                          **decision_benchmark(p,action,q)})
        key=(c['stage'],c['replicate'],c['case_id'],r['model_key'])
        groups[key][r['role']]=(base,action,r['job_id'])
    games=[]
    for key,roles in sorted(groups.items()):
        base=next(iter(roles.values()))[0]
        p=SymmetricPayoffs(**{k:base[k] for k in ('T','R','P','S')})
        games.append({**base,'simulation_id':'/'.join(map(str,key)),
                      'row_job_id':roles.get('row',(None,None,None))[2],
                      'column_job_id':roles.get('column',(None,None,None))[2],
                      **joint_benchmark(p,roles.get('row',(None,None))[1],roles.get('column',(None,None))[1])})
    return decisions,games


def belief_figure(out,ds):
    fig,axes=plt.subplots(2,2,figsize=(12,9),layout='constrained')
    edges=[-np.inf,-2,-1,-.5,-.25,-.1,-TOL,TOL,.1,.25,.5,1,2,np.inf]
    for ax,(model,label) in zip(axes.flat,LABELS.items()):
        ax.plot([-3,0],[0,0],'k--',lw=1.5,label='Theoretical best response')
        ax.plot([0,3],[1,1],'k--',lw=1.5)
        for stage,name,color in STAGES:
            rs=[r for r in ds if r['model_key']==model and r['stage']==stage
                and r['stated_belief_action_consistent'] is not None]
            buckets=defaultdict(list)
            for r in rs:
                m=r['stated_belief_margin_normalized']
                if abs(m)>TOL:
                    buckets[int(np.searchsorted(edges,m,side='right')-1)].append(r)
            points=[(mean(r['stated_belief_margin_normalized'] for r in bucket),
                     mean(r['action']=='C' for r in bucket),len(bucket)) for _,bucket in sorted(buckets.items())]
            for sign in (-1,1):
                selected=[p for p in points if sign*p[0]>0]
                ax.plot([p[0] for p in selected],[p[1] for p in selected],color=color,lw=1,alpha=.8)
            ax.scatter([p[0] for p in points],[p[1] for p in points],s=[12+min(p[2],200)/4 for p in points],
                       color=color,label=f'{name} (n={len(rs)})',zorder=3)
            ties=[r for r in rs if r['stated_belief_tie']]
            if ties:
                ax.scatter([0],[mean(r['action']=='C' for r in ties)],marker='D',s=35,
                           facecolors='none',edgecolors=color,zorder=4)
        ax.axvline(0,color='#888',lw=.8)
        ax.set(title=label,xlabel='Expected C advantage under stated belief / (R − P)',
               ylabel='Observed C-choice frequency',xlim=(-3.05,3.05),ylim=(-.05,1.05))
        ax.legend(fontsize=8,loc='center left');ax.grid(alpha=.15)
    fig.suptitle('Does each choice maximize payoff under the model’s own stated belief?',x=.02,ha='left')
    fig.supxlabel('Binned nonzero margins; marker size reflects sample count. Hollow diamond: exact indifference (either action optimal).\n'
                  'Original: four blocks; own-payoff: two blocks. Self-reported beliefs are not assumed calibrated.',fontsize=9)
    save(fig,out,'17_stated_belief_best_response')


def dominance_figure(out,ds):
    fig,axes=plt.subplots(1,2,figsize=(13,5.5),layout='constrained')
    for ax,action in zip(axes,['D','C']):
        for offset,(stage,name,color) in zip([-.18,.18],STAGES):
            counts=[];values=[]
            for model in LABELS:
                rs=[r for r in ds if r['model_key']==model and r['stage']==stage
                    and r['strict_dominant_action']==action and r['valid_action']]
                counts.append(len(rs));values.append(100*mean(not r['dominant_action_chosen'] for r in rs))
            bars=ax.barh(np.arange(4)+offset,values,height=.34,color=color,label=name)
            for bar,n,value in zip(bars,counts,values):
                ax.text(value+.5,bar.get_y()+.17,f'{value:.1f}% (n={n})',va='center',fontsize=8)
        ax.set_yticks(range(4),list(LABELS.values()));ax.invert_yaxis()
        ax.set(xlim=(0,55),xlabel='Choices violating strict dominance (%)',title=f'{action} is strictly dominant')
        ax.grid(axis='x',alpha=.15)
    axes[0].legend(fontsize=8,loc='lower right')
    fig.suptitle('Agreement with theory where the optimal action is unambiguous',x=.02,ha='left')
    fig.supxlabel('Every opponent belief implies the same action. All valid role decisions; ties excluded.\n'
                  'Four original blocks versus two own-payoff blocks; descriptive comparisons, not paired causal estimates.',fontsize=9)
    save(fig,out,'18_dominance_theory_comparison')


def raw_figure(out,ds):
    fig,axes=plt.subplots(2,2,figsize=(12,8.5),layout='constrained')
    for ax,(name,cut,strategic,direction) in zip(axes.flat,[('T',2,3,-1),('R',6,5,1),('P',-2,0,-1),('S',3,1,1)]):
        points=[r for r in ds if r['stage']=='transects' and r['axis']==name and r['valid_action']]
        for model,label in LABELS.items():
            cells=defaultdict(list)
            for r in points:
                if r['model_key']==model: cells[r['axis_value']].append(r['action']=='C')
            x=sorted(cells)
            ax.plot(x,[mean(cells[v]) for v in x],color=COLORS[model],marker='o',ms=3,label=label)
        lo=min(r['axis_value'] for r in points);hi=max(r['axis_value'] for r in points)
        low_action=1 if direction<0 else 0
        ax.plot([lo,cut],[low_action,low_action],'k--',lw=2,label='Optimal if q = ½')
        ax.plot([cut,hi],[1-low_action,1-low_action],'k--',lw=2)
        ax.axvline(cut,color='#222',ls=':',lw=1)
        ax.axvline(strategic,color='#888',ls='-.',lw=1,label='Strategic-class boundary')
        ax.set(title=f'Vary {name}: q = ½ cutoff at {cut:g}; class boundary at {strategic:g}',
               xlabel=f'Raw {name}',ylabel='C-choice frequency',ylim=(-.06,1.08))
        ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=7.5,loc='center left')
    fig.suptitle('Individual-payoff sweeps versus an explicit theoretical threshold',x=.02,ha='left')
    fig.supxlabel('Baseline (T,R,P,S)=(5,3,1,0). Black: fixed belief q=½ benchmark; either action is optimal exactly at the cutoff.\n'
                  'Observed: original matrix, two label blocks, up to four valid decisions/point. Actual beliefs may differ.',fontsize=9)
    save(fig,out,'19_raw_payoff_theoretical_thresholds')


def mixed_figure(out,gs):
    fig,axes=plt.subplots(2,2,figsize=(11,9),layout='constrained')
    for ax,(model,label) in zip(axes.flat,LABELS.items()):
        cells=defaultdict(list)
        for g in gs:
            if g['stage']=='perspective_grid' and g['model_key']==model and g['valid'] and g['symmetric_interior_mixed_C_probability'] is not None:
                cells[g['case_id']].append(g)
        for regime,name,color,marker in [('coordination','Coordination','#2777B4','o'),
                                         ('anti_coordination','Anti-coordination','#D47C3B','^')]:
            counts=Counter((round(g[0]['symmetric_interior_mixed_C_probability'],8),mean(x['cooperation_rate'] for x in g))
                           for g in cells.values() if g[0]['regime']==regime)
            ax.scatter([x for x,y in counts],[y for x,y in counts],s=[30*n for n in counts.values()],
                       color=color,marker=marker,alpha=.6,label=name,edgecolors='white',linewidths=.5)
        ax.plot([0,1],[0,1],'k--',lw=1,label='Symmetric mixed NE benchmark')
        ax.set(title=f'{label} · {len(cells)} payoff cells',xlim=(-.05,1.05),ylim=(-.05,1.05),
               xlabel='Theoretical symmetric mixed cooperation probability',ylabel='Observed C-choice frequency')
        ax.grid(alpha=.15);ax.legend(fontsize=8)
    fig.suptitle('Mixed-equilibrium behavior is a benchmark, not a unique prediction',x=.02,ha='left')
    fig.supxlabel('Own-payoff grid: up to two valid games/cell. Area reflects coincident cells. Boundary games excluded.\n'
                  'Pure equilibria also exist here. Departing from this diagonal does not establish irrationality.',fontsize=9)
    save(fig,out,'20_mixed_equilibrium_benchmark')


def regret_figure(out,gs):
    fig,axes=plt.subplots(1,2,figsize=(12,5.5),layout='constrained')
    for ax,(field,title) in zip(axes,[('maximum_unilateral_regret_normalized','Largest unilateral gain from switching'),
                                     ('welfare_gap_normalized','Shortfall from maximum joint payoff')]):
        for model,label in LABELS.items():
            vals=sorted(g[field] for g in gs if g['stage']=='perspective_grid' and g['model_key']==model and g['valid'])
            x=np.unique(vals)
            y=np.searchsorted(vals,x,side='right')/len(vals)
            ax.step(x,y,where='post',color=COLORS[model],lw=2,label=f'{label} (n={len(vals)})')
            ax.scatter([x[0]],[y[0]],color=COLORS[model],s=20)
        ax.set(title=title,xlabel='Gap / (R − P)',ylabel='Fraction of games with gap ≤ x',ylim=(0,1.03),xlim=(0,None))
        ax.grid(alpha=.15)
    axes[0].legend(fontsize=8,loc='lower right')
    fig.suptitle('Per-simulation distance from individual and collective optima',x=.02,ha='left')
    fig.supxlabel('Own-payoff grid; valid joint outcomes only. Left value at zero = pure Nash outcome rate.\n'
                  'Right value at zero = social-optimum outcome rate. Realized regret is not expected regret under mixed play.',fontsize=9)
    save(fig,out,'21_per_simulation_theoretical_gaps')


def report(out,ds,gs):
    rows=[]
    for stage,_,_ in STAGES:
        for model,label in LABELS.items():
            records=[r for r in ds if r['stage']==stage and r['model_key']==model]
            dominant=[r for r in records if r['dominant_action_chosen'] is not None]
            belief=[r for r in records if r['stated_belief_action_consistent'] is not None]
            strict=[r for r in belief if not r['stated_belief_tie']]
            games=[g for g in gs if g['stage']==stage and g['model_key']==model and g['valid']]
            rows.append({'stage':stage,'model_key':model,'model':label,
                         'dominance_n':len(dominant),'dominance_agreement':mean(r['dominant_action_chosen'] for r in dominant),
                         'belief_n':len(belief),'belief_agreement':mean(r['stated_belief_action_consistent'] for r in belief),
                         'belief_strict_n':len(strict),'belief_strict_agreement':mean(r['stated_belief_action_consistent'] for r in strict),
                         'belief_ties':len(belief)-len(strict),
                         'valid_games':len(games),'pure_nash_rate':mean(g['nash'] for g in games),
                         'social_optimum_rate':mean(g['welfare_optimal'] for g in games)})
    audit={'attempt_rows':len(ds),'simulation_rows':len(gs),'valid_actions':sum(r['valid_action'] for r in ds),
           'valid_joint_outcomes':sum(g['valid'] for g in gs),'additional_paid_calls':0,'groups':rows}
    (out/'theory_comparison_summary.json').write_text(json.dumps(audit,indent=2)+'\n')
    text='# Recorded model behavior versus theoretical thresholds\n\n'
    text+=f'Analyzed **{len(ds):,} recorded decisions and {len(gs):,} paired simulations**, including invalid records with explicit missing outcomes. **No additional API calls or spending.**\n\n'
    text+='Every decision can be traced to `job_id` in [the decision audit](theory_decisions.csv); every paired game has both job IDs in [the simulation audit](theory_simulations.csv). Figures use the stages named in their captions; pilots and other controls remain in the exports.\n\n'
    text+='## What theory predicts\n\n'
    text+='Let q be the probability the opponent chooses C. Expected-payoff advantage is\n\n'
    text+='    Δ(q) = q(R − T) + (1 − q)(S − P).\n\n'
    text+='Choose C when Δ>0, D when Δ<0; **both actions are optimal at Δ=0**. We compare each choice with its own reported q, using a tolerance of 1e−9 after dividing by R−P. This checks internal consistency, not whether the stated belief is truthful, calibrated, or a faithful explanation of how the action was produced.\n\n'
    text+='The indifference belief is `q*=(P−S)/(R−T+P−S)` when the denominator is nonzero. C is optimal above q* in coordination games and below it in anti-coordination games. A value outside [0,1] is not a feasible belief threshold. Parallel payoff lines have no unique cutoff; completely equal action utilities make every belief indifferent.\n\n'
    text+='The [SIAM article](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/) gives this interior mixed-equilibrium probability and describes pure equilibria and social optima. Our decision-level regret and threshold comparisons are derived directly from expected utility.\n\n'
    text+='## Agreement where there is a definite optimal action\n\n'
    text+=table(['Presentation','Model','Dominance agreement (n)','Stated-belief agreement (n)','Non-tie belief agreement (n)','Belief ties'],
                [[r['stage'],r['model'],f"{pct(r['dominance_agreement'])} ({r['dominance_n']})",
                  f"{pct(r['belief_agreement'])} ({r['belief_n']})",f"{pct(r['belief_strict_agreement'])} ({r['belief_strict_n']})",r['belief_ties']] for r in rows])
    text+='Original = four blocks; own-payoff = two blocks. These are descriptive averages over the same payoff grid. Sample counts differ and choices within a paired game are not treated as independent confidence-interval samples.\n\n'
    text+='![Dominant action agreement](18_dominance_theory_comparison.png)\n\n'
    text+='![Best response to stated belief](17_stated_belief_best_response.png)\n\n'
    examples=[]
    for model,label in LABELS.items():
        candidates=[r for r in ds if r['stage']=='perspective_grid' and r['model_key']==model
                    and r['stated_belief_regret_normalized'] is not None]
        r=max(candidates,key=lambda r:r['stated_belief_regret_normalized'])
        examples.append([label,f"{r['case_id']} / block {r['replicate']} / {r['role']}",
                         ', '.join(f'{r[k]:g}' for k in ('T','R','P','S')),f"{r['stated_q']:g}",
                         r['action'],r['stated_belief_best_response'],f"{r['stated_belief_regret_normalized']:.4f}"])
    text+='### Concrete decision-level examples\n\n'
    text+='These are the **largest stated-belief regret cases per model** in the own-payoff grid, selected for diagnosis rather than as representative samples. Case, block, role, and model identify the exact CSV row and raw request.\n\n'
    text+=table(['Model','Case / block / role','T, R, P, S','Stated q','Chosen','Best response','Regret / (R−P)'],examples)
    text+='## Which payoff values should cause a switch?\n\n'
    text+='Holding the opponent belief at q=½ gives these exact thresholds around the original baseline. **They differ from strategic-class boundaries:** changing the preferred action under one belief does not make that action dominant under all beliefs.\n\n'
    text+=table(['Changed payoff','q=½ indifference','C preferred when','Strategic-class boundary'],
                [['T','2','T < 2','T = R = 3'],['R','6','R > 6','R = T = 5'],
                 ['P','−2','P < −2','P = S = 0'],['S','3','S > 3','S = P = 1']])
    text+='![Raw payoff thresholds](19_raw_payoff_theoretical_thresholds.png)\n\n'
    text+='Black curves assume q=½; a model with a different belief need not follow them. The raw sweep used the original presentation, whose role sensitivity was documented in the main report. We do not infer an exact empirical threshold from sparse or nonmonotonic curves.\n\n'
    text+='The decision audit additionally computes each T/R/P/S cutoff under that decision’s stated q. C is weakly optimal for T/P below the respective cutoff or R/S above it. Missing cutoffs at q=0 or q=1 indicate that the corresponding payoff cannot affect that decision. These counterfactuals hold q and the other three payoffs fixed; models may change beliefs when payoffs change. Thresholds can lie outside the R>P chart.\n\n'
    text+='For the joint defection-cost intervention, the per-belief weak-C threshold is `max(0,−Δ(q))`; the all-belief threshold is `max(0,T−R,P−S)`. At baseline those are 1.5 for q=½ and 2 for all beliefs. These are analytic utility costs, not API dollars; no new intervention simulations were run. Strict preference requires crossing an equality threshold.\n\n'
    text+='## Equilibrium selection and per-simulation payoff gaps\n\n'
    text+='![Mixed equilibrium benchmark](20_mixed_equilibrium_benchmark.png)\n\n'
    text+='In coordination and anti-coordination regions, the symmetric interior mixed equilibrium is one possible benchmark alongside pure equilibria. The scatter does not grade deviation from that benchmark as a reasoning error. A realized joint profile can fall outside the pure Nash set even when both players correctly randomize at a mixed equilibrium. The simulation export therefore includes the theoretical probability of a pure-Nash outcome under independent symmetric mixed play. Boundary games can have equilibrium continua; we retain their pure equilibria but do not claim to enumerate all mixed equilibria there.\n\n'
    text+='![Per-simulation theoretical gaps](21_per_simulation_theoretical_gaps.png)\n\n'
    text+='For each realized game, unilateral regret is the gain from switching only one player’s action while holding the other fixed. Its maximum across the two players is zero exactly at a pure Nash outcome (up to tolerance). Welfare shortfall is `max(2R,S+T,2P) − realized joint payoff`. Both are divided by R−P for scale comparability. A Nash outcome can have a large welfare shortfall; these measure different objectives.\n\n'
    text+=table(['Model (own-payoff grid)','Valid games','Pure Nash outcomes','Social optima'],
                [[r['model'],r['valid_games'],pct(r['pure_nash_rate']),pct(r['social_optimum_rate'])] for r in rows if r['stage']=='perspective_grid'])
    text+='## S–T maps of deviation from utility benchmarks\n\n'
    text+='These maps use the clearer own-payoff grid, holding R=1 and P=0. Each model has its own panel, '
    text+='with S horizontal and T vertical. White means zero gap, darker red a larger gap, gray no usable observations; '
    text+='a dot marks fewer valid samples than scheduled. All models share a color scale within each figure. '
    text+='There are only two games or four individual decisions per cell, so these are descriptive maps, not significance tests.\n\n'
    text+='![Stated-belief deviation map](22_belief_deviation_heatmap.png)\n\n'
    text+='Figure 22 is the fraction of choices that do not maximize expected payoff under that decision’s reported opponent belief. '
    text+='A value of 0.5 means half the usable decisions chose a strictly worse action; it does not mean 50% cooperation. '
    text+='Exact indifference contributes zero violations and remains in the denominator. This measures internal consistency, '
    text+='not disagreement with a unique equilibrium strategy.\n\n'
    text+='![Expected utility loss map](23_expected_regret_heatmap.png)\n\n'
    text+='Figure 23 measures severity: the expected payoff of the best action minus that of the chosen action, '
    text+='conditional on the stated belief, divided by R−P and averaged within each cell. '
    text+='Self-reported beliefs can themselves be wrong or reflect post-hoc rationalization.\n\n'
    text+='![Realized regret map](24_realized_regret_heatmap.png)\n\n'
    text+='Figure 24 averages the larger of the two players’ realized unilateral switching gains per game, divided by R−P. '
    text+='It needs no reported belief; it describes stability of realized joint outcomes and should not be interpreted '
    text+='as expected-utility error under mixed play. [Cell values, sample counts, tie counts, and source IDs](deviation_heatmap_cells.csv).\n\n'
    text+='All figures have editable SVG copies. Reproduce with `python scripts/compare_phase_space_theory.py --output /path/to/experiment`. [Return to the main report](index.html).\n'
    (out/'THEORY_COMPARISON.md').write_text(text)
    import markdown_it
    body=markdown_it.MarkdownIt('commonmark').enable('table').render(text)
    (out/'theory_comparison.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>Theory comparison</title><style>body{font:16px system-ui;max-width:1150px;margin:45px auto;padding:0 24px;line-height:1.6;color:#182334}img{max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left}h2{margin-top:45px}pre{overflow:auto}a{color:#2563a5}</style></head><body>'+body+'</body></html>')
    return audit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output
    protected=[out/'attempts.jsonl',out/'ledger.json']
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in protected]
    records=[json.loads(line) for line in protected[0].read_text().splitlines() if line.strip()]
    assert len({r['job_id'] for r in records})==len(records),'Duplicate jobs must be resolved explicitly'
    ds,gs=build_rows(records)
    # Independently replay every existing joint score before publishing new metrics.
    prior=json.loads((out/'summary.json').read_text())
    indexed={(g['stage'],g['replicate'],g['case_id'],g['model_key']):g for g in gs}
    checked=0
    for g in prior['games']:
        c=g['case'];replayed=indexed[(c['stage'],c['replicate'],c['case_id'],g['model_key'])]
        for key,value in g['scores'].items():
            assert replayed[key]==value,(key,c['case_id'])
        checked+=1
    assert checked==len(gs)
    write_csv(out/'theory_decisions.csv',ds);write_csv(out/'theory_simulations.csv',gs)
    style();belief_figure(out,ds);dominance_figure(out,ds);raw_figure(out,ds);mixed_figure(out,gs);regret_figure(out,gs)
    deviation_maps(out,ds,gs)
    audit=report(out,ds,gs)
    audit['prior_joint_scores_replayed']=checked
    audit['protected_input_sha256']={p.name:h for p,h in zip(protected,hashes)}
    (out/'theory_comparison_summary.json').write_text(json.dumps(audit,indent=2)+'\n')
    assert hashes==[hashlib.sha256(p.read_bytes()).hexdigest() for p in protected]
    print(json.dumps({k:v for k,v in audit.items() if k!='groups'}))


if __name__=='__main__':
    main()
