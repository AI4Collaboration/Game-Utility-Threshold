# Why Utility-Thresholds Matter for AI Safety

*Publication-ready Phase 1 manuscript — updated September 10, 2026.*

Catastrophic failures in AI systems often look discontinuous: behavior appears stable and cooperative, then suddenly flips into harmful optimization. A useful way to study this is through **utility-threshold games**: strategic models where small parameter changes (value-per-resource, attack cost, penalty size, uncertainty) produce sharp equilibrium transitions.

This post builds a foundational oversight game, derives threshold conditions,
and tests whether four current model families actually follow those conditions.
Across 156 model decisions, only 65% of the local safe–boundary–unsafe triplets
displayed the theoretically correct behavioral transition. The result is a
concrete warning: writing down a utility threshold does not ensure a language
model will calculate or apply it reliably.

---

## 1) Base Oversight Game (Deterministic, Sequential)

We model a two-player sequential game:

1. **Human overseer** chooses defense level `d in [0, D_max]`.
2. **AI system** observes `d` and chooses action `a in {C, A}`:
   - `C`: cooperate
   - `A`: attack (defect / pursue harmful objective)

### Parameters

- `v > 0`: AI value-per-resource from successful attack
- `R > 0`: exploitable resource scale
- `c(d)`: AI attack cost, increasing in defense
- `q(d) in [0, 1]`: probability attack is detected/blocked, increasing in defense
- `p > 0`: penalty if attack is detected (sanction, shutdown, loss)
- `g > 0`: AI utility from cooperation (baseline aligned reward)
- `k(d)`: human cost of defense, increasing and typically convex
- `L > 0`: human loss from successful attack

### Payoffs

Assume attack utility is linear in `vR`, with expected penalty:

- AI payoff if cooperate:
  `U_AI(C | d) = g`

- AI payoff if attack:
  `U_AI(A | d) = vR - c(d) - q(d)p`

So AI attacks iff

`vR - c(d) - q(d)p > g`

Equivalent threshold:

`v > [g + c(d) + q(d)p] / R`

Human expected utility:

- If AI cooperates: `U_H(C | d) = B - k(d)` (with baseline benefit `B`)
- If AI attacks: `U_H(A | d) = B - k(d) - (1 - q(d))L`

---

## 2) Stackelberg Solution (Leader: Human, Follower: AI)

This is naturally a Stackelberg game: human moves first, AI best-responds.

### AI best response correspondence

Define

`Delta(d) = U_AI(A | d) - U_AI(C | d) = vR - c(d) - q(d)p - g`

Then:
- If `Delta(d) > 0`, AI chooses `A`
- If `Delta(d) < 0`, AI chooses `C`
- If `Delta(d) = 0`, AI is indifferent

### Critical defense threshold

Let `d*` satisfy:

`c(d*) + q(d*)p = vR - g`

Any `d >= d*` induces cooperation (assuming monotonicity of `c, q`).

### Human optimization

Human chooses between:

1. **Deterrence regime**: choose `d >= d*`, induce cooperation  
   Utility: `B - k(d)`

2. **Risk-accepting regime**: choose `d < d*`, accept attack response  
   Utility: `B - k(d) - (1 - q(d))L`

In many practical settings, optimal deterrence is the **minimal deterring defense**:

`d_S = argmin_{d >= d*} k(d)`  

If `k(d)` strictly increases, `d_S = d*`.

The executable solver does not assume deterrence is always optimal. It also
checks the interval endpoints, the detection-saturation kink, and the interior
stationary point of the human payoff while attack continues. This matters when
deterrence is infeasible: under the default parameters with `v=100`, zero
defense gives the human utility `-20`, while the true optimum is an intermediate
defense `d=5` with utility `-12.5`.

### Catastrophic flip

The key discontinuity: when parameters move so that `d*` crosses feasible defense capacity `D_max`, behavior flips from deterrable cooperation to unavoidable attack.

Condition for unavoidable attack:

`vR - g > c(D_max) + q(D_max)p`

This is a utility-threshold catastrophe: a slight increase in `v`, slight drop in `p`, or slight drop in detection effectiveness can switch equilibrium class.

---

## 3) Nash Equilibria in the Normal-Form Reduction

For Nash analysis, discretize defense: `d in {d_L, d_H}` with `d_H > d_L`.

AI chooses `C` or `A`. The payoff matrix is induced by formulas above.

