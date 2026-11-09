# Human–AI oversight lab

Run `python3 serve.py` and open <http://127.0.0.1:8765/oversight>.
The selector also opens the existing four canonical games. Defense belongs to
this oversight game; it is not silently added to their payoff tables.

## Executable rules

[`Oversight.payoff`](../gut/oversight.py) is the single payoff definition for
the UI, thresholds, equilibrium solver, and simulations. The human chooses
one of eleven defense levels: 0, 0.1, …, 1. The AI sees it, then cooperates or
attacks. All parameters are known. Defense protects a fraction of resources
and harm and enforces a deterministic penalty. It is **not** a detection
probability; there is no random attack-success event.

| Parameter | Meaning | Default |
| --- | --- | ---: |
| v | AI points per captured resource | 4 |
| r | Resources available before defense | 1 |
| a | Fixed cost to AI for every attack, even at full defense | 1 |
| p | AI penalty at full defense; actual penalty is p × d | 3 |
| b | AI reward for cooperation | 1 |
| w | Human cooperation benefit, before defense cost | 2 |
| h | Human harm from an attack at zero defense | 6 |
| c | Human full-defense cost; actual cost is c × d | 2 |

| AI action | Human payoff | AI payoff |
| --- | --- | --- |
| Cooperate | w − c d | b |
| Attack | −h(1−d) − c d | v r(1−d) − a − p d |

The penalty is not transferred to the human. Harm and penalty are separate:
a larger penalty does not itself undo harm. Cooperation benefit and attack
harm belong to alternative outcomes, not quantities added together. The HTTP
interface accepts finite nonnegative decimals up to 1000 with at most twelve
decimal places, converting them to exact fractions.

These linear functions are **our toy specification**, not a calibrated model
or a theorem from the references below. Zero residual harm at full defense is
an assumption, not a demonstrated real-world safety guarantee.

## Exact thresholds

AI cooperation advantage: `M(d) = b + a + p d − v r(1−d)`.
Positive means cooperate pays more; negative means attack pays more; zero
means both are best responses. Each threshold holds other inputs fixed:

| Input varied | Equality | Cooperation strictly preferred |
| --- | --- | --- |
| Defense d | (v r − a − b)/(v r + p) | Above root, if denominator > 0 |
| Resource value v | (b + a + p d)/(r(1−d)) | Below root, if denominator > 0 |
| Attack cost a | v r(1−d) − p d − b | Above root |
| Full-defense penalty p | (v r(1−d) − a − b)/d | Above root, if d > 0 |

Zero denominators produce constant comparisons. Negative roots are labeled
outside the domain, as are defense roots above 1. Ties do not use floating
point tolerances. Defaults give `d*=2/7`; the first available defense making
cooperation strictly better is `3/10`. The continuous curve explains the
threshold; equilibrium optimization uses only the eleven defense choices.
Changing that grid changes the game.

The 21×21 resource-value/penalty map varies only those two inputs at the chosen
defense. Cells are calculated incentives, not model observations. Threshold
roots are solved algebraically, not estimated from this grid.

## Equilibria

An AI strategy specifies its response at **every** defense, including defenses
not reached. All solver outputs concern the same observed-defense game:

* **Pure Nash:** neither player gains by changing their whole strategy alone.
  Responses at defenses not chosen may include threats the AI would not want
  to carry out. These outcomes are displayed separately.
* **Subgame-perfect Nash:** the AI best responds at every defense, and the
  human optimizes against that response plan. Every possible tie response is
  retained. These are the credible sequential outcomes.
* **Stackelberg with favorable ties:** the human commits to a defense; the AI
  best responds and, if indifferent, favors the human (strong Stackelberg
  under this pure-commitment specification).
* **Stackelberg with unfavorable ties:** the human optimizes against the least
  favorable tied AI best response at each defense. This finite grid ensures
  an optimum exists. It may differ from the favorable result.

Only pure strategies are solved. There is no hidden defense, mixed commitment,
or enumeration of randomized Nash strategies. A user-selected defense is a
conditional scenario, not necessarily an optimal human choice.

For each candidate outcome, the solver requires an AI best response at the
selected defense and collects allowable responses at every other defense
giving the human no higher payoff. Independent combinations represent every
supporting pure Nash strategy. Subgame perfection additionally requires each
response to be an AI best response. Response sets, a witness, and exact counts
avoid exponential enumeration. Tests compare the algorithm against independent
exhaustive enumeration on small games, including degenerate and tied payoffs.

## Toy simulations

* **Always cooperate:** cooperate regardless of incentives.
* **Always attack:** attack regardless of incentives.
* **Payoff maximizer:** compare exact payoffs after observing defense; an
  explicit selector resolves exact ties toward cooperation or attack.

Run once at the selected defense or once at each of the eleven levels. Rounds
are independent: no learning, memory, randomness, or LLM/API calls. Repeating
identical rounds is not additional empirical evidence. No confidence interval
is fitted to these deterministic demonstrations.

JSON/CSV exports include parameters, tie convention, actions, both payoffs,
remaining human harm, and AI regret (best payoff minus chosen payoff). They
are labeled synthetic. Input changes invalidate the displayed simulation.
These records do not claim Lean verification: the existing canonical-game
proof pipeline has not been extended to this oversight model.

## Methods references

* Ben Polak, Yale ECON 159, [Lecture 15: Backward Induction, Strategies, and
  Credible Threats](https://oyc.yale.edu/economics/econ-159/lecture-15): Nash
  outcomes versus sequentially credible responses.
* Korzhyk, Yin, Kiekintveld, Conitzer & Tambe (2011), [Stackelberg vs. Nash in
  Security Games](https://www.cs.cmu.edu/~conitzer/stackelbergJAIR11.pdf),
  JAIR 41, 297–327: leader/follower modeling and favorable follower ties.
  Their randomized commitment setting differs from our observed pure defense;
  their security-game theorems are not automatically results for our model.

This increment does not implement uncertain monitoring, incomplete information,
repeated play, learned strategies, or a new live LLM experiment.
