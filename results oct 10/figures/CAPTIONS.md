# Figures for a LessWrong post on payoff incentives

Four figures: use figures 1 and 2 for the empirical results, figure 3 to explain the theoretical game regions, and figure 4 to show the presentation effect that motivated the clearer-payoff experiment. “Susceptibility” is operationalized here as response to payoff incentives. These are descriptive data with few repeats per cell, not universal model rankings.

The full experiment contains 10,096 calls / 5,048 paired simulations (including pilots and controls), with 10,066 valid decisions and 5,021 fully valid joint outcomes. The own-payoff grid used in the lead figures has 2,704 calls and 1,350 fully valid games across two blocks. Total accounted API cost was $40.4406, including a $0.045349425 reserve for one unreturned request. No new calls were made for this figure set.

The data were collected on 2026-10-09 UTC. “results oct 10” is the requested repository folder name.

Scientific basis: [Falmagne, The Phase Space of Symmetric 2×2 Games](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/). The article gives an analytic classification; the LLM experiment is our extension.

## Claims these figures support

- Choices change across the payoff landscape under the specified individual-utility objective.
- Some choices conflict with the models’ reported opponent beliefs; magnitude and frequency are separate quantities.
- Presentation materially affects observed behavior.
- Theoretical indifference and dominance thresholds can be calculated exactly.

## Claims these figures do not establish

- A precise empirical threshold shift, a universal ranking, or a general AI-safety score.
- That higher C frequency always means better reasoning or higher joint welfare.
- That disagreement with one mixed-equilibrium branch is irrational.
- That reported beliefs are truthful or faithfully describe the reasoning process.

## Main figure 1: response to payoff incentives

**Cooperation frequency across normalized payoffs**

Each panel shows one model in isolated, simultaneous self-play. We normalize payoffs to R=1 and P=0, varying S horizontally and T vertically on a 13×13 grid with spacing 0.25. Color is the fraction of individual C choices, averaged within valid joint games: yellow means all observed choices were C and purple means all were D. C and D are analytical labels; prompts used neutral A/B labels, reversed across two blocks. Each cell contains at most two valid games (four decisions). Dashed/red regime boundaries at S=0 and T=1 separate dominance, coordination, and anti-coordination regions. The clearer own-payoff presentation was an exploratory follow-up. Here “susceptibility” means observed response to payoff incentives, not a safety or manipulation score. Most cells are not strict Prisoner’s Dilemma; strict PD occupies S<0, T>1.

![Cooperation frequency across normalized payoffs](01_cooperation_susceptibility.png)

[PNG](01_cooperation_susceptibility.png) · [Editable SVG](01_cooperation_susceptibility.svg)

## Main figure 2: deviation in utility units

**Expected utility lost relative to the stated-belief best response**

At each normalized S–T point, color measures mean expected payoff loss from the chosen action relative to the best response to that decision’s reported opponent-cooperation probability q. The cooperation advantage is Δ(q)=q(R−T)+(1−q)(S−P); loss is max(0,−Δ) after choosing C or max(0,Δ) after choosing D, divided by R−P. White indicates zero loss and deeper red larger loss, on a common scale across models. The own-payoff grid provides at most four usable decisions per cell. Either action is accepted at indifference; a dot marks a reduced count. This is a test of action–belief consistency. Reported beliefs may be inaccurate or post-hoc rationalizations. It is not a displacement of an empirical switching threshold in S–T units.

![Expected utility lost relative to the stated-belief best response](02_expected_utility_deviation.png)

[PNG](02_expected_utility_deviation.png) · [Editable SVG](02_expected_utility_deviation.svg)

## Figure 3: theoretical context

**The theoretical phase space of symmetric two-action games**

Positive affine normalization maps payoffs to s=(S−P)/(R−P) and t=(T−P)/(R−P), for R>P. This leaves two degrees of freedom and preserves expected-utility incentives. The map shows twelve strict payoff orderings, regime boundaries, and group-payoff boundaries. The repository’s (5,3,1,0) baseline is at (s,t)=(−0.5,2). It is an analytic reconstruction following Falmagne’s SIAM article; no model calls are involved.

![The theoretical phase space of symmetric two-action games](03_analytic_game_map.png)

[PNG](03_analytic_game_map.png) · [Editable SVG](03_analytic_game_map.svg)

## Figure 4: presentation control

**Matrix presentation substantially changes apparent cooperation**

The targeted exploratory control compares the same strict-PD payoff cells and first two label blocks under row/column wording and explicit “your payoff / opponent payoff” wording. Each bar contains 32 valid decisions per model and role. Qwen’s column-role C frequency changes from 31/32 to 1/32, while its row-role frequency changes from 0/32 to 2/32. The game utilities and individual-payoff objective are identical, but both payoff perspective and display order change. These observations demonstrate presentation sensitivity without isolating its cause. This control motivated the clearer-presentation grid used in figures 1 and 2.

![Matrix presentation substantially changes apparent cooperation](04_presentation_control.png)

[PNG](04_presentation_control.png) · [Editable SVG](04_presentation_control.svg)
