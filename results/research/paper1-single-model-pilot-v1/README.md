# Single-model Paper 1 pilot: frozen run record

The user approved **US$20 total**, including retries, on 7 November 2026
(America/Toronto). The approved design contains **736 decisions**, eight per
setting, for the `z-ai/glm-5.3` candidate. This is a pilot to test the prompts,
collection and useful ranges; it does not provide confirmation precision.

At preparation, **no model calls have been made for this study**. Collection is
waiting for locally configured OpenRouter credentials. A manifest or public
price quote is not an observation. Read the [protocol](../../../docs/research/paper-one-protocol.md)
for the scientific questions and interpretation limits.

- `manifest.json` exactly matches the previously reviewed frozen design.
  Its hash is `de8aab8a060598ac68faac7068f9fd639a91717ce675d66da285cc1541481668`.
- `authorization.json` records the one cumulative spending cap for this study.
- `public-price-quote.json` records a fresh public catalog check with maximum
  initial-call reservations of **US$16.6110208**. This is a conservative
  reservation, not an expected bill. Retry reservations must fit inside the
  same US$20 total.

Run from the repository root with credentials in the local environment or
gitignored `.env`:

```bash
uv run --frozen run_research_study.py collect --live \
  --manifest results/research/paper1-single-model-pilot-v1/manifest.json \
  --output results/research/paper1-single-model-pilot-v1/observations.json \
  --log-dir logs/research/paper1-single-model-pilot-v1 \
  --budget-usd 20 --batch-size 32 --max-samples 4
```

The collector refreshes availability and pricing before paid requests. Keep
`observations.json` and `observations.ledger.json` together and reuse these exact
paths when resuming. Never delete or replace a ledger to restore an allowance.
Unknown-charge attempts retain their reservations. An unexpected provider
billing excess stops collection; the software cannot reverse a provider charge.
Keep native Inspect logs in the stated local log directory; inspect them for
credentials before preparing any public archive.

After collection, audit all records and produce the report:

```bash
uv run --frozen run_research_study.py audit \
  --manifest results/research/paper1-single-model-pilot-v1/manifest.json \
  --observations results/research/paper1-single-model-pilot-v1/observations.json
uv run --frozen analyze_research_study.py \
  --manifest results/research/paper1-single-model-pilot-v1/manifest.json \
  --observations results/research/paper1-single-model-pilot-v1/observations.json \
  --output results/research/paper1-single-model-pilot-v1/report
```

Report invalid, missing and unattempted episodes separately. Preserve the full
planned denominator and unresolved threshold results. Complete a pilot decision
memo before freezing any fresh confirmation study; this budget approval does
not cover additional studies.
