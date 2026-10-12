"""Offline S/T crossing table, with conservative game-cluster confidence sets.

Grid brackets describe the sample. Confidence sets target a hypothetical single
population crossing; they do not assume that one exists. No fitted curves or
new model calls. Each independent bounded observation is one complete game.
"""
from pathlib import Path
from collections import defaultdict, Counter
import argparse
import gzip
import hashlib
import html
import json
import math
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_threshold_displacement import LABELS, TOL, crossing_bracket, displacement

ROOT = Path(__file__).resolve().parents[1]
STAGES = {'perspective_grid', 'perspective_pd_refinement'}


def load_games(sources):
    latest = {}
    for source in sources:
        opener = gzip.open if source.suffix == '.gz' else open
        with opener(source, 'rt') as f:
            for line in f:
                r = json.loads(line)
                if r['case']['stage'] in STAGES:
                    latest[r['job_id']] = r
    groups = defaultdict(dict)
    for r in latest.values():
        c = r['case']
        key = (r['model_key'], c['stage'], c['replicate'], c['case_id'])
        if r['role'] in groups[key]:
            raise ValueError('Different job IDs for the same game role')
        groups[key][r['role']] = r
    games = []
    for roles in groups.values():
        if set(roles) != {'row', 'column'}:
            continue
        pair = [roles['row'], roles['column']]
        if not all(r['decision'].get('valid') and r['decision'].get('action') in ('C', 'D') for r in pair):
            continue
        for r in pair:
            q = r['decision'].get('belief_opponent_C')
            if type(q) not in (int, float) or not math.isfinite(q) or not 0 <= q <= 1:
                raise ValueError('Complete valid game lacks usable reported belief')
        if pair[0]['case']['payoffs'] != pair[1]['case']['payoffs']:
            raise ValueError('Game roles have different payoff matrices')
        games.append(pair)
    return games


def confidence_band(mean, n, comparisons, alpha=.05):
    """Two-sided Hoeffding + union bound; independent [0,1] game scores.

    Non-identical label blocks are allowed. The target is their mean expectation,
    conditional on valid outputs; this is not an across-provider guarantee.
    """
    if n <= 0 or comparisons <= 0 or not 0 < alpha < 1:
        raise ValueError('Invalid confidence-band inputs')
    radius = math.sqrt(math.log(2 * comparisons / alpha) / (2 * n))
    return max(0., mean-radius), min(1., mean+radius)


def build_cells(games):
    groups = defaultdict(list)
    for pair in games:
        r = pair[0]; p = r['case']['payoffs']
        if p['R'] != 1 or p['P'] != 0 or p['s'] != p['S'] or p['t'] != p['T']:
            raise ValueError('Expected normalized R=1, P=0')
        groups[r['model_key'], p['S'], p['T']].append(pair)
    cells = []
    for (model, s, t), pairs in sorted(groups.items()):
        records = [r for pair in pairs for r in pair]
        n = len(records)
        margins = [r['decision']['belief_opponent_C'] * (1-t) +
                   (1-r['decision']['belief_opponent_C']) * s for r in records]
        c = sum(r['decision']['action'] == 'C' for r in records)
        strict_c = sum(x > TOL for x in margins)
        strict_d = sum(x < -TOL for x in margins)
        row = dict(model_key=model, s=s, t=t, games=len(pairs), decisions=n,
                   observed_C=c/n, theory_min=strict_c/n, theory_max=1-strict_d/n,
                   observed_sign=(c > n/2)-(c < n/2),
                   theory_sign=1 if strict_c > n/2 else -1 if strict_d > n/2 else 0,
                   indifferent=n-strict_c-strict_d,
                   stages=sorted({r['case']['stage'] for r in records}),
                   job_ids=[r['job_id'] for r in records])
        # Three processes per cell: observed C, strict-best-response C, and
        # admissible C (strict C plus utility ties). Within-game dependence allowed.
        for name in ('observed_C', 'theory_min', 'theory_max'):
            row[name+'_band'] = confidence_band(row[name], len(pairs), 3*len(groups))
        # Intersect sampling bands with exact best-response restrictions valid
        # for EVERY belief q in [0,1]. Do not add uncertainty to known dominance.
        low_margin, high_margin = min(s, 1-t), max(s, 1-t)
        if low_margin > TOL:
            row['theory_min_band'] = row['theory_max_band'] = (1.,1.)
        elif high_margin < -TOL:
            row['theory_min_band'] = row['theory_max_band'] = (0.,0.)
        else:
            if high_margin <= TOL: row['theory_min_band'] = (0.,0.)
            if low_margin >= -TOL: row['theory_max_band'] = (1.,1.)
        cells.append(row)
    return cells


