"""Threshold confidence sets by inverting whole-slice, bounded-mean tests.

No fitted logistic curve, per-cell bootstrap, or new API calls. Conditional on
an ordered 50% crossing, a candidate threshold constrains the mean response on
each side. Independent complete games supply bounded observations. Chernoff
tests are inverted over every interval/point of the sampled axis; the outer
hull is reported. Bonferroni covers nested windows on both curves, and optionally
all slices. Dependence between players, observed/theory scores, and slices is
allowed; independence between games is assumed.
"""
from pathlib import Path
from collections import defaultdict, Counter
import argparse
import hashlib
import html
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_threshold_table import (ROOT, LABELS, TOL, load_games, build_cells,
    build_rows, finite_json, bracket, num)


def game_scores(games):
    scores = []
    for pair in games:
        p = pair[0]['case']['payoffs']
        margins = [r['decision']['belief_opponent_C']*(1-p['T']) +
                   (1-r['decision']['belief_opponent_C'])*p['S'] for r in pair]
        # Theory is set-valued at ties; retain both permissible endpoints.
        scores.append(dict(model_key=pair[0]['model_key'], s=p['S'], t=p['T'],
            observed=sum(r['decision']['action']=='C' for r in pair)/2,
            theory_lower=sum(d>TOL for d in margins)/2,
            theory_upper=sum(d>=-TOL for d in margins)/2,
            certain_C=min(p['S'],1-p['T'])>TOL,
            certain_D=max(p['S'],1-p['T'])<-TOL,
            job_ids=[r['job_id'] for r in pair]))
    return scores


def bounded_tail(values, require_cooperation):
    """Conservative one-sided p-value bound under a mean on the required side.

    If C-majority is required, H0: average expectation >= .5; otherwise <= .5.
    The pooled expectation constraint follows from the candidate crossing's
    constraint at every selected cell. Values are independent [0,1] game scores.
    """
    if not values: return 1.
    n=len(values);mean=sum(values)/n
    if not 0<=mean<=1 or any(not 0<=v<=1 for v in values):
        raise ValueError('Game scores must lie in [0,1]')
    if (mean>=.5 if require_cooperation else mean<=.5): return 1.
    # For any independent [0,1] variables with mean expectation constrained
    # relative to .5, the Bernoulli moment-generating function bounds theirs.
    # Optimizing the Chernoff bound gives exp[-n KL(mean || .5)], including
    # non-identical label blocks. This is NOT an assumption of Bernoulli games:
    # actual game scores can equal .5, and players may be dependent.
    kl=math.log(2.)
    if mean>0: kl+=mean*math.log(mean)
    if mean<1: kl+=(1-mean)*math.log(1-mean)
    return math.exp(-n*kl)


def accepts_candidate(scores, axis, theta, increasing, source, tail_alpha):
    for side in ('left','right'):
        chosen=[r for r in scores if r[axis]<theta] if side=='left' else [r for r in scores if r[axis]>theta]
        # Observations exactly at a candidate boundary are omitted, conservatively.
        want_c=(side=='right') if increasing else (side=='left')
        if source=='observed':
            values=[r['observed'] for r in chosen]
        elif source=='theory':
            # A possible C-majority needs upper >= .5; a possible D-majority
            # needs lower <= .5. Never force a theoretical action at a utility tie.
            if any(r['certain_D'] if want_c else r['certain_C'] for r in chosen):
                return False
            key='theory_upper' if want_c else 'theory_lower'
            values=[r[key] for r in chosen]
        else: raise ValueError('Unknown source')
        # Examine nested groups of whole cells nearest the proposed threshold.
        # A distant, strongly cooperative region must not wash out contrary
        # evidence just above a proposed increasing-cooperation boundary.
        # Window endpoints depend only on the payoff design, never responses.
        ordered=sorted({r[axis] for r in chosen},reverse=side=='left')
        for endpoint in ordered:
            window=[value for r,value in zip(chosen,values)
                    if (r[axis]>=endpoint if side=='left' else r[axis]<=endpoint)]
            if bounded_tail(window,want_c)<tail_alpha: return False
    return True


