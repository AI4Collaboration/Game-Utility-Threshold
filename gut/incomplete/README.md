# Design 1: separate private-payoff experiments

These are **new versioned games**, not replacements for `gut/canonical.py`.
The four base games, their collectors and historical datasets remain separate.

| ID | Public row rewards | Column's private parameter |
| --- | --- | --- |
| `private_pd_v1` | R=1, P=0, T=2, S=-1/2 | T is 7/4 or 9/4; other entries equal row's |
| `private_stag_hunt_v1` | R=1, P=0, T=1/2, S=-1/2 | S is -3/4 or -1/4; other entries equal row's |

Each column profile has probability 1/2. Low/high refer to the numerical
parameter, not model capability. All starting profiles preserve their base game
inequalities. Column knows its own profile; row knows its own fixed rewards.
Neither sees the other's action. The information rules are common knowledge.

**Intervention:** subtract public cost `z` from each D chooser's own payoff.
Sweep `z`, keeping the profiles, prior and payoff units fixed. This intentionally
changes final incentives; it is not a sweep of the starting payoff parameters.
At each cost/profile, run both revealed and hidden conditions with identical
reward tables. Revealed gives row the actual column profile; hidden gives row
only the possibilities and probabilities. There is no mean-table replacement.

## Code and commands

- `games.py`: immutable specifications, visibility boundaries, thresholds and scores.
- `solver.py`: complete exact equilibrium sets for one public player and finite
  private column types. Includes pure, mixed, tied and continuous solution sets.
- `inspect_task.py`: fresh isolated model histories, explicit roles, shuffled
  matched conditions, two action-label mappings crossed independently with two table orders, native events and strict scoring.
- `report.py`: cells and paired contrasts, validity counts, per-profile 2D plots.
- `../../private_games.py`: mock-only runner and deterministic UI-theory export.

From the repository root:

```sh
python -m pip install '.[inspect,figures]'
python private_games.py run runs/private-check --game all --figures
inspect view --log-dir runs/private-check/logs
python private_games.py export web/private-games.json
```

Use `--game private_pd_v1` or `--game private_stag_hunt_v1` independently.
`--baseline equilibrium|always_c|always_d|uniform` selects scripted behavior.
The equilibrium script chooses the first representative policy; that selection
is arbitrary, and is not a claim about LLM equilibrium selection. Output folders
must be new. Native logs, `observations.jsonl`, `cells.csv`, `pairs.csv` and
`summary.json` retain condition identities and errors. Figures are synthetic
when their inputs are synthetic. The default single repetition checks software;
it is not sufficient for empirical threshold estimation.

## Interpretation and source

For each known own payoff table, the largest conditional cost threshold gives
the bound above which C strictly beats D against either action. Hiding the
opponent's private reward does not change that bound. Belief-dependent behavior
in between the bounds is represented by the entire Bayesian equilibrium set;
we do not assign one universally correct action there or score hindsight regret
as a reasoning error. Individual actions do not establish an empirical equilibrium.

This is an independent finite-private-values adaptation of
[Harsanyi (1967–68)](https://doi.org/10.1287/mnsc.14.3.159).
Our numbers, intervention grid and LLM interface are not a reproduction of that
paper's experimental protocol. The runner makes no live model calls. The native
task API accepts explicit model roles with a per-sample cost limit, but a live
study still needs its frozen sampling/repetition choices and total budget control.
Noisy signals, private row rewards, Chicken and Battle of the Sexes extensions
are not implemented. The existing canonical versions of all four remain runnable.
