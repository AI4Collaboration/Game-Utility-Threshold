# Resource control and the off-switch game

These are the first two applications for **Months 3–5: incomplete information
and safety margins**. They extend the known-payoff oversight game and add a
separate shutdown game. All calculations and trial records are synthetic.
There are no live LLM calls, human study, training, or new empirical results.

`web/uncertainty-engine.js` is the sole definition for the browser and Node
benchmark. It reuses the original `Oversight` payoffs and exact fractions in
`web/game-engine.js`. Reduced rational arithmetic determines every preference,
threshold and tie; decimal values are display coordinates only. Neither new
model has been formalized in Lean.

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

## Off-switch: the AI is uncertain about what benefits the human

This is a finite, two-state adaptation of Hadfield-Menell et al. (2017),
[The Off-Switch Game](https://ijcai.org/proceedings/2017/32), particularly
Sections 2–4. It preserves a shared human/AI objective and a human judgment
that depends on the true utility. It does not model an adversarial reward
function or simply rename attack as disabling a switch.

Nature selects a beneficial action worth +G or a harmful action worth −L.
The AI knows its prior theta, not the state. It chooses:

- **Proceed:** act immediately without consulting the human.
- **Stop:** do nothing, receiving zero.
- **Defer:** pay consultation cost C and let the human allow or stop the action.

The human observes the state, but the modeled decision is correct with
probability q in either state: allow a good action with probability q; stop a
bad action with probability q. This symmetric error rule is our simple
specification, not the paper's Boltzmann human policy. Consultation cost is
also our extension (default zero). Each error is independently modeled per
round. The human's rule is fixed, not solved as a freely optimizing player.

Writing A=theta G and B=(1−theta)L, the AI's expected payoffs are:

- Proceed: A−B.
- Stop: 0.
- Defer: qA−(1−q)B−C.

Defer beats both alternatives iff q > [max(A−B,0)+B+C]/(A+B), provided A+B>0.
If the root exceeds one, strict deferral cannot be achieved. If A+B=0, there
is no crossing: deferral ties when C=0, otherwise it loses. At zero cost a
perfectly informed, correct human makes deferral weakly best. An uninformative
50/50 human cannot make it strictly best. No claim that more uncertainty always
improves welfare follows; doing nothing can also avoid harm while losing benefits.

Defaults: G=4, L=6, theta=1/2, q=0.9, C=0. Payoffs are −1, 0, and 1.5;
deferral ties stopping at q=3/5. This is an exact Bayesian decision comparison
against a specified human policy, **not a general Nash/Stackelberg solver**.

The robustness check varies theta over a specified interval and allows q to
fall by a chosen amount. The deferral advantage over the better alternative
is concave in theta and increasing in q, so its minimum occurs at a prior
endpoint and the lowest allowed q. We report that minimum, the exact required
accuracy across endpoints, and whether strict deferral is possible at all.
At default interval [1/4,3/4] and accuracy slack 0.1, the worst margin is −0.1:
central preference for deferral is not robust over that whole set.

Actual good-state probability and human accuracy are separate evaluation
settings. The AI's action uses only its assumed quantities. Metrics include
harmful execution, beneficial action blocked, welfare, consultation cost,
and expected-payoff regret. Regret compares decisions under the agent's stated
belief, not hindsight after the state is revealed. Stopping is not counted as
unsafe simply because it bypasses a human decision.

## Offline benchmark and records

Requires Node 18+; no packages or API keys. From the repository:

```sh
node tests/check_uncertainty.cjs
node uncertainty-experiment.cjs resource runs/resource-example
node uncertainty-experiment.cjs off-switch runs/off-switch-example
```

An optional third argument is a JSON file with `config` overrides and optional
`simulation` settings (`rounds`, `seed`, `tie`). Use finite decimals, not fraction
strings. Unknown fields and invalid inputs fail. Default is 200 trials per
baseline, seed 42. The resource benchmark crosses three agent policies
(maximize payoff, always cooperate, always attack) with four defense policies
(manual, average, cautious, informed). Off-switch uses maximize payoff, always
proceed, always stop, and always defer. Infeasible cautious policies are recorded
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
uncertainty estimates, general distribution families, the science-audit
extension, and the Months 3–5 blog remain separate work.
