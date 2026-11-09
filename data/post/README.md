# Evidence used in the LessWrong post

This folder preserves only the model experiment behind [When Defection Stops
Paying: Why Utility Thresholds Matter for AI Safety](https://www.lesswrong.com/posts/HJSWoWCQefj2L8W8d/when-defection-stops-paying-why-utility-thresholds-matter-1),
published 3 November 2026 and accessed 9 November 2026. These are historical
model responses, not new calls or simulated choices.

The retained experiment is the archived `perspective_grid` stage: a 13 × 13
grid with S and T independently taking values −1, −0.75, …, 2, while R=1 and
P=0. Four models each played two separate games at every matrix, giving
**1,352 planned paired games / 2,704 player decisions**. Each player received
a fresh context, its own payoff perspective, and no other player's answer.
The objective was to maximize its own numerical payoff in a one-shot game.
The action labels were A/B; their C/D meaning reversed between the two blocks.
There was no intervention, communication, repeated match, or live opponent
adaptation in this retained experiment.

## Files and reconstruction

- `records.jsonl.gz`: all 2,704 selected source records, with each original
  JSON line unchanged. Records retain complete request messages and settings,
  full returned responses, timestamps, model/provider identifiers, label maps,
  finish reasons, usage and reported costs. Authorization headers were not
  serialized by the historical collector.
- `block-0.json` and `block-1.json`: byte-identical copies of the original
  `manifest_perspective_grid_0.json` and `manifest_perspective_grid_1.json`.
  These contain the complete planned job IDs, including failed parsing cases.
- `manifest.json`: source selection, post link, historical flags, original
  source hashes, extracted-data hashes, dates and expected cohort size.

`gut.study.load_study()` verifies the retained file hashes and both original
manifests. It checks every ID, role, payoff matrix, reversed label mapping,
prompt, requested reasoning setting, returned model and timestamp. It then
parses `final_action` from raw response content again. Saved `decision`,
classification and outcome fields inherited from the archive are not used to
calculate results. `gut.study.prompt(s, t, role, replicate)` reconstructs the
collection prompt without importing the former engine or making any calls.

From the repository root, using Python 3.11 or newer:

```bash
python3 -c 'from gut.study import load_study; print(load_study().summary())'
python3 -m unittest discover -s tests -p 'test_study.py'
```

The loader returns all planned games in `.games`. `.cells()` returns counts
for each model and matrix; `.regions()` returns counts for the five regions;
`.summary()` returns totals and dominance agreement. All rates use explicit
counts. The core loader and its tests need only Python's standard library.

## Missing outcomes and denominators

All 2,704 scheduled requests have records. Two responses do not supply a
valid action under the stated JSON-only rule:

- GLM, block 0, `grid-122`, row: the returned message content is null.
- Fable, block 1, `grid-108`, row: prose precedes the JSON object.

Their two partners returned valid actions. The post uses complete paired
games, so all four decisions from those two pairs are outside its outcome
denominator. The retained data therefore contain **2,702 individually valid
actions**, but the post's figures use **1,350 complete games / 2,700 choices**.
The two invalid outputs and two excluded valid partners remain in this folder.
Neither is replaced by a guessed action. Missing or duplicate source records
cause an audit error; they cannot silently shrink the planned denominator.

Recomputed anchors are **1,277/1,280** choices agreeing with a strictly better
action (99.77%, rounded). In the Stag Hunt and Chicken regions respectively,
Qwen chooses C **51/128 (39.84%)** and **93/128 (72.66%)**; Fable chooses C
**102/128 (79.69%)** and **114/128 (89.06%)**. These region names refer to the
two action-comparison signs, not every strict ordering among all four payoffs.
Boundary matrices have at least one tied action comparison and are kept as
their own region. C is an action label, not a universal safety outcome.

## Historical scope and limits

The recorded model IDs are `z-ai/glm-5.3`, `qwen/qwen3.8-2.4t-a95b`,
`openai/gpt-6-astra`, and `anthropic/claude-fable-5.1`. They identify the
historical requests; this folder makes no claim about current availability
or model rankings. Requests specified low reasoning effort and a 4,096-token
allowance, with provider-default temperature. Seeds were sent for GLM, Qwen
and Astra, but not Fable. Exact request bodies and actual provider metadata
are retained. Requested settings do not establish identical implementations
across providers or deterministic repeatability.

Collection ran from 2026-10-09 19:54:23.826246 UTC to
2026-10-09 20:01:20.569853 UTC. The folder name of the former source bundle,
`results oct 10`, was not the collection date. Its engine originated at
commit `b4a2e54b6aa34973d2849ff92e38502b4b0e6869`; the source compressed log
also contained other experiments. Extraction selected only
`case.stage == "perspective_grid"` without changing any selected record.

This own-payoff presentation was introduced after differences between player
roles were noticed in earlier experiments. It also removed role-dependent
matrix ordering. It is exploratory and does not isolate which presentation
change caused any difference. There are only two paired games per model and
matrix; the percentages are descriptive, not precise population estimates or
evidence for a reliable model ranking. The archive's later PD refinement,
other grids, pilots, payoff sweeps, scale/offset controls and fitted or
confidence-based threshold reports are outside this folder's scope. Analytic
intervention paths are not additional observed model responses.
