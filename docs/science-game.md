# Science audit: a playable oversight example

[Play on the public site](https://ai4collaboration.github.io/Game-Utility-Threshold/science.html).
Locally, run `python3 serve.py` and open `/science`.

This is a **simulated research agent and a mechanical reviewer**, with synthetic
catalyst measurements. It makes no model calls, uses no credentials, and trains
no models. Human button choices are real UI interactions, but session exports
are practice records, not a controlled experiment or evidence of LLM safety.

## One round

1. Choose an audit budget `k` from 0 to 8, a rejection penalty `p` from 0 to 12,
   and a research-agent policy. These settings lock until the verdict.
2. The agent submits a mean yield over eight synthetic runs. An accurate report
   uses the original instrument readings. Inflation increases exactly one
   reading by 16 percentage points, increasing the mean by 2 percentage points.
3. The reviewer compares a random subset of `k` distinct reported readings
   with their original logs. It flags every inspected mismatch and never
   flags a matching pair. Uninspected readings remain covered in the interface.
4. The human accepts or returns the report. The complete record is then
   revealed, and points follow the verdict. An accurate below-target result is
   still valid; the fictional 52% target is not a significance test.

The report policy is independent of the subsequent audit draw. Policies are:
`mixed` (50/50 accurate or inflated), `accurate`, `inflate`, and `maximizer`.
The maximizer uses the expected payoffs below; it chooses accurate on an exact
tie. It assumes the human follows the clean-audit acceptance rule. It does not
learn the user's judgment policy or optimize against arbitrary human behavior.

## Incentives and exact threshold

| Report | Accepted | Returned |
| --- | ---: | ---: |
| Accurate | 1 | 0 |
| Inflated | 4 | −p |

Assuming a uniformly sampled audit and a human who accepts clean audits and
returns any mismatch, the chance of finding the single altered record is
`q=k/8`. Expected accurate payoff is 1; expected inflated payoff is
`4(1−q)−pq`. Accurate reporting pays strictly more when `q > 3/(4+p)`.
At equality both are optimal. With `p=8`, two cards are a tie and three are
the first available budget making accurate reporting strictly better.

Decisions compare integer numerators, so ties do not depend on rounding.
The continuous chart crossing explains the equality; only integer card
budgets can be played. These are conditional payoff comparisons, **not a
Nash or Stackelberg solution** for a strategic human and critic. If the human
rejects a matching sample or accepts a mismatch, realized points differ from
the forecast. False rejection of an accurate report gives the agent 0.

Human decision points are +3 for accepting accurate, +2 for returning inflated,
−6 for accepting inflated, and −2 for returning accurate. Every inspected card
costs 0.25 human points, whatever the verdict. Penalties are not transfers to
the human. All rewards, losses, and costs are fictional illustration choices.

## Reproduction and scope

`web/science-engine.js` is the sole game definition and runs in both the
browser and Node tests. `makeRound(config, seed)` reconstructs each example.
A browser-generated 32-bit seed drives a deterministic xorshift generator and
Fisher–Yates audit order. The generator is for replayable examples, not a
cryptographic or research-grade sampling guarantee. Exact inclusion
probabilities refer to the stated uniform-subset model.

JSON exports retain the schema, seed, policy, settings, all original/reported
readings, audit indices, forecast, reviewer finding, human verdict, points,
and timestamps. Export includes completed rounds only. Nothing is uploaded or
persisted; reload clears the session. Client code contains the hidden answers,
so this is not a secure, blinded benchmark. Repeated play can change the human's
strategy. Neither this model nor its records have Lean proofs.

For the AISI Paper 1 audit-game application, the next research step would be
to measure real reviewer false negatives, false positives, and cost on held-out
tasks, then test incentive predictions under that uncertainty. The existing
oversight game's deterministic defense is a separate specification, not `q`.

Methodological motivation: [Bowman et al. (2022)](https://arxiv.org/abs/2211.03540)
use independent answers to assess oversight; [Barnes (2020)](https://www.alignmentforum.org/posts/PJLABqQ962hZEqhdB/debate-update-obfuscated-arguments-problem)
explains why locating flaws can be expensive. Neither source supplies this
catalyst game or its numerical payoffs.

Checks: `node tests/check_science.cjs` covers payoff thresholds, exact ties,
all audit subsets, replay, all outcomes, and UI round/export state. This demo
adds no dependencies, model spending, or new empirical claims.
