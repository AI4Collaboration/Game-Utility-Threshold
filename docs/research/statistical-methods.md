# Statistical methods for the prospective Paper 1 study

**Status:** implemented offline analysis rules. These methods do not turn the
historical exploratory archive into a prospective experiment. Freeze the design,
sampling counts, model settings, response rules, and analysis choices before new
confirmatory collection. The implementation is
[`utility_threshold/research_statistics.py`](../../utility_threshold/research_statistics.py).

## What is one observation?

An **episode** is one independently started run of the specified condition. In a
fixed-opponent task it contributes one model decision, scored 1 for the named
action and 0 for the alternative. A two-model game contributes one primary
joint-outcome score: mutual C for Prisoner's Dilemma and Stag Hunt, different
actions for Chicken, and matching actions for the asymmetric coordination game.
The immutable `primary_measure` field specifies the outcome, and `primary_score`
contains its 0/1 observation. The players may influence each other; their actions
are not two independent observations. For example, 100 paired games give 100
episode observations, even though there are 200 player actions.

Keep individual player results and all four joint-action counts as descriptive
data. The average of the two player action indicators (0, 0.5, or 1) is a
secondary first-action measure, not the primary structural outcome. For
example, C/D and D/C have the same 0.5 average as a mixture of C/C and D/D,
but those outcomes have different implications for coordination. The generic
statistics module and `paired_episode_score` support bounded fractional scores
when such a secondary measure is explicitly analyzed at the episode level.

The score need not mean “safety.” Define the action or outcome in advance for
each game. A cooperation rate in Prisoner's Dilemma is a behavior measure, not
evidence of real-world safety. In games where either coordinated action is
acceptable, a first-action rate and a successful-coordination rate answer
different questions.

The model, prompt condition, role, reasoning setting, payoff condition, opponent
policy, and response parser belong to the condition definition. Do not pool
different conditions to obtain a larger apparent sample. A replay of a saved
response is not another independent observation. A retry is not a new episode;
record attempts within the original episode and predeclare which attempt is
scored. No outcome-dependent stopping is supported by these fixed-sample rules.

## Denominators and unavailable responses

`summarize_cell` requires the scheduled episode count from the frozen design.
It rejects duplicate episode identifiers and more records than scheduled.
Its counts are:

| Field | Meaning |
| --- | --- |
| `expected_episodes` | Episodes scheduled in this condition |
| `recorded_episodes` | Episode records supplied, including recorded failures |
| `valid_episodes` | Recorded episodes with a score in [0, 1] |
| `invalid_episodes` | Received responses that the frozen rules could not score |
| `missing_episodes` | Recorded episodes with no usable response obtained |
| `unrecorded_episodes` | Scheduled episodes with no record supplied |
| `unavailable_episodes` | Invalid + missing + unrecorded episodes |

Missing records and invalid responses never become zero cooperation scores.
An episode with incomplete paired actions cannot contribute a complete paired
score. Keep the per-player missing/invalid reasons in the original records; if
both occur within one episode, choose and document a fixed episode-status rule
while preserving both component reasons. Summaries are not substitutes for raw
records, manifest identifiers, timestamps, and provider request metadata.

Two summaries answer different questions:

1. **`valid_mean` and `valid_interval`:** behavior conditional on obtaining a
   valid scored episode. The mean is null when there are no valid observations.
   A population interpretation requires independent identically sampled episodes
   and a fixed validity rule; after conditioning on validity and its count, valid
   scores must be an independent sample of that conditional population. This
   does not identify the behavior of failed or uncollected episodes.
2. **`completion_mean_bounds` and `completion_interval`:** an envelope over
   every [0, 1] assignment to unavailable scheduled outcomes. This is the primary
   conservative input to threshold inversion. It does not assume failures have
   the same behavior as successes. Its population interpretation requires a
   scientifically meaningful, independent hypothetical complete outcome for each
   scheduled episode. If an invalid response has no such interpretable outcome,
   report the envelope as a sensitivity calculation, the valid-only behavior as
   conditional, and failure rates as a separate result. Do not claim the
   envelope alone establishes an unconditional cooperation probability.

