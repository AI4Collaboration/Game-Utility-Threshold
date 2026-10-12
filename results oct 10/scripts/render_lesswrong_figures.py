"""Curate the saved scientific figures and write publication captions. No API calls."""
from pathlib import Path
import argparse
import html
import json
import shutil
import zipfile

FIGURES=[
('01_cooperation_susceptibility','14_own_payoff_cooperation','Main figure 1: response to payoff incentives',
 'Cooperation frequency across normalized payoffs',
 'Each panel shows one model in isolated, simultaneous self-play. We normalize payoffs to R=1 and P=0, varying S horizontally and T vertically on a 13×13 grid with spacing 0.25. Color is the fraction of individual C choices, averaged within valid joint games: yellow means all observed choices were C and purple means all were D. C and D are analytical labels; prompts used neutral A/B labels, reversed across two blocks. Each cell contains at most two valid games (four decisions). Dashed/red regime boundaries at S=0 and T=1 separate dominance, coordination, and anti-coordination regions. The clearer own-payoff presentation was an exploratory follow-up. Here “susceptibility” means observed response to payoff incentives, not a safety or manipulation score. Most cells are not strict Prisoner’s Dilemma; strict PD occupies S<0, T>1.'),
('02_expected_utility_deviation','23_expected_regret_heatmap','Main figure 2: deviation in utility units',
 'Expected utility lost relative to the stated-belief best response',
 'At each normalized S–T point, color measures mean expected payoff loss from the chosen action relative to the best response to that decision’s reported opponent-cooperation probability q. The cooperation advantage is Δ(q)=q(R−T)+(1−q)(S−P); loss is max(0,−Δ) after choosing C or max(0,Δ) after choosing D, divided by R−P. White indicates zero loss and deeper red larger loss, on a common scale across models. The own-payoff grid provides at most four usable decisions per cell. Either action is accepted at indifference; a dot marks a reduced count. This is a test of action–belief consistency. Reported beliefs may be inaccurate or post-hoc rationalizations. It is not a displacement of an empirical switching threshold in S–T units.'),
('03_realized_equilibrium_regret','24_realized_regret_heatmap','Main figure 3 / companion: belief-free comparison',
 'Profitable unilateral deviations in realized joint outcomes',
 'For each recorded own-payoff game, we hold the opponent’s action fixed and calculate each player’s gain from switching. The larger gain is divided by R−P, then averaged within each S–T cell. White means zero profitable unilateral deviation in the observed games; darker red indicates larger available gains. At most two valid games contribute per cell. This measure uses actual choices rather than stated beliefs. A positive realized regret can occur when players validly sample a mixed Nash equilibrium; it is not by itself a reasoning-error rate. Comparing this map with figure 2 separates internal utility consistency from stability of realized self-play outcomes.'),
('04_presentation_control','13_payoff_perspective_control','Essential control',
 'Matrix presentation substantially changes apparent cooperation',
 'The targeted exploratory control compares the same strict-PD payoff cells and first two label blocks under row/column wording and explicit “your payoff / opponent payoff” wording. Each bar contains 32 valid decisions per model and role. Qwen’s column-role C frequency changes from 31/32 to 1/32, while its row-role frequency changes from 0/32 to 2/32. The game utilities and individual-payoff objective are identical, but both payoff perspective and display order change. These observations demonstrate presentation sensitivity without isolating its cause. This control motivated the clearer-presentation grid used in figures 1–3.'),
('05_analytic_intervention_threshold','16_joint_incentive_intervention','Theory / intervention figure',
 'A joint defection cost crosses two separate incentives',
 'Analytic intervention around (T,R,P,S)=(5,3,1,0): deduct k from both defection payoffs, giving T=5−k and P=1−k. The C advantage is k−2 against C and k−1 against D. Thus k=2 makes C weakly dominant and k>2 makes it strictly dominant. Under normalization the path is s=(k−1)/(k+2), t=4/(k+2). Changing one raw payoff alone leaves one baseline defection incentive intact. This figure is an algebraic result, not a separately sampled model experiment; k is a utility cost, not API dollars.'),
('06_analytic_game_map','01_analytic_phase_space','Opening explainer / appendix',
 'The theoretical phase space of symmetric two-action games',
 'Positive affine normalization maps payoffs to s=(S−P)/(R−P) and t=(T−P)/(R−P), for R>P. This leaves two degrees of freedom and preserves expected-utility incentives. The map shows twelve strict payoff orderings, regime boundaries, and group-payoff boundaries. The repository’s (5,3,1,0) baseline is at (s,t)=(−0.5,2). It is an analytic reconstruction following Falmagne’s SIAM article; no model calls are involved.'),
('07_raw_payoff_thresholds','19_raw_payoff_theoretical_thresholds','Optional appendix: one-payoff sweeps',
 'Observed one-payoff sweeps against a fixed-belief benchmark',
 'Each panel changes only T, R, P, or S around (5,3,1,0). Colored curves show observed C frequencies from up to four valid decisions per value under the original matrix presentation. Black dashed segments are the expected-utility best response assuming q=1/2: the indifference points are T=2, R=6, P=−2, S=3, with either action optimal at equality. Gray boundaries mark changes in strategic class. The fixed-q step is one conditional benchmark, not the complete equilibrium prediction. The original presentation is known to be sensitive to player role. No binary search or empirical threshold-location fit was performed.')]


def build(analysis: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    intro=('Use figures 1 and 2 for the central empirical argument; figure 3 distinguishes belief consistency from equilibrium stability. '
           'Keep figure 4 close to the results because presentation effects are large. Figures 5 and 6 explain the utility theory; figure 7 is optional. '
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
        '- Some choices conflict with the models’ reported opponent beliefs; magnitude and frequency are separate quantities.\n'
        '- Presentation materially affects observed behavior.\n'
        '- Theoretical indifference and dominance thresholds can be calculated exactly.\n\n'
        '## Claims these figures do not establish\n\n'
        '- A precise empirical threshold shift, a universal ranking, or a general AI-safety score.\n'
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
    (output/'CAPTIONS.md').write_text('\n'.join(md))
    css='body{max-width:1100px;margin:45px auto;padding:0 24px;font:16px system-ui;line-height:1.65;color:#182334}img{width:100%;height:auto}section{margin:60px 0}h2{border-top:1px solid #ccc;padding-top:25px}a{color:#2563a5}'
    (output/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><title>LessWrong figure pack</title><style>'+css+'</style></head><body>'+''.join(body)+'</body></html>')
    (output/'figure_manifest.json').write_text(json.dumps([{'file':n,'source_figure':s,'role':r,'title':t,'caption':c} for n,s,r,t,c in FIGURES],indent=2)+'\n')
    print(f'Prepared {len(FIGURES)} publication figures in {output}')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.analysis,a.output)
