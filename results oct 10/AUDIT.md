# Experiment code and result audit — 12 October 2026

**No result-changing errors were found in the archived experiment or the four publication figures.** The independent audit checks all 10,096 records, all 5,048 paired games, and every empirical heatmap cell. The four figures and their numerical results are unchanged.

## What was verified

- Every scheduled request ID is present exactly once. The saved code reproduces each recorded request payload, label mapping, payoff case, and reservation amount from its manifest and catalog.
- All four displayed payoff cells were parsed from each saved prompt. Row/column perspective, own-payoff perspective, alternating A/B labels, and normalized coordinates agree with the game being scored. Both players in every pair saw the same game.
- Final actions and opponent beliefs were decoded independently from raw response JSON. There are 10,066 valid actions and 5,021 valid joint outcomes. Invalid outputs remain excluded rather than filled in.
- A separate oracle enumerates matrix outcomes and computes expected payoffs directly. It does not call the experiment's scoring or best-response functions. It matches the saved Nash, pure-profile Pareto, welfare, regret, best-response, and payoff-threshold results. Expected-utility comparisons for every usable decision, every saved joint-outcome score, and every deviation-cell denominator/source ID were checked.
- The arrays actually passed to the plotting functions were captured and checked: 1,352 values across the cooperation and expected-regret heatmaps, 16 presentation-control bars, and 32,400 nonboundary cells in the analytic game map. Axis centers and common color scales agree with the data.
- The presentation-control bars use exactly the same valid PD case/block identities in both presentations for this dataset.
- Returned model identifiers match requested identifiers for every successful response. Provider-reported costs reconcile to $40.39529008; accounted costs, including the unknown-cost reservation, reconcile to $40.44063951. No recorded charge exceeded its reservation.

Machine-readable results: [record and scoring audit](audit/independent_audit.json), [plot-array audit](audit/plot_data_audit.json).

## Issues corrected

1. **Unsafe resume after a lost ledger.** The runner previously could initialize a fresh budget ledger in a directory containing old records. It now refuses missing or inconsistent accounting, duplicate attempt IDs, and interrupted log/ledger states that require reconciliation. Duplicate model selections are also rejected before scheduling. The archived run had a complete, consistent ledger and no duplicate IDs, so this does not change its costs or results.
2. **Reproduction overwrite protection.** The offline reproducer now refuses an output directory containing different raw records and refuses output inside the source-data directory or at the bundle root.
3. **Broken report links.** Offline reproduction now supplies the methods file. The report links an implementation patch only when that optional file exists.
4. **Independent verification gap.** The earlier score replay reused the same engine. New audit scripts check the archived results with a separate matrix-enumeration oracle and inspect the numeric arrays passed to plotting. The offline reproduction now runs the record/scoring audit automatically.

Request prompts, model IDs, request settings, saved responses, theoretical formulas, and publication figure data were not changed by these fixes.

## Validation and reproduction

From this folder:

```sh
python -m unittest discover -s tests
python scripts/audit_experiment.py --data data --output reproduced/independent_audit.json
python reproduce.py
python scripts/audit_plot_data.py --data data --output reproduced/plot_data_audit.json
```

The experiment tests and added regression tests pass. Full offline reproduction was also checked with outbound socket connections blocked and no API key. No new paid calls were made. The raw-log SHA-256 remains `8c3f995078bd7b0ef14e476ebd653a42b5bbff6e49b44a4ed0086ecd37b13c79`.

## What this audit does not establish

The record count includes one explicitly reconstructed, unreturned request, not 10,096 successful completions; there are 10,095 successful API responses. The stored metadata identifies the requested/returned endpoints, but cannot independently attest to a provider's underlying weights or implementation.

The leading grid has at most two games/four decisions per cell. Label blocks are not repeated samples of an identical prompt, provider sampling defaults differ, and the own-payoff experiment was exploratory. These remain descriptive results. Stated-belief regret measures action–belief consistency; it does not establish belief calibration or reasoning faithfulness. There was no binary search or fitted empirical switching-threshold displacement. The whole S–T grid is broader than strict Prisoner's Dilemma.
