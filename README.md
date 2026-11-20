# Game Utility Thresholds

**When does a safer choice become the better-paying choice—and do language
models respond as the payoff calculations predict?** This repository contains
our games, exact calculations, interactive demos, and retained model experiments.

[Play the games](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html)
· [See experimental results](https://ai4collaboration.github.io/Game-Utility-Threshold/results.html)
· [Find a game's code](games/README.md)
· [Sweep design](docs/sweep-design.md)
· [Controlled experiment setup and AISI progress](docs/controlled-thresholds.md)
· [Methods and plans](docs/README.md)
· [Datasets](data/README.md)

## Find a game

A **threshold** is a setting where two choices earn the same expected points;
crossing it can change which choice pays more. Each game has its own assumptions.

| Game | What happens | Guide and code |
| --- | --- | --- |
| Prisoner's Dilemma (PD) | Each player is tempted to defect, although both would gain from mutual cooperation. We vary the cost of defection. | [PD](games/README.md#prisoners-dilemma) |
| Stag Hunt | The better joint outcome requires trust: cooperating alone is costly. | [Stag Hunt](games/README.md#stag-hunt) |
| Chicken | Each wants the other to yield; both insisting gives the worst outcome. | [Chicken](games/README.md#chicken) |
| Battle of the Sexes | Both want to coordinate, but prefer different shared outcomes. | [Coordination game](games/README.md#battle-of-the-sexes) |
| Human–AI oversight | The human chooses protection; the AI sees it and chooses cooperation or a resource attack. | [Oversight](games/README.md#humanai-oversight) |
| Resource control | The same protection problem, but the human does not know how strongly the AI values resources. | [Resource control](games/README.md#resource-control) |
| Lab Notebook Audit | A reporting agent can swap an eligible run for a better-looking ineligible run; a reviewer checks limited evidence. | [Research prototype](games/README.md#lab-notebook-audit) |

These are four small simultaneous games, two protection settings, and one
science-audit environment. They are not seven completed LLM studies. Shared engines keep the same calculations consistent across games.

The off-switch game and the earlier science demo were removed from the active
scope on 19 November 2026; they remain recoverable in Git history. Lab Notebook
Audit is retained. This intentionally defers the AISI plan’s off-switch example.

## Current research status

**The selected controlled-study design has no completed live LLM validation.**
Months 1–3 remain open: implemented equations, solvers and collectors do not
complete the revised empirical work. Months 3–5 and 5–6 are also incomplete.
See the [requirement-by-requirement assessment and next steps](docs/controlled-thresholds.md#aisi-status-all-three-stages-remain-open).

The [new live protocol](docs/controlled-validation-protocol.md) is frozen.
Collection was attempted on 19 November, but OpenRouter rejected all eight
initial pilot requests for insufficient account credits. **No main requests or
new model choices were collected.** [Failure records and status](data/controlled/2026-11-19/README.md)
are preserved alongside the unchanged historical datasets.
The [replacement-key attempt](data/controlled/2026-11-19-funded/README.md)
was also blocked by account credits on its first request; validation is still pending.

## Historical model studies

| Historical evidence | What was collected | What it does not establish for the current plan |
| --- | --- | --- |
| [Original payoff grid](docs/post-study.md) | Four models; 169 payoff settings; 1,350 valid paired games. Includes PD, Stag Hunt, Chicken, dominance and boundary regions. | No added-cost intervention, Battle of the Sexes study, or precise behavioral threshold estimate. |
| [Earlier oversight study](docs/oversight-validation-results.md) | Three models; 3,660 main decisions plus 12 pilot decisions, at fixed human protection settings. | Not completion of the selected v2 validation. Some defense conditions overlap; the new diagnostic and broader suite remain unrun. No empirical equilibrium or safety guarantee. |
| Selected v2 studies | Frozen live protocol, budgeted collector, synthetic checks and archived billing failures. | No live model results under the selected plans. The notebook audit's paid collector is still to be implemented. |

Lean checks payoff statements for recorded choices in the four canonical
games. It does not verify a model's internal reasoning or certify the oversight
and uncertainty games. See [proof scope](lean/README.md).

## Repository map

| Location | Put/find this here |
| --- | --- |
| [games/](games/README.md) | Start here to find each game's rules, UI, source, runner and tests. |
| [gut/](gut/) | Python payoff engines, collectors and analysis. |
| [web/](web/) | Browser pages, shared JavaScript engines and interactive controls. |
| [docs/](docs/README.md) | Rules, study protocols, findings and publication instructions. |
| [data/](data/README.md) | The two retained model datasets and their provenance. |
| [lean/](lean/README.md) | Formal payoff proofs and recorded-choice certificates. |
| [tests/](tests/) | Mathematical, data-integrity, browser and publication checks. |
| Root scripts | Run experiments, reproduce reports, serve locally or build the website; see commands below. |

`runs/`, `report/` and `_site/` are generated, Git-ignored outputs. Retained
historical studies and the [older repository archive](docs/post-study.md#earlier-repository-snapshot)
remain separate.

## Run locally

Python 3.11+ is sufficient for the local UI, core calculations and data audit:

```sh
python3 serve.py
```

Open **http://127.0.0.1:8765/games**. The original post explorer is at `/`.
Use `--port 8766` if needed. The public site needs no account or API key.

| Task | Command / instructions |
| --- | --- |
| Audit the retained original grid | `python3 reproduce.py --data-only` |
| Rebuild its figures and report | [Post reproduction](docs/post-study.md#reproduce-offline) |
| Run a synthetic canonical cost study | [Cost-study commands](docs/experiments.md#run-the-offline-demonstration) |
| Prepare all controlled threshold studies, without API calls | `python3 prepare_threshold_studies.py runs/threshold-plans` |
| Reproduce the completed oversight study | [Dataset instructions](data/oversight/2026-11-09/README.md#reproduce-without-paid-calls) |
| Run resource-control baselines | [Node benchmark commands](docs/uncertainty-games.md#offline-benchmark-and-records) |
| Run a synthetic notebook-audit pilot | `python3 lab_experiment.py runs/lab-pilot` |
| Run Python checks | `python3 -m unittest discover -s tests -v` |
| Build the public site | [Pages instructions](docs/pages.md#build-without-paid-calls) |

Figures need matplotlib; rebuilding the oversight analysis also needs the
[pinned analysis packages](data/oversight/2026-11-09/analysis-requirements.txt).
The uncertainty benchmark needs Node 18+. Lean verification needs the pinned
[Lean toolchain](lean/README.md). These offline tasks make no model calls.
GitHub Actions runs the full checks and deploys successful `main` commits.
