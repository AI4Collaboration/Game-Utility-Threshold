# Resource control under uncertain incentives

This application addresses **Months 3–5: incomplete information and safety
margins**. It extends the known-payoff oversight game with a private AI resource
value. All calculations and trial records are synthetic. There are no live LLM
calls, human study, training, or new empirical results.

`web/uncertainty-engine.js` is the sole definition for the browser and Node
benchmark. It reuses the original `Oversight` payoffs and exact fractions in
`web/game-engine.js`. Reduced rational arithmetic determines every preference,
threshold and tie; decimal values are display coordinates only. This model has not been formalized in Lean.

## Play on the public UI

[Resource control](https://ai4collaboration.github.io/Game-Utility-Threshold/resource-control.html)
explains the players, information and incentives, updates live payoff plots,
and exports complete toy runs. Choose defense and play to reveal the resource
type. Downloads retain the completed run’s settings even after controls change.
Only the latest completed round or batch is exported; practice interactions are
not a controlled human study. Browser data is inspectable, not a secure
hidden-state benchmark. No session is uploaded.

## Resource control: the human does not know the AI's incentive

1. Nature draws low or high resource value. Only the AI observes its type.
2. The human commits to observed defense d, from 0, 0.1, …, 1.
3. The AI chooses cooperate or attack after seeing d.
4. Both receive the original oversight payoffs; defense is paid either way.

| Action | Human payoff | AI payoff |
| --- | --- | --- |
| Cooperate | w − c d | b |
| Attack | −h(1−d) − c d | v r(1−d) − a − p d |

Defaults: low v=4, high v=8; r=1, a=1, p=3, b=1, w=2, h=6, c=2.
The human assumes high-type probability 1/2, with an uncertainty interval
[1/4,3/4]. The evaluator's actual probability is separately configurable.
Changing actual probability never changes the uninformed human's decision.
The AI knows its v and all payoff rules. The human knows both possible v
values and the rules, but not which type was drawn. The analyst has full access.

This is a two-point utility distribution, not arbitrary unknown objectives.
Defense is the original deterministic protection/penalty variable, **not a
detection probability**. Attack probability measures choice, not residual harm:
an always-attacking agent at full defense attacks but causes zero modeled harm.

The cooperation margin is M_v(d)=b+a+pd−vr(1−d). At default payoffs the roots
are 2/7 and 6/11, with first strictly cooperative grid choices 0.3 and 0.6.
The UI reports both types, the minimum margin, the additional defense needed
for strict cooperation by both, and the remaining tolerance to higher v at
the selected defense. A zero denominator has no finite value crossing.
An exact tie retains both actions; it is never labeled strict deterrence.

### Three decision references

- **Best average outcome:** enumerate all 11 defenses and maximize expected
  human payoff under the assumed prior, anticipating each type's best response.
  Report separate favorable and unfavorable HUMAN-payoff tie conventions and
  every maximizing defense. This is a pure-commitment Bayesian Stackelberg
  calculation; it is not an enumeration of all Bayesian Nash equilibria.
- **Cautious protection:** among defenses whose worst attack probability over
  the prior interval is at most the chosen risk limit, minimize defense cost.
  Agent ties count as attacks. Retain all cheapest choices; simulations choose
  the smallest defense among ties. No feasible defense is reported explicitly.
- **Fully informed reference:** reveal the type before the human chooses;
  separately maximize the human payoff for each type using unfavorable ties.
  This has extra information and is not an implementable hidden-type policy.

Expected quantities are affine in the prior, so interval extrema are exactly
at its endpoints. The cautious bound assumes payoff-maximizing agents and the
specified two-type support. It does not cover always-attack agents or larger
unmodeled resource values. With a correct prior the average policy recovers
the old deterministic model when the two types coincide. With misspecification,
the evaluation reports actual outcomes without allowing the planner to see
that actual prior. The margin across both types is independent of the prior;
the risk-constrained policy is a different criterion and may allow rare attacks.

### Where the resource game design came from

We constructed this game by extending the existing oversight model with two
private resource values and uncertainty about how often each occurs. It is
not a reproduction of a published paperclip-maximizer environment. “Paperclip”
is an informal motivation for valuing resources; the implementation has no
production process, long-term accumulation, learning, or autonomous planning.

The traceable methodological reference is Korzhyk et al. (2011),
[Stackelberg vs. Nash in Security Games](https://www.cs.cmu.edu/~conitzer/stackelbergJAIR11.pdf).
It was cited in the
[original oversight specification](https://github.com/AI4Collaboration/Game-Utility-Threshold/blob/d661e9f/docs/oversight.md#methods-references),
before the
[resource extension](https://github.com/AI4Collaboration/Game-Utility-Threshold/commit/d2d539d).
It supplies background for defender commitment, an observing follower's best
response, and favorable follower ties. Its randomized security setting differs
from our observed, discrete protection choice; its theorems do not automatically
apply here. The original guide also cites
[Polak's backward-induction lecture](https://oyc.yale.edu/economics/econ-159/lecture-15).

Our design choices are the linear resource/attack/penalty functions, eleven
protection levels, values 4 and 8, their probabilities, and the cautious risk
criterion. We chose these to make the uncertainty and comparisons explicit,
then derived thresholds from those assumptions. The original extension does
not document a separate literature source for the two-type specification.
These parameters are not empirically calibrated, and the results do not yet
establish a realistic model of AI resource-seeking behavior.

## Offline benchmark and records

Requires Node 18+; no packages or API keys. From the repository:

```sh
node tests/check_uncertainty.cjs
node uncertainty-experiment.cjs resource runs/resource-example
```

An optional third argument is a JSON file with `config` overrides and optional
`simulation` settings (`rounds`, `seed`, `tie`). Use finite decimals, not fraction
strings. Unknown fields and invalid inputs fail. Default is 200 trials per
baseline, seed 42. The resource benchmark crosses three agent policies
(maximize payoff, always cooperate, always attack) with four defense policies
(manual, average, cautious, informed). Infeasible cautious policies are recorded
as unavailable, rather than silently omitted or replaced. Benchmark planners
still assume maximization when tested against non-maximizing baselines.

`benchmark.json` retains configuration, exact analysis, every trial, summaries,
all policies, seed/generator version, commit, dirty-tree status and source hashes.
`summary.csv` compares baselines and `curve.csv` supplies separate 2D plot data.
Files are created in a new directory; existing outputs are never overwritten.
Seeds use Mulberry32 with rational rejection sampling. Replay is deterministic;
this is a toy generator, not a cryptographic or empirical sampling guarantee.
Fixed-round frequencies should be compared to exact expectations and must not
be represented as LLM validation. The GUI exposes the same simulation engine.

Tests independently enumerate finite outcomes, verify interval extrema and
degenerate cases, preserve ties, check known-payoff recovery and information
boundaries, and reproduce seeded trials. New paid/model experiments, empirical
uncertainty estimates, general distribution families, live Lab Notebook Audit validation, and the Months 3–5 blog remain separate work.

## Controlled response study

The versioned `oversight_experiment.py --design resource` planner/collector
now supports 22 imposed-defense conditions: 11 defenses separately for each
known-to-AI value type. It reuses the exact oversight payoffs and four neutral
label/order blocks. [Setup and scope](controlled-thresholds.md) distinguish this
conditional-response study from the Node human-planning benchmark above.
No new live resource responses have been collected.
