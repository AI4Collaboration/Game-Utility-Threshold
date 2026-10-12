# Payoff phase-space experiment

## Scientific basis

Guillaume Falmagne's [SIAM News article (1 October 2026)](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/)
is an analytic classification, not a binary-search algorithm or an LLM experiment.
It removes translation and positive-scale freedom from symmetric 2x2 payoff
matrices, fixes R > P through action relabeling, and maps twelve strict payoff
orderings in an (S,T) plane. It overlays Nash, Pareto, maximin, and group-payoff
properties. The linked extended OSF v3 preprint could not be retrieved in this
session; this implementation is based on the supplied SIAM article.

Our coordinate implementation is

    s = (S-P)/(R-P), t = (T-P)/(R-P), R' = 1, P' = 0.

The repository baseline (T,R,P,S)=(5,3,1,0) maps to (s,t)=(-0.5,2).
The chart requires R>P. We do not silently relabel a raw sweep when it crosses
R=P: that chart is singular. The one-parameter ranges retain R>P.

## Derived checks used in this experiment

For belief q that the counterpart selects C:

    U(C)-U(D) = q(R-T) + (1-q)(S-P).

The four strict best-response regimes are:

| Condition | Regime |
|---|---|
| T>R, S<P | D dominant (strict Prisoner's Dilemma when T>R>P>S) |
| T<R, S>P | C dominant |
| T<R, S<P | Coordination |
| T>R, S>P | Anti-coordination |

Equalities receive explicit boundary labels. The payoff-order classifier also
handles all other payoff ties. The general `SymmetricTwoByTwoGame` engine
computes pure equilibria, fully mixed interior equilibria, Pareto efficiency,
and social optima. Fully mixed cooperation is (P-S)/(P-S+R-T) when interior.
The maximum unilateral defection incentive is max(T-R,P-S,0). Crossing that
cost gives weak C dominance; strict dominance requires a strict inequality.

From the original baseline, one-coordinate changes cannot make C dominant:
changing T or R fixes only R-T, while changing S or P fixes only S-P. The
existing competitive-action cost k changes T to 5-k and P to 1-k together.
It reaches weak C dominance at k=2 and strict C dominance for k>2. Its
normalized path is s=(k-1)/(k+2), t=4/(k+2). The intervention figure is an
analytic derivation, not another paid model experiment.

Mutual cooperation has group payoff 2R; asymmetric profiles have S+T. Thus
T>R>P>S alone does not imply that CC maximizes total payoff. The new module
allows the S+T>2R subregion rather than deleting it as a malformed dilemma.
Pure-action maximin is reported separately from mixed-strategy maximin.

## Design

- Primary experiment: normalized s,t in {-1,-0.75,...,2}, a 13x13 grid.
- Every cell has isolated row and column calls to the same model, resolved as
  one simultaneous self-play game. This experiment does not test cross-play.
- Four exact model IDs: `z-ai/glm-5.3`, `qwen/qwen3.8-2.4t-a95b`,
  `openai/gpt-6-astra`, `anthropic/claude-fable-5.1`.
- GLM and Qwen are selected as current open-weight flagships from their
  respective families, not claimed to be a universally established top-two
  ranking. Model cards: [GLM](https://huggingface.co/zai-org/GLM-5.3),
  [Qwen](https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B).
- Objective: maximize own numerical expected payoff. No communication,
  latent payoff state, intervention, repeated interaction, or social framing.
  These controls isolate the effect of changing payoffs.
- Prompts use A/B, not game-family names or morally loaded action names.
  C/D are internal analytic labels. Their A/B mapping reverses in alternating
  replicate blocks. Matrix display order reverses between roles.
- Cell order is deterministically shuffled within blocks. Each role call is
  a fresh context. No opponent answer or identity is shown before resolution.
- Common reasoning request: low; common main-run output allowance: 4096
  tokens including reasoning. Provider default temperature is retained
  because both frontier endpoints do not advertise temperature support.
  Seed is sent only where advertised; exact settings and returned models are
  retained per request. Provider reasoning implementations are not identical.
- Pilot: four archetypal points. The initial 1024-token pilot truncated three
  of 32 answers; it remains in the data but is excluded from main-run plots.
- Secondary raw-payoff sweeps vary each of T,R,P,S independently around
  (5,3,1,0), including the baseline and exact incentive crossing. Ranges:
  T [-1,7], R [1.5,8], P [-3,2.5], S [-2,4]. These ranges include both
  the strategic-class crossing and the q=1/2 indifference point. They were
  fixed before any raw-payoff sweep calls.
- Affine controls repeat six anchor games under u, 2u+1, 10u, and u+10.
  Analytic invariance is guaranteed; empirical model invariance is measured.

An exploratory perspective control was added after observing role differences
in the first grid. It repeats the 16 strict-PD cells and four other anchor
cells, showing exactly the same symmetric game as `your action / opponent
action` and `your payoff / opponent payoff`. Both roles receive the same
matrix order. It changes representation, not utilities. Its matched
comparison uses the same grid cells and replicate indices; it is not an
independent, prospectively specified confirmation of the initial finding.

The targeted control showed a large change in column-role PD choices, so we
extended the own-payoff presentation to the entire 13x13 grid in two additional
blocks (2,704 calls). These exploratory blocks retain the same utilities,
objective, output allowance, and alternating label mappings. They are reported
separately from the original four grid blocks. The representation change also
removes the role-dependent display ordering, so it does not isolate which
presentation component caused the difference.

The final number of completed blocks is recorded in the output manifests and
report. All phases share a $50 cap. Do not infer completeness from the design:
check manifest job IDs against actual records.

## Why a grid first

The analytic boundaries are known exactly, so binary search is unnecessary for
the game-theory oracle. Model responses may be stochastic or nonmonotonic. A
binary search that assumes a single switch can produce a spurious threshold.
The grid measures the shape first. The raw sweeps and fixed-s/fixed-t transects
then show directional changes. An observed switch is a bracket between sampled
values, not an exact threshold or fitted phase transition.

## Outcomes and interpretation

Retain valid-action rate, C frequency, CC/DD frequency, pure Nash outcomes,
Pareto-efficient outcomes, welfare-optimal outcomes, total payoff, and each
role's unilateral deviation regret. Regret and comparative welfare are scaled
by R-P for comparison across raw-payoff sweeps. We also check whether choices
maximize utility under the model's declared opponent belief.

An outcome need not be a pure Nash equilibrium even if both players correctly
sample an interior mixed equilibrium. Conversely, matching a pure equilibrium
does not establish a calibrated stochastic strategy. The experiment elicits
actions and beliefs, not an explicit equilibrium distribution. Do not label
all non-Nash realized profiles reasoning failures.

Invalid/failed outputs are recorded and excluded from outcome averages, with
coverage shown explicitly. No text fallback guesses the final action. No
catastrophe metric is assigned to these abstract payoff matrices: a low payoff
alone does not define an AI catastrophe. The study has few observations per
cell; pooled metrics are descriptive over this fixed design. Hosted endpoint
drift, provider defaults, and within-game dependence limit generalization.

## Reproduction and artifacts

From the repository root, install the existing environment and plotting extra.
Provide `OPENROUTER_API_KEY` through the environment or an ignored local .env.
Download the public OpenRouter `/api/v1/models` catalog to a JSON file and pass
its path with `--catalog`. Keep it for model/pricing provenance.

    python run_phase_space.py grid --replicate 0 --max-tokens 4096 \
      --output /absolute/path/to/experiment --catalog /path/to/models.json --budget 50
    python run_phase_space.py transects --replicate 0 --max-tokens 4096 \
      --output /absolute/path/to/experiment --catalog /path/to/models.json --budget 50
    python run_phase_space.py affine --replicate 0 --max-tokens 4096 \
      --output /absolute/path/to/experiment --catalog /path/to/models.json --budget 50
    python run_phase_space.py perspective_grid --replicate 0 --max-tokens 4096 \
      --output /absolute/path/to/experiment --catalog /path/to/models.json --budget 50
    python run_phase_space.py summarize --output /absolute/path/to/experiment
    python scripts/render_phase_space.py --output /absolute/path/to/experiment
    python -m unittest tests.test_phase_space

Use another replicate index for another block; reuse an index only to resume
identical settings. No automatic retries erase failures. The direct HTTP
runner records raw JSONL traces rather than native Inspect logs; this is an
explicit cost-controlled extension, reusing the repository's analytic engine.

`ledger.json` reserves cost before requests using provider price ceilings,
conservative prompt-token bounds, and the entire output allowance. Reported
cost replaces reservations on success. Unknown costs retain reservations.
Outstanding reservations survive crashes. A filesystem lock prevents two
local runners sharing a budget concurrently. Existing key/account settings
are not modified. All paid phases, including pilots, share the ledger.

One GLM call in the first affine block stalled for several minutes despite
the HTTP read timeout. The worker was terminated with only that call pending.
Its record is explicitly `abandoned_timeout`, with no response, no action,
unknown start time, and an intended request reconstructed from its saved
manifest. Its entire reservation remains charged in budget accounting. The
record is not a model completion. Subsequent workers use an absolute
180-second timeout as well as the HTTP timeout. Unknown costs must not be
reported as zero spend.

## Per-decision comparison with theory

Run `python scripts/compare_phase_space_theory.py --output /path/to/experiment`
to compare every recorded decision with expected-utility best responses and
every joint outcome with Nash and welfare benchmarks. This is offline analysis
and makes no API calls. It exports `theory_decisions.csv`,
`theory_simulations.csv`, eight PNG/SVG figures, and a separate theory report.
The original request log and cost ledger are checked for unchanged hashes.

The fixed-belief q=1/2 raw cutoffs are T=2, R=6, P=-2, S=3. They are distinct
from the strategic-class boundaries T=3, R=5, P=0, S=1. Each decision also gets
payoff cutoffs conditional on its own stated belief, with endpoint cases and
exact indifference handled explicitly. Regret uses normalized payoff units.
Self-reported beliefs are not assumed calibrated or faithful accounts of model
reasoning. The symmetric interior mixed equilibrium is one benchmark among
several possible equilibria; its predicted rate is not a unique target.

Figures 22–24 map deviation across S and T using the own-payoff grid. They
report the fraction of choices violating the stated-belief best response,
mean expected payoff loss under that belief, and mean maximum unilateral
realized regret per game. All gaps use R−P units. Indifference accepts either
action, missing outcomes are excluded, and reduced denominators are marked.
`deviation_heatmap_cells.csv` preserves cell counts and source request IDs.


## Publication threshold-displacement figure

`render_threshold_displacement.py` adds an offline analysis of the own-payoff grid.
It compares observed C-majority crossings with majority crossings in the
best-response choices implied by each decision's reported opponent belief.
The same valid action/belief samples contribute to both curves. At exact
indifference either action is admissible; no forced tie-breaking is used.

For every fixed S, scan T upward; for every fixed T, scan S upward. A single
expected-direction majority crossing is bracketed by adjacent decisive samples,
allowing intervening ties. Subtract theoretical bracket [Lt,Ut] from observed
bracket [Lo,Uo] to obtain displacement range [Lo-Ut,Uo-Lt]. No point estimate
or interpolation is used. Multiple/reversed crossings are marked, and absence
of a bracket can produce a conditional one-sided bound or an unresolved result.
A one-sided bound assumes a single-switch continuation; a threshold need not
exist beyond the measured range.

Across 104 slices there are 48 two-sided comparisons, 16 one-sided bounds,
13 multiple/reversed cases and 27 unresolved cases. The 2,700 usable decisions from 1,350 fully valid paired games
are reused between perpendicular slices; slices are not independent. The bars
are descriptive grid-resolution ranges, not statistical confidence intervals.
This is a comparison conditional on reported beliefs, which vary with payoffs,
not a unique equilibrium prediction. No additional API calls or binary search
were performed. CSV exports retain both crossing brackets and source cell IDs.

The boundary-map output places observed (black) and theoretical (pink) T-crossing brackets on the original S–T cooperation heatmap. It uses exactly Figure 1’s complete-game cohort (337/338/338/337 games by GLM/Qwen/Astra/Fable), excluding the two individually valid decisions whose partners were invalid. All included decisions have usable beliefs. Brackets are slightly offset horizontally only for visibility. The renderer also saves the detailed displacement diagram for both sweep directions; the curated gallery retains four figures.

## Signed cooperation-deviation publication heatmap

The curated second figure is now `27_cooperation_deviation`. For observed C
frequency p and theoretical admissible interval [a,b], color is
100*(p - min(max(p,a),b)), in percentage points. Here a is the strict-C fraction
and b includes indifferent decisions. The CSV also records the full signed
range [100*(p-b),100*(p-a)]. Positive means excess C, negative means less C.
Zero is only aggregate compatibility; individual errors can cancel. This map
shows behavioral deviation around utility thresholds, not a measured shift
in threshold location. The direct threshold plots remain reproducible and
their slice data remain in the four-figure publication gallery.