def threshold_set(scores, axis, source, comparison_alpha=.05, family_size=1):
    """Joint per-comparison coverage >=1-alpha for observed and theory sets.

    At most N nested windows across both sides of each of two curves are
    allocated alpha/(2*N*family_size). Inverting a test does
    NOT require a penalty for the number of candidate theta values: coverage is
    controlled by the test at the true theta. Taking the outer hull is conservative.
    """
    if not scores or axis not in ('s','t') or family_size<1 or not 0<comparison_alpha<1:
        raise ValueError('Invalid threshold-set arguments')
    xs=sorted({r[axis] for r in scores});edges=[-math.inf,*xs,math.inf]
    atoms=[]
    for left,right in zip(edges,edges[1:]):
        candidate=right-1 if left==-math.inf else left+1 if right==math.inf else (left+right)/2
        atoms.append((left,right,candidate,'open_interval'))
    atoms += [(x,x,x,'point') for x in xs]
    accepted=[]
    alpha=comparison_alpha/(2*len(xs)*family_size)
    for left,right,candidate,kind in sorted(atoms):
        if accepts_candidate(scores,axis,candidate,axis=='s',source,alpha):
            accepted.append(dict(low=left,high=right,kind=kind))
    if not accepted:
        return dict(status='empty',low=None,high=None,accepted_atoms=[],tail_alpha=alpha)
    low=min(a['low'] for a in accepted);high=max(a['high'] for a in accepted)
    status=('finite' if math.isfinite(low) and math.isfinite(high) else
            'unbounded' if low==-math.inf and high==math.inf else 'one_sided')
    return dict(status=status,low=low,high=high,accepted_atoms=accepted,tail_alpha=alpha)


def difference_set(observed,theory):
    if observed['status']=='empty' or theory['status']=='empty':
        return dict(status='empty',low=None,high=None,excludes_zero=None,minimum_abs_shift=None)
    low=observed['low']-theory['high'];high=observed['high']-theory['low']
    excludes=low>0 or high<0
    return dict(status='finite' if math.isfinite(low) and math.isfinite(high) else
                'unbounded' if low==-math.inf and high==math.inf else 'one_sided',
                low=low,high=high,excludes_zero=excludes,
                minimum_abs_shift=low if low>0 else -high if high<0 else 0.)


def analyze(games):
    rows=build_rows(build_cells(games));scores=game_scores(games)
    for r in rows:
        for legacy in ('observed_95_set','theoretical_95_set','difference_95_set',
                       'confidence_comparison','distance_outside_95_set'):
            r.pop(legacy,None)
        axis=r['varied_payoff'].lower();fixed=r['fixed_payoff'].lower()
        chosen=[g for g in scores if g['model_key']==r['model_key'] and g[fixed]==r['fixed_value']]
        assert len(chosen)==r['games']
        for mode,family in [('individual',1),('familywise',len(rows))]:
            observed=threshold_set(chosen,axis,'observed',family_size=family)
            theory=threshold_set(chosen,axis,'theory',family_size=family)
            r[mode]=dict(observed=observed,theoretical=theory,difference=difference_set(observed,theory))
    return rows


def summary_for(rows):
    return {mode:dict(
        observed_sets=dict(Counter(r[mode]['observed']['status'] for r in rows)),
        theoretical_sets=dict(Counter(r[mode]['theoretical']['status'] for r in rows)),
        difference_sets=dict(Counter(r[mode]['difference']['status'] for r in rows)),
        zero_excluded=sum(r[mode]['difference']['excludes_zero'] is True for r in rows),
        zero_not_excluded=sum(r[mode]['difference']['excludes_zero'] is False for r in rows),
        empty_comparisons=sum(r[mode]['difference']['status']=='empty' for r in rows))
        for mode in ('individual','familywise')}


