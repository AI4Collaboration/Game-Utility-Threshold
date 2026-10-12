"""Check the numeric arrays actually passed to the four publication plots."""
from pathlib import Path
from collections import defaultdict
import argparse
import json
import statistics
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import matplotlib.pyplot as plt
from scripts.audit_experiment import artifact, displayed_matrix, oracle_decision, require
from scripts import render_phase_space as renderer
from scripts import compare_phase_space_theory as comparison


def audit_plot_data(data):
    records=[json.loads(x) for x in artifact(data,'attempts.jsonl').splitlines()]
    summary=json.loads(artifact(data,'summary.json'))
    captured={}
    def capture(fig,out,name):
        if name in ('01_analytic_phase_space','14_own_payoff_cooperation','23_expected_regret_heatmap'):
            axes=fig.axes[:1] if name=='01_analytic_phase_space' else fig.axes[:4]
            captured[name]=[{'array':ax.collections[0].get_array().copy(),
                             'coordinates':ax.collections[0].get_coordinates().copy(),
                             'clim':ax.collections[0].get_clim()} for ax in axes]
        elif name=='13_payoff_perspective_control':
            captured[name]=[[p.get_width() for p in ax.patches] for ax in fig.axes[:2]]
        plt.close(fig)
    with tempfile.TemporaryDirectory() as temp:
        out=Path(temp);(out/'attempts.jsonl').write_bytes(artifact(data,'attempts.jsonl'))
        with patch.object(renderer,'save',capture),patch.object(comparison,'save',capture):
            renderer.style();renderer.analytic_figures(out);renderer.measured_figures(out,summary)
            ds,gs=comparison.build_rows(records);comparison.deviation_maps(out,ds,gs)
    groups=defaultdict(dict); expected_regret=defaultdict(list); expected_cooperation=defaultdict(list)
    for r in records:
        c=r['case'];d=r['decision']
        if c['stage']!='perspective_grid':continue
        groups[r['model_key'],c['replicate'],c['case_id']][r['role']]=r
        if d['valid'] and d.get('belief_opponent_C') is not None:
            p=c['payoffs'];b=oracle_decision(displayed_matrix(r),r['role'],d['action'],d['belief_opponent_C'],p['R']-p['P'])
            expected_regret[r['model_key'],p['s'],p['t']].append(b['stated_belief_regret_normalized'])
    for roles in groups.values():
        if all(roles[role]['decision']['valid'] for role in ('row','column')):
            r=roles['row'];p=r['case']['payoffs']
            expected_cooperation[r['model_key'],p['s'],p['t']].append(sum(x['decision']['action']=='C' for x in roles.values())/2)
    axis=[-1+i/4 for i in range(13)]
    for name,expected in [('14_own_payoff_cooperation',expected_cooperation),('23_expected_regret_heatmap',expected_regret)]:
        for model,plot in zip(('glm','qwen','astra','fable'),captured[name]):
            want=np.array([[statistics.mean(expected[model,s,t]) if expected[model,s,t] else np.nan for s in axis] for t in axis])
            actual=np.ma.filled(plot['array'],np.nan).reshape(13,13)
            np.testing.assert_allclose(actual,want,rtol=1e-10,atol=1e-9,equal_nan=True)
            coords=plot['coordinates'];centers=(coords[:-1,:-1]+coords[1:,1:])/2
            np.testing.assert_allclose(centers[:,:,0],np.tile(axis,(13,1)))
            np.testing.assert_allclose(centers[:,:,1],np.tile(np.array(axis)[:,None],(1,13)))
        require(len({tuple(p['clim']) for p in captured[name]})==1, name+': model color scales differ')
    for role,actual in zip(('row','column'),captured['13_payoff_perspective_control']):
        want=[]
        for stage in ('grid','perspective'):
            for model in ('glm','qwen','astra','fable'):
                selected=[r for r in records if r['case']['stage']==stage and r['case']['replicate'] in (0,1)
                          and r['model_key']==model and r['role']==role and r['case']['payoffs']['strict_pd'] and r['decision']['valid']]
                want.append(statistics.mean(r['decision']['action']=='C' for r in selected))
        np.testing.assert_allclose(actual,want)
    theory=captured['01_analytic_phase_space'][0]
    coords=theory['coordinates'];centers=(coords[:-1,:-1]+coords[1:,1:])/2
    checked=0
    for values,locations in zip(theory['array'],centers):
        for value,(s,t) in zip(values,locations):
            if abs(s)<1e-9 or abs(t-1)<1e-9:continue
            # Enumerate the optimal response against each pure opponent action.
            against_C='C' if 1>t else 'D';against_D='C' if s>0 else 'D'
            expected={('C','C'):0,('D','D'):1,('C','D'):2,('D','C'):3}[against_C,against_D]
            require(value==expected,'Analytic regime plot mismatch');checked+=1
    return {'status':'passed','publication_figures_checked':4,'empirical_heatmap_values_checked':2*4*13*13,
            'presentation_bar_values_checked':16,'analytic_nonboundary_cells_checked':checked,
            'coordinate_centers_and_shared_color_scales':'passed','additional_paid_calls':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=audit_plot_data(a.data);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
