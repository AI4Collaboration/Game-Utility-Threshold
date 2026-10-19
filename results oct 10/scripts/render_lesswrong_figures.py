"""Curate the saved scientific figures and write publication captions. No API calls."""
from pathlib import Path
import argparse
import html
import json
import shutil

FIGURES = [('01_cooperation_susceptibility',
  '14_own_payoff_cooperation',
  'Main figure 1: response to payoff incentives',
  'How LLM Cooperation Changes Across Strategic Incentives',
  'Each panel shows one model in isolated, simultaneous self-play. We normalize payoffs to R=1 and P=0, '
  'varying S horizontally and T vertically on a 13×13 grid with spacing 0.25. Color is the fraction of '
  'individual C choices, averaged within valid joint games: green means all observed choices were C and '
  'red means all were D, with cream at 0.50. Each cell is labeled with its observed cooperation proportion '
  'from 0.00 to 1.00; defection is one minus that proportion. '
  'Both axes label every tested value, at 0.25 intervals; no interpolation or new trials were used. '
  'C and D are analytical labels; prompts used neutral A/B labels, reversed across '
  'two blocks. Each cell contains at most two valid games (four decisions). GLM at (S,T)=(0.25,1.25) '
  'and Fable at (0.25,1) each have only one valid game. Regime boundaries at '
  'S=0 and T=1 are shown as bright yellow lines with thin dark outlines; they separate dominance, coordination, '
  'and anti-coordination regions. For legibility, these guides are shifted outward by half a grid step to the nearest '
  'cell edges, outlining the strict-PD cells S<0 and T>1 without bisecting sampled cells. The clearer own-payoff '
  'presentation was an exploratory follow-up. Here “susceptibility” means observed response to payoff '
  'incentives, not a safety or manipulation score. Most cells are not strict Prisoner’s Dilemma; strict PD '
  'occupies S<0, T>1.'),
 ('02_cooperation_deviation',
  '27_cooperation_deviation',
  'Main figure 2: signed cooperation deviation',
  'Cooperation above or below reported-belief best-response predictions',
  'The same 1,350 complete valid games as Figure 1 are shown: GLM 337, Qwen 338, Astra 338, Fable 337 (2,700 decisions). At each normalized S–T cell, theory uses each decision’s reported opponent cooperation belief q and the own-payoff margin Δ=q(1−T)+(1−q)S. Positive Δ favors C, negative Δ favors D, and indifference permits either action. Thus the theoretical aggregate C-rate lies between the fraction strictly preferring C and the fraction not strictly preferring D. Color is 100 times the observed C-rate minus the nearest point in this permitted range: red means excess cooperation, blue means less cooperation, white means aggregate compatibility. For example, +50 means 50 percentage points more cooperation than the upper theoretical bound. White does not establish individual best-response consistency because opposing deviations can cancel. The full signed difference range is exported in threshold_cells.csv. This is a descriptive cooperation-rate deviation map conditional on reported beliefs, not a unique equilibrium prediction, payoff regret, a threshold displacement estimate, or a significance test. It illustrates behavior around utility thresholds but cannot by itself establish how far a threshold moved. Each cell contains at most four decisions; the dashed S=0 and T=1 lines mark strategic regime boundaries. The separate threshold renderer and threshold_displacements.csv retain direct crossing-bracket comparisons for both sweep directions. No new API calls were made.'),
 ('03_analytic_game_map',
  '01_analytic_phase_space',
  'Figure 3: theoretical context',
  'The theoretical phase space of symmetric two-action games',
  'Positive affine normalization maps payoffs to s=(S−P)/(R−P) and t=(T−P)/(R−P), for R>P. This leaves two '
  'degrees of freedom and preserves expected-utility incentives. The map shows twelve strict payoff '
  'orderings, regime boundaries, and group-payoff boundaries. The repository’s (5,3,1,0) baseline is at '
  '(s,t)=(−0.5,2). It is an analytic reconstruction following Falmagne’s SIAM article; no model calls are '
  'involved.'),
 ('04_presentation_control',
  '13_payoff_perspective_control',
  'Figure 4: presentation control',
  'Matrix presentation substantially changes apparent cooperation',
  'The targeted exploratory control compares the same strict-PD payoff cells and first two label blocks '
  'under row/column wording and explicit “your payoff / opponent payoff” wording. Each bar contains 32 valid '
  'decisions per model and role. Qwen’s column-role C frequency changes from 31/32 to 1/32, while its '
  'row-role frequency changes from 0/32 to 2/32. The game utilities and individual-payoff objective are '
  'identical, but both payoff perspective and display order change. These observations demonstrate '
  'presentation sensitivity without isolating its cause. This control motivated the clearer-presentation '
  'grid used in figures 1 and 2.')]