METHODS = r'''# Confidence intervals for observed minus theoretical payoff thresholds

This is an exploratory, offline re-analysis of existing data, not new model
experiments or a preregistered confirmatory study. It leaves the earlier
cell-by-cell confidence table intact and supplies a more informative analysis
of the same crossing estimand. No fitted logistic curves or midpoint estimates
are used. All numerical threshold bounds are normalized payoff units.

## Quantity being estimated

At a held-fixed payoff, the observed boundary separates mean cooperation above
and below 0.5. As S increases, the expected direction is D-majority to C-majority;
as T increases it is C-majority to D-majority. This is a single-crossing assumption
about population means, not a requirement that every sampled response is monotone.
The response need not have a logistic shape or even a constant slope. Flat ties
can make the boundary set-valued. Existence of a unique boundary is not established.

The theoretical comparator uses each decision's reported opponent belief q and
the margin q(1-T)+(1-q)S. For each game, L is the fraction of its two decisions
strictly favoring C, and U the fraction permitting C, including utility ties.
Its admissible mean cooperation is between E[L] and E[U]. A theoretical boundary
means a single-crossing selection from this admissible range. It is conditional
on reported beliefs, not a unique equilibrium prediction. Ties remain set-valued.

Each complete game yields an observed C fraction Y in {0, 0.5, 1} and paired
L,U scores in the same range. We assume independent games but allow dependence
between a game's players and between Y,L,U. The target at each cell is the
average expectation over its retained label blocks, conditional on complete
valid outputs. Two cells have only one retained block. The results do not correct
for informative invalid-output selection, provider drift, or unfaithful beliefs.
The original and refinement batches were collected at different times. Statistical
coverage is conditional on treating the tested design as fixed and on the stated
sampling/shape assumptions; it is not a guarantee against adaptive-study effects.

## Candidate-threshold tests

A proposed threshold theta requires particular signs relative to 0.5 on each
side. For example, for increasing S, means at x < theta must be <= 0.5 and means
at x > theta must be >= 0.5. At x = theta the cell is omitted conservatively.

On each side, test every nested window of whole cells starting nearest theta
and expanding outward. Window endpoints depend on the payoff design, not on
observed responses. Whole cells preserve the tested label-block mixture.
Pooling across a window is valid because a required sign at every cell implies
the same sign for their game-count-weighted mean expectation.

For observed scores use Y. For theoretical scores, a required C-majority needs
E[U] >= 0.5; a required D-majority needs E[L] <= 0.5. This tests compatibility
with the range of tie resolutions, rather than imposing one action at ties.
Any candidate contradicting strict dominance for any sampled cell is rejected
deterministically, since the corresponding theoretical rate is known exactly
for every q in [0,1].

For n independent bounded [0,1] game scores with observed mean m on the wrong
side of 0.5, the one-sided tail probability is bounded above by

    p_bound = exp[-n KL(m || 0.5)]
    KL(m || 0.5) = m log(2m) + (1-m) log(2(1-m)), with 0 log 0 = 0.

Use p_bound=1 on the allowed side or when the window is empty. This is a
Chernoff bound obtained from the Bernoulli moment-generating-function upper
bound for bounded variables. It does NOT assume game scores are Bernoulli or
that player choices are independent. Non-identical game expectations are allowed.
By convexity, E[exp(lambda Y_i)] <= 1-p_i+p_i exp(lambda), where p_i=E[Y_i].
Independence and concavity of log bound the product by the moment-generating
function of n Bernoulli variables with the same average expectation. Optimizing
lambda gives the KL bound above, which is sharper than exp[-2n(m-0.5)^2].

If a slice contains N cells, at most N windows occur across its two sides for
one candidate. Allocate alpha/(2 N F) to each window, with alpha=0.05. The factor
2 covers the observed and theoretical boundaries; F=1 for an individual-slice
comparison, or F=128 for familywise coverage across all reported comparisons.
The union bound does not require independence between windows, curves, or slices.

Invert these tests over all candidate thresholds. No further correction for
the number of candidate values is needed: confidence coverage is determined by
the rejection probability of the test at the true threshold. Tests change only
at sampled x values, so every open interval and every sampled point is checked.
The reported interval is the closed outer hull of the accepted set; accepted
atoms are saved in JSON. An empty accepted set would flag incompatibility with
the crossing description, rather than being interpreted as a threshold shift.

## Comparing boundaries

If observed and theoretical confidence sets are [Lo,Uo] and [Lt,Ut], the reported
confidence interval for d = observed minus theoretical is [Lo-Ut, Uo-Lt]. These
are outer intervals, not paired bootstrap or fitted-model intervals. The joint
coverage allocation makes the difference interval at least 95% for each fixed
slice when F=1, and jointly at least 95% across all slices when F=128, conditional
on the assumptions above. The separate threshold sets in a row have joint
coverage of at least 95%; they are not independent error bars.

Zero excluded means evidence of a shift under the stated assumptions. Zero
included means the method does not establish a shift; it does not establish
equality or practical equivalence. The minimum supported absolute shift is the
interval's distance from zero, not the magnitude of the observed point difference.
No finite point estimate is fabricated when only a sample bracket exists.

The original descriptive crossing brackets remain in the table. They are not
confidence intervals. More informative sets here do not invalidate the earlier
cellwise method: they use the crossing sign restrictions to pool observations.
This analysis is still conservative and is not the only valid inferential method.

## Sources and reproducibility

- Hoeffding (1963), Probability Inequalities for Sums of Bounded Random Variables:
  https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf
- P. B. Stark, confidence sets by inversion of hypothesis tests:
  https://www.stat.berkeley.edu/~stark/Teach/S240/Notes/ch5.htm
- Archived raw records: data/attempts.jsonl.gz and data_pd_refinement/attempts.jsonl.gz.
  Their SHA-256 hashes appear in threshold_confidence.json.

Run: python scripts/report_threshold_confidence.py --output reproduced/threshold-confidence
'''


