# Symmetric-game phase-space experiments

## Method and research question

Reference: Guillaume Falmagne, [The Phase Space of Symmetric 2x2 Games](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/), SIAM News, 1 October 2026.

The article is a mathematical classification, not an LLM experiment or a binary-search procedure. For R>P, a common positive affine transformation gives s=(S-P)/(R-P), t=(T-P)/(R-P), R'=1 and P'=0. The two-dimensional map distinguishes twelve strict payoff orderings, equilibrium regions, and welfare boundaries. Ties must be treated separately. In particular, asymmetric outcomes have higher total welfare than CC when S+T>2R. This restriction must not be silently excluded from Prisoner's Dilemma.

Our implementation applies that coordinate map to live model experiments. It asks whether models follow the incentives at different points and where observed behavior departs from analytical best responses. Mathematical affine invariance does not imply that LLM responses are invariant to payoff wording or scale; this study fixes one scale rather than claiming empirical invariance.

## Payoffs and scope

The normalized row payoff matrix is [[1,S],[T,0]]; the column matrix is its transpose. Strict PD is S<0,T>1. Other points are explicitly classified as other games or ties. The R=P chart is not represented. The shared game engine reports pure Nash, isolated interior symmetric mixed equilibria, and boundary continua separately. Pareto efficiency and maximin summaries explicitly concern pure profiles/actions.

This study has no institutional intervention and no latent payoff uncertainty. It is a new baseline experiment, separate from the older four-game treatment factorial. A mathematical intervention-threshold plot is not an observed model switching curve.

## Declared sampling design

- Self-play: S,T each in {-1,-0.5,0,0.5,1,1.5,2}, plus the PD refinement S in {-1,-0.75,-0.5,-0.25,-0.05}, T in {1.05,1.25,1.5,1.75,2}. Deduplication leaves 70 coordinates, including 25 strict PD coordinates. Four models and four repetitions produce 1,120 joint games / 2,240 decisions.
- Cross-play: all 12 ordered distinct-model pairings at five anchors: PD (-0.5,1.5), Stag Hunt (-0.5,0.5), Chicken (0.5,1.5), cooperation-dominant (0.5,0.5), and turn-taking-welfare PD (-0.5,2.75). Two repetitions produce 120 games / 240 decisions. This is not a full-grid cross-play study.
- Fixed opponent: q in {0.25,0.5,0.75}, S=-0.5, T centered at 1+(1-q)S/q with offsets {-0.2,-0.1,0,0.1,0.2}. Four repetitions and four models produce 240 individual decisions. These are expected-payoff decisions against a stipulated random policy, not model cross-play. These slices cross coordination/indifference boundaries, not just the strict PD region.
- Pilot calls are separate and excluded from production plots. The first pilot identified visible text before JSON and one upstream rate limit; the corrected pilot uses the production parser and provider routing.

Every agent receives only its isolated perspective and the full payoff matrix. A/B action names are counterbalanced by role and repetition. Neither action is described as morally good. The objective is explicit individual expected-utility maximization. There is no communication or history. Cell scheduling is shuffled deterministically within each repetition and interleaves models. This seed controls experiment ordering, not provider randomness.

## Models and generation controls

Exact requested OpenRouter IDs:

| Model | Pinned provider route |
|---|---|
| openai/gpt-6-astra | openai |
| anthropic/claude-fable-5.1 | anthropic |
| z-ai/glm-5.3 | z-ai/fp8 |
| qwen/qwen3.8-2.4t-a95b | alibaba |

The open-weight models are strong current GLM/Qwen candidates, not a claim of universally highest performance. Availability, canonical slugs, routing, supported parameters, and pricing are snapshotted from the public OpenRouter catalog at each live preflight. The native response preserves the returned model and provider. Aliases can still evolve.

All use reasoning effort `low` and a 4,096-token output ceiling, including reasoning. Temperature is deliberately not overridden because it is not supported consistently. Matching effort labels does not guarantee identical computation. Requested output is an action, declared belief/confidence, and a short justification. Provider-exposed reasoning stays in native Inspect logs; no claim is made to access hidden thoughts.

The parser accepts exact JSON or one unambiguous final JSON object preceded by visible text. Multiple competing decision objects are invalid. Format adherence is recorded independently from valid action extraction. Failed/truncated/invalid responses remain visible; they are never interpreted as defection or cooperation.

## Budget and restart safety

User authorization: US$100. Execution ceiling: US$90 shared by pilots and all stages, also bounded by remaining key allowance with US$1 headroom. Each call reserves a conservative maximum before dispatch. Both roles are reserved before a joint episode begins. Pending, interrupted, and unpriced calls retain their entire reservation. A file lock prevents simultaneous runners from sharing the ledger unsafely.

`phase_space_provider.py` captures the raw OpenRouter response's `usage.cost` before Inspect can replace `ModelUsage.total_cost` with a price-table estimate. Only that raw receipt releases unused reservation. Missing receipts or charges above the reservation pause the run. Routing rate caps, no provider fallback, disabled SDK/Inspect retries, and explicitly budgeted rate-limit retries prevent untracked repeat calls. At most two additional 429 attempts are made, each with its own reservation. Native retry counters may count classification of a failed request even when no SDK retry was executed.

Completed episodes are checkpointed immediately. `--resume` rejects mismatched configurations and skips completed sample IDs. Invalid attempted episodes are retained, not silently rerolled. A process failure before an episode checkpoint may require another attempt; its old reservation remains charged to the budget. This is conservative, not a guarantee of exactly-once network execution.

The first production batch exposed an HTTP-client lifecycle issue between separate Inspect `eval()` calls. The runner now recreates clients for each batch and records execution-source hashes at each start/resume. Previously attempted transport failures remain in the same dataset and are counted separately from malformed model outputs. Scheduling slots skipped after the circuit breaker trips are marked `not_attempted` in native logs and are not observations.

## Analysis and figures

Observed plots use only saved model decisions. Missing cells are gray, not interpolated. Mathematical panels are marked ANALYTICAL; model panels are marked OBSERVED. Cooperation denotes action C, not a universal optimality score across the entire phase space. Report equilibrium, regret, welfare, and validity alongside it.

Self-play has two dependent participant records per joint episode. Confidence intervals resample whole episodes rather than treating their two roles as independent. Four repetitions per cell provide exploratory uncertainty, not strong confirmatory precision. A unanimous small sample can give a zero-width bootstrap interval; this does not prove certainty. No fitted monotonic switching threshold or binary-search result is claimed.

## Commands

```bash
# Offline planning: no model inference and no key required.
python3 run_phase_space.py --plan --stage self_play --max-tokens 4096 \
  --output results/phase_space/new_plan.json

# Paid run: reads the ignored local .env; never pass a key on the command line.
python3 run_phase_space.py --live --stage self_play --replicates 4 \
  --max-tokens 4096 --max-samples 8 --batch-size 64 --budget-usd 90 \
  --output results/phase_space/self_play_01.json --log-dir logs/phase_space/self_play_01

# Add --resume only when continuing the same configuration/output.
python3 analyze_phase_space.py results/phase_space/self_play_01.json \
  --output results/phase_space/self_play_analysis.json
python3 scripts/render_phase_space_figures.py results/phase_space/self_play_01.json \
  --output-dir results/phase_space/figures_self_play

# Mathematical figures alone are explicitly distinct from live results.
python3 scripts/render_phase_space_figures.py --theory-only \
  --output-dir results/phase_space/figures_theory
```

Results are complete only when the saved run status and its planned/observed sample audit say so. Spending less than the cap is not a failure: the cap is a limit, not a target.
