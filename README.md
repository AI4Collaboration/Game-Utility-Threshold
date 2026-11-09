# Game Utility Thresholds

A small, reproducible starting point for [When Defection Stops Paying: Why Utility Thresholds Matter for AI Safety](https://www.lesswrong.com/posts/HJSWoWCQefj2L8W8d/when-defection-stops-paying-why-utility-thresholds-matter-1).

The starting point contains the post's symmetric, one-shot, two-player
games, its defection-cost calculations, and the saved experiment behind its
169-setting model heatmap. It has one game implementation, one data reader,
one reproduction command, and a small local explorer. The next addition is a
controlled PD cost experiment with a small Lean framework for verifying
recorded choices. See [the experiment guide](docs/experiments.md) and
[the proof guide](lean/README.md).

The same tools now also support fixed **Stag Hunt, Chicken, and Battle of the
Sexes** examples. [The four-game guide](docs/games.md) states their payoffs,
thresholds, collection design, and limits. The local explorer is at `/games`.

The **human–AI oversight lab** at `/oversight` now adds an observed human
defense choice, explicit resource/attack/harm payoffs, live exact thresholds,
pure Nash and Stackelberg solvers, and a toy-simulation tab with JSON/CSV exports.
See [the oversight guide](docs/oversight.md) for the executable assumptions,
tie handling, references, and the distinction between calculations and data.

## Start here

Python 3.11 or newer is enough for the game, data audit, explorer and tests.
No API key, paid call, JavaScript build, or extra package is needed for them.

```sh
python3 -m unittest discover -s tests -v
python3 reproduce.py --data-only
python3 serve.py
```

Open **http://127.0.0.1:8765/** to change the defection cost and inspect both
conditional thresholds. Use `--port 8766` if another process occupies the port.
The two presets follow the post's Chicken and Stag Hunt transition examples.
The explorer is a view of the calculations; it does not collect observations.

For the five figures, a readable HTML report, and the same JSON/CSV tables:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'matplotlib>=3.8,<4'
.venv/bin/python reproduce.py
```

Open `report/index.html`, or use the report link in the explorer. Figures are
saved as PNG and SVG. The first four illustrate the post's mathematics; the
fifth is reconstructed from saved model responses. Generated files are ignored
by Git. `--output PATH` selects another output directory. All reproduction is
offline and makes no model calls.

## What the code does

| File | Purpose |
| --- | --- |
| [`gut/game.py`](gut/game.py) | Exact payoff arithmetic, normalization, the two conditional thresholds, four incentive regions, and the 625-table theory grid. |
| [`gut/study.py`](gut/study.py) | Verify the retained data, reconstruct prompts, parse raw actions, and recompute cell and region counts. |
| [`data/post/`](data/post/) | Only the post's two collection blocks, including their original prompts, responses, settings, failures, and provenance. |
| [`reproduce.py`](reproduce.py) | Recreate the calculations, five figures, report, and count tables. |
| [`serve.py`](serve.py), [`web/index.html`](web/index.html) | A local view of the same payoff comparisons. |
| [`tests/`](tests/) | Mathematical checks, data-integrity checks, published-count checks, and local-server checks. |

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
invalid answers remain in the data. See [data provenance](data/post/README.md).

There are at most **two games per model per payoff setting**. These are
exploratory observations. Cooperation rates in Chicken and Stag Hunt do not
by themselves establish correct choices, because the best response depends on
the opponent. The grid did **not** test responses to the defection-cost
intervention. It does not establish precise behavioral thresholds or real-world
safety. Reported beliefs and confidence are retained but are not used to score
the post's heatmap or dominance result.

## Scope and the next step

`experiment.py` now implements the next experiment: hold one baseline PD fixed
and vary only the defection cost near its two conditional thresholds. It can
freeze a plan, collect and resume requests, reproduce uncertainty and counts,
and map choices to Lean proofs. Offline synthetic runs test the pipeline;
the new live experiment has not been conducted.

Repeated interactions, uncertain monitoring, institutional
mechanisms, risk criteria, and the
broader Paper 1 planning/collection framework are outside this starting point.
They were removed from the active tree, along with the old oversight model, unrelated datasets and
duplicated engines. This also removes the advanced risk paths identified as
incorrect during the preceding assessment; it does not claim to have fixed them.
The new deterministic oversight lab is a small, separately specified implementation.

The complete earlier repository is recoverable at
[`before-lesswrong-simplification-2026-11-09`](https://github.com/AI4Collaboration/Game-Utility-Threshold/tree/before-lesswrong-simplification-2026-11-09)
(`63e411fb54e7eaab00bd38b72f27dd7c3e32f0fd`). No historical experiment was
relabelled as a new run. No new model calls were made during this simplification.
