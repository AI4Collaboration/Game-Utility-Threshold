# Months 3–5: infrastructure audit

19 November 2026, America/Toronto. Companion to the
[design review](months3-5-design-review.md). These are source snapshots inspected
during research, not versions installed or certified to work together. Package
compatibility must be checked when implementing the adapter.

| Project / reviewed revision | What was verified | Reuse decision |
| --- | --- | --- |
| [Inspect AI — c574b6b](https://github.com/UKGovernmentBEIS/inspect_ai/tree/c574b6bf6674e6d5f6cbb0f95059d7427b23d54b) | Active repository; MIT. Official logging, roles, reasoning and limits docs inspected, plus local mock-provider code. | Use as the evaluation/logging layer. Build the game's information boundaries and exact scorer ourselves. |
| [ControlArena — fa57942](https://github.com/UKGovernmentBEIS/control-arena/tree/fa57942bcbf681d2a358f6c3f947087a55e3efbc) | Active repository; MIT with a third-party license inventory. README, dependency configuration and evaluation documentation inspected. | Candidate for later tool-using oversight tasks. Not needed for a small numerical security game. |
| [OpenSpiel — 4956843](https://github.com/google-deepmind/open_spiel/tree/4956843d7375e29a4c986425c66f897d7ac15340) | Active repository; Apache-2.0. Bargaining header, implementation and tests inspected; catalogue marks bargaining lightly tested. | Best reusable hidden-value game engine found in this review. Use only if bargaining answers an explicit research question. Not installed or executed here. |
| [End-to-End Negotiator — bbb93bb](https://github.com/facebookresearch/end-to-end-negotiator/tree/bbb93bbf00f69fced75d5c0d22e855bda07c9b78) | Archived author repository with dialogue data and code. Actual LICENSE is CC BY-NC 4.0; GitHub's automatic detection reported `NOASSERTION`. | Historical source for Lewis et al.; do not assume it has OpenSpiel's license or current runtime support. |
| [Third-party Bayesian Stackelberg script — 6473fad](https://github.com/vignesh-viswanathan/Bayesian-Stackelberg-Games/tree/6473fadc73140bb457dabe1e40b203daa59431b5) | Old third-party repository, README and DOBSS.py inspected. No license detected; not an author reference implementation. | Not adopted, copied into the project, or executed. Does not establish solver correctness. |

## What exists locally

The project's existing `.venv` contains `inspect-ai==0.3.263` and SciPy 1.18.1.
OpenSpiel and ControlArena were not installed at inspection. Inspect is not
declared in `pyproject.toml`, and there is no tested Months 3–5 Inspect adapter.
No dependency change or native evaluation was made as part of this review.

The local Inspect mock provider accepts predetermined outputs, including model
outputs with separate reasoning/text content. This provides a route to an
offline logging test without calling a paid model. Such a test is still to be
written; it would establish log plumbing only, not validate a game or model.

## First implementation checks

Before relying on these packages, pin a tested release and record it in each
run. Use a tiny offline fixture to establish that:

1. Each role receives exactly its authorized information. Changing an attacker's
   hidden type cannot change the defender's prompt before any permitted signal.
2. Native model events retain the correct role, inputs and returned output.
   Exposed reasoning is distinguishable from public action text and never copied
   into the opponent's history.
3. Logs can be reopened through `read_eval_log`; exported sample IDs and exact
   payoff calculations agree with the native records.
4. Invalid actions, missing roles, ties, cancellations and failures remain
   visible. Retries retain lineage and do not become new independent samples.
5. Costs from every paid role count against the shared budget; per-sample limits
   are not mistaken for a study-wide spending cap.

Do not add OpenSpiel and ControlArena merely because they are available. There
is no verified single package here that supplies a published deterrence task,
private-utility model, exact commitment solver and complete LLM protocol together.
