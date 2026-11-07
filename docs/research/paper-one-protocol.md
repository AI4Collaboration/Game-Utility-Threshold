# Paper 1: prospective study protocol and completion plan

**Prepared 7 November 2026. Status: design and implementation, before new
collection under this protocol.** The repository contains older exploratory
observations; they are not observations from this newly specified study. A
generated manifest or an empty preview is a plan, not an experimental result.

This document defines the proposed route to a defensible Paper 1. It separates
the controlled game experiments from the mathematical oversight model. The
[literature review](literature-review.md), [statistical methods](statistical-methods.md)
and [oversight derivations](oversight-bounds.md) give the supporting detail.

## 1. Questions the paper can answer

The central experimental question is: **when one understandable incentive
changes, how reliably does a model change its choice in the way predicted by
the stated numerical rewards?** Three separate quantities must appear in the
paper:

1. **The mathematical boundary:** the setting where two actions give equal
   expected points under a specified opponent policy.
2. **The observed response:** how often the model chooses each action, and
   how many expected points it gives up through its choice.
3. **A safety objective, if one is claimed:** a separately defined consequence
   for a person or application. Abstract action names do not establish this.

The controlled experiments cover Prisoner's Dilemma, Chicken, Stag Hunt and
Battle of the Sexes, called **protocol coordination** in the study configuration.
These names describe different payoff arrangements. They do not imply that
the same action is desirable in all four games.

The oversight analysis asks a related but different question: what defense
works when an AI's resource value is unknown, and which declared errors can
that defense tolerate? Its mathematical answers do not demonstrate actual
model compliance. Keep theory results and model observations separate.

## 2. Make each change interpretable

For the symmetric games, use two abstract actions, `C` and `D`, and the
following payoff table for the player making the decision:

| Own action | Other player chooses C | Other player chooses D |
| --- | ---: | ---: |
| C | R | S |
| D | T | P |

When `R>P`, subtract `P` from each payoff and divide by `R-P`. The resulting
table has `R=1`, `P=0`, `t=(T-P)/(R-P)` and `s=(S-P)/(R-P)`. This changes the
unit and starting point of the numerical scale. It preserves which action
maximizes expected numerical points. It does not establish that a language
model is indifferent to how the numbers are displayed.

Vary `t` while fixing `s`, or vary `s` while fixing `t`. Put the varied
coordinate on the horizontal axis and choice frequency on the vertical axis.
Different roles, models and reasoning settings belong in separate panels.
Do not change four payoffs independently and summarize the result with one
unexplained response curve.

For strict Prisoner's Dilemma, `t>1` and `s<0`. If the opponent chooses C with
probability `q`, the expected advantage of choosing C is

```text
M = expected points from C - expected points from D
  = q(1-t) + (1-q)s.
```

This is negative throughout strict one-shot Prisoner's Dilemma. Changing
incentives within that game can change model behavior, but does not create a
new mathematical best-action boundary. We must not present an observed
50% cooperation crossing as such a boundary.

To create a meaningful boundary, the third PD experiment adds a declared cost
`c` whenever a player chooses D. The new margin is `M+c`, so equality occurs at
`c*=q(t-1)-(1-q)s`. This single mechanism changes both payoffs earned through D.
It remains a one-coordinate experiment. Keep the original units and record
the complete changed table; silently normalizing again would move the scale.
The changed game can cease to be Prisoner's Dilemma, and reports must say so.

The default temptation sweep includes `t=2.75, s=-0.5`. It satisfies the strict
PD ordering, but `t+s>2`: the two unequal outcomes then produce more combined
points than mutual C. Treat this as a declared stress condition. If the paper
requires the additional condition `2R>T+S`, remove or replace this point before
freezing confirmation and state that narrower scope. In a repeated game,
alternating the two unequal outcomes would also give each player more average
points than repeated mutual C at this setting; the present protocol does not
test repeated play or claim mutual C is always efficient.

## 3. Primary experiment: specify the opponent's policy

Start with a **fixed random opponent**: the prompt states its probability of
each action. A fresh model call makes one decision, with no previous rounds,
communication or shared conversation. The model is instructed to maximize
its own expected numerical payoff. The current runner evaluates expected
points directly; it does not draw a random opponent action for each trial.

