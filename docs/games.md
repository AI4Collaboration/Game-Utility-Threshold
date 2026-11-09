# The four starting games

These are four explicit examples, each with two players, two actions, one
round, and numerical payoffs. They share the same exact arithmetic, collector,
reporting and Lean certificate generator. They are not four separate engines.
The PD example is from the post. The other three are newly added research
setups; their synthetic demonstrations are not historical model results.

Open the local explorer at **http://127.0.0.1:8765/games** after starting
`python3 serve.py`. It shows both players' payoffs and conditional comparisons,
including exact ties. The original post calculator remains at `/`.

## Fixed starting tables

Each pair lists **row player's points, column player's points**. The first
action names a row or column; it does not mean that player moves first.

| Game | Both first action | Row first, column second | Row second, column first | Both second action |
|---|---|---|---|---|
| PD: first C, second D | (1, 1) | (−0.5, 2) | (2, −0.5) | (0, 0) |
| Stag Hunt: first C, second D | (1, 1) | (−0.5, 0.5) | (0.5, −0.5) | (0, 0) |
| Chicken: first C, second D | (1, 1) | (0.5, 1.5) | (1.5, 0.5) | (0, 0) |
| Battle of the Sexes: first X, second Y | (2, 1) | (0, 0) | (0, 0) | (1, 2) |

These convenient values are declared modeling choices, not estimates from
real populations. The symmetric games use R=1, P=0. Battle of the Sexes uses
the listed fixed point units; it is not squeezed into a shared T/R/P/S table.
We do not interpret equal numerical costs across different games as equal
real-world interventions.

**Stag Hunt:** matching pays. Both players prefer CC to DD, but choosing C
alone is worse than choosing D against D. There are two stable baseline
outcomes: CC and DD. D can be called the safer option, but this particular
example does not make its payoff constant across opponent actions.

**Chicken:** opposite actions pay. Choosing C can be interpreted as yielding;
D as insisting. The stable baseline outcomes are CD and DC. Neither player
has a single action that is best against both opponent choices. Mutual D
gives both players their lowest payoff.

**Battle of the Sexes:** both prefer matching to mismatching, but the row
player prefers XX while the column player prefers YY. Both XX and YY are
stable baseline outcomes. X is not cooperation, and Y is not defection.
The historical name describes conflicting preferences, not a claim about sex
or gender; the prompts use neutral A/B labels and numerical tables only.

These response patterns follow the standard distinction between coordination
and opposing-action games; see Ben Polak's [Yale lecture on Nash equilibrium](https://oyc.yale.edu/economics/econ-159/lecture-5),
[Battle of the Sexes](https://oyc.yale.edu/economics/econ-159/lecture-6), and
[Hawk–Dove / Chicken](https://oyc.yale.edu/economics/econ-159/lecture-12).
Our chosen numbers and cost sweeps are explicitly our own design choices.

## One varying quantity

Keep each starting table fixed. Subtract z only from the payoff of a player
who chooses the **second** action. This is the defection cost in PD, a cost on
D in Stag Hunt and Chicken, and a cost on **Y** in Battle of the Sexes.
It is one shared experimental control, even though it updates several cells.
The table is never normalized again after applying the cost.

In Battle of the Sexes this deliberately favors coordination on X. It is
not a neutral coordination aid: it penalizes the column player's preferred
baseline agreement. Interpret effects and each player's payoff separately.

| Game/player | Tie against first action | Tie against second action |
|---|---:|---:|
| PD, either player | 1 | 0.5 |
| Stag Hunt, either player | −0.5 | 0.5 |
| Chicken, either player | 0.5 | −0.5 |
| Battle of the Sexes, row | −2 | 1 |
| Battle of the Sexes, column | −1 | 2 |

Negative tie costs lie outside this nonnegative-cost experiment. In Stag Hunt,
C is already better against C at zero cost. In Chicken, C is already better
against D. For both examples, above 0.5 C is strictly better against either
opponent action. At 0.5 the remaining comparison is tied.

In Battle of the Sexes, the row player prefers X against either action above
1, and the column player does so above 2. At equality the relevant comparison
ties. YY remains a stable outcome at z=1, but disappears immediately above
1. XX is stable at every nonnegative cost. Stability does not predict actual
play, and the explorer lists only pure outcomes, not mixed-strategy equilibria.

## Collect, summarize, and check

Use the [same protocol and audit rules as PD](experiments.md). Change only
`--game` when creating a new plan:

```sh
python3 experiment.py plan runs/stag-demo --game stag_hunt
python3 experiment.py run runs/stag-demo
python3 experiment.py report runs/stag-demo --plot
python3 experiment.py proofs runs/stag-demo --check
```

Other identifiers are `pd`, `chicken`, and `battle_of_sexes`. For live runs,
add the explicit model/provider settings when planning and use the live switch
and call limit when collecting, as described in the experiment guide.

Stag Hunt and Chicken use the PD cost schedule, which samples tightly around
0.5. Battle of the Sexes uses 0, 0.5, 0.95, 1, 1.05, 1.5, 1.95, 2, 2.05,
2.25, sampling both players' positive thresholds. All have two label mappings
and the same default pilot size. Label changes do not exchange player roles
or preferences. Each player's prompt presents **their own payoff first**.

For all games, the report includes joint outcomes, each player's first-action
rate, matching rate, and each player's average adjusted payoff. Rates and
means give equal weight to the two label blocks. The same game-level
uncertainty formula applies to each rate separately. Average payoffs are
descriptive means, not confidence bounds. Reported `missing_lower/upper`
bound the average first-action fraction in the full planned sample.

For PD, Stag Hunt and Chicken, `cooperation.png` plots the rate of C. For
Battle of the Sexes, `outcomes.png` shows row-X, column-X and matching rates;
`cooperation_rate` is deliberately null. The exact joint outcome counts
distinguish XX from YY and do not pool the conflicting preferences.

The proof mapper uses the correct role-specific payoff table. Every valid
choice gets both conditional comparisons, even if its partner's response is
invalid. Ties and unfavorable findings are retained. A hindsight best-response
failure is not proof of irrationality under uncertainty about the opponent.

This is a shared, tested starting framework. New live experiments, empirical
threshold estimates, prompt robustness, mixed-strategy analysis and broader
game families remain future work.
