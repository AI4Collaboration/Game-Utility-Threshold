# Confidence intervals for observed minus theoretical payoff thresholds

This is an exploratory, offline re-analysis of existing data, not new model
experiments or a preregistered confirmatory study. It leaves the earlier
cell-by-cell confidence table intact and supplies a more informative analysis
of the same crossing estimand. No fitted logistic curves or midpoint estimates
are used. All numerical threshold bounds are normalized payoff units.

## Quantity being estimated

At a held-fixed payoff, the observed boundary separates mean cooperation above
and below 0.5. As S increases, the expected direction is D-majority to C-majority;
as T increases it is C-majority to D-majority. This is a single-crossing assumption
about population means, not a requirement that every sampled response is monotone.
The response need not have a logistic shape or even a constant slope. Flat ties
can make the boundary set-valued. Existence of a unique boundary is not established.

The theoretical comparator uses each decision's reported opponent belief q and
the margin q(1-T)+(1-q)S. For each game, L is the fraction of its two decisions
strictly favoring C, and U the fraction permitting C, including utility ties.
Its admissible mean cooperation is between E[L] and E[U]. A theoretical boundary
means a single-crossing selection from this admissible range. It is conditional
on reported beliefs, not a unique equilibrium prediction. Ties remain set-valued.

Each complete game yields an observed C fraction Y in {0, 0.5, 1} and paired
L,U scores in the same range. We assume independent games but allow dependence
between a game's players and between Y,L,U. The target at each cell is the
average expectation over its retained label blocks, conditional on complete
valid outputs. Two cells have only one retained block. The results do not correct
for informative invalid-output selection, provider drift, or unfaithful beliefs.
The original and refinement batches were collected at different times. Statistical
coverage is conditional on treating the tested design as fixed and on the stated
sampling/shape assumptions; it is not a guarantee against adaptive-study effects.

## Candidate-threshold tests

A proposed threshold theta requires particular signs relative to 0.5 on each
side. For example, for increasing S, means at x < theta must be <= 0.5 and means
at x > theta must be >= 0.5. At x = theta the cell is omitted conservatively.

On each side, test every nested window of whole cells starting nearest theta
and expanding outward. Window endpoints depend on the payoff design, not on
observed responses. Whole cells preserve the tested label-block mixture.
Pooling across a window is valid because a required sign at every cell implies
the same sign for their game-count-weighted mean expectation.

For observed scores use Y. For theoretical scores, a required C-majority needs
E[U] >= 0.5; a required D-majority needs E[L] <= 0.5. This tests compatibility
with the range of tie resolutions, rather than imposing one action at ties.
Any candidate contradicting strict dominance for any sampled cell is rejected
deterministically, since the corresponding theoretical rate is known exactly
for every q in [0,1].

For n independent bounded [0,1] game scores with observed mean m on the wrong
side of 0.5, the one-sided tail probability is bounded above by

    p_bound = exp[-n KL(m || 0.5)]
    KL(m || 0.5) = m log(2m) + (1-m) log(2(1-m)), with 0 log 0 = 0.

Use p_bound=1 on the allowed side or when the window is empty. This is a
Chernoff bound obtained from the Bernoulli moment-generating-function upper
bound for bounded variables. It does NOT assume game scores are Bernoulli or
that player choices are independent. Non-identical game expectations are allowed.
By convexity, E[exp(lambda Y_i)] <= 1-p_i+p_i exp(lambda), where p_i=E[Y_i].
Independence and concavity of log bound the product by the moment-generating
function of n Bernoulli variables with the same average expectation. Optimizing
lambda gives the KL bound above, which is sharper than exp[-2n(m-0.5)^2].

If a slice contains N cells, at most N windows occur across its two sides for
one candidate. Allocate alpha/(2 N F) to each window, with alpha=0.05. The factor
2 covers the observed and theoretical boundaries; F=1 for an individual-slice
comparison, or F=128 for familywise coverage across all reported comparisons.
The union bound does not require independence between windows, curves, or slices.

Invert these tests over all candidate thresholds. No further correction for
the number of candidate values is needed: confidence coverage is determined by
the rejection probability of the test at the true threshold. Tests change only
at sampled x values, so every open interval and every sampled point is checked.
The reported interval is the closed outer hull of the accepted set; accepted
atoms are saved in JSON. An empty accepted set would flag incompatibility with
the crossing description, rather than being interpreted as a threshold shift.

## Comparing boundaries

If observed and theoretical confidence sets are [Lo,Uo] and [Lt,Ut], the reported
confidence interval for d = observed minus theoretical is [Lo-Ut, Uo-Lt]. These
are outer intervals, not paired bootstrap or fitted-model intervals. The joint
coverage allocation makes the difference interval at least 95% for each fixed
slice when F=1, and jointly at least 95% across all slices when F=128, conditional
on the assumptions above. The separate threshold sets in a row have joint
coverage of at least 95%; they are not independent error bars.

Zero excluded means evidence of a shift under the stated assumptions. Zero
included means the method does not establish a shift; it does not establish
equality or practical equivalence. The minimum supported absolute shift is the
interval's distance from zero, not the magnitude of the observed point difference.
No finite point estimate is fabricated when only a sample bracket exists.

The original descriptive crossing brackets remain in the table. They are not
confidence intervals. More informative sets here do not invalidate the earlier
cellwise method: they use the crossing sign restrictions to pool observations.
This analysis is still conservative and is not the only valid inferential method.

## Sources and reproducibility

- Hoeffding (1963), Probability Inequalities for Sums of Bounded Random Variables:
  https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf
- P. B. Stark, confidence sets by inversion of hypothesis tests:
  https://www.stat.berkeley.edu/~stark/Teach/S240/Notes/ch5.htm
- Archived raw records: data/attempts.jsonl.gz and data_pd_refinement/attempts.jsonl.gz.
  Their SHA-256 hashes appear in threshold_confidence.json.

Run: python scripts/report_threshold_confidence.py --output reproduced/threshold-confidence
