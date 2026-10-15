"""Plot archived threshold-difference confidence sets; no fitting or API calls."""
from pathlib import Path
import argparse
import hashlib
import json
import math

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
MODELS = ['glm', 'qwen', 'astra', 'fable']
COLORS = {'finite': '#245E8A', 'one_sided': '#237A78', 'unbounded': '#A4A9AF'}


def draw_interval(ax, x, bounds, limit):
    """Finite endpoints have caps; infinite endpoints have outward arrows."""
    if bounds['status'] == 'empty':
        ax.plot(x, 0, marker='x', color='black', ms=7)
        return
    lo, hi = float(bounds['low']), float(bounds['high'])
    color = COLORS[bounds['status']]
    bottom = lo if math.isfinite(lo) else -limit + .08
    top = hi if math.isfinite(hi) else limit - .08
    ax.vlines(x, bottom, top, color=color, lw=1.8, zorder=3)
    for endpoint, position, marker in [(lo, bottom, 'v'), (hi, top, '^')]:
        if math.isfinite(endpoint):
            ax.plot([x-.035, x+.035], [position, position], color=color, lw=1.8, zorder=4)
        else:
            ax.plot(x, position, marker=marker, color=color, ms=5.5, zorder=4)


def render(data, out, mode):
    rows = data['rows']
    endpoints = [abs(float(r[mode]['difference'][k])) for r in rows for k in ('low', 'high')
                 if r[mode]['difference'][k] is not None and math.isfinite(float(r[mode]['difference'][k]))]
    limit = max(3., math.ceil(max(endpoints, default=0) + .25))
    plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'font.size': 14, 'axes.titlesize': 20, 'axes.labelsize': 17,
        'mathtext.fontset': 'stix', 'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 4, figsize=(23, 12.5), sharey=True)
    for row_index, axis in enumerate(['T', 'S']):
        for col, model in enumerate(MODELS):
            ax = axes[row_index, col]
            selected = sorted([r for r in rows if r['model_key'] == model and r['varied_payoff'] == axis],
                              key=lambda r: r['fixed_value'])
            assert len(selected) == 16
            for r in selected:
                draw_interval(ax, r['fixed_value'], r[mode]['difference'], limit)
            ax.axhline(0, color='#222222', ls=(0, (5, 4)), lw=1.3, zorder=2)
            ax.set_xlim(-1.12, 2.12)
            ax.set_ylim(-limit, limit)
            ax.set_xticks([r['fixed_value'] for r in selected])
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:g}'))
            ax.tick_params(axis='x', labelrotation=90, labelsize=11)
            ax.set_yticks(range(-int(limit), int(limit)+1))
            ax.set_xlabel('Fixed normalized ' + ('S' if axis == 'T' else 'T'), labelpad=10)
            if row_index == 0:
                ax.set_title(selected[0]['model'], pad=14)
            if col == 0:
                ax.set_ylabel(f'{axis} threshold: observed − theoretical\n(normalized payoff units)', labelpad=14)
            ax.spines[['top', 'right']].set_visible(False)
            ax.spines[['left', 'bottom']].set_color('#7A7A7A')
            ax.grid(axis='y', color='#ECECEC', lw=.7, zorder=0)
    handles = [Line2D([], [], color=COLORS['finite'], lw=2, marker='|', ms=10, label='Finite 95% interval'),
        Line2D([], [], color=COLORS['one_sided'], lw=2, marker='^', ms=6, label='One-sided 95% interval'),
        Line2D([], [], color=COLORS['unbounded'], lw=2, marker='^', ms=6, label='Unbounded in both directions'),
        Line2D([], [], color='#222222', lw=1.3, ls='--', label='Zero threshold difference')]
    title = ('Observed − Theoretical Thresholds: Individual 95% Confidence Intervals'
             if mode == 'individual' else
             'Observed − Theoretical Thresholds: Simultaneous 95% Confidence Intervals')
    fig.suptitle(title, fontsize=26, y=.97)
    fig.legend(handles=handles, loc='upper center', bbox_to_anchor=(.5, .925), ncol=4,
               frameon=False, fontsize=14, handlelength=2.5, columnspacing=2)
    fig.subplots_adjust(left=.075, right=.985, bottom=.11, top=.83, hspace=.48, wspace=.18)
    name = 'threshold_difference_' + mode
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(out / f'{name}.{ext}', dpi=220, facecolor='white')
    plt.close(fig)


