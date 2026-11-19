# Original post: mathematics and retained experiment

[Repository guide](../README.md) · [All games](../games/README.md) · [Data catalogue](../data/README.md)

This is the starting study behind [When Defection Stops Paying: Why Utility
Thresholds Matter for AI Safety](https://www.lesswrong.com/posts/HJSWoWCQefj2L8W8d/when-defection-stops-paying-why-utility-thresholds-matter-1).
Its saved payoff grid and theoretical cost calculations are separate. The
later [controlled cost-study framework](experiments.md) has no new live results.

## Reproduce offline

From the repository root, with Python 3.11+:

```sh
python3 reproduce.py --data-only
```

For five figures, an HTML report, and JSON/CSV tables, install matplotlib and
run without `--data-only`:

```sh
python3 -m pip install 'matplotlib>=3.8,<4'
python3 reproduce.py
```

Open `report/index.html`, or run `python3 serve.py` and follow the report link.
Figures are PNG and SVG. The first four illustrate the mathematics; the fifth
uses saved model responses. `--output PATH` selects another output directory.
Generated output is ignored by Git. Reproduction makes no model calls.

[`gut/game.py`](../gut/game.py) supplies the exact payoff arithmetic and theory
grid; [`gut/study.py`](../gut/study.py) audits the original observations;
[`reproduce.py`](../reproduce.py) builds the report. The original interactive
calculator is [`web/index.html`](../web/index.html).

## The mathematical starting point

Each player chooses C or D. Payoff pairs list the row player's points first:

| Row / column | C | D |
| --- | --- | --- |
| C | (R, R) | (S, T−k) |
| D | (T−k, S) | (P−k, P−k) |

The **baseline** is strict Prisoner's Dilemma when `T > R > P > S`.
The nonnegative cost `k` is paid only by a player choosing D.

- Against C, the two actions tie at `k = T−R`.
- Against D, they tie at `k = P−S`.
- Above both thresholds, C strictly earns more against either opponent action.
- At a threshold, both actions are optimal in the corresponding comparison.

For the original `(T,R,P,S)=(5,3,1,0)` example, the thresholds are 2 and 1.
Subtract baseline P from every payoff and divide by baseline `R−P` to put
games into common units. This gives `R=1`, `P=0`, `T=2`, `S=−0.5`, and `z=k/2`.
The normalized thresholds are `z=T−1` and `z=−S`.
We retain the original units when applying a cost; we do not normalize again
after changing the table.

The signs of `1−T+z` and `S+z` determine the four incentive regions. Crossing
one threshold first gives either a Chicken region (opposite actions pay) or a
Stag Hunt region (matching actions pay). Exact equalities remain explicit
boundaries. These names describe response patterns, not a complete ordering of
every adjusted payoff. Strict PD alone does not imply that mutual cooperation
always maximizes the sum of points.

The theoretical 625-table grid uses 25 equally spaced values each of
`S ∈ [−1,−0.05]` and `T ∈ [1.05,2]`. Against D, the threshold depends only on S,
so there are 25 distinct thresholds. These are calculations, not model trials.

## What the saved experiment establishes

The **separate empirical grid** has 13×13 values of S and T from −1 to 2 in
steps of 0.25, with `R=1`, `P=0`, and no added penalty. It includes PD, Chicken,
Stag Hunt, cooperation dominance, and boundary cells.

Four model identities each played two label blocks through independent,
stateless row and column requests. Both players saw the full table and were
told to maximize their own points. Neither saw the other's choice. A/B labels
reversed between blocks. Requested reasoning was low, the output limit was
4,096 tokens, and temperature used the provider default. Returned identities
and original request settings are retained; these are historical endpoints,
not a statement about currently available models.

| Quantity | Recomputed result |
| --- | ---: |
| Scheduled and recorded paired games | 1,352 |
| Games with two valid actions | 1,350 |
| Recorded model decisions | 2,704 |
| Invalid actions | 2 |
| Individually valid partners excluded with an invalid action | 2 |
| Choices in the paired analysis | 2,700 |
| Dominant-action matches / choices in strict-dominance regions | **1,277 / 1,280 (99.77%)** |

The data reader verifies hashes, identities, prompts, payoffs, label blocks,
and all scheduled records. It recomputes actions from raw answers instead of
trusting old summary scores. Missing or duplicate records stop reproduction;
invalid answers remain in the data. See [data provenance](../data/post/README.md).

There are at most **two games per model per payoff setting**. These are
exploratory observations. Cooperation rates in Chicken and Stag Hunt do not
by themselves establish correct choices, because the best response depends on
the opponent. The grid did **not** test responses to the defection-cost
intervention. It does not establish precise behavioral thresholds or real-world
safety. Reported beliefs and confidence are retained but are not used to score
the post's heatmap or dominance result.

## Earlier repository snapshot

The repository was simplified around the post on 9 November 2026. Older
engines, unrelated datasets and planning scaffolding were removed from the
active tree; advanced risk paths identified as incorrect were removed, not
certified as fixed. Later oversight and uncertainty games are separately
specified additions, described in the [current catalogue](../games/README.md).

The complete earlier tree remains at
[`before-lesswrong-simplification-2026-11-09`](https://github.com/AI4Collaboration/Game-Utility-Threshold/tree/before-lesswrong-simplification-2026-11-09)
(commit `63e411fb54e7eaab00bd38b72f27dd7c3e32f0fd`). Historical experiments are
not relabelled as new runs or pooled into the current evidence.
