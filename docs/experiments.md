# One game, one changing cost

The first experiment fixes the baseline at T=2, R=1, P=0, S=−0.5. Choosing
D subtracts z from that player's payoff. Nothing else in the payoff table is
changed independently. We show the final adjusted table without telling the
model a preferred answer or asking it to explain its reasoning.

The ten costs are 0, 0.25, 0.45, **0.5**, 0.55, 0.75, 0.95, **1**, 1.05,
and 1.25. Cooperation ties with defection against D at 0.5, and against C at
1. Below 0.5, D is strictly better against either action; above 1, C is.
Between these values the best response depends on the opponent. We do not fit
or assume a single behavioral threshold.

## Run the offline demonstration

```sh
python3 experiment.py plan runs/pd-demo
python3 experiment.py run runs/pd-demo
python3 experiment.py report runs/pd-demo --plot
python3 experiment.py proofs runs/pd-demo --check
```

Only the plot requires matplotlib. Only `proofs --check` requires the pinned
Lean toolchain (see [the proof guide](../lean/README.md)). All four commands
above are offline. Synthetic mode uses a deliberately artificial noisy rule;
its plots, summaries and verification manifests are marked **synthetic**.
Successful proof checking of synthetic choices is a software check, not model
evidence. Each output directory is a separate immutable plan; choose a new
directory when changing settings.

## Plan and collect real model responses

Use an exact model identifier and one provider endpoint supported by that
model. These are explicit choices, not hard-coded historical endpoints:

```sh
python3 experiment.py plan runs/pd-pilot --mode openrouter \
  --model YOUR_MODEL_ID --provider YOUR_PROVIDER_SLUG \
  --repetitions 10 --temperature 0.7 --max-tokens 512
python3 experiment.py run runs/pd-pilot --live --max-calls 20
python3 experiment.py report runs/pd-pilot --plot
python3 experiment.py proofs runs/pd-pilot --check
```

Set `OPENROUTER_API_KEY` in the environment before the live command. Keys and
authorization headers are never written into the plan or log. Set a spending
limit on the provider key: `--max-calls` limits **new attempts in that invocation**,
not dollars or cumulative spending. Run the same command again to continue
unattempted jobs. No live experiment was performed during implementation.

The default is a **pipeline pilot**, not a justified final research sample:
10 games for each of two label mappings at each of ten costs = 200 paired
games / 400 requests. Choose a final sample size and budget before collection.
At 20 complete games per cost, the conservative error radius is about 0.304.
For a radius at most 0.10, this bound requires at least 186 complete games per
cost, balanced between labels. More calls do not solve prompt or model bias.

Both players see the whole matrix from their own perspective. The calls are
stateless, with no sharing of answers; transport need not occur at the same
instant to keep decisions informationally simultaneous. The schedule shuffles
all requests using a recorded seed. This is a schedule seed, not a promise of
deterministic model responses. Each cost has equal planned counts for the two
A/B label mappings. Settings remain fixed within the run.

Routing uses one specified provider, no fallback, and requires support for
the supplied settings. Raw response metadata is retained. A returned model
identity mismatch is excluded and stops further live calls. API errors also
stop the live invocation. Invalid action content is recorded and excluded,
not replaced. See the official [OpenRouter request format](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)
and [routing controls](https://openrouter.ai/docs/guides/routing/provider-selection).

## Audit trail and interruptions

`plan.json` contains the exact prompts, settings, paired-game IDs, label maps
encoded by block, cost values, complete randomized schedule, and a checksum.
`records.jsonl` records a durable start before each call, followed by the raw
response body, HTTP status and timestamps. Usage, returned provider and model
identities stay in that body. Parsing always starts from the raw answer.

There are no automatic retries. If a process stops after recording a start,
the request might already have been billed. Resume skips it and reports the
missing completion. It never guesses an answer or resends the request.
One collector can hold the run lock. After a hard crash, remove `.collect.lock`
only after confirming the old process has exited. A truncated log line must
be investigated; the audit deliberately fails instead of discarding it.
Checksums detect inconsistency, not malicious rewriting or provider authenticity.

## Results and uncertainty

`analysis/cells.csv` and `summary.json` retain every planned cost, denominators,
the four joint outcomes, missing pairs, and individual response-status counts.
Primary summaries require both actions. A valid choice with an invalid partner
is excluded from the paired result but can still receive a conditional Lean
comparison against each possible action.

For each complete game define X as the fraction of its two players choosing
C: 0, 1/2 or 1. Compute a mean in each label block, then average those two
means with equal weight. Do not treat two players as two independent games.
If either label block has no complete games, the combined estimate is absent.

We use the bounded-variable inequality in [Hoeffding (1963), Theorem 2](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830).
For n0 and n1 complete games in the two blocks, the 95% radius is
`sqrt(log(40) × (1/n0 + 1/n1) / 8)`, clipped to [0,1]. These conservative,
pointwise bounds assume independent games and do not simultaneously cover
the entire curve. They do not establish representativeness across prompts,
model versions, providers or time. Shared service effects can violate the
independence assumption. Synthetic intervals demonstrate the calculation only.

Missing outputs may be selective; complete-case uncertainty does not fix that.
The separate `missing_lower` and `missing_upper` columns bound the finite
planned sample by treating every excluded pair as all-D or all-C. They are
missing-data bounds, not confidence intervals. The plot shows valid and planned
pair counts, and never substitutes zero for a missing estimate.
