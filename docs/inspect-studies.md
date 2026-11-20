# Native Inspect studies: collection and recovery

This is the operating guide for implemented code in [inspect_study.py](../inspect_study.py)
and [gut/inspect_study.py](../gut/inspect_study.py). No live results are claimed.
The four canonical experiments keep their existing collector and separate history.
A native adapter also makes their existing v2 prompts/tables available under this
shared budget. For the fully selected models, sample counts, analysis and one-command
workflow, use the [manager handoff](manager-handoff.md).

## Exactly what varies

| Study ID | Research comparison | Fixed quantities |
| --- | --- | --- |
| `pd`, `stag_hunt`, `chicken`, `battle_of_sexes` | Existing v2 cost conditions; BoS cost directions and sparse scale/offset controls reported separately. | Existing starting tables; no sweep of their base rewards. |
| `private_pd_v1` | Sweep public defection cost; pair revealed/hidden trials at each cost. | Starting payoff tables, both private profiles, equal prior, payoff units. |
| `private_stag_hunt_v1` | Same design, with the separate private Stag Hunt tables. | Starting tables, profiles, equal prior, payoff units. |
| `audit_threshold` | Sweep only checking probability q, including exact response boundaries and points 0.02 to either side. | Unchecked rewards (0.2, 0.1) / (0.8, 0.7), equal prior, checked rewards (−0.5, −0.6), penalty 0.5, defender payoffs. Only the attacker is a model. |
| `audit_information` | Reveal/hide the SAME actual reward profile before the defender chooses q. Compare chosen q, violations and defender payoffs. **No continuous parameter sweep.** | Profiles (0.8, 0.1) / (0.2, 0.7), equal prior, checked rewards (−0.5, −0.6), added penalty 0, defender payoffs. Both players are models. |

The two audit instances use the same published payoff rules. Their numbers and
LLM collection controls are our adaptations, not an empirical replication.
Each information pair shares actual rewards, type, presentation block and environment
seed. Neither transcripts nor sampled model answers are shared between conditions.

The original shared-offset profiles have zero value of revelation for an ideal
defender at the default settings: one policy can serve both profiles optimally.
They remain in the threshold benchmark and exploratory API. The separately named
target-preference instance makes information relevant: revealed defenders can
deter either profile, but the required checking ranges do not overlap. The exact
favorable-tie optimum is 0 when revealed versus −19/65 when hidden. These are
conditional mathematical predictions, not observed LLM results; unfavorable ties
and unattained limits are also retained. Zero added penalty still leaves negative
checked payoffs.

In the private games, knowing one's own rewards means hiding the opponent's
rewards does not move one's unconditional dominance threshold. Information
effects concern the region where choices depend on the opponent.

## Presentation controls

For two actions: two neutral label mappings × two display orders = four blocks.
For the audit game's three actions: three cyclic label mappings × three cyclic
orders = nine blocks. Every underlying action has each label in each position
equally often. These are balanced rotations, not all 36 permutations. Payoff
rows/columns and action parsing follow the mapping. The audit defender chooses a
continuous probability; the presentation controls reorder the displayed discrete
follower alternatives, not that probability's meaning.

Each information pair uses the same block. Schedules are seeded and shuffled.
Repetitions mean repetitions **per profile, condition, cost and block**, not total
calls. The preparation command prints total trials and maximum role calls.

## Offline check

Install `python -m pip install '.[inspect]'`. These commands make no model calls:

```sh
python inspect_study.py prepare runs/inspect-check \
  --studies audit_information private_pd_v1 \
  --repetitions 1 --budget-usd 1
python inspect_study.py run runs/inspect-check --stage pilot --max-trials 100
python inspect_study.py run runs/inspect-check --stage main --max-trials 10
python inspect_study.py status runs/inspect-check
python inspect_study.py export runs/inspect-check runs/inspect-check-export
inspect view --log-dir runs/inspect-check/logs
```

The single repetition is a software check, not an adequate empirical sample.
Synthetic trials exercise budget reservations of one cent per possible role call;
their reconciled actual spending is always zero. Every trial has its own native
`.eval` file under `logs/<job-id>/`; the viewer can also open that subfolder directly.

