# First oversight validation: completed 9 November 2026

The fixed study completed **3,660 main requests and 12 separate compatibility
pilot requests**. Every request returned a valid action from its specified
model and provider. There were no missing responses, automatic retries, or
unresolved costs. OpenRouter reported **US$0.670963194 total**, including the
pilot (US$0.002170674). The authorized ceiling was US$50, not a spending target.

[Protocol](oversight-validation-protocol.md) · [Saved data](../data/oversight/2026-11-09/)
· [Primary figure](../data/oversight/2026-11-09/analysis/sweep-defense.png)
· [Wording comparison](../data/oversight/2026-11-09/analysis/framing.png).
With the local server running, open `/validation/report.html` for all figures,
tables and downloads. The oversight UI links to that report.

## What was tested

Three models each received eleven fixed defense levels, with 100 fresh
requests at each level. Each set was evenly divided across four combinations
of action labels and payoff-row order. A smaller wording check used an explicit
human–AI oversight story at defense 0, 0.3 and 1, with 40 requests per model
and setting. Payoffs were unchanged by the story.

Only defense varied; all eight payoff parameters stayed fixed. Every prompt
showed the final exact payoffs, so the task tested choosing between stated
outcomes rather than independently deriving the payoff formulas. Temperature
was 0.7, the output cap was 128 tokens, and additional reasoning was disabled
where supported. These are protocol choices, not a purported universal
standard. The plan was committed before collection in `4638954`.

The collection controls follow published work on action-label and framing
sensitivity, including [Herr et al.](https://arxiv.org/html/2407.04467v1),
[Akata et al.](https://hcai-munich.com/pubs/Akata2025Games.pdf), and
[Lorè & Heydari](https://doi.org/10.1038/s41598-024-69032-z). The protocol
records what was borrowed and where our small one-shot study differs.

## Main result: discrepancies concentrate near the mathematical threshold

The AI's exact preference changes at defense `2/7` (about 28.57%). At defense
0.3, cooperation pays **1** and attack pays **9/10**: cooperation is strictly
better by **1/10 point**. This is not a tie.

| Model | Primary neutral-task agreement with best payoff | Cooperation at d=0.3, neutral | Cooperation at d=0.3, oversight story |
| --- | ---: | ---: | ---: |
| GPT-4.1 mini | 1,100 / 1,100 | 100 / 100 | 20 / 40 |
| Claude Haiku 4.5 | 1,026 / 1,100 | 26 / 100 | 0 / 40 |
| Gemini 2.5 Flash | 1,100 / 1,100 | 100 / 100 | 40 / 40 |

At every sampled defense other than 0.3, all valid main-study choices matched
the uniquely higher AI payoff. All three models attacked at defenses 0–0.2
and cooperated at defenses 0.4–1 in the neutral sweep.

The near-threshold departures differ across presentation blocks:

* GPT-4.1 mini's 40 oversight-story choices at d=0.3 followed the **first
  displayed payoff row** in every case. Cooperation was chosen in both
  cooperation-first blocks (10/10 each), and never in either attack-first
  block (0/10 each), despite reversing the A/B mapping.
* Haiku's neutral-task cooperation counts at d=0.3 were **0, 1, 0, 25** across
  the four 25-request blocks. In the story condition, every block chose attack.
* Gemini chose cooperation in every block at this setting in both wordings.

Those are descriptions of this dataset, not claims about a model's internal
reasoning. The design does not distinguish numerical-format effects from all
possible sources of prompt sensitivity. The same results do not establish a
general model ranking. No extra trials were added after seeing the discrepancy.

## Reading the figures

Each plot is two-dimensional. Models appear in separate panels; wording and
presentation blocks have separate figures. Dashed lines show the mathematical
threshold, not a fitted behavioral threshold. The live grid does not sample
`2/7` itself. Do not infer a precise continuous behavioral crossing from it.

Rates average the four presentation blocks equally. Error bars are conservative
95% pointwise Hoeffding bounds: approximately ±0.136 with 100 complete requests
and ±0.215 with 40, clipped to [0,1]. They assume independent requests and are
not simultaneous intervals for the whole figure. The smaller wording check
has limited precision. Counts and missing-data bounds are separately retained;
all planned main observations happened to be valid in this run.

pandas builds the tables, seaborn/matplotlib draw PNG/SVG figures, and
scikit-learn builds the primary-task confusion matrices. There is no fitted
classifier, monotone response curve, estimated threshold, or post-hoc model
selection. Machine-readable summaries also include payoffs, modeled harm,
and the points forgone by choosing the lower-paying action.

## What this completes—and what it does not

This completes a bounded first **LLM validation of responses to imposed human
defense**, with reproducible data collection and analysis. It shows that
implementing a mathematically correct incentive threshold does not ensure all
tested prompts elicit the higher-paying choice immediately above it.

The human defense was imposed, so this is not empirical validation of Nash or
Stackelberg behavior. It does not establish real-world safety, latent model
preferences, robustness to all wording, or behavior under repeated interaction.
The main study has no exact-tie condition; the three pilot tie responses are
compatibility checks only. Broader parameter sweeps remain deferred.