This design allows an exact comparison between a model's choice and the best
choice for the information it was given. A model's stated belief, if collected
in a future version, must not replace the probability assigned by the study.
The current prompt asks for an action and brief explanation, not a separate
belief estimate. Explanations are descriptive records, not evidence of the
model's internal calculation.

The implemented default pilot contains these six experiments:

| Experiment | Single changing input | Fixed inputs | Mathematical comparison |
| --- | --- | --- | --- |
| PD temptation | `t`: 1.05, 1.25, 1.5, 2, 2.75 | `s=-0.5`, `q=0.5` | D remains strictly better in the tested range |
| PD exploitation loss | `s`: -1, -0.75, -0.5, -0.25, -0.05 | `t=1.5`, `q=0.5` | D remains strictly better in the tested range |
| PD action cost | `c`: 0, .25, .325, .35, .375, .4, .425, .5, .75 | Baseline `t=1.5`, `s=-0.25`, `q=0.5` | Equal expected points at `c=0.375` |
| Chicken opponent policy | `q`: 0, .25, .4, .45, .5, .55, .6, .75, 1 | `t=1.5`, `s=0.5` | C is better below `q=0.5`, D above |
| Stag Hunt opponent policy | Same `q` grid | `t=0.5`, `s=-0.5` | D is better below `q=0.5`, C above |
| Protocol coordination | `q`: 0, .25, .45, 11/23, .5, 12/23, .55, .75, 1 | Asymmetric table below | Different boundaries for the two roles |

Protocol coordination uses `CC=(4,3)`, `CD=DC=(-8,-8)` and `DD=(3,4)`, where
each pair lists row and column rewards. Either matching choice avoids the
large mismatch loss, but the players prefer different matching choices.
The row player's boundary is `q=11/23`; the column player's is `q=12/23`.
The normalized symmetric table cannot represent this asymmetry. At any
mathematical equality, either action maximizes points. The scorer permits
both, retains the numerical margin and uses only a documented arithmetic
rounding tolerance, not a substantive region of indifference.

For each role and setting, the primary outcome is the probability of C,
translated back from the displayed labels. Secondary outcomes include
expected points forgone by the chosen action, validity of the response and
usage. A low C rate is not necessarily an error: D is the best numerical
choice throughout the strict-PD sensitivity experiments.

## 4. Secondary experiment: two model players

In **self-play**, both roles are independent fresh requests to the same model
identity, with each role's reasoning setting specified. Neither receives the
other's current answer. The current
implementation supports this mode, but the six default pilot experiments
above all use a fixed opponent. A self-play study needs its own declared
arms; it cannot vary a stipulated `q`, because the other model chooses its
own action. Cross-model pairings need a separate supported design.

The checked-in self-play pilot varies the PD action cost, Chicken action
cost, Stag Hunt temptation and protocol-coordination numerical scale in
separate arms. It crosses low/low, low/high, high/low and high/high requested
reasoning settings. A cost intervention can change the game's incentives;
keep the declared primary outcome but inspect and report the resulting game
class instead of treating the family name as a guarantee about every point.

One complete paired game is one observation. Two player actions do not create
two independent samples. Record all four joint outcomes, both individual
payoffs, their sum and each player's possible gain from changing its own
action after seeing the other action. That last quantity is an after-the-fact
comparison, not expected loss against a known random opponent.

| Game | Declared primary joint outcome | Interpretation |
| --- | --- | --- |
| Prisoner's Dilemma | Both choose C | Mutual cooperation frequency; not always the highest possible combined payoff |
| Stag Hunt | Both choose C | Frequency of the higher-payoff coordinated choice |
| Chicken | Players choose different actions | Frequency of avoiding mutual competition through opposite choices |
| Protocol coordination | Players choose the same action | Frequency of either successful coordinated protocol |

Retain the complete joint-outcome table alongside these summaries. In
particular, counting C choices alone cannot establish successful coordination.
A mathematical mixed equilibrium is one reference pattern, not a uniquely
required response when other equilibria exist. Do not infer a known-opponent
utility threshold from self-play without an additional model of the opponent.

Repeated games are outside this one-shot protocol. If added, start a separate
study with a declared number of rounds, information history and opponent
policy. Its independent observation is the complete match, not each round.

## 5. Labels, presentation and generation settings

