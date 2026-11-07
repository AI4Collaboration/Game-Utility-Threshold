# Reproducible Paper 1 study designs

These files specify **unrun pilots**. They do not contain new model observations.
Read the [protocol](../../docs/research/paper-one-protocol.md) before changing a
study. Python 3.11+ and the `research` extra are required.

| Configuration | Independent episodes | Model decisions | Purpose |
| --- | ---: | ---: | --- |
| `fixed_opponent_single_model_pilot.json` | 736 | 736 | Smaller first pilot using the GLM candidate only |
| `fixed_opponent_pilot.json` | 2,944 | 2,944 | Primary one-shot payoff and known-policy comparisons across four candidate models |
| `self_play_effort_pilot.json` | 2,560 | 5,120 | Separate paired games with low/low, low/high, high/low and high/high requested reasoning effort |
| `affine_controls_pilot.json` | 640 | 640 | Separate common-scale and common-offset checks |

Each cell has eight scheduled episodes: two complete four-condition label
blocks. Eight is a software/prompt pilot size, not sufficient precision for a
confirmation study. The 368-cell primary pilot's conservative simultaneous
half-width exceeds the probability scale at this sample size. A confirmation
plan must reduce or justify the claim family and specify its precision and
fixed sample size before collecting fresh observations. Do not combine these
three studies into one silently selected set of significance tests.

The models are existing repository candidates, not a ranking or promise of
availability. Quote and authenticated preflight validate current routes.
Requested reasoning effort is an experimental setting; it is not a measurement
of intelligence or equal compute across providers. Actual tokens and billing
receipts are saved. Prompts have no game-family names or narrative framing.

## Freeze and inspect, without model calls

```bash
uv sync --frozen --extra research
uv run --frozen run_research_study.py plan \
  --config experiments/paper_one/fixed_opponent_pilot.json \
  --output work/paper_one/manifest.json
uv run --frozen analyze_research_study.py \
  --manifest work/paper_one/manifest.json \
  --output work/paper_one/design-preview
```

The manifest contains every matrix, role, label permutation, requested effort,
replicate, primary measure, known-policy prediction, and prompt hash. The
collection order shuffles complete label blocks across conditions. It makes
provider sampling no more independent than the API actually is: the scheduler
seed does not control provider randomness. Manifests survive JSON round trips
and are rebuilt and checked before collection or analysis.

The HTML report includes separate calculated-payoff panels, empty observation
panels, denominators, CSV, full JSON, PNG and editable SVG. No observations are
invented to make an empty chart attractive. Actual post-intervention game
classes are recorded rather than continuing to call every treated matrix PD.
The high-temptation sensitivity point need not make mutual C maximize total
payoff; that property is recorded separately.

## Read public prices, without model calls

```bash
uv run --frozen run_research_study.py quote \
  --manifest work/paper_one/manifest.json \
  --output work/paper_one/public-price-quote.json
```

The quote reads public endpoint catalogs only. It reserves a conservative
input-byte upper bound, maximum output tokens, request fees and a 10% margin.
It is not an expected invoice or an authorization to spend. Separately
budgeted rate-limit retries can consume more than the initial-call total.
All spending is still limited by the explicit collection ledger cap; an
unexpected provider billing excess halts further work but cannot undo a charge.

On 7 November 2026, the four-model fixed-policy design quoted approximately
$399.86 in initial-call reservations: $180.24 each for the OpenAI and Anthropic
candidates, $22.78 for Qwen, and $16.61 for GLM. Prices and availability must be
checked again at collection. A smaller first pilot can be frozen from a copy
of the config containing only one selected model; it has 736 decisions. Its
results are a pilot for that model, not a four-provider comparison.

## Collect only after selecting a budget

Put `OPENROUTER_API_KEY` in the local environment or gitignored `.env`; never
put it in a config, prompt, shell argument, or committed artifact. Substitute
the explicitly approved ceiling for `APPROVED_USD_LIMIT` below.

```bash
uv run --frozen run_research_study.py collect --live \
  --manifest work/paper_one/manifest.json \
  --output work/paper_one/observations.json \
  --log-dir work/paper_one/inspect-logs \
  --budget-usd APPROVED_USD_LIMIT
```

Each paired episode reserves both calls before sending either. Raw completions,
parser fields, requested effort, prompt hash, returned model, usage, receipts,
source hashes, environment versions, endpoint metadata, and native Inspect
traces are retained. A returned malformed answer is invalid; an absent
response after a transport error is missing. For a paired episode, any missing
role makes the primary joint outcome unavailable, while both role-level
records remain. Budget exhaustion leaves unattempted episodes explicitly
unrecorded. Neither an invalid answer nor a missing answer counts as D.

The output and `.ledger.json` file must stay together. Repeat the command with
the same files to resume; the cap cannot silently increase. Changed design or
collection source, a foreign ledger, or a reservation without a checkpoint
blocks automatic resume. Reconcile an uncertain call with logs and provider
receipts; never delete its reservation to get a new spending allowance. An
ordinary preflight error preserves an empty, bound pair for a safe retry.
There are no automatic parse retries or silent replacements of poor results.

## Audit and report saved observations

```bash
uv run --frozen run_research_study.py audit \
  --manifest work/paper_one/manifest.json \
  --observations work/paper_one/observations.json
uv run --frozen analyze_research_study.py \
  --manifest work/paper_one/manifest.json \
  --observations work/paper_one/observations.json \
  --output work/paper_one/report
```

The audit checks membership, duplicate episodes, prompt/effort provenance,
strict parser types, raw completion parsing and recomputed scientific scores.
It detects inconsistencies, not deliberate fabrication of an entire consistent
record: preserve the native logs and provider receipts as independent evidence.
Analysis records its own source hashes so a later correction is attributable.
Raw historical observations must stay unchanged.

Only tested settings receive uncertainty bars. Valid-output means and
all-scheduled completion bounds answer different questions. Population
interpretation requires the documented independence and hypothetical complete
outcome assumptions. A crossing is left unresolved unless the declared
assumption and evidence justify a bounded result. Numerical ties in the new
abstract game study allow either action; the older oversight model's explicit
cooperation-at-equality rule remains a separate convention.
