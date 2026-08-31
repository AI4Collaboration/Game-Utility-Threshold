# Lean foundation

`UtilityThreshold.lean` is a Lean 4 formalization of the unsaturated base
utility-threshold game. It proves the two threshold implications and defines a
proof-carrying `DecisionWitness` that mirrors the Python certificate recorded
in Inspect logs.

The repository does not currently include a Lean toolchain, so this artifact is
not validated in CI yet. Once Lean 4 is available, verify it with:

```bash
lean UtilityThreshold.lean
```

The Python model uses a saturated detection curve; the Lean foundation uses the
linear portion, so future work should add the piecewise saturation proof and a
cross-language equivalence test.
