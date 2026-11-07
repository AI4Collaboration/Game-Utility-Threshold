# Exact mathematical examples — no model experiments

`oversight_examples.json` contains deterministic calculations under the stated
oversight model. **It contains zero model calls and no observed AI behavior.**
Do not pool these records with empirical runs or report their probabilities as
measured success rates.

Regenerate from the repository root:

```bash
python3 scripts/research_oversight_examples.py
```

Verify the saved artifact without changing it:

```bash
python3 scripts/research_oversight_examples.py --check
```

The generator uses only the Python standard library and repository code. It
works from any directory when invoked by its absolute script path. It includes
source SHA-256 hashes and omits timestamps so unchanged code produces identical
bytes. After changing a recorded source file, regenerate and review the
artifact; do not remove the provenance checks to preserve an old result.

Every numerical input and calculated value is stored as an exact
`numerator`/`denominator` pair. Restore a number with
`Fraction(record["numerator"], record["denominator"])`. Keep these exact values
when replaying decisions; floats are only for display. The accompanying test
reconstructs the inputs and recomputes every saved certificate and curve point.

The examples include:

- **Average outcome versus attack risk.** The AI privately values a resource at
  `1` with probability `3/4` or `10` with probability `1/4`. With the stated
  default payoffs, the best average human outcome uses defense `5/4`, permits
  attack probability `1/4`, and has expected human utility `−145/32`. Eliminating
  attack risk requires defense `10` and human utility `−30`. A defense budget of
  `4` makes zero attack probability infeasible. These are exact theoretical
  outputs under an illustrative prior.
- **One-variable presentation data.** Only defense changes on the saved curve;
  all type values, probabilities, and other payoff parameters stay fixed. Use
  separate panels for attack probability, human utility, and minimum margin.
  The grid includes exact theoretical boundaries and selected defense values.
- **Protection under bounded errors.** The admitted ranges include uncertain
  actual defense and uncertain slopes for detection and direct attack cost.
  The worst cooperation advantage is `2/5`, which exceeds the requested buffer
  `1/4`. The bounds are assumptions, not estimated confidence intervals.
- **A counterexample.** Cooperation maximizes the worst outcome of each action
  separately, yet an admitted parameter combination favors attack. This shows
  why that decision rule must not be reported as uniform safety.
- **Distance to a tie.** One quantity changes at a time around `v=4,d=4`. The
  saved report distinguishes reachable harmful crossings from domain limits.

For assumptions, literature, proofs, and the detection-versus-prevention
limitation, see [the oversight methods note](../../docs/research/oversight-bounds.md).
