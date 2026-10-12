# Payoff phase-space experiment and LessWrong figure pack

This folder preserves the code and records used in the October 9, 2026 experiment,
under the requested folder name **results oct 10**. It is an isolated snapshot;
the current repository root contains a separate, subsequently updated phase-space
implementation. Run the commands below **from this folder** so Python uses this
experiment's engine and runner.

Start with [the seven curated publication figures and captions](figures/index.html)
or [copy-ready captions](figures/CAPTIONS.md). The two lead figures show:

1. Cooperation frequency as normalized S and T change, for all four models.
2. Expected utility lost relative to each decision's stated-belief best response.

“Susceptibility” here means response to payoff incentives. The second figure
measures utility loss, **not a measured displacement of a behavioral threshold**.
We ran grid searches and raw payoff sweeps, not binary search.

## Offline reproduction — no key and no API calls

Use Python 3.12 (the original run used Python 3.12.12):

```sh
cd 'results oct 10'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python reproduce.py
```

Open `reproduced/post-figures/index.html` for the publication set and
`reproduced/index.html` for the full 24-figure gallery and experiment report.
The detailed theory report is `reproduced/theory_comparison.html`.
`requirements.lock.txt` records the installed environment; `requirements.txt`
lists direct dependencies for a compatible environment if exact pins are
unavailable on your platform. Matplotlib figures are saved as PNG and editable SVG.

## Files

- `run_phase_space.py`: direct-HTTP OpenRouter runner, budget reservations,
  resumable manifests, strict action parser, and raw request/response records.
- `utility_threshold/`: engine snapshot, including the new normalization and
  theoretical-comparison modules. Original engine provenance is recorded below.
- `scripts/render_phase_space.py`: analytic and empirical phase maps and sweeps.
- `scripts/compare_phase_space_theory.py`: decision/game audits, threshold
  comparisons, and S–T deviation maps.
- `scripts/report_phase_space.py`: coverage, model identity, parsing, and cost audit.
- `scripts/render_lesswrong_figures.py`: curated figures and publication captions.
- `reproduce.py`: offline reproduction orchestration.
- `tests/`: budget/resume, parsing, analytic thresholds, invariance, and heatmap checks.
- `data/`: compressed raw records and summaries; manifests, catalog snapshot,
  costs, and derived data. Compressed JSONL retains the original API responses.
- `figures/`: ready-to-use PNG/SVG figures, captions, and manifest.
- `docs/phase-space-experiment.md`: full methods, limitations, and execution details.
- `PROVENANCE.json`: original base commit, dates, and raw-log hash.
- `SHA256SUMS.txt`: archived source/data/figure checksums.

## Experiment and limits

Four exact model IDs were used: `z-ai/glm-5.3`, `qwen/qwen3.8-2.4t-a95b`,
`openai/gpt-6-astra`, and `anthropic/claude-fable-5.1`. This is not a claim of a
universal model ranking. There were 10,096 calls / 5,048 paired games including
pilots and controls; 10,066 actions and 5,021 joint outcomes were valid.
Provider-reported cost was $40.39529008; conservatively accounted cost was
$40.44063951, including a $0.045349425 reserve for one unreturned request.

The primary grid had four label blocks. The exploratory own-payoff grid used
in the lead figures had two blocks: at most two games/four decisions per cell.
Exact indifference accepts either action; invalid outputs are retained and
excluded from appropriate denominators. Stated beliefs need not be calibrated
or faithful accounts of reasoning. Multiple equilibria exist in parts of the
space. A non-pure-Nash realized profile is not automatically a reasoning error.
The full grid extends beyond strict Prisoner's Dilemma, which occupies S<0,T>1
when R=1,P=0. C-choice is an analytic action label, not a general safety metric.

## Running new paid experiments

The offline reproduction above requires no credentials. New model calls require
`OPENROUTER_API_KEY` in your environment or an ignored `.env`. Never commit it.
Use a fresh output directory and an explicitly chosen budget. The runner's
historical catalog snapshot is in `data/openrouter_catalog.json`; for a new live
run, verify current availability/prices and pass an updated catalog explicitly.

```sh
python run_phase_space.py grid --replicate 0 --max-tokens 4096 \
  --catalog /path/to/current-openrouter-models.json \
  --output live-runs/new-experiment --budget 50
```

All phases of a given run must share one output directory/ledger. The runner
caps this experiment at $50, reserves costs before submission, retains full
reservations when charges are unknown, and prevents simultaneous writers.
No new paid experiments were made when preparing this publication folder.

## Provenance

The original engine came from repository commit
`b4a2e54b6aa34973d2849ff92e38502b4b0e6869`. This folder snapshots that engine plus
the code developed for the experiment. The runner's default catalog path was
made portable; its request payload and sampling logic are unchanged. The
publication folder is added to the newer repository without replacing its
root implementation. See the repository LICENSE for source licensing.

The normalization and analytic classification follow
[Falmagne's SIAM article](https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/).
The article did not run these LLM experiments or prescribe binary search.
