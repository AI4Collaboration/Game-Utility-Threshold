# Recorded choices → checked payoff statements

The framework checks what a recorded action earns under the supplied payoff
table. It does **not** prove the model's internal reasoning, future behavior,
honesty, safety, or optimality under an unobserved belief.

Install Lean using its [official installation instructions](https://lean-lang.org/install/).
The `lean-toolchain` file pins version 4.33.1. This project uses only Lean's
standard library; there is no Mathlib download.

```sh
cd lean
lake build
cd ..
python3 experiment.py proofs runs/pd-demo --check
python3 tests/check_lean.py
```

If Lake is not on PATH, pass `--lake /absolute/path/to/lake`. Without `--check`,
the command writes proposed certificates and sets `verified: false`. Only a
successful compiler run sets `verified: true`. A failed check leaves it false.
CI builds the general theorems, checks generated evidence, and ensures that
an intentionally false dominance claim is rejected.

## Meaning of the mapping

For every individually valid recorded choice, `proofs/mapping.json` links its
job ID to a named Lean certificate. It records the chosen action, both possible
opponent actions, exact payoff differences, and the source table. The outcomes
are **better**, **tied**, or **worse**. Both actions are best responses at a tie.
Unparseable and missing responses have no invented action or certificate.

The generated `Choices.lean` proves:

- The comparison against each of the opponent's two possible actions.
- Whether the choice is at least as good against both (weak dominance), or a
  proof that this property does not hold.
- When the opponent's action is recorded, whether the choice was a best
  response to that action, or a proof that it was not.

The last comparison is **in hindsight**. A simultaneous player did not know
the opponent's choice. A hindsight loss in Chicken or Stag Hunt does not by
itself establish a decision error under the player's expectations.

`AgentProof.lean` defines these properties and proves the two cost thresholds
for arbitrary integer payoff tables, including ties. `bestResponse_sound`
and `dominance_sound` connect those definitions to comparison with every
alternative action. A `Certificate` contains the two comparisons and their
proofs. This same definition can verify unfavorable findings; it never forces
agent decisions to look correct.

## What is trusted

Python parses raw model content, reconstructs the displayed table, and
multiplies all four rational payoffs by one positive common denominator.
No floating-point rounding enters the proof statements. Python tests check
the exact integer-to-rational correspondence. Lean then checks the resulting
integer statements using `decide`; it does not independently parse the JSON
or prove that the model actually received the prompt. This small translation
and the interpretation of the statements remain part of the trusted boundary.

The verification manifest hashes the plan, raw log, generated Lean source and
core theorem file. The compiler output and axiom listings are saved in
`lean-check.log`. No placeholder proof, custom axiom, or `native_decide` is used.
See Lean's [proof validation guidance](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)
for why a checked statement and its intended real-world meaning are distinct.
