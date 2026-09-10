# Release notes

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