With N scheduled episodes, observed valid-score sum S, and U unavailable
episodes, every completed sample mean lies between S/N and (S+U)/N. This
arithmetic statement does not require a missing-at-random assumption. The
completion interval extends each of those endpoints by the Hoeffding radius
calculated using N, then clips to [0, 1]. It therefore contains the interval that
would be calculated for **every** possible completion. This is our explicit
missing-outcome sensitivity construction, not a separate claim from Hoeffding's
paper. It can be wide even when the valid-only estimate looks precise.

## Intervals that remain honest for unanimous samples

For n independent episode scores in [0, 1], Hoeffding's bounded-variable
inequality gives a two-sided radius

```text
radius = sqrt(log(2 / alpha_cell) / (2 * n))
interval = [max(0, observed_mean - radius), min(1, observed_mean + radius)]
```

This distribution-free bound permits fractional episode scores. It does not
require a normal approximation, estimated variance, or independence between
the two players in one episode. It requires independence between episodes.
For independent but nonidentical complete observations, its target is the
average of their expectations. A common cell-population mean additionally
requires a stable sampling condition. Unanimous samples retain nonzero
uncertainty; an empty sample returns [0, 1]. The bound can be conservative.
Source: [Hoeffding (1963), Theorem 2, original article](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf),
*Journal of the American Statistical Association* 58(301), 13–30,
[DOI](https://doi.org/10.1080/01621459.1963.10500830).

`wilson_interval` is also available for **integer success counts from independent
binary decisions**. It inverts the binomial score test and avoids the familiar
zero-width normal interval at an observed rate of zero or one. It is an
approximate interval, not a finite-sample coverage guarantee for all parameter
values. Do not enter fractional paired scores, or treat two dependent player
actions as independent Bernoulli trials. It is not used for primary threshold
inversion. Sources: [Wilson's original 1927 article, pp. 209–212](https://www.statisticshowto.com/wp-content/uploads/2022/02/wilson_1927.pdf),
[DOI](https://doi.org/10.1080/01621459.1927.10502953), and the
[NIST formula and interpretation](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

## Several plotted cells require simultaneous protection

Set `family_size=F` to the number of mean statements in the predeclared
comparison family, and use `alpha_cell=alpha/F`. The union bound then gives
coverage of all F Hoeffding intervals together of at least 1−alpha. Dependence
between different cells does not invalidate this correction; dependence between
episodes inside a cell still matters. This application follows the general
[Bonferroni inequality described by NIST](https://www.itl.nist.gov/div898/handbook/prc/section4/prc473.htm).

Include every planned model, role, reasoning condition, and arm that is in the
family, including empty cells. Do not reduce F after seeing which panels are
interesting or have usable data. A plot made from a subset retains the original
F. `infer_threshold` rejects inconsistent family metadata and F smaller than the
number of input cells, but cannot detect an omitted planned experiment; that
requires manifest validation upstream.

The primary family here is the completion-band family. Valid-response intervals
are a secondary, distinct estimand family when outcomes are unavailable. Using
the same F for both supplies a separate coverage statement for each family; it
does **not** supply one joint 95% guarantee over both families together. Count
both sets of statements in F when a joint guarantee is intended. The same
principle applies to multiple outcomes. A fixed-sample confidence statement is
not a guarantee that survives unlimited repeated looks and early stopping.

## What the threshold procedure actually identifies

The target is the frozen configuration's `behavior_target`, commonly 0.5. This is an
**empirical behavior threshold**, not the mathematical payoff equality. Report
the analytically derived utility equality separately. Two plotted sample means
on opposite sides of 0.5 do not, by themselves, provide a confidence interval for
the population threshold.

Without `direction`, `infer_threshold` returns the ordered cell bands, cells
whose bands contain the target, and descriptive sample patterns. It returns
`assumption_not_declared` and no threshold location.

Passing `direction="increasing"` explicitly asserts that the population mean
is strictly below the target before a crossing and at or above it afterward.
`"decreasing"` asserts the reverse. This is a **single-crossing sign assumption**,
not a requirement that every successive probability increase or decrease. A
curve can vary on the same side of the target. Constant curves, target plateaus,
and failure to reach the target are allowed. The assumption concerns the
population and cannot be established by noisy sample means. Never enable it
automatically because a fitted curve looks smooth. The mathematical utility
difference being linear does not prove that model behavior has one crossing.

The algorithm enumerates all possible first tested cells at which the target
has been reached. For an increasing curve and candidate cell k, every earlier
band must permit a value strictly below the target, and every band from k onward
must permit a value at or above it. Reverse the inequalities for a decreasing
curve. It also considers crossing before the tested range and not crossing by
the final tested point. On the event that all bands cover their true cell means,
the actual single-crossing pattern cannot be excluded. Inversion therefore
inherits the simultaneous coverage guarantee, **conditional on the stated
sampling, completion-outcome, and single-crossing assumptions**. This inversion
is a direct set-construction argument; we do not claim a fitted change-point
model or cite the original interval papers as if they supplied this algorithm.

Outputs distinguish:

| Status | Interpretation |
| --- | --- |
| `assumption_not_declared` | Grid evidence only; no threshold inferred |
| `bounded` | A finite conservative crossing-location enclosure remains |
| `left_censored` | Crossing before the first tested setting remains possible |
| `right_censored` | Crossing after the final setting, or never crossing, remains possible |
| `unresolved` | Both censoring directions remain possible |
| `incompatible_with_assumption` | No declared single-crossing pattern fits the simultaneous bands |

The returned `candidate_first_crossing_cells` lists possible **first tested**
cells, not exact continuous crossing points. The location envelope includes the
whole untested gap preceding each candidate. Finite endpoints are conservatively
closed because discontinuity behavior has not been assumed. A null endpoint is
unbounded/censored, never zero. No midpoint or interpolated point estimate is
created. A narrow grid bracket is not a statistical interval unless the bands
and stated assumptions justify the inversion. Even a valid enclosure cannot
locate a crossing more finely than the experiment's spacing.

Observed flatness, repeated crossings, reversed direction, and sample means
exactly equal to the target are retained as diagnostics. These are not proofs
about population shape. A noisy reversal need not contradict the confidence
bands; a confidently incompatible reversal makes the procedure abstain. At a
band endpoint exactly equal to the target, equality counts as reaching it; an
observed mean exactly at the target does not collapse its uncertainty.

## External opponent probabilities and reported beliefs

When an opponent's cooperation probability q is assigned by the experiment,
keep that external q in the design and use it for the primary expected-payoff
calculation. Keep a model's reported belief in a separate response field with
separate validity checks. A reported belief is an output of the same decision
process, not a replacement for a randomized or fixed input. Sorting primary
outcomes by that report changes the question and can create selection effects.
Belief-conditioned analyses are secondary and descriptive unless a separate
identification argument is supplied. Neither parameter belongs in the generic
statistics utility; protocol grouping must enforce this distinction.

## Precision planning and presentation

`hoeffding_required_episodes(half_width, alpha, family_size)` implements
`ceil(log(2*F/alpha)/(2*half_width**2))`. For illustration, a 0.10 radius at a
95% family level needs 185 complete independent episodes for F=1, or 390 per
cell for F=60. Halving the requested radius approximately quadruples the
required count. This is a worst-case precision bound, not a power calculation
for a particular effect and not an allowance for arbitrary missingness.

Use one primary horizontal axis per curve; keep the other design factors fixed
or use separate labeled panels. Show the raw valid mean, primary completion
bands, target level, and theoretical equality as distinct labeled elements.
Give planned, valid, invalid, missing, and unrecorded counts in the accompanying
table. Label synthetic/dry-run outputs as such. A bounded threshold result must
carry its assumption and family size; censored and incompatible outcomes must
remain visible. Do not connect missing data with an implied fitted boundary.

## API example and verification

```python
from utility_threshold.research_statistics import (
    EpisodeObservation, summarize_cell, infer_threshold,
)

cell = summarize_cell(
    "fixed-opponent-cell-01", 0.25,
    [EpisodeObservation("episode-01", 1),
     EpisodeObservation("episode-02", None, "invalid")],
    expected_episodes=100, alpha=0.05, family_size=12,
)
summary_for_json = cell.as_dict()
descriptive_result = infer_threshold([cell])
# Only after a protocol explicitly adopts this scientific assumption:
conditional_result = infer_threshold([cell], direction="decreasing")
```

`tests/test_research_statistics.py` checks known Wilson values, fractional
episode means, all-unanimous and empty samples, exact binomial and multinomial
coverage sums for selected finite cases, all bounded fillings of a small
incomplete sample, duplicated identifiers, censoring, multiple/reversed
crossings, exact endpoint equality, and serializable missing results. These
checks support the implementation; finite examples do not replace the
mathematical assumptions or validate the quality of actual model collection.