def invert_band(points, increasing):
    """Outer set for a single monotone .5 crossing, allowing out-of-domain values.

    Without continuity/monotonicity a unique threshold is not defined. Strict
    band separation from .5 is required; equality does not establish a side.
    """
    lo, hi = -math.inf, math.inf
    for x, lower, upper in points:
        before = upper < .5 if increasing else lower > .5
        after = lower > .5 if increasing else upper < .5
        if before: lo = max(lo, x)
        if after: hi = min(hi, x)
    return lo, hi


def minimum_gap(lo, hi):
    if lo is None or hi is None: return None
    return lo if lo > 0 else hi if hi < 0 else 0.


def build_rows(cells):
    rows = []
    for model in LABELS:
        for vary, fixed in [('T', 'S'), ('S', 'T')]:
            groups = defaultdict(list)
            for c in cells:
                if c['model_key'] == model: groups[c[fixed.lower()]].append(c)
            for value, selected in sorted(groups.items()):
                selected.sort(key=lambda c: c[vary.lower()])
                xs = [c[vary.lower()] for c in selected]
                observed = crossing_bracket(list(zip(xs, [c['observed_sign'] for c in selected])), vary == 'S')
                theory = crossing_bracket(list(zip(xs, [c['theory_sign'] for c in selected])), vary == 'S')
                gap = displacement(observed, theory)
                obs_ci = invert_band([(x, *c['observed_C_band']) for x, c in zip(xs, selected)], vary == 'S')
                theo_ci = invert_band([(x, c['theory_min_band'][0], c['theory_max_band'][1])
                                       for x, c in zip(xs, selected)], vary == 'S')
                diff_ci = (obs_ci[0]-theo_ci[1], obs_ci[1]-theo_ci[0])
                unbounded = diff_ci == (-math.inf, math.inf)
                min_gap = minimum_gap(gap['low'], gap['high'])
                rows.append(dict(model_key=model, model=LABELS[model], varied_payoff=vary,
                    fixed_payoff=fixed, fixed_value=value, sampled_values=xs,
                    cells=len(selected), games=sum(c['games'] for c in selected),
                    decisions=sum(c['decisions'] for c in selected),
                    games_per_cell_min=min(c['games'] for c in selected),
                    games_per_cell_max=max(c['games'] for c in selected),
                    observed=observed, theoretical=theory, difference=gap,
                    minimum_signed_grid_gap=min_gap,
                    grid_comparison='unresolved' if min_gap is None else 'separated' if min_gap else 'overlap or touch',
                    observed_95_set=obs_ci, theoretical_95_set=theo_ci, difference_95_set=diff_ci,
                    confidence_comparison='Unresolved: unbounded observed threshold and difference sets' if unbounded else 'See confidence sets',
                    distance_outside_95_set=None if unbounded else minimum_gap(*diff_ci)))
    return rows


def num(x):
    if x is None: return '—'
    if x == math.inf: return '+∞'
    if x == -math.inf: return '−∞'
    return f'{x:g}'.replace('-', '−')


def bracket(b):
    if b['status'] == 'multiple_or_reversed': return 'Multiple / reversed'
    if b['low'] is None: return 'Not located'
    if b['low'] == -math.inf: return '≤ '+num(b['high'])
    if b['high'] == math.inf: return '≥ '+num(b['low'])
    return f"[{num(b['low'])}, {num(b['high'])}]"


def confidence_text(bounds):
    if bounds == (-math.inf, math.inf): return 'unbounded'
    return bracket(dict(status='confidence_set', low=bounds[0], high=bounds[1]))


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value): return '+Infinity' if value > 0 else '-Infinity'
    if isinstance(value, dict): return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [finite_json(v) for v in value]
    return value