CAPTION = '''Each panel compares observed and reported-belief theoretical 50%-cooperation crossing thresholds, holding the other normalized payoff fixed (R=1, P=0). Top row: T thresholds; bottom row: S thresholds. Intervals show observed minus theoretical threshold in normalized payoff units. Finite endpoints have caps; outward arrows indicate infinite bounds, not values at the plotted axis limits. No point estimates or midpoint estimates are plotted. All 128 comparisons appear, including unresolved comparisons. The underlying data contain 1,614 complete games and 3,228 decisions across 202 payoff matrices; slices reuse observations. Added midpoint cells cover only the PD region, not a complete 16×16 grid.

The individual-comparison figure has 6 finite, 9 one-sided and 113 fully unbounded intervals; none excludes zero. These are exploratory individual intervals, not simultaneous 95% coverage across the sweep. The companion figure applies correction across all 128 comparisons: every difference interval is unbounded. No statistically significant threshold shift is established, and equality is not established. Coverage is conditional on independent games, an ordered single population crossing, the tested design, and complete valid responses. Theory uses each decision's reported opponent belief and permits either action at an exact utility tie. Positive T displacement means cooperation persists to higher temptation; positive S displacement means more favorable S is required for cooperation. Theoretical cooperation switches do not occur inside strict PD under the own-expected-payoff benchmark. See the confidence table's METHODS.md for the derivation and limitations. No additional model calls were made.
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'threshold-confidence/threshold_confidence.json')
    parser.add_argument('--output', type=Path, default=ROOT/'reproduced/threshold-confidence-figure')
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    assert len(data['rows']) == 128
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in ['individual', 'familywise']:
        render(data, args.output, mode)
    (args.output/'CAPTION.md').write_text(CAPTION)
    (args.output/'figure_manifest.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(), comparisons=128,
        plotted_results=data['summary']['results'], additional_paid_calls=0), indent=2)+'\n')
    (args.output/'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Threshold differences with confidence intervals</title>
<style>body{max-width:1800px;margin:35px auto;padding:0 24px;font:18px/1.6 Georgia,serif;color:#252525}img{width:100%;height:auto}p{max-width:1100px}a{color:#245e8a}section{margin:35px 0}</style>
<h1>Threshold differences with confidence intervals</h1>
<p>Blue: finite intervals. Teal: one-sided bounds. Gray: unbounded in both directions. Arrows mean the interval extends to infinity. The dashed line is zero difference. No point estimates are implied.</p>
<section><img src="threshold_difference_individual.png" alt="Individual 95 percent threshold difference intervals for all four models across both sweeps">
<a href="threshold_difference_individual.png">Full-size PNG</a> · <a href="threshold_difference_individual.pdf">PDF</a> · <a href="threshold_difference_individual.svg">SVG</a></section>
<p>None of the 128 individual intervals excludes zero. After correction across all 128 comparisons, every interval is unbounded:</p>
<section><img src="threshold_difference_familywise.png" alt="Simultaneous 95 percent difference intervals, all unbounded">
<a href="threshold_difference_familywise.png">Full-size PNG</a> · <a href="threshold_difference_familywise.pdf">PDF</a> · <a href="threshold_difference_familywise.svg">SVG</a></section>
<p>'''+CAPTION.replace('\n\n', '</p><p>')+'''</p><a href="CAPTION.md">Copyable caption</a></html>''')
    print(f'Rendered both interval figures: {args.output}')


if __name__ == '__main__':
    main()