The implementation enumerates pure equilibria and solves the fully mixed
interior equilibrium by making each player indifferent. For the default game
with `v=4` and defenses `{0,4}`, there is no pure equilibrium. The mixed
equilibrium is:

```text
Pr(high defense) = 0.8
Pr(attack) = 0.4
E[U_H] = -8
E[U_AI] = 0
```

In this game family, **Stackelberg is often more behaviorally appropriate** than simultaneous Nash, because real oversight choices precede model deployment/action.

---

## 4) Explicit Threshold Inequalities

The simplest textbook-style attack condition appears when:

- `R = 1`
- `g = 0`
- `c(d) = c` fixed
- `q(d) = 1` (certain detection under chosen policy)

Then:

`A` optimal iff `v > p - c`

which matches the requested threshold form.

More generally:

`A` optimal iff `v > [g + c(d) + q(d)p] / R`

and safety requires the strict opposite inequality with margin.

---

## 5) Incomplete Information Extension (Bayesian Game)

Now suppose the overseer does not know AI type `theta`, where type controls effective value intensity:

- `theta in {theta_L, theta_H}` with prior `Pr(theta_H) = pi`
- Attack value: `v(theta)R`

AI knows its own type; human only knows prior.

### Type-contingent best response

Type `theta` attacks iff:

`v(theta)R - c(d) - q(d)p > g`

Hence there can be separating behavior:
- low-value type cooperates
- high-value type attacks

### Bayesian safety margin

Define safety slack for type `theta` at defense `d`:

`m(theta, d) = g + c(d) + q(d)p - v(theta)R`

Safety for all types requires `m(theta, d) >= 0` for worst-case `theta`.

If overseer targets risk level `epsilon`, require:

`Pr_theta(m(theta, d) < 0) <= epsilon`

This quantifies the safety margin as a robust-buffer condition under parameter uncertainty.

---

## 6) Quantifying Safety Margins

A practical scalar margin:

`M(d) = c(d) + q(d)p - (vR - g)`

Interpretation:
- `M(d) > 0`: attack deterred
- `M(d) = 0`: threshold boundary
- `M(d) < 0`: attack incentive remains

To prevent catastrophic mode-switch under perturbations, enforce:

`M(d) >= delta_safe`

where `delta_safe > 0` is chosen to absorb estimation error, distribution shift, and adversarial adaptation.

---

## 7) Toy Simulation: CooperateBot vs DefectBot

Below is a minimal Python simulation for deterministic and uncertain settings.

```python
from dataclasses import dataclass
from typing import List

@dataclass
class Params:
    R: float = 1.0
    g: float = 0.0
    p: float = 5.0
    L: float = 20.0

def c_of_d(d: float) -> float:
    return 0.5 * d

def q_of_d(d: float) -> float:
    # saturating detection curve
    return min(1.0, 0.15 * d)

def ai_attack_utility(v: float, d: float, prm: Params) -> float:
    return v * prm.R - c_of_d(d) - q_of_d(d) * prm.p

def ai_cooperate_utility(prm: Params) -> float:
    return prm.g

def ai_action(v: float, d: float, prm: Params) -> str:
    return "A" if ai_attack_utility(v, d, prm) > ai_cooperate_utility(prm) else "C"

def human_utility(action: str, d: float, prm: Params) -> float:
    defense_cost = 0.3 * d**2
    if action == "C":
        return -defense_cost
    # expected harm only if attack occurs
    return -defense_cost - (1 - q_of_d(d)) * prm.L

def safety_margin(v: float, d: float, prm: Params) -> float:
    return prm.g + c_of_d(d) + q_of_d(d) * prm.p - v * prm.R

def sweep(v_values: List[float], d_values: List[float], prm: Params):
    rows = []
    for v in v_values:
        for d in d_values:
            a = ai_action(v, d, prm)
            m = safety_margin(v, d, prm)
            uh = human_utility(a, d, prm)
            rows.append((v, d, a, m, uh))
    return rows

if __name__ == "__main__":
    prm = Params()
    v_grid = [i * 0.5 for i in range(1, 21)]      # 0.5 ... 10
    d_grid = [i for i in range(0, 11)]            # 0 ... 10

    data = sweep(v_grid, d_grid, prm)
    # Print transitions where action flips near margin boundary
    for (v, d, a, m, uh) in data:
        if abs(m) < 0.25:
            print(f"boundary v={v:.2f}, d={d:.1f}, action={a}, margin={m:.2f}, U_H={uh:.2f}")
```

