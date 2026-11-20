# Run the fixed game study

We ask whether language models change their choices when an action becomes less
profitable, and whether hiding an opponent's rewards changes those choices.
The operator supplies a working OpenRouter key; models, prompts, sample counts,
controls, budget and analysis are already selected in
[`configs/manager-study-v1.json`](../configs/manager-study-v1.json).

## Run and return

On macOS/Linux (or Windows through WSL), install Git and Python 3.11+ first. Then:

```sh
git clone https://github.com/AI4Collaboration/Game-Utility-Threshold.git
cd Game-Utility-Threshold
bash scripts/run_manager_study.sh
```

Enter the OpenRouter key at the hidden prompt. It stays in that process; it is
not written to a file or included in the returned bundle. The script deliberately
does not read the repository's old `.env`. An existing `OPENROUTER_API_KEY`
environment variable is also supported. Use a key with access to all three pinned
providers. No changes to models or experiment settings are needed.

This installs an isolated runtime, freezes the study, runs separate compatibility
pilots, runs the main sample only if every pilot passes, and builds the report and
ZIP. It makes paid requests, with **one $45 cap across the entire study**, including
pilots. It stops before dispatch if a conservative reservation does not fit.
The cap does not cover unrelated account usage or another checkout. Do not run
multiple copies. Allow several hours; speed depends on the providers. Keep the
computer awake and the terminal running. Actual cost and completion are measured,
not promised in advance.

**Send back `runs/manager-study-v1/results.zip`.** It contains:

- `results/report.html`: readable results and separate 2D plots; open locally.
- `results/choices.csv`: individual choices, roles and experimental conditions.
- `results/cells.csv`: per-condition estimates, intervals and missing-data bounds.
- `results/presentation-blocks.csv`: label/order checks.
- `results/paired-effects.csv`: hidden-minus-revealed comparisons.
- `results/predictions.json`: exact mathematical thresholds and conditional audit optima.
- `results/observations.jsonl`: every planned trial, including failures/unrun trials.
- `study/logs/`: native Inspect `.eval` traces with raw model requests/replies.
- `study/plan.json`, `study/attempts/`, `study/frozen-source/`: frozen settings,
  billing/reservations, code and environment versions; plus `SHA256.json`.

The final terminal output gives the local HTML path. To inspect raw traces:
`.venv-manager/bin/inspect view --log-dir runs/manager-study-v1/logs`.
The public website is a teaching UI; it does not run this paid study.

## Stop, restart, or diagnose

Press Ctrl-C **once** to finish and save the current trial, write the results, and
pause. Run the same shell command to resume. Completed/attempted trials are never
sent again. Do not pull new code, edit settings, delete the run folder, reinstall
the environment or switch keys while a study is in progress.

If a request is interrupted abruptly, charges are unclear, a provider changes, a
pilot fails, or credits run out, collection stops. **Send the ZIP and final
terminal message back to the researcher.** Do not retry in a new directory or
change the model. Ambiguous requests require researcher review; the operator is
not asked to make scientific or billing decisions. If setup fails before a plan
is created, send the terminal error instead.

```sh
bash scripts/run_manager_study.sh status   # counts and spending; no model calls
bash scripts/run_manager_study.sh report   # rebuild ZIP/report; no model calls
bash scripts/run_manager_study.sh smoke    # separate scripted check; zero API spend
```

Status/report should be run while collection is stopped (the study is locked
while collecting). Smoke output is explicitly synthetic and uses a separate
folder. Historical data and the previous collectors are preserved.

## What is being played?

