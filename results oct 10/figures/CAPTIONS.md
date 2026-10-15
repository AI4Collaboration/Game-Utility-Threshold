# Figures for a LessWrong post on payoff incentives

Four figures: use figures 1 and 2 for the empirical results, figure 3 to explain the theoretical game regions, and figure 4 to show the presentation effect that motivated the clearer-payoff experiment. “Susceptibility” is operationalized here as response to payoff incentives. These are descriptive data with few repeats per cell, not universal model rankings.

The full experiment contains 10,096 calls / 5,048 paired simulations (including pilots and controls), with 10,066 valid decisions and 5,021 fully valid joint outcomes. The own-payoff grid used in the lead figures has 2,704 calls and 1,350 fully valid games across two blocks. Total accounted API cost was $40.4406, including a $0.045349425 reserve for one unreturned request. No new calls were made for this figure set.

The data were collected on 2026-10-09 UTC. “results oct 10” is the requested repository folder name.

Scientific basis: [Falmagne, The Phase Space of Symmetric 2×2 Games](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/). The article gives an analytic classification; the LLM experiment is our extension.

## Claims these figures support

- Choices change across the payoff landscape under the specified individual-utility objective.
- Aggregate cooperation can differ from conditional best-response predictions under reported beliefs.
- Presentation materially affects observed behavior.
- Theoretical indifference and dominance thresholds can be calculated exactly.

## Claims these figures do not establish

- Precise population switching thresholds, statistically significant threshold shifts, a universal ranking, or a general AI-safety score.
- That higher C frequency always means better reasoning or higher joint welfare.
- That disagreement with one mixed-equilibrium branch is irrational.
- That reported beliefs are truthful or faithfully describe the reasoning process.

## Main figure 1: response to payoff incentives

**How LLM Cooperation Changes Across Strategic Incentives**

Each panel shows one model in isolated, simultaneous self-play. We normalize payoffs to R=1 and P=0, varying S horizontally and T vertically on a 13×13 grid with spacing 0.25. Color is the fraction of individual C choices, averaged within valid joint games: green means all observed choices were C and red means all were D, with yellow at 0.50. Each cell is labeled with its observed cooperation proportion from 0.00 to 1.00; defection is one minus that proportion. Both axes label every tested value, at 0.25 intervals; no interpolation or new trials were used. C and D are analytical labels; prompts used neutral A/B labels, reversed across two blocks. Each cell contains at most two valid games (four decisions). GLM at (S,T)=(0.25,1.25) and Fable at (0.25,1) each have only one valid game. Regime boundaries at S=0 and T=1 separate dominance, coordination, and anti-coordination regions. The clearer own-payoff presentation was an exploratory follow-up. Here “susceptibility” means observed response to payoff incentives, not a safety or manipulation score. Most cells are not strict Prisoner’s Dilemma; strict PD occupies S<0, T>1.

![How LLM Cooperation Changes Across Strategic Incentives](01_cooperation_susceptibility.png)

[PNG](01_cooperation_susceptibility.png) · [Editable SVG](01_cooperation_susceptibility.svg)

## Main figure 2: signed cooperation deviation

**Cooperation above or below reported-belief best-response predictions**

The same 1,350 complete valid games as Figure 1 are shown: GLM 337, Qwen 338, Astra 338, Fable 337 (2,700 decisions). At each normalized S–T cell, theory uses each decision’s reported opponent cooperation belief q and the own-payoff margin Δ=q(1−T)+(1−q)S. Positive Δ favors C, negative Δ favors D, and indifference permits either action. Thus the theoretical aggregate C-rate lies between the fraction strictly preferring C and the fraction not strictly preferring D. Color is 100 times the observed C-rate minus the nearest point in this permitted range: red means excess cooperation, blue means less cooperation, white means aggregate compatibility. For example, +50 means 50 percentage points more cooperation than the upper theoretical bound. White does not establish individual best-response consistency because opposing deviations can cancel. The full signed difference range is exported in threshold_cells.csv. This is a descriptive cooperation-rate deviation map conditional on reported beliefs, not a unique equilibrium prediction, payoff regret, a threshold displacement estimate, or a significance test. It illustrates behavior around utility thresholds but cannot by itself establish how far a threshold moved. Each cell contains at most four decisions; the dashed S=0 and T=1 lines mark strategic regime boundaries. The separate threshold renderer and threshold_displacements.csv retain direct crossing-bracket comparisons for both sweep directions. No new API calls were made.

![Cooperation above or below reported-belief best-response predictions](02_cooperation_deviation.png)

[PNG](02_cooperation_deviation.png) · [Editable SVG](02_cooperation_deviation.svg)

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

## Threshold data

[All 104 sweep slices and crossing brackets](threshold_displacements.csv) · [Cell counts, theoretical ranges, and source IDs](threshold_cells.csv)
