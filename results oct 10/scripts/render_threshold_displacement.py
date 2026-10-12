"""Compare sampled majority-choice crossings with reported-belief best responses.

No continuous response curve, fixed opponent belief, or unique equilibrium is
assumed. Crossings are brackets between strict-majority samples. Their differences
are descriptive grid-resolution intervals, not statistical confidence intervals.
"""
from pathlib import Path
from collections import defaultdict, Counter
import argparse
import csv
import gzip
import json
import math
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

LABELS={'glm':'GLM-5.3','qwen':'Qwen3.8 2.4T A95B','astra':'GPT-6 Astra','fable':'Claude Fable 5.1'}
AXIS=tuple(-1+i/4 for i in range(13))
TOL=1e-9


def cell_values(records):
    grouped=defaultdict(list)
    for r in records:
        if r['case']['stage']!='perspective_grid':continue
        d=r['decision'];q=d.get('belief_opponent_C')
        if not d.get('valid') or d.get('action') not in ('C','D') or type(q) not in (float,int) or not math.isfinite(q) or not 0<=q<=1:continue
        p=r['case']['payoffs'];scale=p['R']-p['P']
        if not (p['R']==1 and p['P']==0):raise ValueError('Threshold grid requires R=1, P=0')
        uc=q*p['R']+(1-q)*p['S'];ud=q*p['T']+(1-q)*p['P']
        grouped[r['model_key'],p['s'],p['t']].append((r['job_id'],d['action'],(uc-ud)/scale))
    cells=[]
    for model in LABELS:
        for t in AXIS:
            for s in AXIS:
                rows=grouped[model,s,t];n=len(rows)
                observed=sum(a=='C' for _,a,_ in rows)
                strict_c=sum(m>TOL for _,_,m in rows);strict_d=sum(m< -TOL for _,_,m in rows)
                # Ties permit either action. Never impose an arbitrary choice on them.
                obs_sign=(observed>n/2)-(observed<n/2) if n else None
                theory_sign=(1 if strict_c>n/2 else -1 if strict_d>n/2 else 0) if n else None
                cells.append({'model_key':model,'s':s,'t':t,'n':n,'observed_C':observed,
                              'strict_theory_C':strict_c,'strict_theory_D':strict_d,'indifferent':n-strict_c-strict_d,
                              'observed_C_rate':observed/n if n else None,
                              'theory_C_rate_min':strict_c/n if n else None,
                              'theory_C_rate_max':(n-strict_d)/n if n else None,
                              'observed_majority':obs_sign,'theory_majority':theory_sign,
                              'job_ids':[jid for jid,_,_ in rows]})
    return cells


def crossing_bracket(points, increasing):
    """Find a single sampled crossing; retain censoring and reversals explicitly.

    Signs are +1 C majority, -1 D majority, 0 tied/undetermined. Expected direction
    is increasing C for S sweeps, decreasing C for T sweeps. No interpolation.
    One-sided bounds are conditional on extending that single-crossing pattern.
    """
    if any(sign is None for _,sign in points):
        return {'status':'missing','low':None,'high':None,'changes':[]}
    direction=1 if increasing else -1
    decisive=[(x,sign*direction) for x,sign in sorted(points) if sign]
    changes=[(a,b) for a,b in zip(decisive,decisive[1:]) if a[1]!=b[1]]
    if len(changes)==1 and changes[0][0][1]==-1:
        return {'status':'bracketed','low':changes[0][0][0],'high':changes[0][1][0],'changes':changes}
    if changes:
        return {'status':'multiple_or_reversed','low':None,'high':None,'changes':changes}
    if not decisive:return {'status':'ambiguous','low':None,'high':None,'changes':[]}
    if decisive[0][1]==-1:
        return {'status':'lower_bound_only','low':decisive[-1][0],'high':math.inf,'changes':[]}
    return {'status':'upper_bound_only','low':-math.inf,'high':decisive[0][0],'changes':[]}


def displacement(observed, theory):
    if any(b['status']=='multiple_or_reversed' for b in (observed,theory)):
        return {'status':'multiple_or_reversed','low':None,'high':None}
    if any(b['low'] is None for b in (observed,theory)):
        return {'status':'unresolved','low':None,'high':None}
    lo=observed['low']-theory['high'];hi=observed['high']-theory['low']
    if not math.isfinite(lo) and not math.isfinite(hi):return {'status':'unresolved','low':None,'high':None}
    return {'status':'bracketed' if math.isfinite(lo) and math.isfinite(hi) else 'one_sided','low':lo,'high':hi}


def build_rows(cells):
    indexed={(c['model_key'],c['s'],c['t']):c for c in cells}
    rows=[]
    for model in LABELS:
        for vary in ('T','S'):
            for fixed in AXIS:
                selected=[indexed[model,fixed,x] if vary=='T' else indexed[model,x,fixed] for x in AXIS]
                obs=crossing_bracket([(x,c['observed_majority']) for x,c in zip(AXIS,selected)],vary=='S')
                theory=crossing_bracket([(x,c['theory_majority']) for x,c in zip(AXIS,selected)],vary=='S')
                delta=displacement(obs,theory)
                rows.append({'model_key':model,'varied_payoff':vary,'fixed_payoff':'S' if vary=='T' else 'T',
                             'fixed_value':fixed,'observed_status':obs['status'],'observed_low':obs['low'],'observed_high':obs['high'],
                             'theory_status':theory['status'],'theory_low':theory['low'],'theory_high':theory['high'],
                             'displacement_status':delta['status'],'displacement_low':delta['low'],'displacement_high':delta['high'],
                             'observed_changes':obs['changes'],'theory_changes':theory['changes'],
                             'minimum_cell_n':min(c['n'] for c in selected)})
    return rows


