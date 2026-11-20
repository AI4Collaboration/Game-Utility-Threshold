# Months 1–3: controlled LLM validation

Frozen 19 November 2026 **before any paid request in this study**. This is a
bounded first validation, not completion of all AISI deliverables. The user
authorized new collection; the suite enforces **US$45 including pilots** within
the previously agreed US$50 ceiling. Stop at the frozen sample even if cheaper.

**Credential replacement, before successful collection:** nine requests in the
first compatibility attempt returned billing rejections, with no model choices.
The user supplied a new key. A fresh, complete compatibility pilot and the same
untouched main schedule are frozen in `data/controlled/2026-11-19-funded/`.
All request bodies, sampling settings and schedule entries are unchanged.
The new ledger caps spending at **$41.86**; retaining the previous **$3.137152**
unknown-cost hold keeps their combined ceiling below $45. The old failures stay
in their original directory and are never relabeled as successful observations.

## Question and scope

When a specified action becomes less profitable, do model choices change in
the predicted direction? Test four simultaneous games and the known-payoff
oversight game. Resource uncertainty and Lab Notebook Audit are later work.

Keep starting payoff tables fixed and vary only the selected intervention.
The exact tables, costs and controls are in [the design](controlled-thresholds.md).
Canonical prompts show final payoffs, not an additional cost to subtract.
The experiment does not test whether a model understands a separately described
enforcement mechanism. Incentives can leave the starting game's original region.

In oversight, `d` is deterministic protection of resources and reduction of
modeled harm, with a proportional attack penalty. It is **not a probability of
detection**. The AI sees the human's imposed choice and both exact outcome
payoffs. Human choice, two-sided equilibrium play, scalable review and real-world
safety are outside this experiment. Pure-strategy solvers remain mathematical
reference calculations, not empirical equilibrium findings.

## Fixed sample

Three model configurations: GPT-4.1 mini through OpenAI, Claude Haiku 4.5 through
Anthropic, and Gemini 2.5 Flash through Google AI Studio. Endpoint specifications,
price ceilings and accepted returned model identities are archived. No provider
fallback. Temperature .7; maximum output 128 tokens; reasoning disabled where
the endpoint exposes that control; strict JSON with one A/B choice. Do not infer
equal internal reasoning across these models. No requested explanation.

Every condition crosses label reversal with display order (four blocks). Both
players in a canonical pair use the same model configuration, see role-specific
tables, and receive separate stateless requests. Global schedule seed 20261119
interleaves studies, models and costs. This seed controls scheduling only.

| Study | Conditions per model | Repetitions per block | Main requests, all 3 models |
| --- | ---: | ---: | ---: |
| PD primary | 10 | 10 paired games | 2,400 |
| Stag Hunt primary | 6 | 10 paired games | 1,440 |
| Chicken primary | 6 | 10 paired games | 1,440 |
| Battle of the Sexes, both cost directions | 20 | 10 paired games | 4,800 |
| Separate canonical scale/offset checks | 36 across four games | 3 paired games | 2,592 |
| Oversight defense | 11 | 25 responses | 3,300 |
| Oversight attack-cost diagnostic | 5 | 10 responses | 600 |
| **Total main** | | | **16,572** |

**120 additional pilot requests**: eight per canonical game/model (one pair in
each block, alternating zero and maximum primary cost), plus four per sequential
study/model. All pilots are separate requests excluded from main estimates.
Pilot acceptance concerns format, identity and cost reporting, never which action
was chosen. No sample extension, selective replacement or outcome-based stopping.

This is more conditions than the historical grid because it includes controlled
interventions, four presentation blocks and mirrored/representation checks. It
is not an exhaustive parameter search. Counts are our budget/precision choices,
not a claim that the literature mandates this exact sample.

## Outcomes and uncertainty