The prompt displays actions as A and B. Four balanced label arrangements
prevent a fixed preference for the letter A from being confused with a
preference for C:

| Label block | Row player's C label | Column player's C label |
| --- | --- | --- |
| 0 | A | A |
| 1 | A | B |
| 2 | B | A |
| 3 | B | B |

D receives the other label. The payoff table follows the displayed labels,
and each player sees its own payoff first. Use a multiple of four trials per
setting. Cases are shuffled within complete collection blocks, interleaving
models, roles and coordinates. The scheduling seed makes that order
reproducible; it does not control provider randomness.

The primary target averages equally across the four planned label
arrangements. They need not have identical choice probabilities. The primary
uncertainty calculation permits independent observations with different
expectations. If responses are missing unevenly across label blocks, the
valid-only pooled mean can change the block weights; report that limitation
and keep the all-planned sensitivity bounds. Report label-block results as
diagnostics before claiming invariance.

Two additional checks must remain separate experiments:

- **Numerical scale and offset:** multiply the entire payoff table by a
  positive number, or add the same constant to every payoff. Vary one of
  those at a time while fixing game structure. These axes are implemented
  but absent from the default pilot. Numerical checks reject transformations
  that erase payoff distinctions through stored precision.
- **Wording and framing:** hold all payoffs fixed while comparing a small
  predeclared set of equivalent prompt wordings. The current runner provides
  one versioned abstract prompt; a wording comparison requires additional
  prompt versions and recording before collection. It is not already run or
  implied by the label controls.

Freeze exact model identifiers, provider route, reasoning setting, token
limit and available generation settings. The present runner records that
temperature uses the provider default; this is not a claim of a common known
temperature across models. Where an immutable model version or an effective
setting is unavailable, disclose that limitation. Record returned model
identifiers, timestamps, usage and execution sessions. A requested reasoning
level is a treatment label, not a measured amount of internal reasoning or a
common computational budget across providers.

## 6. Pilot first; independent confirmation second

The default configuration explicitly says `purpose="pilot"`. With one model,
one reasoning setting and eight repetitions, its 46 coordinates and two
roles produce **92 settings and 736 decisions**. Each setting has only two
decisions in each label arrangement. That is sufficient to test the
collection and reporting workflow, not to establish a precise threshold.

Three checked-in pilot configurations name four candidate models from the
repository. Availability and supported settings still require preflight.
Their current planned sizes are:

| Configuration | Settings | Independent episodes | Model decisions |
| --- | ---: | ---: | ---: |
| [Fixed-opponent pilot](../../experiments/paper_one/fixed_opponent_pilot.json) | 368 | 2,944 | 2,944 |
| [Paired-effort pilot](../../experiments/paper_one/self_play_effort_pilot.json) | 320 | 2,560 | 5,120 |
| [Scale/offset controls](../../experiments/paper_one/affine_controls_pilot.json) | 80 | 640 | 640 |

These are **unrun designs**, totaling 8,704 planned decisions. The recommended
order is the fixed-opponent pilot first, then separately assessed self-play
and representation controls. Each manifest currently defines its own primary
comparison family. Three separate 95% family statements do not supply one
joint 95% guarantee over all three studies.

Use the pilot to check prompt comprehension, parser failures, response
limits, missingness, label effects, costs and whether the grid covers useful
regions. Record every resulting change. Pilot-driven grid or prompt choices
remain exploratory findings.

Before confirmation, freeze a new study identifier, configuration, exact
prompts, collection code, analysis rules, primary outcomes, planned number of
trials and budget. Use fresh observations. Do not relabel the pilot as
confirmation after looking at it, or silently combine it with the new sample.
The configuration checks for a written precision justification, but the
presence of text is not evidence that the justification is adequate.

Use a fixed planned number of trials per setting. The primary implementation
uses conservative bounds for independent scores between zero and one, with
protection across all planned primary settings. For desired radius `h`,
overall error level `alpha` and `F` primary settings, its planning rule is

```text
N >= log(2F/alpha) / (2h^2), rounded upward to a multiple of four.
```

For the 92-setting single-model design at `alpha=0.05`, a worst-case radius of
0.10 requires **412 complete observations per setting**, or 37,904 decisions.
A radius of 0.05 requires **1,644 per setting**, or 151,248 decisions. These
are conservative precision calculations, not universal minimum sample sizes
or estimates of the cost. Adding models or primary conditions changes `F`.
For example, retaining all 368 settings in the four-model fixed-opponent
design requires 480 complete observations per setting for a 0.10 radius,
or 176,640 decisions. Unavailable responses widen the final bounds further.