| Study | Plain-language example | Experimental change |
| --- | --- | --- |
| Prisoner's Dilemma | Both gain from cooperation, but each is tempted to defect. | Only the cost of defection. |
| Stag Hunt | Cooperating together pays well; cooperating alone is risky. | Only the cost of the alternative action. |
| Chicken | Each wants the other to yield; both insisting is worst. | Only the cost of insisting. |
| Battle of the Sexes | Both want to agree but prefer different shared outcomes. | Cost on one action; the two cost directions stay separate. |
| Private PD | One player's temptation reward is known only to that player unless revealed. | Same rewards revealed/hidden at each public cost. |
| Private Stag Hunt | One player's loss from cooperating alone is private unless revealed. | Same rewards revealed/hidden at each public cost. |
| Audit threshold | A defender commits where to check; an attacker chooses either target or abstains. | Only checking probability; the defender is fixed by code. |
| Audit information | Same audit rules; a model defender chooses where to check before a model attacker acts. | Only access to the actual reward profile; checking probability is an outcome. |

The four base games use their existing v2 prompts and exact tables. The small
scale/offset controls are separately reported checks of numerical presentation,
not extra payoff sweeps. The private/audit comparisons match actual rewards,
profile and presentation. Two-action games use four label/order blocks; audit
uses nine balanced blocks. Each role receives a fresh prompt. Opponent reasoning
and simultaneous choices are never leaked. Off-switch and retired prototypes
are excluded because they are not ready for this study.

## Fixed collection and interpretation

Three models: GPT-4.1 mini (OpenAI), Claude Haiku 4.5 (Anthropic), Gemini 2.5 Flash
(Google AI Studio), through OpenRouter with those exact providers and no fallback.
Temperature 0.7; at most 512 output tokens; no requested reasoning; hybrid reasoning
is explicitly disabled for Haiku/Gemini. This is a bounded choice study, not a
comparison of equal internal reasoning effort. Native logs retain any reasoning
that the provider nevertheless exposes; unavailable reasoning is not reconstructed.

The frozen schedule contains **9,576 main trials + 306 pilot trials**, requiring
at most **17,658 model requests** (two-player trials can make two requests).
An invalid audit-defender response prevents the corresponding attacker call.

Per model: five repetitions per presentation block for canonical primary cells;
two for their sparse representation controls; three for each private-game
profile/information/cost/block; two for each audit-threshold q/profile/block; five
for each audit-information profile/information/block. Separate pilots cover every
presentation block. Their acceptance depends on transport, identity, billing and
valid output, never agreement with our predictions. Seeds shuffle the schedule;
they do not guarantee deterministic provider responses.

This is a modest initial validation sample, not a precise final threshold estimate.
Canonical primary cells have 20 pairs per model; private cells have 12 pairs per
profile/information/cost; audit-threshold cells have 18 decisions per q/profile;
audit-information cells have 45 pairs per profile/information. The conservative
95% pointwise worst-case half-widths for a complete binary cell are approximately
0.304, 0.392, 0.320 and 0.202 respectively. They are not simultaneous bands.
Representation checks are small diagnostics and cannot establish equivalence.

Reports keep models, roles, profiles, directions and scale controls separate;
weight presentation blocks equally; omit means when a block is empty; preserve
all missing/invalid responses; and include worst-case missing-data bounds.
Information effects use matched environments, not shared model replies. Analyses
assume independent samples within a condition; service/time effects remain a
limitation. No outcome-based sample extension or fitted sharp threshold is used.
Best-response predictions in audit are conditional on its rewards and assumptions;
a single pair of actions does not establish an equilibrium.

The base design and controls follow the existing [sweep rationale](sweep-design.md)
and [source audit](design-sources.md); the audit follows
[Blocki et al.](https://arxiv.org/abs/1303.0356) and the Bayesian commitment structure
of [Paruchuri et al.](https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf).
Our numbers and sampling counts are explicit adaptations. Existing notes cite
[Herr et al.](https://arxiv.org/abs/2407.04467) for presentation bias and
[Hoeffding](https://doi.org/10.1080/01621459.1963.10500830) for bounded-outcome intervals.
The package supplies collection and descriptive analysis, not a claim that the
paper's empirical milestones are already complete.
