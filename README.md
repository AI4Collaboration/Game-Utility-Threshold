# Game Utility Thresholds

**When does a safer choice become the better-paying choice—and do language
models respond as the payoff calculations predict?** This repository contains
our games, exact calculations, interactive demos, and retained model experiments.

[Play the games](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html)
· [See experimental results](https://ai4collaboration.github.io/Game-Utility-Threshold/results.html)
· [Find a game's code](games/README.md)
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
| Off-switch | An AI unsure whether an action helps the human chooses to proceed, stop, or ask a fallible human. | [Off-switch](games/README.md#off-switch) |
| Science audit demo | Inspect a limited sample of lab readings before accepting or returning a possibly inflated report. | [Playable demo](games/README.md#science-audit-demo) |
| Lab Notebook Audit | A reporting agent can swap an eligible run for a better-looking ineligible run; a reviewer checks limited evidence. | [Research prototype](games/README.md#lab-notebook-audit) |

These are four small simultaneous games, three sequential decision settings,
and two versions of a science-audit setting. They are not nine completed LLM
studies. Shared engines keep the same calculations consistent across games.

## What has actually been tested with models?

| Evidence | Completed | What it does not establish |
| --- | --- | --- |
| [Original payoff grid](docs/post-study.md) | Four models; 169 payoff settings; 1,350 valid paired games. Includes PD, Stag Hunt, Chicken, dominance and boundary regions. | No added-cost intervention, Battle of the Sexes study, or precise behavioral threshold estimate. |
| [Oversight validation](docs/oversight-validation-results.md) | Three models; 3,660 main decisions plus 12 pilot decisions, at fixed human protection settings. | No empirical test of two-sided equilibrium play or general safety guarantee. |
| Other games and new cost sweeps | Exact calculations, interactive examples and offline software checks. | No new live LLM results. The notebook audit's paid collector is still to be implemented. |

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

`runs/`, `report/` and `_site/` are generated, Git-ignored outputs. Current
results and the [older repository archive](docs/post-study.md#earlier-repository-snapshot)
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
| Reproduce the completed oversight study | [Dataset instructions](data/oversight/2026-11-09/README.md#reproduce-without-paid-calls) |
| Run resource/off-switch baselines | [Node benchmark commands](docs/uncertainty-games.md#offline-benchmark-and-records) |
| Run a synthetic notebook-audit pilot | `python3 lab_experiment.py runs/lab-pilot` |
| Run Python checks | `python3 -m unittest discover -s tests -v` |
| Build the public site | [Pages instructions](docs/pages.md#build-without-paid-calls) |

Figures need matplotlib; rebuilding the oversight analysis also needs the
[pinned analysis packages](data/oversight/2026-11-09/analysis-requirements.txt).
The uncertainty benchmark needs Node 18+. Lean verification needs the pinned
[Lean toolchain](lean/README.md). These offline tasks make no model calls.
GitHub Actions runs the full checks and deploys successful `main` commits.