def ci_label(bounds):
    if bounds['status']=='empty': return 'No compatible single crossing'
    if bounds['low']==-math.inf and bounds['high']==math.inf: return '(−∞, +∞)'
    return f"[{num(bounds['low'])}, {num(bounds['high'])}]"


def report(rows,summary,out):
    ordered=sorted(rows,key=lambda r:(r['individual']['difference']['status']!='finite',
                                     list(LABELS).index(r['model_key']),r['varied_payoff'],r['fixed_value']))
    columns=['Model / sweep','Games / decisions','Expected threshold¹','Observed threshold¹',
             '95% interval: observed − expected²','Zero excluded?','Minimum supported |shift|',
             '95% interval corrected across 128 slices³']
    md=['# Threshold differences and confidence intervals','',
        'Conditional on a single ordered 50% crossing and independent games. Brackets describing sampled crossings are not confidence intervals.',
        '', '| '+' | '.join(columns)+' |','|'+'|'.join(['---']*len(columns))+'|']
    body=[]
    for r in ordered:
        difference=r['individual']['difference'];finite=difference['status']=='finite'
        condition=f"{r['model']} · vary {r['varied_payoff']}, {r['fixed_payoff']}={num(r['fixed_value'])}"
        verdict='Yes' if difference['excludes_zero'] is True else 'No' if difference['excludes_zero'] is False else 'Not testable'
        values=[condition,f"{r['games']} / {r['decisions']}",
            bracket(r['theoretical'])+'; 95% set: '+ci_label(r['individual']['theoretical']),
            bracket(r['observed'])+'; 95% set: '+ci_label(r['individual']['observed']),
            ci_label(difference),verdict,num(difference['minimum_abs_shift']),ci_label(r['familywise']['difference'])]
        md.append('| '+' | '.join(values)+' |')
        cells=[]
        for i,value in enumerate(values):
            if i in (2,3):
                a,b=value.split('; 95% set: ')
                cells.append('<td>'+html.escape(a)+'<small>95% set: '+html.escape(b)+'</small></td>')
            else: cells.append('<td>'+html.escape(value)+'</td>')
        body.append(f'<tr data-model="{r["model_key"]}" data-axis="{r["varied_payoff"]}" data-finite="{str(finite).lower()}">'+''.join(cells)+'</tr>')
    notes=('¹ First line: descriptive sampled crossing bracket; second line: confidence set. '
        'One-sided sample brackets require continuing the single-crossing pattern. '
        '² At least 95% joint coverage per fixed comparison under the stated assumptions. '
        'Positive difference means a higher observed payoff threshold; negative means lower. '
        '³ Familywise 95% coverage across 128 comparisons. '
        '“No” means zero is included, not that the thresholds are equal. '
        'A minimum supported shift of zero is not an estimate of zero shift.')
    md+=['',notes,'','See METHODS.md for definitions, derivation, and limitations.']
    (out/'table.md').write_text('\n'.join(md)+'\n')
    (out/'METHODS.md').write_text(METHODS)
    individual=summary['results']['individual'];family=summary['results']['familywise']
    text=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Threshold differences: confidence intervals</title><style>
