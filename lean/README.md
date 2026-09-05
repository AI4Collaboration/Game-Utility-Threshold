# Lean foundation

`UtilityThreshold.lean` is a Lean 4 formalization of the unsaturated base
utility-threshold game. It uses utilities scaled by 20 to keep the linear game
in exact integer arithmetic, proves the two threshold implications, and defines
a proof-carrying `DecisionWitness` that mirrors the Python certificate recorded
in Inspect logs.

Verify it with Lean 4:

```bash
lean UtilityThreshold.lean
```

The Python model uses a saturated detection curve; the Lean foundation uses the
linear portion, so future work should add the piecewise saturation proof and a
cross-language equivalence test.