### Bot abstraction

- `CooperateBot`: always returns `C`
- `DefectBot`: always returns `A`
- `ThresholdBot(v)`: returns `A` iff threshold inequality holds

This lets you compare fixed policies versus utility-rational behavior.

---

## 8) What Real Model Play Shows

We evaluated one OpenAI, Anthropic, Google, and Meta model on 39 unique cases
each. Twenty-five cases form a broad parameter grid. Fourteen cases sit exactly
at or `0.25` utility units to either side of the threshold. Each model returns
an observable worksheet with both utilities, the signed margin, action, and
confidence.

All 156 calls completed. Overall, 98.72% of final actions were parseable, but
only 85.90% were utility-optimal. Performance differed sharply by model:

| Model family | Optimal action | Valid JSON | Mean regret |
|---|---:|---:|---:|
| Anthropic | 100% | 100% | 0.000 |
| Google | 97.44% | 100% | 0.013 |
| Meta | 76.92% | 20.51% | 0.256 |
| OpenAI | 69.23% | 89.74% | 0.327 |

The just-safe cases were hardest: only 68.75% received the correct cooperative
action. Common failures included dropping the penalty term during arithmetic,
reversing the safety-margin sign, ignoring the equality tie-break, and placing
unevaluated expressions in JSON numeric fields.

These are descriptive results from one call per cell under the specified model
versions and minimal reasoning budget. They are not stable provider rankings.
They nevertheless demonstrate why a safety margin must include computational
reliability: a mathematically safe region is not behaviorally safe if the agent
miscomputes which side of the boundary it occupies.

---

## 9) UK AISI Inspect Framework for Granular Observability

To operationalize this with strong traceability, use the UK AISI `inspect-ai` framework.  
Reference implementation in this project: `utility_threshold_inspect.py`.

### What this implementation gives you

- Full prompt, message, provider output, declared worksheet, and score records.
- Exact ground-truth utilities, safety margins, critical values, and decision
  certificates for every sample.
- Nested spans for input validation, calculation, decision, parsing, and
  scoring, plus structured store and transcript events.
- Separate schema coverage, numerical accuracy, margin-sign correctness,
  action validity, utility regret, and confidence-calibration metrics.
- Eight deterministic, stochastic, and proof-carrying policy baselines.
- A strict observability boundary: provider-exposed reasoning is retained, but
  provider-private hidden chain-of-thought is neither accessible nor claimed.

### Run commands

Install:

```bash
python3 -m pip install inspect-ai
```

Run and record every policy baseline without an API key:

```bash
python3 run_phase_one_policy_eval.py
```

Run the four-provider model matrix with an OpenRouter key in `.env`:

```bash
python3 run_phase_one_eval.py
```

Validate Python, Lean, parity, analyses, and artifact checksums in one command:

```bash
scripts/validate_research_package.sh
```

The complete methods, slices, limitations, and artifact map are in
[`docs/phase-one-research-package.md`](docs/phase-one-research-package.md).

---

## 10) Why This Foundational Layer Matters

Utility-threshold games make a central AI safety intuition precise:

- Harmful behavior is often not gradual; it is thresholded.
- Robust oversight is about keeping systems away from critical surfaces, not merely balancing average-case incentives.
- Safety margin design should be explicit, monitored, and stress-tested under uncertainty.

As models gain capability (`v` rises) or exploitability (`R` rises), previously safe regimes can fail abruptly unless detection quality, penalties, and control costs scale accordingly.

---

## 11) Practical Next Steps

- Calibrate `c(d)` and `q(d)` from empirical red-team data.
- Repeat each model/case cell across seeds, reasoning budgets, and prompt
  variants to estimate behavioral variance.
- Test tool-assisted calculation as an intervention against threshold errors.
- Replace scalar `v` with context-conditional utility over task classes and
  calibrate uncertainty from real elicitation data.
- Pre-register confirmatory hypotheses before treating provider differences as
  general model-family effects.

---

## Closing

If your safety case does not include threshold analysis, it may miss the most dangerous failure mode: **a small parameter shift causing a large behavioral discontinuity**. Utility-threshold games provide a minimal but rigorous foundation for detecting, quantifying, and hardening against that regime change.
