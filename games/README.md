# Game catalogue

[Home](../README.md) · [Methods](../docs/README.md) · [Data and results](../data/README.md)

Use this directory as the entry point for every game. Implementations stay in
`gut/` and `web/` so shared calculations are not copied into separate engines.
**Points are chosen toy rewards, not measured real-world benefits or harms.**

## Four simultaneous games

Two players choose without seeing the other's choice. The table specifies
both players' points. We keep a starting table fixed and vary one cost on the
second action. A threshold depends on what the other player does; a single
universal cooperation threshold is not assumed.

All four share these files:

| Need | Location |
| --- | --- |
| Fixed tables, game IDs and exact comparisons | [gut/canonical.py](../gut/canonical.py) |
| Original symmetric-game arithmetic and normalization | [gut/game.py](../gut/game.py) |
| Browser calculations and selector | [game-engine.js](../web/game-engine.js), [games.html](../web/games.html) |
| Plan, collect, report | [experiment.py](../experiment.py), [gut/experiment.py](../gut/experiment.py) |
| Recorded-choice proof mapping | [gut/proofs.py](../gut/proofs.py), [Lean guide](../lean/README.md) |
| Checks | [test_canonical.py](../tests/test_canonical.py), [test_game.py](../tests/test_game.py), [test_experiment.py](../tests/test_experiment.py), [browser agreement](../tests/check_browser_engine.cjs) |
| Exact tables and study design | [Four-game rules](../docs/games.md), [cost-study protocol](../docs/experiments.md) |

### Prisoner's Dilemma

**Choice:** cooperate or defect. Defection initially earns more regardless of
the other player's choice, although both would gain by cooperating together.
**Question:** how much added defection cost changes those incentives?

- ID: `pd`; [play PD](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=pd).
- The [original explorer](../web/index.html) also varies the symmetric table.
- Evidence: PD settings appear in the [retained payoff grid](../docs/post-study.md).
  The fixed-PD cost intervention has an implemented collector, but no new live run.

### Stag Hunt

**Choice:** attempt cooperation or choose the less demanding option. Mutual
cooperation gives the better joint outcome, but cooperating alone is costly.
**Question:** can a cost on the second action remove that reason to avoid cooperation?

- ID: `stag_hunt`; [play Stag Hunt](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=stag_hunt).
- Evidence: Stag Hunt settings appear in the retained grid. The separate fixed-table
  cost study has only synthetic pipeline checks.

### Chicken

**Choice:** yield or insist. Each wants the other to yield; both insisting is
worst for both. **Question:** when does a cost on insisting make yielding
better against either choice?

- ID: `chicken`; [play Chicken](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=chicken).
- Evidence: Chicken settings appear in the retained grid. The separate fixed-table
  cost study has only synthetic pipeline checks.

### Battle of the Sexes

**Choice:** X or Y. Both prefer agreeing to disagreeing, but one prefers X and
the other Y. **Question:** how does a cost on Y change coordination and each
player's points? X/Y do not mean cooperation/defection here.

- ID: `battle_of_sexes`; [play the coordination game](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=battle_of_sexes).
- Evidence: exact calculations and synthetic checks; no retained live model study.
  The cost favors X, so report each player's outcomes separately.

## Human–AI oversight

The human first buys protection. The AI sees that choice and cooperates for a
fixed reward or attacks for resources. Protection reduces captured resources
and harm, and adds an AI penalty. It is **not a probability of detecting an attack**.
We calculate when cooperation pays more and how a human anticipating the AI's
response would choose protection.