If that design is unaffordable, choose fewer primary comparisons or a wider
honest precision target before confirmation. A different statistical method
requires a written justification and validated implementation. Do not choose
a smaller correction or omit uninteresting conditions after seeing results.

## 7. Data collection and audit rules

The offline planning command creates a deterministic manifest: a complete
list of cases, payoff tables, role assignments, labels, prompt hashes and
expected counts. The collector binds observations to that manifest and the
collection source. It refuses a resume after either changes. The output and
spending ledger must stay together.

Keep the raw completion, parsed decision, parser result, prompt identity,
returned model identifier, provider billing record, usage and native logs.
Retain invalid responses. The audit re-parses returned raw text, checks
membership and duplicate identifiers, and recomputes scientific scores.
These checks support traceability; they are not independent authentication
of provider claims or proof of statistical independence.

No extra model request should be made merely to repair an invalid action.
Automatic SDK and evaluation retries are disabled. The current transport
policy permits at most two explicitly budgeted rate-limit retries within
the original decision. Attempts do not become new observations. Interrupted
reservations with unknown outcomes require reconciliation before resuming.

The collector can halt for budget limits, provider problems or repeated
invalid responses. Such a halt leaves an incomplete study; it does not
reduce the planned denominator or establish successful confirmation.
Document the reason and preserve all scheduled cases in the report. Do not
continue until a favorable result appears or stop because an interval first
crosses a desired level.

For every setting report planned, recorded, valid, invalid, missing and
unrecorded counts. Report behavior among valid responses separately from
bounds allowing every possible outcome for unavailable cases. The latter
need a meaningful hypothetical complete outcome to support a population
statement; otherwise they are sensitivity bounds. Missing or invalid answers
must not silently count as safe, cooperative or competitive choices.

## 8. Analysis and figures

Use the frozen `behavior_target`, initially 0.5, when asking where a behavior
frequency reaches a chosen level. This level is a reporting choice, not a
game-theory law. Plot each tested setting with its primary uncertainty bounds,
the valid-response mean and the separately derived numerical equality.
The new report generator already produces this form of plot, an audit,
machine-readable analysis and a flat table of counts.

The default design does **not** assume a single behavioral crossing. If the
paper later uses that assumption, state it before confirmation: behavior is
on one side of the target before the crossing and on the other side
afterward. A straight mathematical payoff margin does not prove that model
behavior obeys this assumption. The interval procedure must retain an
unresolved boundary, a boundary outside the sampled range, or incompatible
evidence rather than manufacture a point estimate. Uncertainty applies at
tested settings; an interpolated line would require further assumptions.

Use Wilson intervals only as optional descriptive intervals for independent
binary trials from the same sampling condition. Do not apply an ordinary
binomial formula to dependent player actions or assume that fixed label
strata are identically distributed. The primary analysis uses the bounded
score method documented in [statistical methods](statistical-methods.md).

Each final figure needs a caption stating the experiment, what was held
fixed, outcome, unit, count, failure treatment and uncertainty method. Include
the full joint-action table for self-play. Report point losses in declared
units; raw payoff totals from different games or scale controls are not a
common model ranking. Show theoretical oversight curves separately from
observed model frequencies. Label empty previews and synthetic test fixtures
so they cannot be mistaken for evidence.

## 9. Literature-to-method mapping

The [review](literature-review.md) gives the precise versions, sections read,
adoption decisions and limitations. The relevant links are:

