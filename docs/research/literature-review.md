# Literature and methodological decisions for Paper 1

Reviewed 7 November 2026. This is a targeted methodological review, not a
systematic review or a claim to have covered every relevant publication.
The bibliography is in [references.bib](references.bib). The sources below
were checked in primary full texts, including the methods or formal sections
on which the recommendations depend. Published metadata and the version read
are distinguished where they differ.

The central recommendation is to study a small number of understandable
changes, with enough independent observations to measure their effects.
Experiments should distinguish three questions: what action maximizes the
specified points, what action an AI actually chooses, and whether that action
meets a separately defined safety objective. Those questions can have
different answers. In particular, cooperation is not automatically safe,
and defection is not automatically harmful outside a specified application.

## 1. Primary evidence and what we will reuse

### Controlled changes to Prisoner's Dilemma payoffs

**Gächter, Lee, Sefton and Weber (2024), `gachter2024payoffs`.**
*The role of payoff parameters for cooperation in the one-shot Prisoner's
Dilemma*, European Economic Review 166, 104753.
[Published article](https://doi.org/10.1016/j.euroecorev.2024.104753);
[author working paper and appendices read](https://docs.iza.org/dp16814.pdf),
Sections 3, 5.1 and Appendix J.

The experiments separate payoff changes using controlled designs; the
between-person study avoids experience across different games. Section 5.1
explicitly subtracts `P` and divides by `R-P`, yielding mutual-cooperation
payoff 1 and mutual-defection payoff 0. Their main experimental indices differ
from these normalized coordinates. We adopt independent coordinate changes,
fresh contexts for one-shot trials, and explicit recording of opponent
beliefs. We do not transplant their human cooperation rates or assume that
their main three-index design is identical to ours. Their findings vary with
experimental design, so a predicted direction of AI behavior remains a
testable hypothesis.

**Moisan, ten Brincke, Murphy and Gonzalez (2018), `moisan2018pd`.**
*Not All Prisoner's Dilemma Games Are Equal: Incentives, Social Preferences,
and Cooperation*, Decision 5(4), 306–322.
[Published article](https://doi.org/10.1037/dec0000079);
[author-hosted published PDF read](https://ryanomurphy.com/resources/Moisan-tenBrincke-Murphy-Gonzalez-2018.pdf),
pp. 308–314, equations 2–6, Methods and Tables 2–3.

This study uses a different normalization: `T'=1, S'=0`, with `R'` and `P'`
free. Its four repeated games distinguish incentive structure from measured
social preferences; a single cooperation index does not explain all observed
differences. We adopt two-dimensional descriptions and keep point rewards
separate from inferred preferences. Their 60-round, fixed-partner human
experiment is not a one-shot LLM experiment. Neither their social-preference
measure nor an AI's explanation licenses attributing a stable human-like
preference to the AI. The issue year is 2018; the online-first date was 2017.

### AI behavior, game families and presentation controls

**Akata et al. (2025), `akata2025repeated`.**
*Playing repeated games with large language models*, Nature Human Behaviour
9, 1380–1390.
[Published article](https://doi.org/10.1038/s41562-025-02172-y);
[author-hosted published PDF read](https://hcai-munich.com/pubs/Akata2025Games.pdf),
Methods, pp. 1387–1388.

The study evaluates repeated interactions across game families, using neutral
action labels, payoff descriptions, recorded interaction histories and
hand-coded opponents. It examines Prisoner's Dilemma and Battle of the Sexes
in greater depth. We reuse those controls and the separation of cooperation
from coordination. Its ten-round, temperature-zero setup is one experimental
choice, not evidence that those settings are universally preferable. Our
one-shot and repeated studies must have distinct analysis units. Good
one-round point maximization and good long-run interaction are different
outcomes; the paper does not establish a universal ranking of current models.

**Lorè and Heydari (2024), `lore2024strategic`.**
*Strategic behavior of large language models and the role of game structure
versus contextual framing*, Scientific Reports 14, 18490.
[Published article](https://doi.org/10.1038/s41598-024-69032-z);
[full published text read](https://pmc.ncbi.nlm.nih.gov/articles/PMC11316122/),
Methods: Background on game theory and Simulation routine.

This study crosses four payoff structures with five contexts and collects
300 initializations for each combination and model. We adopt a separate
framing experiment while holding wording fixed in the main payoff study.
We also distinguish Prisoner's Dilemma, Chicken, Stag Hunt and Harmony by
their incentives. Their mixed-equilibrium comparisons are useful references,
but do not make the mixed equilibrium the sole rational target when pure
equilibria also exist. We do not adopt that interpretation or infer internal
reasoning from selected verbal explanations.

**Sclar, Choi, Tsvetkov and Suhr (2024), `sclar2024format`.**
*Quantifying Language Models' Sensitivity to Spurious Features in Prompt
Design or: How I learned to start worrying about prompt formatting*, ICLR.
[Official paper and metadata](https://proceedings.iclr.cc/paper_files/paper/2024/hash/6c0e99d736da621403018ca7b32b1a4d-Abstract-Conference.html),
full paper Sections 3–4.

The authors define meaning-preserving format variations and measure the
performance range across them. We adopt a small, predefined set of equivalent
formats, with separate results for label/order controls. We will not select
the most favorable prompt after observing confirmation results. Their tasks
are mainly classification tasks; the magnitude of their effects cannot be
assumed for games. We borrow the controlled comparison, not an unsupported
numerical expectation or the full adaptive search algorithm.

### Statistical uncertainty and complete reporting

**Hoeffding (1963), `hoeffding1963bounded`.**
*Probability Inequalities for Sums of Bounded Random Variables*, Journal of
the American Statistical Association 58(301), 13–30.
[Published article](https://doi.org/10.1080/01621459.1963.10500830);
[full original article read](https://www.cs.rpi.edu/academics/courses/spring06/random/hoefding.pdf),
Theorem 2.

The theorem bounds deviations of sums of independent bounded observations.
We use it for conservative primary intervals and fixed-sample precision
planning. It allows independent episodes with different expectations, which
matters when the design fixes equal counts across different label arrangements.
The target is their average expectation, not an assumed common binomial
probability. The simultaneous correction, missing-outcome sensitivity envelope
and crossing-set inversion in [statistical methods](statistical-methods.md)
require their own stated construction and assumptions. The theorem does not
make dependent episodes independent or justify unlimited outcome-based stopping.

**Wilson (1927), `wilson1927inference`.**
*Probable Inference, the Law of Succession, and Statistical Inference*, Journal
of the American Statistical Association 22(158), 209–212.
[Published article](https://doi.org/10.1080/01621459.1927.10502953);
[original scanned article read](https://www.statisticshowto.com/wp-content/uploads/2022/02/wilson_1927.pdf),
particularly the improved inference calculation on p. 209.

The score-interval construction is available for optional descriptive binary
proportions under a common sampling condition. It is not the primary threshold
procedure. We do not pool dependent player actions or fixed heterogeneous label
strata into an ordinary binomial sample; Brown et al. below also describe the
coverage limitations of approximate intervals.

**Brown, Cai and DasGupta (2001), `brown2001binomial`.**
*Interval Estimation for a Binomial Proportion*, Statistical Science 16(2),
101–133, including discussion.
[Published article](https://doi.org/10.1214/ss/1009213286);
[author manuscript read](https://www.stat.purdue.edu/~dasgupta/publications/tr99-19.pdf),
Sections 2 and 3.2, including visual inspection of scanned formula pages.

The paper analyzes poor coverage of the usual estimate-plus/minus-standard-
error interval and alternatives, including the Wilson score interval. We
adopt Wilson intervals for descriptive proportions from independent trials
with the same configuration. They remain approximate, pointwise intervals.
They do not handle dependent rounds, optional stopping, changing models,
or all cells simultaneously. Rare-harm claims need a separately specified
one-sided bound and sufficient sample size; no observed errors does not
establish zero error probability.

**Dodge et al. (2019), `dodge2019reporting`.**
*Show Your Work: Improved Reporting of Experimental Results*, EMNLP-IJCNLP,
2185–2194.
[Official paper and metadata](https://aclanthology.org/D19-1224/),
full paper Section 5 and Text Box 1.

The paper shows how model comparisons can depend on computational and tuning
budgets and provides a reporting checklist. We adapt its reporting principle:
publish configuration choices, search history, unsuccessful attempts, costs
and frozen confirmation settings. For reasoning-effort comparisons, record
both the requested setting and measured usage. We do not reuse its estimator
of best validation performance: our target is the distribution of decisions
under a fixed game configuration, not the best result after model tuning.

### Unknown priorities and the limits of oversight guarantees

**Ben-Tal and Nemirovski (1998), `bental1998robust`.**
*Robust Convex Optimization*, Mathematics of Operations Research 23(4), 769–805.
[Published article](https://doi.org/10.1287/moor.23.4.769);
[author-hosted full article read](https://www2.isye.gatech.edu/~nemirovs/MOR_RCO_1998.pdf),
Introduction, pp. 769–772, particularly equations 1–2.

The paper defines robust feasibility as satisfying the constraints for every
realization in a declared uncertainty set. We use that definition to state
exactly which payoff errors a protection claim covers. Our oversight interval
extrema follow from the elementary monotonicity derivation in
[oversight bounds](oversight-bounds.md). We do not transfer the source's
ellipsoidal optimization or tractability results to the repository's different,
discontinuous leader problem. A set of assumed errors is not a statistical
confidence region unless an additional sampling argument establishes it.

**Harsanyi (1967), `harsanyi1967incomplete`.**
*Games with Incomplete Information Played by “Bayesian” Players, I–III.
Part I. The Basic Model*, Management Science 14(3), 159–182.
[Published article](https://doi.org/10.1287/mnsc.14.3.159);
[full original paper read](https://www.cs.siu.edu/~hexmoor/classes/CS491-F10/Harasyani.pdf),
Sections 3–6.

The model represents unknown characteristics using types, probability
distributions and explicit information available to each player. We adopt
this structure for unknown AI resource values: specify possible values,
probabilities, who sees the realized value and when. Randomizing an outcome
is not the same experiment as hiding a player's priorities. A common prior
is an assumption to state and test for sensitivity; it does not by itself
provide protection against every possible type. The DOI above is the
original 1967 article, not the 2004 reprint.

**Hadfield-Menell et al. (2017), `hadfieldmenell2017offswitch`.**
*The Off-Switch Game*, IJCAI, 220–227.
[Official proceedings](https://doi.org/10.24963/ijcai.2017/32);
[author-hosted full paper read](https://people.eecs.berkeley.edu/~russell/papers/ijcai17-offswitch.pdf),
Sections 2–4 and Theorem 1.

The model makes the robot uncertain about the human's utility and treats
the human's decision as informative. Its deference result depends on the
information structure and the human policy. We adopt the discipline of
writing the decision tree and assumptions before claiming a safety result.
The repository's defense/attack model has different actions and potentially
conflicting objectives; it is not an implementation or replication of this
off-switch theorem. A shutdown example requires an explicit mapping and
separate analysis.

**Neth (2025), `neth2025offswitch`.**
*Off-switching not guaranteed*, Philosophical Studies 182(7), 1919–1931.
[Published article](https://doi.org/10.1007/s11098-025-02296-x);
[full author preprint read](https://arxiv.org/html/2502.08864v1),
particularly Sections 4–5.

The paper examines limits of deference arguments when learning assumptions
or access to human preferences fail. Its misleading-signal example is a
useful stress-test pattern: vary one observation-error probability while
keeping the underlying decision problem fixed. We adopt an explicit
distinction between receiving information and being required to follow an
instruction. This is a theoretical counterexample, not an empirical estimate
of deployed AI failure rates. We use it to define assumptions and failure
cases, not to declare all uncertainty-based oversight ineffective.

## 2. A precise, readable payoff design

The following calculations are the project's explicit design derivations.
They state exactly what the benchmark should compute and are not empirical
findings. The literature above motivates the choices; tests must independently
check their implementation.

For a symmetric two-player game, let each player choose `C` or `D`:

| Your choice | Other player chooses C | Other player chooses D |
|---|---:|---:|
| C | R | S |
| D | T | P |

Here `T` is the reward for choosing D against C; `R` is the reward for mutual
C; `P` is the reward for mutual D; `S` is the reward for choosing C against D.
The other player's table is the corresponding transpose.

For finite payoffs with `R>P`, subtract `P` from every payoff and divide
by the positive difference `R-P`:

```text
t = (T-P)/(R-P)       normalized T
s = (S-P)/(R-P)       normalized S
R_normalized = 1      P_normalized = 0
```

For example, `(T,R,P,S)=(5,3,1,0)` becomes `(2,1,0,-0.5)`.
A positive change of units preserves comparisons of expected point rewards:
the difference between two expected rewards is multiplied by a positive
number. It does not prove that an LLM responds identically to the rewritten
numbers. Save both raw and normalized tables and the exact displayed text.

Use `g=t-1` for the extra reward from D against C, and `l=-s` for the loss
from C against D. These are normalized gain and loss; if called “greed” and
“fear,” make clear that they describe incentives, not measured emotions.
Some literature instead divides these two differences by `T-S`. In our
coordinates those alternatives are `(t-1)/(t-s)` and `-s/(t-s)`.
The cooperation index `K=1/(t-s)` combines both axes, so it cannot identify
their separate effects.

The initial PD experiment should contain a `t` sweep with `s` fixed, and an
`s` sweep with `t` fixed. A small crossed grid can subsequently test whether
the effect of one coordinate depends on the other. Four unconstrained payoff
sweeps and a single pooled response plot would obscure that distinction.
Changing one raw payoff is also not sufficient if that change alters several
normalized coordinates.

Strict PD requires `t>1` and `s<0`. If mutual cooperation must yield greater
combined points than taking turns exploiting one another, additionally
require `t+s<2`. Declare whether this additional condition is part of each
study; equality and violations must not silently enter the same stratum.
Reject nonfinite inputs and a zero or negative normalization denominator.

## 3. What a utility threshold can mean

Let `q` be the stated probability that the other player chooses C. It is a
belief or a property of a specified random opponent, not the probability that
the model itself cooperates. The expected advantage of C is

```text
M(q) = expected_points(C) - expected_points(D)
     = q(1-t) + (1-q)s.
```

Choose C when `M>0`, D when `M<0`, and report indifference when `M=0`.
An implementation may have a declared tie convention, but the theory regards
both actions as best responses at equality. Score that distinction explicitly.

In strict PD, both `1-t` and `s` are negative, so `M(q)<0` for every
`q` between 0 and 1. **There is no selfish one-shot best-response switch
inside strict PD.** A changing observed cooperation rate can still be an
interesting behavioral result. It does not demonstrate a changing Nash
equilibrium or reveal the AI's true internal utility.

A meaningful theoretical switch requires a specified change to the decision
problem. For example, charge a fixed expected penalty `c` whenever the player
chooses D, leaving the base table and opponent probability fixed:

```text
M_penalty(q,c) = M(q) + c
c_star(q) = q(t-1) - (1-q)s.
```

The threshold is conditional on that probability and on the penalty actually
being included in the player's objective. For protection against either
opponent action, the condition becomes `c >= max(t-1, -s)`; strict preference
requires `>` or a positive additional buffer. This follows because a linear
function of `q` attains its minimum at an endpoint. Once a sufficient penalty
is included, the effective game may no longer be a strict PD. Label the
base game and the changed incentives separately.

Keep the original unit `R-P` fixed when normalizing the penalty and regret.
Renormalizing each changed game can move the axis while concealing the size
of the intervention. Other interventions, such as a preference for the other
player's points, require their own equations; they are not interchangeable
with a fixed penalty.

Distinguish these outputs in every result table:

| Quantity | Meaning | What does not follow |
|---|---|---|
| Theoretical indifference point | Two specified expected rewards are equal | The model switches there |
| Observed response curve | Fraction choosing an action at each tested setting | A single smooth or monotone boundary exists |
| Observed 50% crossover | The response curve crosses a predefined 0.5 level | A Nash equilibrium or a safety guarantee |
| Safety acceptance boundary | A predefined upper bound on harmful behavior is met | All untested settings are safe |

If observations never bracket the chosen response level, report “not
identified in the tested range.” If they cross it several times, report
multiple crossings. A logistic curve forces a particular shape; do not let
its convenient single crossing substitute for evidence. A finite grid can
support a bracket between tested values, but a more precise interpolated
point needs an explicit model and its uncertainty. Neither a single pair of
different actions nor the steepest visible change is a reliable threshold
estimate.

## 4. Extend to games with different decision problems

The same expected-reward calculation is useful beyond PD. The examples
below are strict interior cases; boundary cases require separate handling.

| Family | Example normalized region | Decision issue | Useful one-coordinate experiment |
|---|---|---|---|
| PD | `t>1, s<0` | D wins against either action | Vary `t`, `s`, or a separately defined penalty |
| Stag Hunt | `0<t<1, s<0` | C is better when the other player is sufficiently likely to choose C | Fix the table and vary the stated `q` |
| Chicken | `t>1, 0<s<1` | C is better when the other player is sufficiently unlikely to choose C | Fix the table and vary `q` |
| Harmony control | `0<t<1, 0<s<1` | C wins against either action | Test payoff comprehension and label sensitivity |

For Stag Hunt and Chicken, the interior indifference probability is

```text
q_star = -s/(1-t-s) = s/(t+s-1).
```

Stag Hunt favors C above this point; Chicken favors C below it. A best
response to a supplied probability is a controlled decision test. When two
AI players instead interact, their expectations are part of the problem.
Stag Hunt has two pure coordination equilibria; Chicken has two pure
equilibria where players choose different actions. Each also has a mixed
equilibrium. Report that multiplicity instead of assigning a unique “correct”
unconditional action.

Battle of the Sexes needs a different table because the players prefer
different coordinated outcomes. One clean one-parameter form is:

| Joint choices | Player 1 points | Player 2 points |
|---|---:|---:|
| A,A | 1 | b |
| B,B | b | 1 |
| A,B or B,A | 0 | 0 |

With `0<b<1`, Player 1 chooses A when the probability of Player 2 choosing A
exceeds `b/(1+b)`. Player 2 chooses A when the probability of Player 1
choosing A exceeds `1/(1+b)`. Vary `b` with other settings fixed, or hold `b`
fixed and vary that stated probability. Swap player roles and action labels.
In actual paired play, report coordination frequency, which coordinated
outcome occurs, and each player's points. “Cooperation rate” alone discards
the central conflict. Do not pass this asymmetric game through a symmetric
PD normalization merely because both have two choices.

This `b` table is an illustrative design, not the checked-in pilot's payoff
table. The [protocol](paper-one-protocol.md) uses the existing protocol game
`CC=(4,3)`, `DD=(3,4)` and mismatches `(-8,-8)`, with role boundaries
`11/23` and `12/23`. Each result must identify which table was actually used.

## 5. One-shot and repeated interactions need separate claims

A fresh, independent prompt with no history answers a one-shot question.
A conversation that retains prior actions answers a repeated-interaction
question even if every round uses the same table. Record the horizon, whether
the final round is known, the information shown after each round, discounting,
and whether opponents persist or are rematched.

For a known finite number of strict-PD rounds, complete information and
common knowledge of selfish point maximization imply defection by backward
reasoning from the final round. This is a conditional theoretical benchmark;
LLM prompts do not establish those assumptions. For an indefinitely repeated
PD with perfect observation, the illustrative strategy “cooperate until a
defection, then always defect” can sustain cooperation when
`R/(1-delta) >= T + delta*P/(1-delta)`, or
`delta >= (T-R)/(T-P)`. This algebra is specific to that strategy and
information structure; it is not a threshold for all repeated play.

Use complete independent matches as the replication unit. For a match-level
summary, first calculate the summary per match and then estimate variability
across matches. Rounds and both players in the same match share a history.
Counting them as independent repetitions understates uncertainty. A later
round-level model must represent this dependence explicitly.

## 6. Data collection and presentation requirements

These are proposed acceptance requirements for the research protocol. They
are not a claim that all are already implemented or that new data exist.

1. **Define the question and outcome before collection.** Freeze the coordinate
   range, points, contrasts, model versions, prompts, number of repetitions,
   exclusions, retry policy, stopping rule and primary figures. Clearly mark
   exploratory observations and confirmation observations.
2. **Separate the sources of variation.** A fresh repeat of the same prompt
   measures variability under that prompt. Different labels, wording, numeric
   scales, roles, model versions and reasoning settings are separate experimental
   factors. Keep them fixed or balance them deliberately. Do not treat one
   model as a representative random sample of all AI systems.
3. **Keep a complete trial record.** Save planned configuration, actual request,
   full available response, parsed action, validation status, raw/normalized
   payoffs, mathematical certificate, timestamps, model identifier, requested
   generation settings, returned usage, software revision and hashes. Do not
   infer unavailable provider settings or private reasoning.
4. **Count failures honestly.** Distinguish an unmade request, a transport error,
   a refusal, malformed output, an invalid action and a valid action. Save each
   attempt and its parent trial. Retrying a transport failure may be permitted
   under a frozen policy; resampling an inconvenient valid response is not.
   Report planned, attempted, returned and valid denominators. Valid-only
   behavior is conditional on validity; it cannot establish whole-system safety.
5. **Choose replication for precision.** With independent, identical trials,
   a 95% Wilson interval near 50% has approximately a 9.6-percentage-point
   half-width at `n=100`, and 4.9 points at `n=400`. These are planning
   calculations, not universal sample-size recommendations. Power for a
   treatment difference and precision of a crossover location are different
   calculations. These pointwise examples do not size the balanced,
   simultaneous confirmation study. Its primary bounded-score calculation is
   given in the [protocol](paper-one-protocol.md) and
   [statistical methods](statistical-methods.md). Simulate the planned design
   before fixing its final budget.
6. **Do not turn inspection into a stopping rule.** Use the frozen sample size
   for confirmation. If more data or a new range is chosen after looking at
   results, identify it as a follow-up study. Repeatedly checking an ordinary
   interval until it looks favorable changes its interpretation.
7. **Limit the number of primary comparisons.** Specify a small family of
   contrasts and an error-control method in advance. Pointwise error bars are
   not a simultaneous band. A simple conservative option is to divide the
   chosen error rate by the number of planned tests; its justification is the
   probability bound for the union of their error events. Report exploratory
   comparisons as exploratory.
8. **Measure decisions, calculations and consequences separately.** Record
   action rates, invalid-output rates, reward-calculation errors, expected
   reward lost relative to the specified best response, and the application's
   harmful outcome. A correct calculation and an action consistent with it
   are distinct observations. A fluent explanation is not a process trace.

For zero harmful outcomes in `n` independent, identical completed trials,
the exact one-sided upper bound at confidence `1-alpha` is
`1-alpha^(1/n)`, because the probability of zero harms is `(1-p)^n`.
At 95% confidence, zero harms in 100 trials still allows a harm probability
of approximately 2.95%. Missing or invalid outcomes cannot simply be counted
as harmless. For joint claims across several configurations, account for
multiple claims as well as the sampling assumptions.

Main figures should remain readable without a multidimensional plot:

| Figure | Horizontal axis | Vertical axis | Required context |
|---|---|---|---|
| PD incentive slices | `t` in one panel; `s` in another | Observed C fraction | Fixed coordinate, model, prompt, counts and intervals |
| Intervention response | Penalty or bonus in fixed units | Action fraction | Calculated boundary, ties, tested range and uncertainty |
| Belief response | Stated opponent probability `q` | Action fraction | Separate game and player-role panels, theoretical `q_star` |
| Small interaction map | `t` and `s` | Color represents response | Only a predefined two-coordinate grid; mark missing cells |
| Data-quality display | Configuration | Failure fractions | Failure categories and planned/actual denominators |
| Repeated-game display | Round | Match-averaged behavior | Independent-match count and dependence-aware uncertainty |

Use the same probability range across comparable panels. Export the numbers
behind every point, including counts and interval limits. Distinguish theory,
real model observations and synthetic validation with explicit labels; never
present synthetic results as collected model behavior. Include a table of
all fixed parameters rather than making readers reconstruct them from code.

## 7. Connection to the oversight contribution of Paper 1

The game-family experiments can validate controlled measurement, but they do
not complete the paper's oversight guarantees. For the repository's leader
choosing defense and follower choosing cooperation/attack, the next formal
object should specify: a finite set or bounded range of follower values, a
prior when probabilities are used, each player's information, the feasible
defenses, and what the leader minimizes. Distinguish lowest expected loss,
lowest worst-case loss and a constraint on attack probability. These are
different objectives and can recommend different protection.

Every claimed buffer must state which parameters may be wrong, by how much,
whether their errors can occur together, and the behavior assumed of the
follower. A positive point-reward advantage only guarantees the action of
the modeled optimizing follower. It does not guarantee that a tested LLM
follows the incentive. Pair the formal result with measured error rates and
state the gap between them.

For resource maximization, shutdown and auditing examples, write the actual
actions, information and consequences first. Then show precisely which
parts of the base model apply and which require changes. A familiar story
attached to a payoff table is insufficient evidence that the table captures
the relevant real-world risk.
