# Data and results catalogue

[Home](../README.md) · [Games](../games/README.md) · [Public results](https://ai4collaboration.github.io/Game-Utility-Threshold/results.html)

Two **historical live model studies** are retained in this active tree.
**Zero live studies have been completed under the selected v2 plans.** Historical
records are preserved for their original questions; neither dataset is counted
as completion of the revised validation. Interactive games, theoretical plots
and synthetic trials do not add empirical evidence. See the
[current evidence assessment](../docs/controlled-thresholds.md#earlier-evidence-what-can-and-cannot-carry-over).

The [new controlled collection](controlled/2026-11-19/README.md) contains frozen
plans and eight archived HTTP 402 pilot failures. It has **zero model choices**;
the account-credit block must be resolved before validation can proceed.
The [replacement-key attempt](controlled/2026-11-19-funded/README.md) likewise
contains one HTTP 402 rejection and no model choices. Both attempts are retained.

| Dataset | What was measured | Where to start |
| --- | --- | --- |
| [post/](post/README.md) | Four models on 169 symmetric payoff tables, two label blocks. 1,352 scheduled paired games; 1,350 valid pairs. Covers PD, Stag Hunt, Chicken, dominance and boundary regions. | [Methods and interpretation](../docs/post-study.md), [raw records](post/records.jsonl.gz), [manifest](post/manifest.json) |
| [oversight/2026-11-09/](oversight/2026-11-09/README.md) | Three models responding to imposed human defense levels, plus a wording check. 3,660 main decisions and 12 separate pilot decisions. | [Findings](../docs/oversight-validation-results.md), [protocol](../docs/oversight-validation-protocol.md), [raw records](oversight/2026-11-09/records.jsonl.gz), [analysis](oversight/2026-11-09/analysis/) |

The first study does not test an added defection cost or Battle of the Sexes.
The second tests choices conditional on a stated human defense, not both
parties learning or selecting an equilibrium. Neither establishes real-world safety.

## Locate an artifact

- **Original prompts and responses:** the compressed records and manifests in
  each dataset; the oversight frozen plan is [plan.json.gz](oversight/2026-11-09/plan.json.gz).
- **Counts and plots:** oversight [summary](oversight/2026-11-09/analysis/summary.json),
  [observations](oversight/2026-11-09/analysis/observations.csv),
  [cells](oversight/2026-11-09/analysis/cells.csv) and
  [report](oversight/2026-11-09/analysis/report.html). The original post report is
  [rebuilt offline](../docs/post-study.md#reproduce-offline) into `report/`.
- **File integrity and collection history:** post [manifest](post/manifest.json);
  oversight [checksums](oversight/2026-11-09/checksums.json) and
  [provenance](oversight/2026-11-09/provenance.json).
- **Toy runs/new work:** local `runs/` directories are generated and ignored by
  Git. They are not part of these published model datasets.
- **Earlier work:** the [archived repository](../docs/post-study.md#earlier-repository-snapshot)
  is separate, not pooled into current study totals.

Retain source bytes and explicit failure records. Regenerate analysis through
the documented commands rather than editing measured counts. A new empirical
study needs its own plan, raw records, provenance and clearly stated scope.
