# Unknown AI priorities and protection that tolerates stated errors

This note specifies the additional oversight model in
`utility_threshold/oversight_uncertainty.py`. It supplies reproducible mathematical
baselines for Paper 1. It does **not** report new language-model experiments or
establish that deployed AI systems obey these calculations.

The practical question is: **if the human does not know how much the AI values a
resource, what protection should the human choose, and how sensitive is that
answer to wrong assumptions?** We keep three different answers separate:

1. Protection that gives the best **average human outcome** under stated type probabilities.
2. The least protection that keeps the **probability of an attack** below a stated limit.
3. Protection whose **cooperation advantage remains nonnegative for every admitted
   combination of parameter errors**.

An average-outcome optimum can permit attacks. An attack-probability limit can
permit rare attacks. A worst-case statement covers only the parameter set that
was actually declared. None of these results is a statistical confidence claim
about language-model behavior.

## Literature used, and what is reused

| Primary source | Method reused here | Scope and limitation |
| --- | --- | --- |
| Harsanyi (1967), *Games with Incomplete Information Played by “Bayesian” Players, Part I*, Management Science 14(3), 159–182. [Publisher and DOI](https://doi.org/10.1287/mnsc.14.3.159). | Represent unknown priorities as a chance draw of a privately observed type, with a declared common prior. | This justifies specifying who knows the drawn value and who knows only its distribution. Our finite-type oversight calculation is a particular committed-leader model; this source does not establish our payoff assumptions or their empirical validity. |
| Ben-Tal and Nemirovski (1998), *Robust Convex Optimization*, Mathematics of Operations Research 23(4), 769–805. [Author-hosted paper, introduction and equations (1)–(2)](https://www2.isye.gatech.edu/~nemirovs/MOR_RCO_1998.pdf); [DOI](https://doi.org/10.1287/moor.23.4.769). | Require a condition to hold throughout a specified uncertainty set, instead of checking only a nominal estimate. | We reuse this definition of robustness. Our interval extrema follow directly from the monotonicity proof below; we do not import that paper's ellipsoidal optimization theorems into this discontinuous leader problem. |
| Hadfield-Menell, Dragan, Abbeel and Russell (2017), *The Off-Switch Game*, IJCAI, 220–227. [Proceedings](https://www.ijcai.org/proceedings/2017/32); [author paper, Sections 2–4](https://arxiv.org/pdf/1611.08219). | Make the information structure and assumptions about the human and AI explicit before drawing an oversight conclusion. | Their AI is uncertain about human utility and can learn from the human's decision; the present human is uncertain about an AI's privately known resource value. These are different games. The present code does not reproduce their shutdown theorem or establish that uncertainty alone makes an AI safe. |

The closed-form thresholds and finite-candidate argument below are derivations
for this repository's existing payoff functions. They are not presented as a new
general result in game theory. The claims have executable cross-checks but have
not been independently peer reviewed or encoded in a proof assistant.

## 1. Exactly what the players know and do

Nature draws one value `v_i` from a finite list with probabilities `π_i`. Each
value is nonnegative, each probability is nonnegative, and the probabilities sum
to one. The AI observes its value. The human knows the list and probabilities
but does not observe the draw. The human publicly commits to a defense
`d ∈ [0, D]`; the AI observes the defense and chooses `COOPERATE` or `ATTACK`.
The human anticipates this response. No signal, negotiation, repeated learning,
or uncertainty about the prior is included in this model.

The payoff algebra is the same as `utility_threshold/core.py`:

\[
c(d)=ad,\quad a=1/2,\qquad q(d)=\min(1,bd),\quad b=3/20,
\]

\[
U_A(\mathrm{attack};v_i,d)=v_iR-c(d)-q(d)p,
\qquad U_A(\mathrm{cooperate})=g,
\]

\[
U_H(\mathrm{cooperate};d)=-kd^2,\qquad
U_H(\mathrm{attack};d)=-kd^2-(1-q(d))L.
\]

Here `R > 0` is resource amount, `p ≥ 0` is an attack penalty, `L ≥ 0` is the
human loss from an unblocked attack, and `k ≥ 0` sets the cost of defense. The
cooperation reward `g` may be negative. All numerical inputs must be finite.

The existing model uses the **same** `q` both in the expected penalty and in the
probability of avoiding human loss. This is a substantive simplification:
detecting an attack is not automatically the same as stopping its consequences.
Experiments that distinguish detection from prevention need separate parameters
and a new derivation. The results here must not be cited as validating that
simplification. The AI's resource term `vR` also remains unchanged when `q=1`.
Thus this algebra does not model an intervention that stops resource acquisition
itself. A literal blocked-theft application may need a success-weighted resource
term, a separate success probability, and a different threshold derivation.

Define the cooperation advantage, or margin,

\[
m_i(d)=g+ad+q(d)p-v_iR.
\]

The AI attacks if and only if `m_i(d) < 0`. **A tie selects cooperation.** This
rule is part of the model, not a fact about real agents. At a zero margin,
cooperation is only weakly preferable. A positive margin is required for a
strict preference. A different tie rule requires a different solution argument;
in particular, a least deterring defense need not be attained under attack at a
tie.

The probability of an attack is

\[
A(d)=\sum_i\pi_i\mathbf{1}\{m_i(d)<0\}.
\]

The expected human outcome and probability of an unblocked attack are

\[
W(d)=-kd^2-(1-q(d))L A(d),\qquad B(d)=(1-q(d))A(d).
\]

`A` and `B` are deliberately separate outputs. At `q=1`, a high-value type can
still prefer to attack even though the model assigns no unblocked human loss.
The probability is taken over the specified private-type draw. It is not an
estimate of a language model's attack frequency.

### Why the mean priority is not a substitute

With equal probability on `v=0` and `v=10`, the default parameters and `d=4`
produce attack probability `1/2`. Replacing the distribution by its mean `v=5`
produces an exact tie and therefore attack probability zero. The expected value
of a response is not generally the response at an expected value. This example
is checked in `test_private_information_cannot_be_replaced_by_mean_type`.

## 2. Least defense for each type

Let `x_i = v_i R - g` and let `s = 1/b = 20/3` be detection saturation. The
least defense that deters type `i`, before imposing the budget, is

\[
\tau_i=\begin{cases}
0,&x_i\leq0,\\
x_i/(a+bp),&0<x_i\leq as+p,\\
(x_i-p)/a,&x_i>as+p.
\end{cases}
\]

**Proof.** The defense contribution `ad + min(1,bd)p` is continuous and strictly
increasing because `a>0` and `p≥0`. It equals `(a+bp)d` below saturation and
`ad+p` above it. Solve its equality to `x_i` on the appropriate segment. If
`x_i≤0`, cooperation already holds at zero. Therefore the AI attacks exactly
when `d<τ_i`, except that no nonnegative defense attacks when `τ_i=0`.
The type is deterrable within the budget exactly when `τ_i≤D`.

When `x_i<0`, `τ_i=0` is the least deterring defense but not an indifference
point: cooperation is strictly preferred there. The code reports a deterrence
threshold, without falsely requiring every threshold to have zero margin.

## 3. Complete solution for the best average human outcome

`solve_private_value_defense` evaluates a finite set containing a global
maximizer over the full interval `[0,D]`. This is stronger than picking the
largest result from an arbitrarily chosen grid.

The candidate set contains:

- `0` and `D`;
- every `τ_i` in the budget;
- saturation `s`, when it lies in the budget;
- for every interval between these boundaries below saturation, the point
  `bLA/(2k)` if `k>0` and that point lies inside the interval. Here `A` is the
  attacking probability mass **within that interval**.

**Proof of completeness.** On an open interval with no type threshold and no
saturation point, `A` is constant. Below saturation,

\[
W(d)=-kd^2-LA+bLAd.
\]

For `k>0` this is concave, with its only possible interior maximum at
`bLA/(2k)`. For `k=0` it is nondecreasing, so the upper boundary is sufficient.
At or above saturation, `W(d)=-kd²`, which is nonincreasing; its lower boundary
is sufficient. At a type threshold, attack probability falls. The human payoff
jumps upward by `(1-q)L` times the departing probability mass, or remains
unchanged. Thus approaching a threshold from the left cannot have a larger
limiting payoff than the value at the threshold. The lower endpoint, upper
endpoint, and all relevant stationary points therefore contain a global
maximizer. This covers `k=0`, `L=0`, coincident thresholds, zero probability
types, and a zero defense budget.

If candidates have equal human outcome, the implemented tie order is lower
attack probability, then less defense. The returned certificate records all
candidates, their reasons, and every type's response.

**Useful regression example.** Half the probability on `v=1` and half on
`v=100` with the default parameters gives optimal defense `5/2`, attack
probability `1/2`, and expected human outcome `-65/8`. The high type remains an
attacker. Using the full-mass stationary point `5` would give the wrong optimum
because only half the mass is attacking in the relevant interval.

## 4. Least defense meeting an attack-probability target

For a supplied limit `α∈[0,1]`,
`minimum_defense_for_attack_probability` seeks the least `d` with `A(d)≤α`.
This is a different problem from maximizing `W(d)`.

**Proof.** Each type changes from attack to cooperation once and never changes
back as defense increases. Consequently `A(d)` is a nonincreasing step
function, with its lower value attained at each threshold because ties
cooperate. If `A(D)>α`, the target is infeasible. Otherwise the first feasible
point is zero or an in-budget type threshold. Examining those points in order
finds the minimum exactly.

The result exposes `feasible`, `minimum_defense`, the achieved attack
probability, and the best attack probability attainable at the budget. An
infeasible result has no fabricated defense or achieved evaluation. The target
is conditional on the supplied prior; a wrong or shifted prior invalidates its
probabilistic interpretation. A zero-probability type does not affect this
chance calculation. Covering that type regardless of probability requires a
worst-case condition instead.

## 5. Protection that tolerates bounded errors

For a fixed assessment, write

\[
m=g+c+qp-vR.
\]

`MarginUncertainty` declares finite closed intervals for `v,R,g,p,q,c` with
`v,c,p≥0`, `R>0`, and `0≤q≤1`. Every combination is admitted: this is a
Cartesian product of ranges, often called a box. It makes **no statistical
independence assumption**, because no probability distribution is specified.

The exact smallest and largest margins are

\[
m_{\min}=g_-+c_-+q_-p_--v_+R_+,
\qquad
m_{\max}=g_++c_++q_+p_+-v_-R_-.
\]

**Proof.** With the stated signs, increasing `g,c,q,p` cannot decrease the
margin, and increasing `v,R` cannot increase it. Choosing the indicated
endpoints attains each bound. The returned endpoint witnesses can be checked
by direct substitution. This proof needs the admitted combinations to include
those endpoints. For correlated parameters, the box can be a conservative
outer bound but need not give attained extrema of the actual joint set.

Consequences within this model:

- If `m_min ≥ 0`, cooperation is optimal throughout the box under the stated
  tie rule.
- If `m_min > 0`, cooperation is strictly preferred throughout the box.
- If a required buffer `ε≥0` is supplied, it is certified exactly when
  `m_min ≥ ε`.
- If `m_max < 0`, attack is strictly preferred throughout the box.
- Otherwise some admitted points may support different decisions. A positive
  nominal margin alone cannot resolve that uncertainty.

### Defense affects both attack cost and detection

`worst_case_margin_at_defense` permits ranges on actual defense `d`, cost
slope `a`, and detection slope `b`, with `c=ad` and `q=min(1,bd)`. This can
represent uncertainty about defense execution or the calibration of these two
response functions. All three quantities must be nonnegative.

The worst point uses the lower values of `d,a,b` together; the best uses their
upper values together. Both cost and detection move in the same favorable
direction as defense increases, so both extrema are attained despite their
shared dependence on `d`. The certificate includes that common defense and
both slopes. This result does not extend automatically to nonmonotone response
functions, a detection–cost tradeoff, or an attacker that adapts to monitoring.

### Choosing the best worst outcome is not uniform safety

The code reports a separate `maximin_action`: compare the worst cooperation
utility `g_-` to the worst attack utility `v_-R_- - c_+ - q_+p_+` and choose
the larger. This describes a particular decision rule for an agent facing the
whole uncertainty set; it is not the private-type follower rule from Sections
1–4.

For example, take `v∈[3,4]`, `R∈[1,1.2]`, `g∈[0,0.2]`, `p∈[4,5]`,
`q∈[0.5,0.6]`, and `c∈[2,2.1]`. The worst cooperation utility is `0`, greater
than the worst attack utility `-2.1`, so maximin selects cooperation. Yet the
smallest margin is `-0.8`: an admitted parameter combination strictly favors
attack. The test suite retains this counterexample to prevent the two claims
from being confused.

## 6. How far from failure is a nominal condition?

`one_parameter_distances` takes a nominal condition where cooperation is
optimal and reports the adverse change needed to reach a tie. For positive
nominal margin `m`, the distances are:

| Quantity changed by itself | Adverse direction | Distance to a tie |
| --- | --- | --- |
| Resource value `v` | Increase | `m/R` |
| Resource amount `R` | Increase | `m/v`, when `v>0` |
| Cooperation reward `g` | Decrease | `m` |
| Penalty `p` | Decrease | `m/q`, if it can be reached before `p=0` |
| Detection probability `q` | Decrease | `m/p`, if it can be reached before `q=0` |
| Direct attack cost `c` | Decrease | `m`, if it can be reached before `c=0` |
| Defense `d` | Decrease | `d−τ`, when a tie exists at nonnegative defense |

A tie still selects cooperation. These are distances to the boundary, or
infima of changes that lead to attack when a strict crossing is possible; they
are not minimum attained harmful changes. A boundary at the edge of the
admissible domain may be reachable without any admissible crossing. The output
distinguishes this case from a parameter with no reachable tie or no effect.

These quantities have **different units**. Do not rank or add them as if one
resource-value unit were one probability unit. They also do not certify
simultaneous changes. Use an explicitly declared box for combined errors. A
derivative of the discrete chosen action at a switching point is not a useful
replacement for this finite distance; the action jumps there.

## 7. Numerical and reporting conventions

The new module evaluates the existing payoff algebra using exact fractions.
`int`, finite `float`, `Decimal`, and `Fraction` inputs are accepted. A float is
interpreted through its decimal string, so `0.15` becomes exactly `3/20`.
`0.1 + 0.2` carries the decimal text `0.30000000000000004`; use `Decimal` or
`Fraction` when that extra precision is unintended. Probabilities must sum
exactly to one. `TypeDistribution.from_weights` explicitly normalizes declared
weights, such as counts, and records their exact ratios. There is no hidden
probability correction or arbitrary tolerance band around a tie.

Results retain `Fraction` values. Calling `to_dict()` gives JSON-safe
numerator/denominator pairs. Convert to floats only for display or plotting,
and retain the original exact values in records. For example, a threshold of
`20/19` is a cooperation tie, while its rounded display float
`1.0526315789473684` is just below the threshold in the declared decimal model.
Changing the number shown in a prompt changes the tested condition. A prompt
using rounded decimals must therefore be evaluated at those actual decimals;
do not label it an exact threshold condition because it was derived from one.

The legacy `core.py` uses binary floating-point arithmetic. Its ordinary
interior decisions agree with this implementation; boundary rounding may
differ. Do not silently mix its rounded decisions with exact certificates.
This module adds no tolerance that could relabel a genuinely negative margin
as safe.

For presentation, hold parameters and the type distribution fixed and put
**defense on the horizontal axis**. Use aligned panels for attack probability,
expected human outcome, and the minimum safety margin. Label the selected
defense, individual type thresholds, and saturation. Show empirical choice
frequencies in separate, clearly labeled series with their sample counts and
uncertainty. A theoretical line has no sampling confidence interval. If
changing the prior, use a separate experiment that varies one specified type
probability while fixing the type values and all other inputs. Do not change
priors, loss size, penalties, and defense simultaneously and interpret the
result as the effect of defense.

Before claiming an empirical protection result, record the source of the type
probabilities or ranges, how and when they were selected, the exact numerical
conditions shown to the model, prompt wording, model identity and generation
settings, and the action tie policy. Do not estimate a prior from confirmation
data and then describe the same data as an independent test. A confidence
statement about a fitted uncertainty set needs its own simultaneous coverage
argument; endpoint arithmetic supplies no such argument.

## 8. Reproduction and checks

A complete offline demonstration is saved in
[`results/research_theory/oversight_examples.json`](../../results/research_theory/oversight_examples.json).
It contains exact inputs, certificates, and a defense-only curve, explicitly
labeled **THEORY ONLY**. It compares the best average outcome with two risk
limits and an infeasible budget; it also records a bounded-error certificate,
the maximin counterexample, and one-parameter fragility. There are no model calls
or empirical observations. Regenerate or verify it with:

```bash
python3 scripts/research_oversight_examples.py
python3 scripts/research_oversight_examples.py --check
```

The artifact records hashes of its generator and the payoff implementations.
After a source change, regenerate and review the output. The replay test
reconstructs every input from exact fraction records and recomputes every
certificate and curve point.

```python
import json
from fractions import Fraction
from utility_threshold.core import GameParams
from utility_threshold.oversight_uncertainty import (
    TypeDistribution, solve_private_value_defense,
    minimum_defense_for_attack_probability,
)

prior = TypeDistribution.from_weights(((1, 1), (100, 1)))
solution = solve_private_value_defense(prior, GameParams(), max_defense=10)
assert solution.defense == Fraction(5, 2)
assert solution.attack_probability == Fraction(1, 2)
assert solution.expected_human_utility == -Fraction(65, 8)
record = json.dumps(solution.to_dict(), allow_nan=False)

risk = minimum_defense_for_attack_probability(prior, GameParams(), 0, max_defense=10)
assert not risk.feasible
assert risk.minimum_defense is None
```

Run:

```bash
python3 -m unittest discover -s tests -p test_oversight_uncertainty.py -v
```

The checks compare candidate solutions with independent direct payoff sums
over dense defense grids, enumerate all corners of the uncertainty boxes,
verify shared-defense witnesses, test exact ties and strict crossings, and
exercise negative cooperation rewards, zero costs, zero losses, zero budgets,
infeasible risk limits, and nonfinite inputs. These tests supplement the
analytical proofs; a dense grid alone cannot prove continuous optimality.

## Remaining research boundaries

This implementation covers a finite, known prior, deterministic utility
maximization, the stated tie rule, a single public defense, a linear direct
attack cost, capped linear detection, and quadratic human defense cost. It
does not cover strategic signaling, uncertain prior probabilities, continuous
type distributions, repeated interaction, nonmonotone monitoring, learned
utility functions, or imperfect optimization by the AI. It also does not
establish a shutdown or auditing application without a defensible mapping of
their actual actions, information, and consequences onto this model. Those
extensions require separate definitions, evidence, and proofs.