METHODS = '''<h2>What the thresholds mean</h2>
<p>R = 1 and P = 0. At each sampled S–T point, for each decision’s reported opponent-cooperation belief q,
EU(C) − EU(D) = q(1 − T) + (1 − q)S. Positive means C is the selfish expected-utility best response;
negative means D; ties allow either. We recompute this using the belief reported at each point, rather than
holding q at 0.5. These are conditional best responses, not equilibrium predictions or evidence of calibrated beliefs.</p>
<p>The <b>observed threshold</b> brackets a sampled C-majority → D-majority crossing as T increases,
or a D-majority → C-majority crossing as S increases. The <b>theoretical threshold</b> uses the same
crossing rule on the admissible best-response C-rate: strictly more than half must favor one action.
Tied cells widen the bracket. Multiple/reversed crossings are retained rather than forced into one threshold.
One-sided bounds require extending the single-crossing pattern. All brackets describe samples; no
interpolation, binary search, logistic fit, or finite statistical precision is implied.</p>
<p>The signed grid difference is [observed lower − theoretical upper, observed upper − theoretical lower].
The minimum signed gap is its endpoint nearest zero when separated, zero when overlapping/touching,
and unavailable when not located. Positive means a higher observed <em>payoff</em> threshold.
For T that suggests more persistent cooperation; for S it suggests cooperation requires a higher S.
Grid separation alone does <b>not</b> establish statistical significance.</p>
<h2>95% confidence sets: method and limits</h2>
<p>Each complete game supplies three bounded [0,1] scores: its two-player mean C choice,
mean strict-C best response, and mean admissible-C best response (including ties).
We use two-sided Hoeffding bands with radius √[log(2K/0.05)/(2n)], where n is complete games at that cell
and K = 3 × 808 = 2,424 cell/quantity comparisons. Clipping gives [0,1]. The union bound provides
at least 95% simultaneous coverage for all three mean-rate processes across the table, assuming independent
games. It does not assume independence between players in a game, between the three quantities, or between slices.</p>
<p>There are only one or two games per cell. <b>Every observed-rate band is [0,1]</b> under this deliberately conservative
method. We intersect theoretical-rate bands with exact payoff restrictions: strict D dominance predicts zero C
for every belief, and strict C dominance predicts C for every belief. Weak dominance restricts the corresponding
admissible endpoint. Thus some theoretical threshold sets retain one-sided information.</p>
<p>Inverting the observed-rate bands still permits every threshold location, including outside the sampled domain,
conditional on a single monotone population crossing existing. Every observed threshold set and difference set
is (−∞,+∞); the data also do not establish that a unique crossing exists. The “inside/outside” comparison
is marked <b>unresolved</b>, and distance outside is unavailable—not zero and not evidence of agreement.
Other methods could be narrower by imposing extra response-curve or independence assumptions.</p>
<p>The target is the mean response of the tested label blocks conditional on valid complete outputs.
Two cells retain only one block; selection from invalid outputs and provider/time changes are not covered
by these intervals. Refinement was collected later, with new seeds. Beliefs and choices are jointly reported,
so this is descriptive consistency analysis, not a causal explanation. Theoretical sampling uncertainty is included;
uncertainty in the reported beliefs’ faithfulness is not.</p>
<h2>Coverage and sources</h2>
<p>202 measured payoff matrices × four models = 808 cells; 1,614 complete games / 3,228 decisions.
The 128 slices reuse these records in both directions; their sample sizes must not be summed as independent data.
Original 0.25 spacing spans [−1,2]. Added 0.125 spacing covers only strict PD (S &lt; 0, T &gt; 1),
so midpoint-only slices have smaller domains. No unmeasured combinations are filled in.
These totals exclude incompatible presentation controls, pilots, and other experiment stages.</p>
<p>The <a href="https://www.lesswrong.com/posts/hzq7bGB22wGRMGyEp/scheming-evals-mislead-in-both-directions">reference article</a>
reports Wilson intervals on a response rate, not confidence intervals on switching locations.
Our table follows its explicit sample-size reporting while using a separate threshold method.
Concentration inequality: <a href="https://doi.org/10.1080/01621459.1963.10500830">Hoeffding (1963)</a>.</p>'''


