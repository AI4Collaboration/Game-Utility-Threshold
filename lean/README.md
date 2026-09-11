# Lean foundation

`UtilityThreshold.lean` is a Lean 4 formalization of the base utility-threshold
game. It uses probabilities and utilities scaled by 20 to keep the Python
model's piecewise saturated detection curve, AI payoff, and human payoff in
exact integer arithmetic. It proves the linear and saturated detection
branches, the two threshold implications, and defines a proof-carrying
`DecisionWitness` that mirrors the Python certificate recorded in Inspect logs.
The formal agent layer includes constant cooperate/attack baselines, the exact
threshold policy, named DUPOC and CUPOD verified agents, and a finite Bernoulli
draw witness for auditing PDUPOC-style stochastic decisions.

The exact Lean release is pinned in `lean-toolchain`, and `lakefile.toml`
declares the proof as the default library target. Verify it with:

```bash
lake build
```

`ParityCheck.lean` emits the exact scaled decision record for the 25-point
Phase 1 research grid. `tests/test_lean_parity.py` executes that oracle and
asserts equality with Python for detection, both utilities, the safety margin,
and the chosen action.
