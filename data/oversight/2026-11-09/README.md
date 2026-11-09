# Oversight validation, 9 November 2026

Completed: **3,660 main-study decisions + 12 separate pilot decisions**, all
valid. Total reported OpenRouter cost: **US$0.670963194**, against a US$50 cap.
There were no automatic retries, missing completions, or unresolved costs.

The frozen plan was committed before collection in `4638954`. The study varies
defense only, with a small separate wording check. Read the
[protocol](../../../docs/oversight-validation-protocol.md) and
[findings and limitations](../../../docs/oversight-validation-results.md).

## Contents

* `plan.json.gz`: complete prompts, settings, prices, counterbalancing and
  randomized schedule; main and pilot stages explicitly separated.
* `records.jsonl.gz`: every original start/completion record and full raw API
  response, including returned identities, token usage and costs. No API key.
* `models.json` and `*-endpoints.json`: selected specifications and public
  provider metadata captured before collection.
* `provenance.json`: counts, collection times in UTC, costs and audit facts.
* `checksums.json`: SHA-256 of the source artifacts. Regenerated analysis files
  are excluded; tests independently compare their counts against the raw data.
* `analysis/`: all planned observations, cell and block tables, summary,
  report HTML, and separate PNG/SVG figures.
* `analysis-requirements.txt`: versions of the scientific Python packages and
  their dependencies used for the report (Python version is in summary.json).

## Reproduce without paid calls

From the repository root:

```sh
python3 -m pip install -r data/oversight/2026-11-09/analysis-requirements.txt
python3 oversight_experiment.py report data/oversight/2026-11-09
python3 serve.py
```

Open <http://127.0.0.1:8765/validation/report.html>. The report loader reads the
compressed files directly and recomputes scores from raw answers. Collection
into a published compressed run is blocked. No credentials are needed to
reproduce the analysis. Re-rendered images can differ across operating systems
or plotting-library versions; source records and numerical counts are fixed.

Each repeated request is a draw under one model/provider/prompt configuration,
not an independently trained agent. The study validates conditional payoff
choices; it does not empirically validate equilibria or real-world safety.
