# Release notes

## 0.5.0 — 2026-09-10

This release turns the Months 1–3 sequential oversight prototype into a
research-grade Phase 1 package with complete supported equilibrium analysis,
formal parity checks, granular observability, and committed empirical results.

### Mathematical foundation

- Replaced the two-candidate Stackelberg heuristic with a global analytic
  solver over interval endpoints, the follower threshold, the detection kink,
  and the attack-region stationary point.
- Added an explicit finite candidate certificate and stress-tested it against
  10,001-point numerical grids across 90 parameter regimes.
- Added the fully mixed equilibrium for the two-defense normal-form reduction;
  the default `(d_low=0,d_high=4,v=4)` game mixes at 80% high defense and 40%
  attack.
- Added fail-closed finiteness, sign, and domain validation to Phase 1 game
  parameters and states.

### Formal verification

- Pinned Lean 4.33.1 with a reproducible Lake project.
- Formalized the Python model's saturated detection curve, scaled human and AI
  payoffs, both threshold branches, deterministic verified agents, and finite
  stochastic draw witnesses.
- Added an executable Lean parity oracle and Python integration test covering
  detection, utilities, safety margins, and actions on the 25-point original
  grid.

### AISI Inspect observability

- Replaced the 25-case grid with 39 unique cases: 25 broad cases, five exact
  thresholds, four just-safe cases, and five just-unsafe cases.
- Added strict observable JSON worksheets, nested validation/calculation/
  decision/parsing/scoring spans, store mutations, transcript events, ground-
  truth certificates, and multidimensional calculation and action metrics.
- Added auditable Bernoulli certificates to probabilistic and PDUPOC decisions.
- Preserved malformed worksheets as behavioral data rather than silently
  repairing them; provider-private hidden chain-of-thought is not claimed.

### Executed experiments

- Committed 312 complete Inspect policy samples across eight fixed,
  stochastic, threshold, and proof-carrying policies.
- Committed 156 complete OpenRouter model samples across pinned OpenAI,
  Anthropic, Google, and Meta models. The factorial audit found no missing or
  duplicate cells and no failed provider runs.
- Overall model action validity was 98.72%, utility-optimal choice was 85.90%,
  and strict worksheet validity was 77.56%. Only 65% of local threshold
  triplets showed the complete expected safe-to-unsafe behavioral transition.
- Added machine-readable audits, slice summaries, transition records, error
  cases, flat CSV tables, and SHA-256 manifests.

### Reproducibility and publication

- Added a one-command validation entrypoint covering 128 tests, analysis
  reproduction, artifact integrity, the Lean build, and Python–Lean parity.
- Added a cross-platform `uv.lock` resolving all Python dependencies for frozen
  environment reproduction.
- Added a ready GitHub Actions workflow template. Activating it under
  `.github/workflows/` requires a GitHub credential with workflow scope.
- Added a full Phase 1 research report and updated the blog deliverable into a
  publication-ready manuscript with the executed findings and limitations.
- Added machine-readable citation metadata for the software and datasets.

### Limits

- Model results use one temperature-zero call per cell and are descriptive,
  not estimates of sampling variance or stable provider rankings.
- Payoffs and state parameters are synthetic rather than incident-calibrated.
- The Lean layer proves payoff and threshold-policy parity, not the floating-
  point implementation of the continuous optimizer.
- External blog publication still requires a venue selected by the project
  owner.

## 0.4.0 — 2026-09-10

This release adds two complete coordination-failure games, integrates them
through every research layer, and commits two audited cross-provider model-play
matrices.

### Complete game families

- Generalized the normal-form engine from symmetric games to validated
  asymmetric two-player, two-action games while retaining strict symmetry
  validation as a subtype.
- Added Stag Hunt with payoff- and risk-dominant equilibria, exact assurance
  belief thresholds, risk-dominance margins, action-dominance thresholds,
  mixed-strategy miscoordination, and catastrophe probability.
- Added Battle of the Sexes with opposed player preferences, both pure
  equilibria, role-specific mixed strategies, focal-action belief thresholds,
  concession compensation, coordination probability, and catastrophe risk.
- Added concrete cross-lab containment and incident-response protocol scenarios
  with complete matrices, actors, stakes, interventions, and catastrophic
  profiles.

### Uncertainty and mechanism design

- Added three latent exploit-severity states to each new scenario, preserving
  Stag Hunt ordering and Battle payoff asymmetry in every state.
- Generalized expected-game, decision, mechanism, institution, repeated-play,
  tournament, CLI, and mixed-strategy code to asymmetric games.
- Added neutral coordination subsidies and a shared family-aware treatment
  design: mutual safety for Prisoner's Dilemma, fair anti-coordination for
  Chicken, payoff-dominant assurance for Stag Hunt, and balanced equilibrium
  selection for Battle of the Sexes.
- Added replicate-indexed Battle focal targets for counterbalanced multi-
  replicate runs and used a fair private mediator distribution over both
  coordinated equilibria.

