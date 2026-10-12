"""Exact best-response shares for strict-PD matrices from the archived experiment.

The same original R=1, P=0 scale is kept as penalty z is subtracted from
both defection payoffs. Fractions keep threshold events exact. This is
an analytic intervention on tested baselines, not a new LLM experiment.
"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import argparse
import csv
import json
import gzip

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

REGIMES=('D_dominant','coordination','anti_coordination','C_dominant')
COLORS=('#EAA5A3','#A8CEB1','#F1CC89','#85BED8')
LABELS=('D dominant: D against either action',
        'Coordination: C against C, D against D',
        'Anti-coordination: D against C, C against D',
        'C dominant: C against either action')


def load_baselines(source):
    raw=source.read_bytes()
    summary=json.loads(gzip.decompress(raw) if source.suffix=='.gz' else raw)
    games=[g for g in summary['games'] if g['case']['stage']=='perspective_grid'
           and g['case']['payoffs']['T']>g['case']['payoffs']['R']>g['case']['payoffs']['P']>g['case']['payoffs']['S']]
    grid=sorted({tuple(Fraction(str(g['case']['payoffs'][k])) for k in ('T','R','P','S')) for g in games})
    if not grid:raise ValueError('No strict-PD baselines in own-payoff experiment')
    if not all(R==1 and P==0 for T,R,P,S in grid):raise ValueError('Expected original R=1, P=0 normalization')
    metadata={'baseline_count':len(grid),'source_stage':'perspective_grid',
              'source_paired_games':len(games),'source_valid_paired_games':sum(g['scores']['valid'] for g in games),
              'source_games_by_model':dict(Counter(g['model_key'] for g in games))}
    return grid,metadata


def regime(payoffs,z):
    T,R,P,S=payoffs
    against_c=R-T+z
    against_d=S-P+z
    if against_c==0 and against_d==0:return 'fully_indifferent'
    if against_c==0 or against_d==0:return 'weak_dominance'
    if against_c<0 and against_d<0:return 'D_dominant'
    if against_c>0 and against_d<0:return 'coordination'
    if against_c<0 and against_d>0:return 'anti_coordination'
    return 'C_dominant'


def composition(grid):
    total=len(grid)
    thresholds=sorted({T-R for T,R,P,S in grid}|{P-S for T,R,P,S in grid})
    edges=[Fraction(0),*thresholds,thresholds[-1]+Fraction(1,4)]
    intervals=[]
    for left,right in zip(edges,edges[1:]):
        counts=Counter(regime(payoffs,(left+right)/2) for payoffs in grid)
        assert sum(counts[k] for k in REGIMES)==total
        intervals.append({'left_exact':str(left),'right_exact':str(right),
                          'left':float(left),'right':float(right),'n_baselines':total,
                          **{k+'_count':counts[k] for k in REGIMES},
                          **{k+'_share':counts[k]/total for k in REGIMES}})
    events=[]
    for z in thresholds:
        counts=Counter(regime(payoffs,z) for payoffs in grid)
        keys=(*REGIMES,'weak_dominance','fully_indifferent')
        assert sum(counts[k] for k in keys)==total
        events.append({'z_exact':str(z),'z':float(z),'n_baselines':total,
                       **{k+'_count':counts[k] for k in keys},
                       **{k+'_share':counts[k]/total for k in keys}})
    return grid,intervals,events


def save_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def render(grid,intervals,events,out,metadata):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'svg.fonttype':'none',
                         'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(12,8))
    fig.subplots_adjust(left=.09,right=.98,top=.79,bottom=.29)
    for row in intervals:
        bottom=0
        for key,color in zip(REGIMES,COLORS):
            height=row[key+'_share']
            ax.bar(row['left'],height,width=row['right']-row['left'],bottom=bottom,
                   align='edge',color=color,linewidth=0)
            bottom+=height
    for key,y,marker in [('weak_dominance',-.047,'|'),('fully_indifferent',-.115,'D')]:
        selected=[e for e in events if e[key+'_count']]
        ax.scatter([e['z'] for e in selected],[y]*len(selected),
                   s=[240*e[key+'_share'] for e in selected],marker=marker,
                   color='#756785',linewidths=1,zorder=5)
    ax.axhline(0,color='#555555',lw=.6)
    ax.set_xlim(0,intervals[-1]['right']);ax.set_ylim(-.16,1.01)
    ax.set_xticks([0,.25,.5,.75,1,1.25]);ax.set_yticks([i/5 for i in range(6)])
    ax.set_xlabel('Defection penalty z  (in the original R − P payoff units)',labelpad=9)
    ax.set_ylabel('Share of sampled baselines')
    ax.grid(axis='x',alpha=.12)
    fig.suptitle('Prisoner’s Dilemma: how best responses change with incentives',
                 x=.09,y=.97,ha='left',fontsize=19)
    fig.text(.09,.914,f'{len(grid)} tested PD payoff matrices · {metadata["source_valid_paired_games"]} valid source games across four models',fontsize=12)
    fig.text(.09,.868,'Starting payoffs: R = 1, P = 0; S ∈ {−1, −0.75, −0.5, −0.25}, T ∈ {1.25, 1.5, 1.75, 2}',fontsize=12)
    fig.text(.09,.828,'Analytic intervention: T′ = T − z and P′ = −z; R and S stay fixed',fontsize=12)
    handles=[Patch(facecolor=c,label=l) for c,l in zip(COLORS,LABELS)]
    handles += [Line2D([],[],color='#756785',marker='|',ls='',markersize=9,label='One best-response comparison tied'),
                Line2D([],[],color='#756785',marker='D',ls='',markersize=5,label='Both comparisons tied')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.54,.105),ncol=2,
               frameon=False,fontsize=10.5,columnspacing=2)
    fig.text(.09,.033,'Filled steps describe open intervals between exact thresholds z = P − S and z = T − R.\n'
                       'Markers below zero show exact tie events; marker area scales with affected share. Endpoint ties are excluded from fills.\n'
                       'Equal weight per tested payoff matrix. Intervention paths are theoretical; no LLM penalty-sweep responses were collected.',fontsize=9.5)
    for suffix in ('png','svg','pdf'):
        fig.savefig(out/f'pd_best_response_composition.{suffix}',dpi=200,facecolor='white')
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-summary',type=Path,default=Path(__file__).resolve().parents[1]/'data/summary.json.gz')
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    grid,metadata=load_baselines(args.source_summary)
    grid,intervals,events=composition(grid)
    render(grid,intervals,events,out,metadata)
    save_csv(out/'pd_regime_interval_shares.csv',intervals)
    save_csv(out/'pd_regime_exact_events.csv',events)
    save_csv(out/'pd_sampled_baselines.csv',[
        {**{k:float(v) for k,v in zip(('T','R','P','S'),payoffs)},
         'threshold_against_C_exact':str(payoffs[0]-payoffs[1]),
         'threshold_against_D_exact':str(payoffs[2]-payoffs[3])} for payoffs in grid])
    summary={**metadata,'open_intervals':len(intervals),'exact_event_locations':len(events),
             'simultaneous_crossing_baselines':sum(T-R==P-S for T,R,P,S in grid),
             'additional_paid_calls':0}
    (out/'pd_regime_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'pd_figure_caption.md').write_text(
        '# Prisoner’s Dilemma: best-response composition\n\n'
        f'The figure equally weights the {len(grid)} distinct strict-PD payoff matrices actually tested '
        f'in the own-payoff grid ({metadata["source_valid_paired_games"]} valid paired games across four models). '
        'The original normalization R=1, P=0 is retained. S ranges from −1 to −0.25 and T from 1.25 to 2, '
        'both in steps of 0.25. A hypothetical penalty z is subtracted from both defection payoffs. '
        'The C-minus-D margins against C and D are R−T+z and S−P+z. Their signs classify D dominance, '
        'coordination, anti-coordination, and C dominance. Filled shares are constant on exact open '
        'intervals between rational thresholds. Separate markers show one tied comparison and full '
        'indifference; event categories are mutually exclusive. Every baseline is equally weighted.\n\n'
        'The starting payoff matrices come from our experiment, but these intervention paths are '
        'calculated analytically. They are not new model responses or empirical response frequencies. '
        'No LLM penalty sweep was performed and no additional model calls were used.\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