| Source | Method used here |
| --- | --- |
| [Gächter et al. (2024)](https://doi.org/10.1016/j.euroecorev.2024.104753) | `R=1, P=0` normalization; controlled payoff changes; separate one-shot conditions |
| [Moisan et al. (2018)](https://doi.org/10.1037/dec0000079) | Preserve more than one incentive coordinate; distinguish payoff structure from inferred preferences |
| [Akata et al. (2025)](https://doi.org/10.1038/s41562-025-02172-y) | Neutral labels, specified opponents, and separate cooperation and coordination outcomes; distinguish one-shot from repeated games |
| [Lorè and Heydari (2024)](https://doi.org/10.1038/s41598-024-69032-z) and [Sclar et al. (2024)](https://proceedings.iclr.cc/paper_files/paper/2024/hash/6c0e99d736da621403018ca7b32b1a4d-Abstract-Conference.html) | Separate payoff and wording experiments; predeclare presentation controls |
| [Hoeffding (1963)](https://doi.org/10.1080/01621459.1963.10500830) | Independent bounded observations; conservative uncertainty and precision planning |
| [Wilson (1927)](https://doi.org/10.1080/01621459.1927.10502953) and [Brown et al. (2001)](https://doi.org/10.1214/ss/1009213286) | Optional score intervals and their limits; avoid zero-width uncertainty for unanimous samples |
| [Dodge et al. (2019)](https://aclanthology.org/D19-1224/) | Publish settings, search decisions, computational usage, unsuccessful attempts and costs |
| [Harsanyi (1967)](https://doi.org/10.1287/mnsc.14.3.159) | Declare possible hidden priorities, their probabilities and who observes them |
| [Ben-Tal and Nemirovski (1998)](https://doi.org/10.1287/moor.23.4.769) | State the complete set of errors a claimed robust condition covers |
| [Hadfield-Menell et al. (2017)](https://doi.org/10.24963/ijcai.2017/32) and [Neth (2025)](https://doi.org/10.1007/s11098-025-02296-x) | Make oversight information and behavior assumptions explicit; test limits of any deference claim |

The specific missing-outcome envelope and threshold inversion are documented
constructions in this repository. The cited interval papers do not establish
those procedures without the additional assumptions stated here.

## 10. Completion gates for Paper 1

Completion means that a reader can trace every claim to a definition, proof
or independently reproducible observation. The following gates are ordered;
passing an implementation check does not pass an empirical gate.

| Gate | Concrete deliverable | Evidence required to pass |
| --- | --- | --- |
| 1. Agree on claims and scope | A short claim-to-evidence table for the manuscript | Every claim names its game, information assumptions, outcome and planned evidence; uncertain real-world interpretations are marked |
| 2. Finish and review the mathematical base | Normalization and family definitions, intervention boundaries, asymmetric-role calculations, private-priority and error-tolerance results | Independent algebra review; tested interior, tie, invalid and infeasible cases; explicit list of results covered by Lean versus numerical tests or written derivations |
| 3. Qualify the collection workflow | Frozen pilot manifest, prompts, parser, dry-run records and report previews | Duplicate, missing, malformed, interrupted, role-reversal and billing cases handled correctly; figures and counts independently checked |
| 4. Complete the pilot | Raw responses, logs, costs, audit and a decision memo | All failures disclosed; useful ranges, label sensitivity and realistic costs assessed; changes recorded rather than hidden |
| 5. Freeze confirmation | New fixed design, precision justification, primary comparison family and collection budget | Independent review before new observations; all intended controls and model settings specified; affordable counts support the chosen claim |
| 6. Collect and audit confirmation | Fresh data and full accounting of scheduled cases | Stable settings or disclosed changes; no duplicate/recycled observations; source and prompt linkage intact; incomplete collection reported as such |
| 7. Produce the evidence package | Reproducible tables and figures, full denominators, uncertainty and threshold results | One command regenerates outputs from archived inputs; unresolved and negative findings retained; captions match what was measured |
| 8. Finish the manuscript and release | Methods, results, limitations, related work, reproducibility instructions and artifact inventory | Every headline claim passes the claim-to-evidence table; independent reviewer can reproduce a sample of calculations and figures |

For the oversight component, completion also requires explicit separation of
the defense that gives the best average human outcome, the least defense
meeting a stated attack-probability limit, and a defense satisfying the margin
condition for every allowed parameter error. These can be different answers.
The current [oversight note](oversight-bounds.md) derives them for a finite
known distribution of hidden resource values and specified payoff functions.
It does not cover unknown distributions, strategic signals, learned utility
functions or a shutdown application without additional modeling.

The four-game prospective framework, analysis tools and oversight calculations
are useful implementation progress. Their existence does not complete the
pilot, independent confirmation, application validation, manuscript review or
any missing formal proof. Historical data may motivate hypotheses and appear
in a clearly identified exploratory section. It cannot retrospectively meet
the new design requirements.