body{{font:16px/1.55 Georgia,serif;color:#202b35;background:#f6f7f8;padding:30px;margin:0}}main{{max-width:1800px;margin:auto}}
h1{{font-size:32px;margin-bottom:8px}}p{{max-width:1100px}}.notice{{background:#fff4dc;border-left:4px solid #bd8c3c;padding:16px 20px;margin:22px 0}}
.stats{{display:flex;gap:14px;flex-wrap:wrap}}.stats span{{padding:14px 18px;background:white;border:1px solid #dce1e5}}a{{color:#245c8a}}
.controls{{display:flex;align-items:center;gap:20px;margin:22px 0 12px;flex-wrap:wrap}}select{{font:inherit;padding:7px;border:1px solid #bcc6ce;border-radius:4px}}
.scroll{{overflow:auto;max-height:75vh;background:white;border:1px solid #cbd4db}}table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}
th{{position:sticky;top:0;background:#273b4b;color:white;text-align:left;z-index:1}}th,td{{padding:14px 12px;border-bottom:1px solid #dce2e8;min-width:110px}}
td:first-child{{min-width:210px;font-weight:bold}}td:nth-child(3),td:nth-child(4){{min-width:180px}}tr:nth-child(even){{background:#f5f7f9}}
tr[data-finite=true] td:nth-child(5){{background:#e8f1f8;font-weight:bold}}small{{display:block;font-size:12px;color:#4b5966;margin-top:5px}}
details{{background:white;padding:18px 22px;margin-top:22px}}summary{{font-weight:bold;cursor:pointer}}pre{{white-space:pre-wrap;font:14px/1.6 Georgia,serif;max-width:1100px}}
@media print{{body{{padding:0;background:white}}.controls{{display:none}}.scroll{{max-height:none;overflow:visible}}th{{position:static}}table{{font-size:9px}}td,th{{min-width:0;padding:6px}}}}
</style><main><h1>Are observed payoff thresholds different from theory?</h1>
<p>Expected behavior uses each decision’s reported opponent beliefs. Each row holds one normalized payoff fixed and varies the other. R = 1, P = 0.</p>
<div class="stats"><span><b>128</b> comparisons</span><span><b>1,614</b> complete games</span><span><b>3,228</b> decisions</span><span><b>{individual['difference_sets'].get('finite',0)}</b> finite individual difference intervals</span></div>
<div class="notice"><b>{individual['zero_excluded']} of 128 individual intervals exclude zero; {family['zero_excluded']} after correction across the full sweep.</b><br>
This analysis does not establish a statistically significant threshold shift. It also does not establish equality.
The intervals are conditional on an ordered single crossing; no unique threshold is assumed for a reversing population response.</div>
<p>Individual difference intervals: {individual['difference_sets'].get('finite',0)} finite,
{individual['difference_sets'].get('one_sided',0)} one-sided, {individual['difference_sets'].get('unbounded',0)} unbounded.
All 128 familywise difference intervals are unbounded. Finite individual intervals appear first and are shaded blue.</p>
<p><a href="table.md">Copyable Markdown table</a> · <a href="threshold_confidence.json">All bounds and provenance (JSON)</a> · <a href="METHODS.md">Statistical derivation and assumptions</a></p>
<div class="controls"><label>Model <select id="model"><option value="">All four</option>{''.join(f'<option value="{k}">{v}</option>' for k,v in LABELS.items())}</select></label>
<label>Vary <select id="axis"><option value="">S and T</option><option>S</option><option>T</option></select></label>
<label><input type="checkbox" id="finite"> Show only finite individual difference intervals</label><span id="count">128 rows</span></div>
<div class="scroll"><table><thead><tr>{''.join('<th>'+html.escape(c)+'</th>' for c in columns)}</tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p>{html.escape(notes)}</p><details><summary>How these intervals were calculated</summary><pre>{html.escape(METHODS)}</pre></details>
<p>Method sources: <a href="https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf">Hoeffding’s bounded-variable inequalities</a>;
<a href="https://www.stat.berkeley.edu/~stark/Teach/S240/Notes/ch5.htm">confidence sets by test inversion</a>.</p>
<script>function filter(){{let n=0;let m=document.getElementById('model').value,a=document.getElementById('axis').value,f=document.getElementById('finite').checked;document.querySelectorAll('tbody tr').forEach(r=>{{let show=(!m||r.dataset.model===m)&&(!a||r.dataset.axis===a)&&(!f||r.dataset.finite==='true');r.hidden=!show;if(show)n++;}});document.getElementById('count').textContent=n+' rows';}}['model','axis','finite'].forEach(k=>document.getElementById(k).addEventListener('change',filter));</script></main></html>'''
    (out/'index.html').write_text(text)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'reproduced/threshold-confidence')
    args=parser.parse_args()
    sources=[ROOT/'data/attempts.jsonl.gz',ROOT/'data_pd_refinement/attempts.jsonl.gz']
    games=load_games(sources);rows=analyze(games)
    summary=dict(complete_games=len(games),decisions=2*len(games),comparisons=len(rows),
        confidence=.95,results=summary_for(rows),additional_paid_calls=0,
        method='Inversion of nested-window bounded-mean Chernoff tests, with joint and familywise coverage allocation',
        sources=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'threshold_confidence.json').write_text(json.dumps(finite_json(dict(summary=summary,rows=rows)),indent=2)+'\n')
    report(rows,summary,args.output)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
