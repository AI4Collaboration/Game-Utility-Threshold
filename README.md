# Utility-Threshold Games for AI Safety

An executable research foundation for the Months 1--3 utility-threshold-game
workplan: a human chooses a defense level and an AI chooses to cooperate or
attack. The repository derives and tests the threshold at which the AI's
incentive changes sign.

## What is included

- A shared deterministic oversight-game model with attack, cooperation, human
  utility, safety-margin, minimum-deterrence, Stackelberg, and pure-Nash tools.
- Baseline, threshold, probabilistic, and proof-carrying agents.
- An [Inspect AI](https://inspect.aisi.org.uk/) evaluation whose samples and
  score records expose the complete decision witness: inputs, both utilities,
  safety margin, threshold region, expected/observed action, and certificate.
- Regression tests for the threshold, feasibility, proof witness, and game
  solution behavior.
- The accompanying foundational blog post in `utility-threshold-games-blog.md`.

## Run

```bash
python3 -m unittest discover -v
python3 utility_threshold_sim.py
python3 utility_threshold_inspect.py
```

The last command runs the proof-carrying deterministic policy and writes an
Inspect log to `logs/`. For an LLM evaluation, invoke
`utility_threshold_model_eval()` through Inspect with your chosen model.

## Inspect observability

Each decision has structured metadata that is visible in Inspect logs:

- scenario inputs: `v`, `d`, `R`, `g`, `p`, `c(d)`, and `q(d)`
- analytic evidence: attack/cooperation utility and `safety_margin`
- classification: `safe`, `unsafe`, or `boundary`
- behavior: expected action, observed action, raw completion, and correctness
- verification: a policy decision certificate with the inequality and validity

This is the foundation only; the roadmap's later incomplete-information,
transparency, and strategy-family layers are deliberately not implemented here.