### AISI Inspect observability

- Expanded the canonical best-response dataset from 32 to 64 probes and the
  uncertainty/mechanism oracle from 96 to 192 cases.
- Expanded true-model play to all four game families and added family-neutral
  opponent-action beliefs.
- Added coordination, miscoordination, structural success, first/second action
  rates, utilitarian and egalitarian optimality, welfare regret, player regret,
  equilibrium, catastrophe, mediation, communication, and confidence metrics.
- Every sample retains isolated role prompts, provider outputs, exposed
  reasoning blocks, declared worksheets, payoff states, treatment transforms,
  parser decisions, random draws, nested spans, store events, transcript events,
  and scores. Provider-private hidden chain of thought is not claimed.

### Executed experiments

- Committed complete 192-game naturalistic and 192-game individual-expected-
  utility matrices across 16 ordered OpenAI, Anthropic, Google, and Meta pairs,
  two new games, and six mechanisms.
- The offline audit found 384 valid joint actions, no missing or duplicate
  factorial cells, and no failed ordered pairs.
- Binding commitment achieved 100% structural success in both conditions;
  trusted mediation achieved 100% and 93.75%. Unstructured communication
  achieved 37.50% and 25.00%, exposing the difference between cheap talk and a
  shared equilibrium-selection device.
- Added machine-readable comparison output and a full research report with
  per-game mechanism interactions, interpretation, observability, and limits.

### Validation and limitations

- Expanded the unit suite to 109 tests covering asymmetric games, uncertainty,
  mechanisms, runners, Inspect datasets, and outcome analysis.
- Both executed matrices use one deterministic replicate per cell, so results
  are descriptive rather than inferential.
- Gemini signed-reasoning envelopes sometimes omit the text field expected by
  Inspect's OpenRouter parser. Final outputs, worksheets, actions, and scores
  remained complete and passed the offline audit.

## 0.3.0 — 2026-09-05

This release completes the uncertainty and rich-mechanism work for the two
implemented AI-safety games and adds executed, auditable true-model play.

### Utility uncertainty

- Added exact finite distributions over three latent payoff states for the
  frontier deployment Prisoner's Dilemma and autonomous escalation Chicken.
- Added state/action joint beliefs, asymmetric action beliefs, Bayesian signal
  updates, information gain, and imperfect monitoring.
- Added expected-value, mean-variance, CARA, lower-tail CVaR, maximin, and
  prospect-value decision criteria.
- Added ambiguity-robust decisions and numerical risk-adjusted utility-threshold
  solving.

### Institutional mechanisms

- Added enforceable commitments, probabilistic penalty contracts, false
  positives, enforcement draws, budget-balanced transfers, and externally
  funded cooperation subsidies.
- Added simultaneous cheap talk, decaying soft-evidence Beta reputations,
  trusted private mediation, and complete correlated-equilibrium obedience
  checks.
- Added seeded repeated institutional play with latent-state, monitoring,
  penalty, transfer, belief, reputation, and mediator records for every round.
- Added auditable expected and sampled resolution of fixed one-shot profiles.

### AISI Inspect observability

- Added a 96-case structured uncertainty/mechanism oracle with nested spans,
  store mutations, info events, explicit decision traces, and multidimensional
  scoring.
- Added role-isolated two-model gameplay with separate simultaneous
  communication calls, private mediator recommendations, structured observable
  decision worksheets, delayed joint resolution, and granular outcome scores.
- Added a resumable 4-by-4 OpenRouter runner covering self-play and both role
  orders of every cross-provider pair.
- Inspect records observable prompts, outputs, model events, provider-exposed
  reasoning, structured summaries, parses, calculations, and scores. The
  release does not claim access to provider-private hidden chain of thought.

### Executed experiments

- Committed a complete 192-game naturalistic matrix and a complete 192-game
  individual-expected-utility matrix across OpenAI, Anthropic, Google, and Meta
  model families.
- Both matrices contain every combination of 16 ordered model pairs, 2 games,
  and 6 mechanisms. All 384 joint actions were valid and no pair failed.
- Added a reproducible offline auditor that detects incomplete factorials,
  duplicate cells, invalid outputs, and failed pairs, and computes exact
  condition deltas.
- Added a full result report with design, mechanism accounting, empirical
  results, limitations, and reproduction commands.

### Validation and known limitations

- Expanded the unit suite across distributions, beliefs, decisions,
  institutions, simulations, Inspect tasks, gameplay, and result auditing.
- Raw Inspect logs remain untracked because they contain complete prompts and
  model outputs; committed summaries retain structured decision and resolution
  records.
- Gemini returned some signed reasoning envelopes without a text field. Inspect
  warned on those envelope fragments, while final responses, structured
  worksheets, actions, and scores remained complete.
- The committed true-model matrices use one deterministic replicate per cell;
  their results are descriptive rather than model-behavior confidence
  intervals.