def build(analysis: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    # Remove only obsolete figures recorded by an earlier run of this curator.
    previous = output / 'figure_manifest.json'
    if previous.exists():
        keep = {row[0] for row in FIGURES}
        for row in json.loads(previous.read_text()):
            name = row['file']
            if name not in keep and Path(name).name == name:
                for suffix in ('.png', '.svg'):
                    (output / (name + suffix)).unlink(missing_ok=True)
    intro=('Four figures: use figures 1 and 2 for the empirical results, figure 3 to explain the theoretical game regions, '
           'and figure 4 to show the presentation effect that motivated the clearer-payoff experiment. '
           '“Susceptibility” is operationalized here as response to payoff incentives. These are descriptive data with few repeats per cell, not universal model rankings.')
    md=['# Figures for a LessWrong post on payoff incentives\n',intro+'\n',
        'The full experiment contains 10,096 calls / 5,048 paired simulations (including pilots and controls), with 10,066 valid decisions and 5,021 fully valid joint outcomes. '
        'The own-payoff grid used in the lead figures has 2,704 calls and 1,350 fully valid games across two blocks. '
        'Total accounted API cost was $40.4406, including a $0.045349425 reserve for one unreturned request. No new calls were made for this figure set.\n',
        'The data were collected on 2026-10-09 UTC. “results oct 10” is the requested repository folder name.\n',
        'Scientific basis: [Falmagne, The Phase Space of Symmetric 2×2 Games](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/). '
        'The article gives an analytic classification; the LLM experiment is our extension.\n',
        '## Claims these figures support\n\n'
        '- Choices change across the payoff landscape under the specified individual-utility objective.\n'
        '- Aggregate cooperation can differ from conditional best-response predictions under reported beliefs.\n'
        '- Presentation materially affects observed behavior.\n'
        '- Theoretical indifference and dominance thresholds can be calculated exactly.\n\n'
        '## Claims these figures do not establish\n\n'
        '- Precise population switching thresholds, statistically significant threshold shifts, a universal ranking, or a general AI-safety score.\n'
        '- That higher C frequency always means better reasoning or higher joint welfare.\n'
        '- That disagreement with one mixed-equilibrium branch is irrational.\n'
        '- That reported beliefs are truthful or faithfully describe the reasoning process.\n']
    body=['<h1>Figures for the post</h1><p>'+html.escape(intro)+'</p>',
          '<p><a href="CAPTIONS.md">Copy-ready captions and methodological limits</a></p>']
    for name,source,role,title,caption in FIGURES:
        for suffix in ['.png','.svg']:
            shutil.copy2(analysis/(source+suffix),output/(name+suffix))
        md.append(f'## {role}\n\n**{title}**\n\n{caption}\n\n![{title}]({name}.png)\n\n[PNG]({name}.png) · [Editable SVG]({name}.svg)\n')
        body.append(f'<section><h2>{html.escape(role)}</h2><h3>{html.escape(title)}</h3>'
                    f'<p>{html.escape(caption)}</p><p><a href="{name}.png">PNG</a> · <a href="{name}.svg">SVG</a></p>'
                    f'<img loading="lazy" src="{name}.png" alt="{html.escape(title)}"></section>')
    for filename in ('threshold_displacements.csv', 'threshold_cells.csv', 'threshold_displacement_summary.json'):
        shutil.copy2(analysis/filename, output/filename)
    md.append('## Threshold data\n\n[All 104 sweep slices and crossing brackets](threshold_displacements.csv) · [Cell counts, theoretical ranges, and source IDs](threshold_cells.csv)\n')
    body.append('<p><a href="threshold_displacements.csv">Threshold brackets and differences (CSV)</a> · <a href="threshold_cells.csv">Source cell values (CSV)</a></p>')
    (output/'CAPTIONS.md').write_text('\n'.join(md))
    css='body{max-width:1100px;margin:45px auto;padding:0 24px;font:16px system-ui;line-height:1.65;color:#182334}img{width:100%;height:auto}section{margin:60px 0}h2{border-top:1px solid #ccc;padding-top:25px}a{color:#2563a5}'
    (output/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>LessWrong figure pack</title><style>'+css+'</style></head><body>'+''.join(body)+'</body></html>')
    (output/'figure_manifest.json').write_text(json.dumps([{'file':n,'source_figure':s,'role':r,'title':t,'caption':c} for n,s,r,t,c in FIGURES],indent=2)+'\n')
    print(f'Prepared {len(FIGURES)} publication figures in {output}')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.analysis,a.output)