def render(rows, cells, sources, output):
    output.mkdir(parents=True, exist_ok=True)
    counts = Counter(r['grid_comparison'] for r in rows)
    summary = dict(matrices=len({(c['s'],c['t']) for c in cells}), cells=len(cells),
        games=sum(c['games'] for c in cells), decisions=sum(c['decisions'] for c in cells),
        slices=len(rows), grid_comparisons=dict(counts), confidence_level=.95,
        simultaneous_quantities=3*len(cells), confidence_method='Game-level Hoeffding bands + union bound + conditional crossing inversion',
        all_observed_rate_bands_vacuous=all(c['observed_C_band'] == (0.,1.) for c in cells),
        sources=[dict(name=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name,
                      sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sources])
    # The displayed methods state exact cohort constants; fail rather than silently
    # misreporting them after a future data change.
    assert (summary['matrices'],len(cells),summary['games'],summary['decisions'],len(rows)) == (202,808,1614,3228,128)
    assert summary['all_observed_rate_bands_vacuous']
    (output/'thresholds.json').write_text(json.dumps(finite_json(dict(summary=summary,rows=rows,cells=cells)),indent=2)+'\n')
    heads=['Model / sweep','Sampled domain','Cells · games · decisions','Expected crossing¹','Observed crossing¹',
           'Observed − expected¹','Minimum signed grid gap¹','95% threshold sets²','Inside / outside 95% sets?','Amount outside 95% sets']
    body=[]; md=['# S/T threshold comparison','', 'All ranges in normalized payoff units. Grid brackets are not confidence intervals.', '',
        '| '+' | '.join(heads)+' |','|'+'|'.join(['---']*len(heads))+'|']
    for r in rows:
        values=[f"{r['model']} · vary {r['varied_payoff']}, {r['fixed_payoff']}={num(r['fixed_value'])}",
                f"[{num(r['sampled_values'][0])}, {num(r['sampled_values'][-1])}]",
                f"{r['cells']} · {r['games']} · {r['decisions']}", bracket(r['theoretical']),bracket(r['observed']),
                bracket(r['difference']),num(r['minimum_signed_grid_gap']),
                'Obs: '+confidence_text(r['observed_95_set'])+'; theory: '+confidence_text(r['theoretical_95_set']),
                'Unresolved','N/A']
        cls='separated' if r['grid_comparison']=='separated' else ''
        body.append(f'<tr class="{cls}" data-model="{r["model_key"]}" data-axis="{r["varied_payoff"]}" data-gap="{r["grid_comparison"]}">'+''.join('<td>'+html.escape(v)+'</td>' for v in values)+'</tr>')
        md.append('| '+' | '.join(values)+' |')
    md += ['', '¹ Descriptive sample crossing brackets and gaps, not confidence intervals.',
        '² Observed threshold confidence sets and differences are unbounded, conditional on a unique monotone crossing existing. Theory retains exact dominance restrictions. Existence is not established. No informative inside/outside test is available.',
        '', 'See index.html for complete definitions, assumptions, sample coverage, and sources.']
    (output/'table.md').write_text('\n'.join(md)+'\n')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>S/T threshold comparison</title><style>
body{font:15px/1.55 system-ui,sans-serif;color:#223242;background:#f4f6f8;margin:0;padding:32px}main{max-width:1700px;margin:auto}
h1{font-size:32px;letter-spacing:-.8px;margin-bottom:6px}h2{font-size:21px}p{max-width:1050px}.eyebrow{color:#536d80;font-size:12px;letter-spacing:2px}
.notice{background:#fff1d9;border-left:4px solid #ba812c;padding:16px 22px;margin:24px 0}.stats{display:flex;gap:18px;flex-wrap:wrap}.stats span{background:white;padding:12px 18px;border-radius:6px}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:24px 0 12px}select,input{font:inherit;padding:8px;border:1px solid #b9c8d1;border-radius:5px}
.scroll{overflow:auto;max-height:72vh;background:white;border:1px solid #d3dde4}table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th{position:sticky;top:0;background:#223242;color:white;text-align:left;z-index:1}td,th{padding:13px 12px;border-bottom:1px solid #dce3e9;min-width:100px}td:first-child{min-width:220px;font-weight:600}
tr:nth-child(even){background:#f6f8fa}tr.separated td:nth-child(7){background:#ffebcd;font-weight:700}a{color:#226488}details{background:white;padding:18px 24px;margin-top:24px}summary{font-weight:650;cursor:pointer}
@media print{body{padding:0;background:white}.controls{display:none}.scroll{max-height:none;overflow:visible}table{font-size:9px}td,th{min-width:0;padding:6px}th{position:static}details{display:block}}
</style><main><div class="eyebrow">NORMALIZED PAYOFF SWEEP · R = 1, P = 0</div><h1>Expected and observed switching thresholds</h1>
<p>Each row varies one payoff and holds the other fixed. Expected behavior uses each model’s reported opponent beliefs.</p>
<div class="stats"><span><b>128</b> sweep slices</span><span><b>202</b> payoff matrices</span><span><b>1,614</b> games</span><span><b>3,228</b> decisions</span></div>
<div class="notice"><b>The grid shows descriptive differences; statistical threshold precision remains unresolved.</b><br>
Only 1–2 games per model/payoff cell. Under conservative simultaneous 95% bands, every observed threshold location remains possible.
Do not interpret separated grid brackets as statistically significant differences.</div>
<p>GRIDCOUNTS. Amber marks a nonzero minimum <em>grid</em> gap, not a confidence-interval exclusion.
<a href="table.md">Copyable Markdown table</a> · <a href="thresholds.json">All rows, cell evidence and provenance (JSON)</a></p>
<div class="controls"><label>Model <select id="model"><option value="">All four</option>MODELOPTIONS</select></label>
<label>Vary <select id="axis"><option value="">S and T</option><option>S</option><option>T</option></select></label>
<label>Grid comparison <select id="gap"><option value="">All</option><option>separated</option><option>overlap or touch</option><option>unresolved</option></select></label><span id="count">128 rows</span></div>
<div class="scroll"><table><thead><tr>HEADS</tr></thead><tbody>ROWS</tbody></table></div>
<p>¹ Sampled crossing brackets / conditional one-sided bounds, <b>not confidence intervals</b>. “Multiple / reversed” means no unique sampled threshold.
² Observed conditional 95% threshold sets and their differences from theory are (−∞,+∞). Theory retains exact dominance restrictions.
N/A means no meaningful distance outside can be resolved.</p>
<details open><summary>Definitions, statistical method and limitations</summary>METHODS</details>
<script>const filters=['model','axis','gap'];function filter(){let n=0;document.querySelectorAll('tbody tr').forEach(r=>{let show=filters.every(k=>!document.getElementById(k).value||r.dataset[k]===document.getElementById(k).value);r.hidden=!show;if(show)n++;});document.getElementById('count').textContent=n+' rows';}filters.forEach(k=>document.getElementById(k).addEventListener('change',filter));</script></main></html>'''
    page=page.replace('GRIDCOUNTS',f"{counts['separated']} separated comparisons · {counts['overlap or touch']} overlapping/touching · {counts['unresolved']} unresolved")
    page=page.replace('MODELOPTIONS',''.join(f'<option value="{k}">{v}</option>' for k,v in LABELS.items()))
    page=page.replace('HEADS',''.join('<th>'+html.escape(h)+'</th>' for h in heads)).replace('ROWS',''.join(body)).replace('METHODS',METHODS)
    (output/'index.html').write_text(page)
    print(json.dumps(summary,indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'reproduced/threshold-table')
    p.add_argument('--sources',type=Path,nargs='+',default=[ROOT/'data/attempts.jsonl.gz',ROOT/'data_pd_refinement/attempts.jsonl.gz'])
    args=p.parse_args()
    cells=build_cells(load_games(args.sources))
    render(build_rows(cells),cells,args.sources,args.output)


if __name__ == '__main__': main()