For canonical games, estimate cooperation/yielding and all four joint outcomes.
For Battle of the Sexes, retain each role's X rate, agreement and individual
payoffs separately; neither action is intrinsically defection. Also report
agreement with strictly dominant choices when one exists, and realized unilateral
payoff loss against the recorded partner. Such retrospective payoff loss does
not mean an agent could have observed its partner before choosing. Do not score
coordination/anti-coordination regions as simply correct or incorrect cooperation.

For oversight, report cooperation, exact best-response agreement, payoff loss,
and human/AI payoffs. The defense crossing is 2/7 and lies between .2 and .3.
The separate attack-cost diagnostic holds defense at .3 and varies cost from
.8 to 1: its exact tie is .9. Either action is optimal at a tie. Do not pool the
diagnostic with the defense curve, or infer a unique continuous behavioral root.

Primary estimates average the four block means equally. A canonical pair is
one unit, not two independent observations. Keep all planned rows, failures,
missing partners and incomplete blocks; empty blocks yield absent aggregate
estimates. Report block-specific findings and finite-sample missing-data bounds.

Use the existing conservative 95% **pointwise** Hoeffding intervals. Complete
samples give maximum half-widths .215 (40 canonical pairs), .392 (12 control
pairs), .136 (100 oversight responses), and .215 (40 diagnostic responses).
These are deliberately disclosed limits: representation checks can reveal large
differences but cannot establish equivalence; primary cells do not resolve small
effects. Intervals assume independent sampling and do not simultaneously cover
all figures. Service/date dependencies and prompt-specific generalization remain
limitations. No significance search, fitted sharp threshold or model ranking.

Plot separate 2D panels by game, model, intervention direction and representation.
Show exact mathematical ties as guide lines, observed points with intervals,
and planned/valid counts. Save the underlying tables and raw replies. Use
pandas/matplotlib/seaborn; the existing oversight analysis uses scikit-learn
confusion matrices for strict choices, excluding and reporting ties.

## Provenance, failures and reproduction

The shared suite manifest commits to all native plans and the complete schedule.
Every attempted request gets a durable start and full raw finish in one ledger.
Reserve a conservative maximum using endpoint context and output ceilings before
dispatch; settle known cost from usage. Unknown costs remain fully reserved.
Stop on transport, identity or cost failures, retain the failed observation,
and resume only unattempted jobs after a written audit. No automatic retries.
Invalid choices remain invalid; they never become invented actions.

The original `data/post/` T/S grid and `data/oversight/2026-11-09/` are retained
byte-for-byte and checked against a precollection SHA-256 inventory. Do not pool
them with this study or silently count them as new observations. New records
are stored under `data/controlled/2026-11-19/`. API keys and headers are excluded.

```sh
# A new run only: endpoint models must first be verified and saved.
python3 threshold_validation.py plan runs/NEW_RUN --models models.json --budget-usd 45
python3 threshold_validation.py run runs/NEW_RUN --stage pilot --live --max-calls 120
python3 threshold_validation.py run runs/NEW_RUN --stage main --live --max-calls 16572
python3 threshold_validation.py status runs/NEW_RUN
# After collection stops, project the ledger into existing native analyzers.
python3 threshold_validation.py materialize runs/NEW_RUN
```

## Methodological sources and what we borrow

- [Gächter et al. (2024), §5.1](https://docs.iza.org/dp16814.pdf): normalization
  and the value of controlled payoff comparisons. Human outcomes do not predict
  LLM behavior; our exact baselines/cost grid are our choices.
- [Herr et al. (2024)](https://arxiv.org/abs/2407.04467): positional/payoff biases
  motivate independent label and order controls. Our design is an adaptation.
- [Akata et al. (2025)](https://hcai-munich.com/pubs/Akata2025Games.pdf): behavioral
  comparisons across games motivate retaining distinct game outcomes and neutral
  presentation. This study does not reproduce their full protocol.
- [Hoeffding (1963)](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830):
  conservative bounded-outcome intervals, as specified above.
- [OpenRouter routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection):
  explicit providers, required settings and price caps. The implementation
  additionally shares one durable budget across all studies.
