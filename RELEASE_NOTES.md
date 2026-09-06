# Release notes

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
