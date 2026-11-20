# Game Utility Thresholds

**When does a safer choice become the better-paying choice—and do language
models respond as the payoff calculations predict?** This repository contains
our games, exact calculations, interactive demos, and retained model experiments.

[Play the games](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html)
· [See experimental results](https://ai4collaboration.github.io/Game-Utility-Threshold/results.html)
· [Find a game's code](games/README.md)
· [Try the audit game](https://ai4collaboration.github.io/Game-Utility-Threshold/audit.html)
· [Separate private PD / Stag Hunt](https://ai4collaboration.github.io/Game-Utility-Threshold/private-games.html)
· [Design sources and scope](docs/design-sources.md)
· [Controlled experiment setup and AISI progress](docs/controlled-thresholds.md)
· [Months 3–5: literature and Inspect plan](docs/months3-5-design-review.md)
· [Methods and plans](docs/README.md)
· [Datasets](data/README.md)
· [Run the fixed study with an OpenRouter key](docs/manager-handoff.md)

## Run the prepared experiments

With Git and Python 3.11+ installed, run these commands on macOS/Linux or Windows
through WSL:

```sh
git clone https://github.com/AI4Collaboration/Game-Utility-Threshold.git
cd Game-Utility-Threshold
bash scripts/run_manager_study.sh
```

Enter your OpenRouter key at the hidden prompt. This installs dependencies and
runs **all eight study configurations** below with fixed settings and a **shared
$45 cap**. It automatically creates the report, 2D plots, tables and raw logs.
Return **`runs/manager-study-v1/results.zip`**. Rerun the same command to resume;
see the [handoff guide](docs/manager-handoff.md) if collection stops with an error.

For a free scripted check, run `bash scripts/run_manager_study.sh smoke`.
Neither that check nor the browser demos produce live LLM evidence.

## Find a game

A **threshold** is a setting where two choices earn the same expected points;
crossing it can change which choice pays more. Each game has its own assumptions.

| Game | Rules / payoff code | Interactive demo | Study ID |
| --- | --- | --- | --- |
| Prisoner's Dilemma | [gut/canonical.py](gut/canonical.py) | [Play PD](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=pd) | `pd` |
| Stag Hunt | [gut/canonical.py](gut/canonical.py) | [Play Stag Hunt](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=stag_hunt) | `stag_hunt` |
| Chicken | [gut/canonical.py](gut/canonical.py) | [Play Chicken](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=chicken) | `chicken` |
| Battle of the Sexes | [gut/canonical.py](gut/canonical.py) | [Play coordination game](https://ai4collaboration.github.io/Game-Utility-Threshold/games.html?game=battle_of_sexes) | `battle_of_sexes` |
| Private-information PD | [gut/incomplete/games.py](gut/incomplete/games.py) | [Private games: select PD](https://ai4collaboration.github.io/Game-Utility-Threshold/private-games.html) | `private_pd_v1` |
| Private-information Stag Hunt | [gut/incomplete/games.py](gut/incomplete/games.py) | [Private games: select Stag Hunt](https://ai4collaboration.github.io/Game-Utility-Threshold/private-games.html) | `private_stag_hunt_v1` |
| Audit game | [gut/audit_game.py](gut/audit_game.py) | [Audit: select threshold or information experiment](https://ai4collaboration.github.io/Game-Utility-Threshold/audit.html) | `audit_threshold`, `audit_information` |

The first four share one engine; the two private-information variants share a
separate engine. Audit has two experiments, giving **seven game settings and
eight study configurations**. The browser links need no installation or API key.
[Game explanations and full module map](games/README.md).

**Where collection lives:** [canonical Inspect tasks](gut/canonical_inspect.py),
[private-game Inspect tasks](gut/incomplete/inspect_task.py),
[audit Inspect tasks](gut/audit_inspect.py). The
[fixed run settings](configs/manager-study-v1.json) and
[shared runner](gut/inspect_study.py) connect them to the command above.

### Run one game as a free software check

After installing the runtime with the `smoke` command above, use a study ID from
the table. This example runs only PD with scripted agents:

```sh
.venv-manager/bin/python inspect_study.py prepare runs/pd-demo --studies pd --repetitions 1 --budget-usd 1
.venv-manager/bin/python inspect_study.py run runs/pd-demo --stage pilot --max-trials 10000
.venv-manager/bin/python inspect_study.py run runs/pd-demo --stage main --max-trials 10000
.venv-manager/bin/python inspect_study.py export runs/pd-demo runs/pd-demo-export
```

For another game, replace `pd` with its study ID and use new output directories.
These commands default to synthetic mode and spend no API credits. For the
prepared live LLM study, use the single command at the top of this page.

These **four established game families** are the active paper experiments.
Our particular payoff values, added costs and collection controls are adaptations,
not a replication of one published experiment. Read the [design-source audit](docs/design-sources.md).

The [published audit-game implementation](games/README.md#audit-game-known-and-hidden-rewards)
adds a sequential setting: commit to where to check, then observe a violation or
abstention. Revealed/hidden conditions now match the same actual reward profile,
exact predictions, an interactive UI and native Inspect tasks. Its checks use
scripted agents; **there are no live LLM results for this game**.

[Design 1](gut/incomplete/README.md) implements **separate, versioned PD and
Stag Hunt extensions** with one private reward profile. Their matched revealed/
hidden conditions keep the same rewards and vary the public action cost. They
have exact equilibrium sets, an independent Inspect runner and UI; current checks
are synthetic. The original four games and their collectors are preserved; a
native Inspect adapter now also runs their existing v2 tables/prompts under the
[shared study runner](docs/inspect-studies.md), with one budget, separate pilots,
native logs and recovery without duplicate trials.

The resource/paperclip game, Lab Notebook Audit and earlier science demo are
removed. **Off-switch remains in the requested research scope**, but its old
implementation is inactive: a faithful published experimental setup still needs
to be implemented and validated. The [protection/attack oversight prototype](games/README.md#humanai-oversight)
remains inspectable and **excluded from new paper-study suites** pending a
defensible published-design mapping. Paid oversight collection is blocked.

## Current research status

**The controlled cost studies have no completed live LLM validation.** The four
standard games have exact payoff comparisons, threshold solvers, pure Nash
calculations, collectors and synthetic checks. Those are mathematical and
software results, not evidence that models follow the predicted incentives.
Months 1–3, 3–5 and 5–6 remain open; see the
[requirement-by-requirement assessment](docs/controlled-thresholds.md#aisi-status-all-three-stages-remain-open).

The [earlier mixed live protocol](docs/controlled-validation-protocol.md) is now
superseded: it included the custom oversight prototype. Its replacement canonical
collector includes only the four standard games; the manager package additionally
includes the approved private/audit studies. The two archived compatibility attempts recorded
nine billing rejections and one replacement-key rejection, respectively, with
**zero model choices and zero main attempts**. Their ledgers and spending holds
remain intact. Fixing billing alone will not resume that superseded suite.

## Historical model studies

| Historical evidence | What was collected | What it does not establish for the current plan |
| --- | --- | --- |
| [Original payoff grid](docs/post-study.md) | Four models; 169 payoff settings; 1,350 valid paired games. Includes PD, Stag Hunt, Chicken, dominance and boundary regions. | No added-cost intervention, Battle of the Sexes study, or precise behavioral threshold estimate. |
| [Earlier oversight study](docs/oversight-validation-results.md) | Three models; 3,660 main decisions plus 12 pilot decisions, at fixed human protection settings. | Custom-prototype evidence; not validation of a published oversight design or of the canonical cost studies. No empirical equilibrium or safety guarantee. |
| Controlled cost studies | Budgeted collector, synthetic checks and archived billing failures. | No live results; the earlier mixed protocol is superseded. The prepared manager run includes the four canonical games plus the private/audit studies above. |

Lean checks payoff statements for recorded choices in the four canonical
games. It does not verify a model's internal reasoning or certify the oversight
prototype. See [proof scope](lean/README.md).

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
| Prepare the four canonical cost studies, without API calls | `python3 prepare_threshold_studies.py runs/threshold-plans` |
| Reproduce the completed oversight study | [Dataset instructions](data/oversight/2026-11-09/README.md#reproduce-without-paid-calls) |
| Run a synthetic audit game with native Inspect logs | `python3 audit_experiment.py runs/audit-check --study information` |
| Prepare/run/resume new Inspect studies with a shared budget | [Study commands and recovery](docs/inspect-studies.md) |
| Run both separate Design 1 games, with 2D figures | `python3 private_games.py run runs/private-check --game all --figures` |
| View Design 1 native traces | `inspect view --log-dir runs/private-check/logs` |
| Open the audit traces | `inspect view --log-dir runs/audit-check` |
| Run Python checks | `python3 -m unittest discover -s tests -v` |
| Build the public site | [Pages instructions](docs/pages.md#build-without-paid-calls) |

Figures need matplotlib; rebuilding the oversight analysis also needs the
[pinned analysis packages](data/oversight/2026-11-09/analysis-requirements.txt).
The native audit runner needs `python3 -m pip install '.[inspect]'`.
Browser checks need Node 18+. Lean verification needs the pinned
[Lean toolchain](lean/README.md). These offline tasks make no model calls.
GitHub Actions runs the full checks and deploys successful `main` commits.