- [Play oversight](https://ai4collaboration.github.io/Game-Utility-Threshold/oversight.html) · [Rules and solvers](../docs/oversight.md).
- Code: [gut/oversight.py](../gut/oversight.py); browser [game-engine.js](../web/game-engine.js), [oversight.html](../web/oversight.html), [oversight.js](../web/oversight.js).
- Collection/analysis: [oversight_experiment.py](../oversight_experiment.py), [collector](../gut/oversight_experiment.py), [report](../gut/oversight_report.py).
- Checks: [payoffs/solvers](../tests/test_oversight.py), [collector](../tests/test_oversight_experiment.py), [data](../tests/test_oversight_data.py), [report](../tests/test_oversight_report.py), [UI](../tests/check_oversight_ui.cjs).
- Evidence: [3,660 main decisions plus 12 pilot decisions](../docs/oversight-validation-results.md).
  Fixed human protection was tested; empirical two-sided equilibrium play was not.

## Resource control

This extends oversight by making the AI's resource value private: resources
are worth either 4 or 8 points per unit to it. The human knows the possibilities,
but not the drawn type. We compare protection chosen for the expected outcome
with protection chosen to limit attack risk under uncertain type frequencies.
“Paperclip/resource maximizer” is an informal motivation; the game does not
simulate manufacturing, long-term accumulation, or an autonomous planning agent.

- [Play resource control](https://ai4collaboration.github.io/Game-Utility-Threshold/resource-control.html) · [Rules](../docs/uncertainty-games.md#resource-control-the-human-does-not-know-the-ais-incentive) · [Design provenance](../docs/uncertainty-games.md#where-the-resource-game-design-came-from).
- Code: [uncertainty-engine.js](../web/uncertainty-engine.js), reusing [game-engine.js](../web/game-engine.js).
- UI: [resource-control.html](../web/resource-control.html), shared [uncertainty.js](../web/uncertainty.js) and [styles](../web/uncertainty.css).
- Runner: [uncertainty-experiment.cjs](../uncertainty-experiment.cjs), with `resource` as its game argument.
- Checks: [engine/baselines](../tests/check_uncertainty.cjs), [UI](../tests/check_uncertainty_ui.cjs).
- Evidence: exact calculations and synthetic trials only; no live LLM study or Lean proof.

## Off-switch

The AI is unsure whether an action benefits or harms the human. It can proceed,
stop, or ask a human whose judgment sometimes fails. The AI and human share the
same objective. We calculate when asking pays more, including consultation
cost and uncertainty about human accuracy.

- [Play off-switch](https://ai4collaboration.github.io/Game-Utility-Threshold/off-switch.html) · [Rules and source paper](../docs/uncertainty-games.md#off-switch-the-ai-is-uncertain-about-what-benefits-the-human).
- Code: the same [uncertainty-engine.js](../web/uncertainty-engine.js); UI [off-switch.html](../web/off-switch.html) and [uncertainty.js](../web/uncertainty.js).
- Runner: [uncertainty-experiment.cjs](../uncertainty-experiment.cjs), with `off-switch` as its argument.
- Checks: [engine/baselines](../tests/check_uncertainty.cjs), [UI](../tests/check_uncertainty_ui.cjs).
- Evidence: synthetic only. Payoffs are compared against a fixed noisy-human rule;
  this is not a general solver for two strategic players. No Lean proof.

## Science audit demo

A simulated research agent may inflate one of eight readings. A reviewer
inspects a limited sample; the human accepts or returns the report. More
inspection or a larger penalty can make accurate reporting pay more.

- [Play the demo](https://ai4collaboration.github.io/Game-Utility-Threshold/science.html) · [Rules](../docs/science-game.md).
- Code/UI: [science-engine.js](../web/science-engine.js), [science.html](../web/science.html), [science.js](../web/science.js), [styles](../web/science.css).
- Records: browser session JSON export; no separate live collector.
- Checks: [check_science.cjs](../tests/check_science.cjs).
- Evidence: illustrative simulation only. For one altered reading, perfect sampled
  checking detects the flaw with probability `k/8`, where `k` is the number inspected.

## Lab Notebook Audit

The research prototype replaces inflated readings with **selective reporting**:
swap an eligible low-scoring run for an ineligible better-scoring run. The
reviewer sees only the submitted report, rules and sampled original records.
An independent evaluator knows the complete truth. The proposed study measures
review errors first, then tests reporting choices under those measured incentives.

- [Explore the environment](https://ai4collaboration.github.io/Game-Utility-Threshold/lab-design.html) · [Rules, protocol and remaining steps](../docs/lab-audit-protocol.md).
- Source of truth: [gut/lab_audit.py](../gut/lab_audit.py); offline study [gut/lab_experiment.py](../gut/lab_experiment.py).
- UI: [lab-design.html](../web/lab-design.html), [lab-design.js](../web/lab-design.js), [fixed examples](../web/lab-examples.json).
- Runner: [lab_experiment.py](../lab_experiment.py).
- Checks: [environment](../tests/test_lab_audit.py), [study](../tests/test_lab_experiment.py), [UI/examples](../tests/check_lab_design.cjs).
- Evidence: offline pilot only; paid model adapter and live collection remain.
  A swap leaves two possible witnesses, so detection is `1 − C(6,k)/C(8,k)`,
  where `C(n,k)` counts subsets. Do not reuse the older demo's `k/8` rule.

## What to change where

- **Rules/payoffs:** edit the source linked above, its specification and affected
  tests together. Canonical/oversight Python and browser calculations have agreement checks.
- **Appearance/interactions:** edit the linked HTML, controller and styles in `web/`.
- **Study design:** update the relevant protocol before collecting. Keep a frozen
  plan, raw responses, exclusions and settings for each new real run.
- **Evidence:** consult [data/](../data/README.md); a successful toy run is not an LLM finding.
- **Publication:** [build_site.py](../build_site.py) has an explicit file allowlist;
  adding a local page does not automatically publish it.
