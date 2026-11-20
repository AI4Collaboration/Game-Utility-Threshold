# Game catalogue

[Home](../README.md) · [Methods](../docs/README.md) · [Data and results](../data/README.md)

Use this directory as the entry point for every game. Implementations stay in
`gut/` and `web/` so shared calculations are not copied into separate engines.
**Points are chosen toy rewards, not measured real-world benefits or harms.**

**The four controlled cost studies have not been validated with live LLM data.** Evidence entries
below describe earlier studies or software checks, not completed validation of
the controlled design. [Current milestone assessment](../docs/controlled-thresholds.md#aisi-status-all-three-stages-remain-open).

Resource control, Lab Notebook Audit and the earlier science demo are removed.
Off-switch remains requested, but a faithful published experimental setup is not
yet implemented. Every game must meet the [same source standard](../docs/design-sources.md).

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
  The UI cost favors X; the v2 collector also tests a cost on X favoring Y.
  Report each direction and player separately.

## Separate Design 1 extensions: private PD and Stag Hunt

**New games; the four base experiments above are preserved.** Row has a fixed
public reward table. Column knows its own low/high reward profile; row sees the
actual profile only in the revealed condition. The hidden condition uses the
same actual rewards, with a public 50/50 prior. Only the cost of D is swept.

- [Interactive page](https://ai4collaboration.github.io/Game-Utility-Threshold/private-games.html).
- IDs: `private_pd_v1` (column's temptation reward is private) and
  `private_stag_hunt_v1` (column's loss from cooperating alone is private).
- [Rules, source, module map and commands](../gut/incomplete/README.md).
- Runner: [private_games.py](../private_games.py); native Inspect and independent
  game logic live in [gut/incomplete/](../gut/incomplete/).
- Predictions retain all pure/mixed equilibrium regions and exact dominance
  thresholds. A single observed action is not an equilibrium test.
- Evidence: synthetic checks only. [Engine tests](../tests/test_incomplete.py),
  [Inspect tests](../tests/test_incomplete_inspect.py), [UI/export checks](../tests/check_private_games.cjs).

## Audit game: known and hidden rewards

**One published game family, two information settings.** The defender commits
to checking A with probability `q` and B with probability `1-q`; exactly one
check happens. The attacker sees those chances and chooses A, B, or abstention.
A detected violation receives the fixed punishment. In the hidden setting,
only the attacker knows which reward profile it has; the defender knows all
possible profiles and their probabilities.

- [Play both settings](https://ai4collaboration.github.io/Game-Utility-Threshold/audit.html).
- Rules: the two-target, fixed-punishment subcase of
  [Blocki et al., *Audit Games*, §2](https://arxiv.org/abs/1303.0356), including
  abstention. Private types use the Bayesian commitment structure of
  [Paruchuri et al. (AAMAS 2008)](https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf).
  Our demo numbers and finite-type extension are explicit adaptations.
- Code: [audit_game.py](../gut/audit_game.py), [exact commitment solver](../gut/commitment.py);
  browser [engine](../web/audit-engine.js), [page](../web/audit.html), [controls](../web/audit.js).
- Predictions: per-type action payoffs, exact checking thresholds, all-type
  deterrence intervals and optimal checking policies under both tie conventions.
  Punishment is fixed per game; this is not the full source algorithm or DOBSS.
- Inspect: [task and scorer](../gut/audit_inspect.py), [offline runner](../audit_experiment.py).
  Separate player prompts, explicit model roles, native `.eval` traces, exact
  payoff scoring and a JSONL export. Invalid responses and provider failures
  remain visible. Provider-exposed reasoning is logged, not treated as proof
  of internal reasoning. The CLI is mock-only; live tasks require a separately
  budgeted study (the adapter's cost limit is per sample, not a total-run cap).
- Checks: [rules/solver](../tests/test_audit_game.py), [native Inspect round-trip](../tests/test_audit_inspect.py),
  [Python/browser agreement and UI](../tests/check_audit.cjs). **Synthetic checks only; no live LLM validation.**

From the repository root, install `python3 -m pip install '.[inspect]'`, run
`python3 audit_experiment.py runs/audit-check --study information`, then
`inspect view --log-dir runs/audit-check`. Replace `hidden` with `known` for the
control setting. `--baseline maximize|abstain|target_a|target_b` chooses a scripted
agent. Samples cover every type and checking condition; aggregate with the
declared type probabilities rather than assuming the balanced sample is a
population draw. Browser rounds are separate, local simulations.

## Human–AI oversight

**Custom prototype; not an approved paper experiment.** Its specific rules are
ours. New paid collection is blocked, and default study suites exclude it.
[Published-design review required](../docs/design-sources.md).

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

## Off-switch: in scope, implementation pending

The requirement is a faithful published experimental setup, not removal of the
game family. The previous custom implementation is inactive; its two-state
reward model, symmetric human-error rule and consultation fee were adaptations.
The original [Off-Switch Game](https://arxiv.org/abs/1611.08219) provides a
mathematical model and simulations, not a ready-made LLM collection protocol.
No current runnable off-switch game or retained live off-switch dataset exists.

Before new model collection, read the [implemented controlled setup](../docs/controlled-thresholds.md) and its remaining live-study requirements. The [parameterization audit](../docs/sweep-design.md) records the rationale.

## What to change where

- **Rules/payoffs:** edit the source linked above, its specification and affected
  tests together. Canonical/oversight Python and browser calculations have agreement checks.
- **Appearance/interactions:** edit the linked HTML, controller and styles in `web/`.
- **Study design:** update the relevant protocol before collecting. Keep a frozen
  plan, raw responses, exclusions and settings for each new real run.
- **Evidence:** consult [data/](../data/README.md); a successful toy run is not an LLM finding.
- **Publication:** [build_site.py](../build_site.py) has an explicit file allowlist;
  adding a local page does not automatically publish it.