## Live preparation and collection

Create a local JSON file containing only public model selections, for example
`[{"id":"openai/gpt-4.1-mini","provider":"openai"}]`. The provider is an exact endpoint
tag, not an arbitrary label. This example specifies a format, not the final model
selection. Preparation reads public OpenRouter endpoint metadata and freezes
identities, prices and context/output limits. It does not call a model.

Use the same prepare command with `--mode openrouter --models /path/to/models.json`,
an explicitly chosen repetition count and a total `--budget-usd` (at most the
authorized $50). Set `OPENROUTER_API_KEY` in the local process environment; never
put it in the manifest. Add `--live` to subsequent run commands.

Choose models, repetitions and output limits before preparing the final study.
Successful compatibility pilots check valid output and transport/billing identity;
they do not select for agreement with theoretical predictions. Main collection
cannot start until every separate pilot succeeds. Failed pilots are preserved;
changed settings require a new study. Pilot records never enter main estimates.

The same budget covers every selected game, model, role and both stages in this
manifest. It does **not** coordinate unrelated API traffic or other study folders.

## Budget and restart behavior

- Before dispatch, atomically save and sync a reservation for all possible role
  calls in the trial. Reserve full endpoint input-context cost plus the output cap
  and request fee for each role, rather than guessing prompt token counts.
- Use pinned providers, no fallback routing, provider price ceilings, bounded
  output, no tools, and disabled Inspect **and SDK** retries. Recheck endpoint
  metadata before each invocation.
- Reconcile using provider-reported raw `usage.cost`, not Inspect's estimated
  bill. Unknown costs keep the full reservation. Billing or identity anomalies
  stop collection. A reported cost beyond the reservation permanently blocks
  further dispatch from that manifest.
- Run one trial at a time under an OS file lock. A crash releases the lock.
  Complete JSON records are installed atomically; incomplete temporary files
  cannot become reservations or settlements.
- Run the same command again to resume. Completed trials are skipped. If a
  native log finished before the settlement was saved, recovery adopts it.
  A started trial without a usable final log is marked interrupted, keeps its
  reservation, and is **never automatically resent**.
- To continue the remaining trials after examining an unresolved attempt:
  `python inspect_study.py review RUN --job ID --note "explanation of the review"`.
  This records the review without clearing the charge hold or replacing the
  observation. It cannot bypass a failed-pilot gate or a price-ceiling breach.
- Code, dependencies, reward configurations, sample IDs, model settings and
  schedules are frozen and hashed. Changed code/settings require the original
  environment or a separate study; native-log or ledger edits fail validation.

The conservative reservations can stop collection with unused actual credit.
That is intentional when a charge is unknown. Exports retain all planned
observations, including not-started, interrupted, invalid and failed trials.
They include stage, model, presentation and matching IDs for analysis. Native logs
retain role calls and provider-exposed reasoning without forwarding it to opponents.
Unavailable private reasoning is not reconstructed.

## Verification and remaining scope

[Tests](../tests/test_inspect_study.py) exercise budget exhaustion, restart without
duplicates, crashes after completed logs, unresolved charges, concurrent locks,
manifest/log corruption, endpoint changes and the real OpenRouter adapter with a
fake SDK response. No paid calls are used by these tests. The
[presentation tests](../tests/test_presentation.py) check payoff-preserving
permutations, information isolation and an independently calculated audit optimum.

These changes finish the collection path, not empirical validation. The
[manager package](manager-handoff.md) now fixes the initial sample/models and
implements descriptive information effects, uncertainty and missing-data bounds.
Live compatibility and collection still need to run; precise fitted behavioral
crossings and broader paper-level analyses are not claimed.
The private-game report now retains individually valid choices and separates
presentation blocks; its paired comparisons still require valid paired outcomes.

References for the integration: [Inspect model roles](https://inspect.aisi.org.uk/models.html#model-roles),
[native logs](https://inspect.aisi.org.uk/eval-logs.html),
[OpenRouter provider price ceilings](https://openrouter.ai/docs/guides/routing/provider-selection#max-price).
