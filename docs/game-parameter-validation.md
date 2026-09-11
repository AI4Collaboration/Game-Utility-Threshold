# Game parameter and inequality validation

The research catalog has an independent executable audit for the mathematical
assumptions attached to each game-family label. This prevents a matrix from
being called a Prisoner's Dilemma, Chicken, Stag Hunt, or Battle of the Sexes
when its actual payoff values do not have that strategic form.

Run it with:

```bash
python3 -m utility_threshold.games validate-catalog
```

To write the deterministic machine-readable report:

```bash
python3 -m utility_threshold.games validate-catalog \
  --output results/game_parameter_validation.json
```

The command exits nonzero if any check fails. The complete research-package
validator regenerates the report, compares it byte-for-byte with the committed
artifact, and verifies its SHA-256 manifest.

## Enforced game-family inequalities

### Prisoner's Dilemma

For each role, the validator extracts the conventional values directly from
the payoff matrix and requires:

```text
T > R > P > S
2R > T + S
```

The first chain means defection is individually tempting against cooperation
and remains preferable against defection. The second inequality ensures that
sustained mutual cooperation has greater total value than alternating between
temptation and sucker outcomes. The structural checks additionally require:

- the competitive action is strictly dominant for both roles;
- mutual competition is the unique pure Nash equilibrium; and
- mutual cooperation is the unique utilitarian optimum.

The canonical deployment scenario reports `5 > 3 > 1 > 0`, with minimum
adjacent margin 1, and `2×3 > 5+0`, also with margin 1.

### Chicken

For both roles:

```text
T > R > S > P
```

Here `P` is mutual escalation/crash. The validator also requires the two
off-diagonal profiles—and only those profiles—to be pure Nash equilibria.

### Stag Hunt

For both roles:

```text
R > T > P > S
```

The two diagonal profiles must be the pure Nash equilibria and mutual
high-assurance cooperation must be the unique utilitarian optimum. The
Cross-Lab Incident Response scenario makes the additional narrative claim that
local lockdown is risk dominant, so its parameters must also satisfy:

```text
P - S > R - T
```

### Battle of the Sexes

Each player must strictly prefer a different coordinated diagonal while
preferring either diagonal to either mismatch:

```text
row preferred > row concession > row mismatch
column preferred > column concession > column mismatch
```

Both mismatch directions must have equal cost in this canonical
parameterization, and the two diagonals must be exactly the pure Nash
equilibria. The preferred-action belief threshold must be strictly inside
`(0, 0.5)`.

## Uncertainty and scenario checks

The audit runs the family checks independently on:

- all four canonical scenario matrices;
- all twelve latent-state matrices;
- all four probability-weighted expected matrices.

It additionally requires all payoff entries to be finite, every latent-state
probability to be positive, probabilities to sum to one, and the catalog's
severity ordering to be coherent. In the declared least-severe-to-most-severe
order, state probability cannot increase, the designated failure payoff must
strictly worsen, and a catastrophe marker cannot disappear at higher severity.
Scenario catastrophe profiles are checked against each narrative: mutual
escalation for Chicken and off-diagonal mismatch for both coordination games.

## What the audit intentionally does not require

Mechanisms are designed to change incentives. A sufficiently large penalty,
subsidy, assurance payment, or intervention can therefore make the original
family inequality false—for example, it can make cooperation dominate in a
game whose baseline is a Prisoner's Dilemma. That is a successful threshold
crossing, not a malformed test case.

The audit consequently validates the baseline matrices, every baseline latent
state, their expected matrices, and the declared uncertainty semantics. The
existing threshold and mechanism tests separately validate post-intervention
regime changes, adjusted payoffs, permitted actions, and equilibrium behavior.

## Current result

The committed report covers 29 validation subjects and 262 checks in nine
categories. All 262 currently pass. Each numeric check records its expression,
the named values on both sides, the signed margin, and the explanatory reason;
failures are therefore diagnostic rather than a single opaque Boolean.