def export_csv(path,rows):
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def render(rows,output):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
                         'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
    fig,axes=plt.subplots(4,2,figsize=(12,12),sharex=True,sharey=True)
    fig.subplots_adjust(left=.09,right=.98,top=.86,bottom=.15,hspace=.45,wspace=.18)
    finite=[abs(r[k]) for r in rows for k in ('displacement_low','displacement_high') if r[k] is not None and math.isfinite(r[k])]
    ymax=max(1.25,math.ceil(max(finite)*4)/4+.25)
    neutral='#687888';resolved='#C44E24'
    for model,pair in zip(LABELS,axes):
        for vary,ax in zip(('T','S'),pair):
            selected=[r for r in rows if r['model_key']==model and r['varied_payoff']==vary]
            ax.axhline(0,color='#202733',ls='--',lw=1)
            for r in selected:
                x=r['fixed_value'];status=r['displacement_status'];lo=r['displacement_low'];hi=r['displacement_high']
                if status=='bracketed':
                    color=resolved if lo>1e-9 or hi< -1e-9 else neutral
                    ax.vlines(x,lo,hi,color=color,lw=2.3)
                    ax.hlines([lo,hi],x-.035,x+.035,color=color,lw=1.8)
                elif status=='one_sided':
                    lower=math.isfinite(lo);bound=lo if lower else hi
                    color=resolved if (lower and lo>1e-9) or (not lower and hi< -1e-9) else neutral
                    tip=bound+(.24 if lower else -.24)
                    ax.hlines(bound,x-.035,x+.035,color=color,lw=1.8)
                    ax.annotate('',xy=(x,tip),xytext=(x,bound),arrowprops={'arrowstyle':'->','color':color,'lw':1.7})
                else:
                    ax.text(x,1.015,'×' if status=='multiple_or_reversed' else '○',transform=ax.get_xaxis_transform(),
                            color='#8A9099',ha='center',va='bottom',fontsize=12)
            n=sum(r['displacement_status']=='bracketed' for r in selected)
            ax.set_title(f'{LABELS[model]}  ·  {n}/13 slices bracketed on both curves',loc='left',fontsize=10.5,pad=22)
            ax.set_xlim(-1.13,2.13);ax.set_ylim(-ymax,ymax);ax.set_xticks(AXIS[::2]);ax.grid(axis='y',alpha=.15)
            ax.set_ylabel(f'Observed − theoretical {vary} threshold',fontsize=9)
    axes[-1,0].set_xlabel('Held-fixed normalized S')
    axes[-1,1].set_xlabel('Held-fixed normalized T')
    fig.suptitle('How far are observed switching thresholds from theory?',x=.09,ha='left',y=.99,fontsize=20)
    fig.text(.09,.948,'Theory uses each decision’s reported opponent belief at that S–T point.  R = 1, P = 0.',fontsize=11)
    fig.text(.09,.902,'Vary T: compare where C-majority gives way to D-majority',fontsize=10.5,weight='bold')
    fig.text(.56,.902,'Vary S: compare where D-majority gives way to C-majority',fontsize=10.5,weight='bold')
    fig.legend(handles=[Line2D([0],[0],color=neutral,lw=2,label='Grid ranges overlap zero'),
                        Line2D([0],[0],color=resolved,lw=2,label='Grid range excludes zero')],
               loc='lower center',bbox_to_anchor=(.5,.075),ncol=2,frameon=False,fontsize=10)
    fig.text(.09,.032,'Bars: differences between sampled crossing brackets, NOT confidence intervals. Arrows: conditional one-sided bounds.\n'
                      'Symbols above panels: × multiple/reversed crossings; ○ no comparable bracket. No binary search or fitted thresholds.\n'
                      'Matched valid choices and beliefs; at most four decisions/cell. Exact utility ties permit either action.',fontsize=9.3)
    for suffix in ('png','svg'):fig.savefig(output/f'25_observed_threshold_displacement.{suffix}',dpi=190)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--output',type=Path)
    args=p.parse_args();out=args.output or args.analysis;out.mkdir(parents=True,exist_ok=True)
    raw=args.analysis/'attempts.jsonl'
    data=raw.read_bytes() if raw.exists() else gzip.decompress((args.analysis/'attempts.jsonl.gz').read_bytes())
    records=[json.loads(x) for x in data.splitlines() if x.strip()]
    cells=cell_values(records);rows=build_rows(cells)
    export_csv(out/'threshold_cells.csv',cells);export_csv(out/'threshold_displacements.csv',rows)
    render(rows,out)
    summary={'benchmark':'Per-decision reported-belief best response; indifference permits either action',
             'valid_matched_decisions':sum(c['n'] for c in cells),'sweep_slices':len(rows),
             'displacement_status_counts':dict(Counter(r['displacement_status'] for r in rows)),
             'additional_paid_calls':0}
    (out/'threshold_displacement_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
