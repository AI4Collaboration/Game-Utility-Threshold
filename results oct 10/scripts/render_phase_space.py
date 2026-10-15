"""Render theoretical phase maps and measured LLM results (PNG + SVG + CSV)."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
from matplotlib.patches import Patch
import numpy as np

from utility_threshold.games.phase_space import SymmetricPayoffs, one_parameter_sweeps, phase_grid, axis_values

LABELS={'glm':'GLM-5.3','qwen':'Qwen3.8 2.4T A95B','astra':'GPT-6 Astra','fable':'Claude Fable 5.1'}
COLORS={'glm':'#25856A','qwen':'#8760A8','astra':'#2777B4','fable':'#D47C3B'}
REGIMES=['C_dominant','D_dominant','coordination','anti_coordination']
REGIME_COLORS=['#D8EFE3','#F5D9D8','#DCE7F5','#F9EBCB']


def style():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,
        'axes.titlesize':13,'axes.labelsize':11,'figure.titlesize':19,
        'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white',
        'figure.facecolor':'white','svg.fonttype':'none'})


def save(fig,out,name):
    fig.savefig(out/f'{name}.png',dpi=180,bbox_inches='tight')
    fig.savefig(out/f'{name}.svg',bbox_inches='tight')
    plt.close(fig)


def boundaries(ax,all_lines=False):
    ax.axvline(0,color='#B5484C',lw=1.2)
    ax.axhline(1,color='#B5484C',lw=1.2)
    if all_lines:
        ax.axvline(1,color='#49505A',lw=.8,ls=':')
        ax.axhline(0,color='#49505A',lw=.8,ls=':')
        x=np.linspace(-1,2,200)
        ax.plot(x,x,color='#49505A',lw=.8,ls=':')
        ax.plot(x,2-x,color='#335B8E',lw=1.3,ls='--')
        ax.plot(x,-x,color='#335B8E',lw=.8,ls='--',alpha=.5)
    ax.set(xlim=(-1,2),ylim=(-1,2),xlabel='Normalized S:  s = (S − P) / (R − P)',
           ylabel='Normalized T:  t = (T − P) / (R − P)')


def cooperation_heatmap(games, out):
    """Annotate every measured cell without interpolating untested payoffs."""
    values = np.array(axis_values())
    cell_edges = np.r_[values - .125, values[-1] + .125]
    # Red–yellow–green as in the reference, with lighter endpoints so neither
    # extreme becomes burgundy or forest green. Keep the numeric scale at [0,1].
    cmap = LinearSegmentedColormap.from_list('defect_to_cooperate',
                       plt.get_cmap('RdYlGn')(np.linspace(.15, .85, 256)))
    cmap.set_bad('#E5E7EB')
    def panel(ax, model, label, single=False):
        cells = defaultdict(list)
        for g in games:
            if g['model_key'] == model:
                p = g['case']['payoffs']
                cells[p['s'], p['t']].append(g['scores']['cooperation_rate'])
        z = np.array([[np.mean(cells[s,t]) if cells[s,t] else np.nan
                       for s in values] for t in values])
        im = ax.pcolormesh(cell_edges, cell_edges, z, cmap=cmap, vmin=0, vmax=1,
                          edgecolors='#FFFFFF50', linewidth=.4, rasterized=True)
        for j, t in enumerate(values):
            for i, s in enumerate(values):
                v = z[j,i]
                if np.isnan(v):
                    text, color = 'N/A', '#28323C'
                else:
                    text = f'{v:.2f}'
                    color = '#111111'
                ax.text(s, t, text, ha='center', va='center', color=color,
                        fontsize=14, zorder=5)
        ax.set_xticks(values, [f'{v:g}' for v in values], rotation=45, ha='right')
        ax.set_yticks(values, [f'{v:g}' for v in values])
        ax.tick_params(labelsize=14 if single else 16, width=.8, length=4)
        ax.set(xlim=(cell_edges[0],cell_edges[-1]), ylim=(cell_edges[0],cell_edges[-1]),
               xlabel=r'Normalized $S$: $(S-P)/(R-P)$',
               ylabel=r'Normalized $T$: $(T-P)/(R-P)$',
               aspect='equal')
        ax.xaxis.label.set_size(20)
        ax.yaxis.label.set_size(20)
        ax.set_title(label, fontsize=25, pad=16)
        return im

    def legend(fig, im, rect, small=False):
        cax = fig.add_axes(rect)
        cb = fig.colorbar(im, cax=cax, ticks=[0,.25,.5,.75,1])
        cb.ax.set_yticklabels(['0.00 (defect)', '0.25', '0.50', '0.75', '1.00 (cooperate)'])
        cb.ax.tick_params(labelsize=14 if small else 17)
        cb.set_label('Cooperation proportion', labelpad=18, fontsize=18 if small else 21)
        cb.outline.set_linewidth(.7)

    def export(fig, name):
        for extension in ('png','svg','pdf'):
            fig.savefig(out/f'{name}.{extension}', dpi=300, bbox_inches='tight', pad_inches=.18)
        plt.close(fig)

    # Local typography leaves the styling of the other publication figures intact.
    with plt.rc_context({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                         'font.size':16, 'axes.linewidth':.8, 'pdf.fonttype':42}):
        fig, axes = plt.subplots(2, 2, figsize=(24, 23))
        fig.subplots_adjust(left=.065, right=.855, bottom=.065, top=.92,
                            wspace=.18, hspace=.22)
        for ax, (model, label) in zip(axes.flat, LABELS.items()):
            im = panel(ax, model, label)
        legend(fig, im, [.89,.29,.016,.43])
        title='How LLM Cooperation Changes Across Strategic Incentives'
        fig.suptitle(title, x=.48, y=.985, fontsize=34)
        export(fig, '14_own_payoff_cooperation')
        for model, label in LABELS.items():
            fig, ax = plt.subplots(figsize=(14, 12))
            fig.subplots_adjust(left=.10, right=.76, bottom=.10, top=.87)
            im = panel(ax, model, label, single=True)
            legend(fig, im, [.81,.24,.024,.52], small=True)
            fig.suptitle(title, x=.49, y=.975, fontsize=23)
            export(fig, f'14_own_payoff_cooperation_{model}')


def analytic_figures(out):
    axis=np.linspace(-1,2,181)
    s,t=np.meshgrid(axis,axis)
    regions=np.where((t<1)&(s>0),0,np.where((t>1)&(s<0),1,np.where((t<1)&(s<0),2,3)))
    fig,ax=plt.subplots(figsize=(10,9))
    ax.pcolormesh(s,t,regions,cmap=ListedColormap(REGIME_COLORS),vmin=-.5,vmax=3.5,shading='nearest')
    boundaries(ax,True)
    # Derive all 12 ordinal labels from strict interior points.
    labels=defaultdict(list)
    for si in np.linspace(-.95,1.95,60):
        for ti in np.linspace(-.95,1.95,60):
            p=SymmetricPayoffs(T=ti,R=1,P=0,S=si)
            order=p.report()['payoff_order']
            if '=' not in order:
                labels[order].append((si,ti))
    for order,coords in labels.items():
        x,y=np.mean(coords,axis=0)
        display={"T>R>P>S":"Prisoner's Dilemma\nT>R>P>S", "R>T>P>S":"Stag Hunt\nR>T>P>S",
                 "T>R>S>P":"Chicken\nT>R>S>P"}.get(order,order)
        ax.text(x,y,display,ha='center',va='center',fontsize=10,fontweight='normal',
                bbox={'boxstyle':'round,pad=.25','fc':'white','ec':'none','alpha':.75})
    ax.scatter([-.5],[2],s=130,marker='*',color='#141D2B',zorder=5,clip_on=False)
    ax.annotate('Repository baseline\n(T,R,P,S) = (5,3,1,0)',xy=(-.5,2),xytext=(-.92,1.73),
                fontsize=9,arrowprops={'arrowstyle':'-','color':'#141D2B'})
    ax.set_title('Symmetric games form a two-dimensional phase space',loc='left',pad=22,fontsize=18)
    ax.legend(handles=[Patch(color=c,label=l) for c,l in zip(REGIME_COLORS,
              ['C dominant','D dominant','Coordination','Anti-coordination'])],
              loc='upper center',bbox_to_anchor=(.5,-.13),ncol=2,frameon=False)
    fig.text(.125,.005,'R = 1, P = 0. Red: Nash boundaries. Dotted: payoff-order boundaries.\n'
             'Blue dashed: group-payoff boundaries S + T = 0 and 2. Star: normalized baseline.\n'
             'Analytic reconstruction using the repository engine; no model calls.',fontsize=9,color='#515967')
    save(fig,out,'01_analytic_phase_space')

    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    fields=[(1-t+s)/2,np.maximum(np.maximum(t-1,-s),0),np.where(s+t>2,s+t,2)]
    titles=['Cooperation advantage at belief q = ½','Cost to make C weakly dominant','Maximum total normalized payoff']
    for ax,z,title in zip(axes,fields,titles):
        im=ax.pcolormesh(s,t,z,shading='nearest',cmap='RdBu' if ax is axes[0] else 'viridis')
        boundaries(ax)
        ax.set_title(title,fontsize=12)
        ax.set_xlabel('Normalized S');ax.set_ylabel('Normalized T')
        fig.colorbar(im,ax=ax,shrink=.75)
    fig.suptitle('Analytic incentives, intervention thresholds, and welfare',x=.03,ha='left')
    save(fig,out,'02_analytic_incentives')

    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    baseline=SymmetricPayoffs()
    for ax,(name,points) in zip(axes.flat,one_parameter_sweeps().items()):
        x=[getattr(p,name) for p in points]
        ax.plot(x,[p.R-p.T for p in points],label='Against C',color='#2777B4',lw=2)
        ax.plot(x,[p.S-p.P for p in points],label='Against D',color='#D47C3B',lw=2)
        ax.plot(x,[p.margin(.5) for p in points],label='At belief q = ½',color='#25856A',ls='--',lw=2)
        ax.axhline(0,color='#666',lw=.8)
        ax.axvline(getattr(baseline,name),color='#666',ls=':',label='Original value')
        ax.set(title=f'Vary {name}; hold the other three payoffs fixed',xlabel=f'Raw {name} payoff',
               ylabel='U(C) − U(D)')
        ax.grid(alpha=.15)
    axes[0,0].legend(fontsize=8,ncol=2)
    fig.suptitle('One-parameter sweeps around (T,R,P,S) = (5,3,1,0)',x=.03,ha='left')
    save(fig,out,'03_one_parameter_incentives')

    fig,axes=plt.subplots(1,3,figsize=(15,5),layout='constrained')
    # Bit masks: 1=CC, 2=CD/DC, 3=both. Pure-profile Pareto conditions
    # are computed independently here, with the engine tested separately.
    cc_pareto=~((s>=1)&(t>=1)&((s>1)|(t>1)))
    asymmetric_pareto=~((s<=1)&(t<=1)&((s<1)|(t<1)))
    pareto=cc_pareto.astype(int)+2*asymmetric_pareto.astype(int)
    wc=np.minimum(1,s);wd=np.minimum(t,0)
    maximin=np.where(np.isclose(wc,wd),2,np.where(wc>wd,0,1))
    social=np.where(s+t>2,2,np.where(s+t<0,0,1))
    configs=[(pareto,ListedColormap(['#D8EFE3','#F9EBCB','#DCE7F5']),1,3,
              'Pareto-efficient pure profiles',[1,2,3],['CC','CD / DC','Both']),
             (maximin,ListedColormap(['#D8EFE3','#F5D9D8','#DCE7F5']),0,2,
              'Pure-action maximin choice',[0,1,2],['C','D','Tie']),
             (social,ListedColormap(['#F0F4FA','#BFD3EB','#709FCE']),0,2,
              'Group-payoff ordering',[0,1,2],['CC > DD > CD','CC > CD > DD','CD > CC > DD'])]
    for ax,(z,cm,lo,hi,title,ticks,labels) in zip(axes,configs):
        im=ax.pcolormesh(s,t,z,cmap=cm,vmin=lo-.5,vmax=hi+.5,shading='nearest')
        boundaries(ax);ax.set(xlabel='Normalized S',ylabel='Normalized T',title=title)
        cb=fig.colorbar(im,ax=ax,shrink=.7,ticks=ticks);cb.ax.set_yticklabels(labels,fontsize=8)
    fig.suptitle('Additional strategic properties across the same payoff space',x=.03,ha='left')
    fig.supxlabel('CD represents either asymmetric profile. Social-order bands omit equality lines.',fontsize=9)
    save(fig,out,'11_pareto_maximin_social_order')

    fig,ax=plt.subplots(figsize=(10,7),layout='constrained')
    for (name,points),color in zip(one_parameter_sweeps().items(),['#2777B4','#D47C3B','#25856A','#8760A8']):
        xs=[p.s for p in points];ys=[p.t for p in points]
        ax.plot(xs,ys,lw=2.5,label=f'Increase raw {name}',color=color)
        mid=len(points)//2
        ax.annotate('',xy=(xs[mid+5],ys[mid+5]),xytext=(xs[mid-5],ys[mid-5]),
                    arrowprops={'arrowstyle':'->','color':color,'lw':2.5})
        ax.text(xs[-1],ys[-1],f'  {name}={getattr(points[-1],name):g}',color=color,fontsize=10)
    ax.axvline(0,color='#B5484C',lw=1,ls='--');ax.axhline(1,color='#B5484C',lw=1,ls='--')
    ax.scatter([-.5],[2],marker='*',s=180,color='#141D2B',zorder=5)
    ax.annotate('Original game',xy=(-.5,2),xytext=(.4,3.2),arrowprops={'arrowstyle':'-','color':'#141D2B'})
    ax.set(xlabel='Normalized S',ylabel='Normalized T',xlim=(-5.3,2),ylim=(-1.3,8.5),
           title='Changing one raw payoff traces a path through phase space')
    ax.grid(alpha=.15);ax.legend(loc='upper right',frameon=False)
    save(fig,out,'12_raw_payoff_paths')

    fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    costs=np.linspace(0,4,161)
    axes[0].plot(costs,costs-2,label='Against C: k − 2',color='#2777B4',lw=2)
    axes[0].plot(costs,costs-1,label='Against D: k − 1',color='#D47C3B',lw=2)
    axes[0].axhline(0,color='#333',lw=.8);axes[0].axvline(2,color='#25856A',ls='--')
    axes[0].axvspan(2,4,color='#D8EFE3',alpha=.5)
    axes[0].set(xlabel='Defection cost k',ylabel='U(C) − U(D)',title='A shared defection cost changes both incentives')
    axes[0].legend(frameon=False);axes[0].grid(alpha=.15)
    axes[1].plot((costs-1)/(costs+2),4/(costs+2),color='#25856A',lw=2.5)
    for k in [0,1,2,3,4]:
        x,y=(k-1)/(k+2),4/(k+2)
        axes[1].scatter(x,y,color='#25856A');axes[1].annotate(f'  k={k}',(x,y),fontsize=10)
    axes[1].axvline(0,color='#B5484C',lw=1);axes[1].axhline(1,color='#B5484C',lw=1)
    axes[1].set(xlabel='Normalized S',ylabel='Normalized T',title='Path: D dominant → anti-coordination → C dominant')
    axes[1].grid(alpha=.15)
    fig.suptitle('Repository intervention: T = 5 − k, P = 1 − k, R = 3, S = 0',x=.03,ha='left')
    fig.supxlabel('Analytic result only: k = 2 gives weak C dominance; k > 2 gives strict C dominance.',fontsize=10)
    save(fig,out,'16_joint_incentive_intervention')

    points=phase_grid(axis_values(-1,2,.05))
    with (out/'analytic_grid.csv').open('w',newline='') as f:
        reports=[p.report() for p in points]
        writer=csv.DictWriter(f,fieldnames=list(reports[0]))
        writer.writeheader();writer.writerows(reports)


def measured_figures(out,summary):
    all_games=summary['games']
    grid=[g for g in all_games if g['case']['stage']=='grid']
    valid=[g for g in grid if g['scores']['valid']]
    if not grid:
        return
    reps=sorted({g['case']['replicate'] for g in grid})
    edges=np.arange(-1.125,2.126,.25)
    measures=[('cooperation_rate','Observed cooperation / C-choice rate','viridis',0,1),
              ('nash','Observed pure Nash outcome rate','viridis',0,1),
              ('regret','Mean unilateral deviation regret','magma',0,None),
              ('welfare_optimal','Observed social-optimum outcome rate','viridis',0,1)]
    for index,(metric,title,cmap,vmin,vmax) in enumerate(measures,start=4):
        fig,axes=plt.subplots(2,2,figsize=(11,10),layout='constrained')
        matrices={}
        for model in LABELS:
            cells=defaultdict(list)
            for g in valid:
                if g['model_key']!=model:
                    continue
                p=g['case']['payoffs'];sc=g['scores']
                value=(sc['row_regret']+sc['column_regret'])/2 if metric=='regret' else sc[metric]
                cells[(round(p['s'],5),round(p['t'],5))].append(value)
            matrices[model]=np.array([[np.mean(cells[(s,t)]) if cells[(s,t)] else np.nan
                                     for s in axis_values()] for t in axis_values()])
        if vmax is None:
            vmax=max(float(np.nanmax(z)) for z in matrices.values()) or 1
        for ax,(model,label) in zip(axes.flat,LABELS.items()):
            cm=plt.get_cmap(cmap).copy();cm.set_bad('#E5E7EB')
            im=ax.pcolormesh(edges,edges,matrices[model],cmap=cm,vmin=vmin,vmax=vmax)
            boundaries(ax)
            ax.set_xlabel('Normalized S');ax.set_ylabel('Normalized T')
            n=sum(g['model_key']==model for g in valid)
            ax.set_title(f'{label}  ·  {n} valid games',loc='left')
        fig.colorbar(im,ax=list(axes.flat),shrink=.7,label='Normalized payoff units' if metric=='regret' else 'Fraction')
        fig.suptitle(title+'\n',x=.02,ha='left')
        fig.supxlabel(f'13 × 13 grid · {len(reps)} replicate block(s) · isolated simultaneous self-play\n'
                      'Red lines: analytic Nash boundaries. Gray: missing/invalid. Descriptive cell averages.',fontsize=10)
        save(fig,out,f'{index:02}_model_{metric}')

    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,(vary,fixed,value) in zip(axes,[('t','s',-.5),('s','t',2.)]):
        for model,label in LABELS.items():
            cells=defaultdict(list)
            for g in valid:
                p=g['case']['payoffs']
                if g['model_key']==model and abs(p[fixed]-value)<1e-8:
                    cells[p[vary]].append(g['scores']['cooperation_rate'])
            x=sorted(cells)
            ax.plot(x,[np.mean(cells[v]) for v in x],marker='o',ms=4,label=label,color=COLORS[model])
        ax.axvline(1 if vary=='t' else 0,color='#B5484C',ls='--',lw=1)
        ax.set(xlabel=f'Normalized {vary.upper()}',ylabel='Observed C-choice rate',ylim=(-.05,1.05),
               title=f'Baseline transect: {fixed} = {value:g}')
        ax.grid(alpha=.15)
    axes[0].legend(fontsize=8)
    fig.suptitle('How model choices change along one direction',x=.03,ha='left')
    save(fig,out,'08_model_grid_transects')

    raw=[g for g in all_games if g['case']['stage']=='transects' and g['scores']['valid']]
    if raw:
        fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
        for ax,name in zip(axes.flat,['T','R','P','S']):
            for model,label in LABELS.items():
                cells=defaultdict(list)
                for g in raw:
                    if g['case']['axis']==name and g['model_key']==model:
                        cells[g['case']['axis_value']].append(g['scores']['cooperation_rate'])
                x=sorted(cells)
                ax.plot(x,[np.mean(cells[v]) for v in x],marker='o',ms=3,label=label,color=COLORS[model])
            ax.axvline(getattr(SymmetricPayoffs(),name),color='#666',ls=':')
            ax.set(title=f'Vary {name}; other raw payoffs fixed',xlabel=f'Raw {name}',
                   ylabel='Observed C-choice rate',ylim=(-.05,1.05))
            ax.grid(alpha=.15)
        axes[0,0].legend(fontsize=8)
        fig.suptitle('Changing T, R, P, and S independently',x=.03,ha='left')
        fig.supxlabel('Two label blocks · up to four valid decisions per model/point · original row/column presentation\n'
                      'Dotted lines: baseline payoff. Lines connect descriptive means; they are not fitted thresholds.',fontsize=9)
        save(fig,out,'09_model_raw_payoff_sweeps')

    aff=[g for g in all_games if g['case']['stage']=='affine' and g['scores']['valid']]
    if aff:
        fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
        for ax,(model,label) in zip(axes.flat,LABELS.items()):
            cells=defaultdict(list)
            for g in aff:
                if g['model_key']==model:
                    c=g['case'];cells[(c['anchor'],c['scale'],c['shift'])].append(g['scores']['cooperation_rate'])
            for scale,shift,color in [(1,0,'#2777B4'),(2,1,'#D47C3B'),(10,0,'#25856A'),(1,10,'#8760A8')]:
                x=list(range(6));y=[np.mean(cells[(i,scale,shift)]) if cells[(i,scale,shift)] else np.nan for i in x]
                ax.plot(x,y,marker='o',label=f'{scale} × payoff + {shift}',color=color)
            ax.set(title=label,xlabel='Anchor game',ylabel='Observed C-choice rate',ylim=(-.05,1.05))
            ax.set_xticks(range(6),['PD','Coord.','Anti-coord.','C dom.','Tie','Mild PD'])
            ax.grid(alpha=.15)
        axes[0,0].legend(fontsize=8)
        fig.suptitle('Do equivalent payoff scales produce equivalent model choices?',x=.03,ha='left')
        fig.supxlabel('Two label blocks · up to four valid decisions per condition · original row/column presentation\n'
                      'Anchor categories are discrete; connecting lines are visual guides.',fontsize=9)
        save(fig,out,'10_affine_invariance_control')

    if (out/'attempts.jsonl').exists():
        from run_phase_space import read_records
        records=read_records(out/'attempts.jsonl')
        perspectives=[r for r in records if r['case']['stage']=='perspective']
        if perspectives:
            rep_ids={r['case']['replicate'] for r in perspectives}
            fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
            for ax,role in zip(axes,['row','column']):
                for offset,stage,color,label in [(-.18,'grid','#D47C3B','Row/column matrix'),
                                                (.18,'perspective','#2777B4','Own-payoff perspective')]:
                    values=[];counts=[]
                    for model in LABELS:
                        rs=[r for r in records if r['case']['stage']==stage and r['role']==role
                            and r['model_key']==model and r['decision']['valid']
                            and r['case']['replicate'] in rep_ids and r['case']['payoffs']['strict_pd']]
                        counts.append(len(rs));values.append(np.mean([r['decision']['action']=='C' for r in rs]) if rs else np.nan)
                    bars=ax.barh(np.arange(4)+offset,values,height=.34,color=color,label=label)
                    for bar,n in zip(bars,counts):
                        ax.text(min(bar.get_width()+.02,.88),bar.get_y()+.17,f'n={n}',va='center',fontsize=8)
                ax.set_yticks(range(4),list(LABELS.values()));ax.invert_yaxis()
                ax.set(xlim=(0,1.05),xlabel='C-choice frequency in strict PD',title=f'{role.title()} player')
                ax.grid(axis='x',alpha=.15)
            axes[0].legend(fontsize=8,loc='lower right')
            fig.suptitle('Does payoff presentation explain role-dependent choices?',x=.03,ha='left')
            fig.supxlabel('Exploratory matched control. Same payoffs and label blocks; valid decisions only. D is strictly dominant.',fontsize=10)
            save(fig,out,'13_payoff_perspective_control')

    rows=[]
    perspective_games=[g for g in all_games if g['case']['stage']=='perspective_grid' and g['scores']['valid']]
    if perspective_games:
        perspective_blocks=len({g['case']['replicate'] for g in perspective_games})
        cooperation_heatmap(perspective_games, out)
        for filename,metric,title in [('15_own_payoff_nash','nash','Pure Nash outcomes with own-payoff presentation')]:
            fig,axes=plt.subplots(2,2,figsize=(11,10),layout='constrained')
            for ax,(model,label) in zip(axes.flat,LABELS.items()):
                cells=defaultdict(list)
                for g in perspective_games:
                    if g['model_key']==model:
                        p=g['case']['payoffs'];cells[(p['s'],p['t'])].append(g['scores'][metric])
                z=np.array([[np.mean(cells[(s,t)]) if cells[(s,t)] else np.nan for s in axis_values()] for t in axis_values()])
                cm=plt.get_cmap('viridis').copy();cm.set_bad('#E5E7EB')
                im=ax.pcolormesh(edges,edges,z,cmap=cm,vmin=0,vmax=1)
                boundaries(ax);ax.set(xlabel='Normalized S',ylabel='Normalized T')
                n=sum(g['model_key']==model for g in perspective_games)
                ax.set_title(f'{label}  ·  {n} valid games',loc='left')
            fig.colorbar(im,ax=list(axes.flat),shrink=.7,label='Fraction')
            fig.suptitle(title+'\n',x=.02,ha='left')
            fig.supxlabel(f'Exploratory representation control · same 13 × 13 grid · {perspective_blocks} label blocks\n'
                          'Red: analytic Nash boundaries. Gray: missing/invalid. Cell means of valid self-play games.',fontsize=10)
            save(fig,out,filename)

    for g in all_games:
        c=g['case']
        rows.append({'model':g['model'],'stage':c['stage'],'replicate':c['replicate'],'case_id':c['case_id'],
                     **{k:c['payoffs'][k] for k in ('T','R','P','S','s','t','regime','payoff_order')},
                     **g['scores'],'belief_regret':g['belief_regret']})
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (out/'model_results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    style();analytic_figures(out)
    if (out/'summary.json').exists():
        measured_figures(out,json.loads((out/'summary.json').read_text()))
    print(f'Rendered {len(list(out.glob("*.png")))} figures to {out}')


if __name__=='__main__':
    main()
