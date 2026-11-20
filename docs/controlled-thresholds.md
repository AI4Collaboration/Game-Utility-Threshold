# Controlled threshold experiments

19 November 2026. **Four canonical cost studies; no completed live validation.**
Exact calculations, collectors and offline checks exist. Historical LLM data
remain unchanged and do not complete these controlled studies.

The [design-source audit](design-sources.md) now limits default study suites to
PD, Stag Hunt, Chicken and Battle of the Sexes. Resource control is removed;
Lab Notebook Audit and the earlier science demo are removed. Off-switch remains
requested, with a faithful published experimental setup still to implement. The
protection/attack oversight prototype remains on hold. Separate private PD /
Stag Hunt and a sequential audit game now have exact solvers and native Inspect
checks, but no live validation. Mathematical correctness alone does not validate
an experimental design.

The [earlier mixed live protocol](controlled-validation-protocol.md) is superseded
and blocked from collection. Its archived attempts contain nine billing failures
and one replacement-key failure, with zero model choices or main attempts.
Those records and spending holds remain intact. Resolving billing does not
resume the mixed suite or complete any empirical milestone.

## The question and the rule

**When an unwanted action stops paying, do model choices change as predicted?**
Fix each game's starting rules and payoffs. Change one intervention, with
observations below, at and above its mathematical ties where the action set
allows. Keep separate 2D figures for each game, model, incentive type and control.
Do not assume a model has one sharp or monotone behavioral threshold.

In PD the starting values remain T=2, R=1, P=0, S=−0.5. Cost z is paid only
by a player choosing D: final T=2−z, R=1, P=−z, S=−0.5. The two players pay
independently. Cooperation ties against D at z=.5 and against C at z=1.
Above 1 it strictly pays more against either action. Between .5 and 1 the
better action depends on the opponent; cooperation is not universally correct.
The same fixed-baseline principle applies to the other games.

| Game/study | Fixed | Varied | Separate outputs |
| --- | --- | --- | --- |
| PD | R=1, P=0, T=2, S=−.5 | D-cost: 0, .25, .45, .5, .55, .75, .95, 1, 1.05, 1.25 | Cooperation and joint outcomes |
| Stag Hunt | R=1, P=0, T=.5, S=−.5 | D-cost: 0, .25, .45, .5, .55, .75 | Cooperation and joint outcomes |
| Chicken | R=1, P=0, T=1.5, S=.5 | D-cost: 0, .25, .45, .5, .55, .75 | Yielding and joint outcomes |
| Battle of the Sexes | Role-specific 2/1/0 starting table | Y-cost, then a separate X-cost mirror: 0, .5, .95, 1, 1.05, 1.5, 1.95, 2, 2.05, 2.25 | Each role's X rate, agreement, XX/YY/mismatch, individual payoffs |

The custom oversight calculations remain documented in the [prototype rules](oversight.md),
not as selected paper experiments. Resource-type and notebook studies are no
longer available. The [game catalogue](../games/README.md) lists the separate
private-information games and the sequential audit implementation.

## Controls actually implemented

- **Four presentation blocks:** neutral label reversal crossed with table/list
  display order. Canonical pairs remain independent, stateless decisions with
  the correct role-specific table. Blocks receive equal analysis weight.
- **Coordination mirror:** BoS changes which substantive option is penalized,
  keeping the players' preferences fixed. Merely renaming X/Y is insufficient.
- **Canonical representation checks:** compare the original final table with
  `10*u` and `u+5`, separately at zero cost, each feasible tie and the highest
  scheduled cost. Transform every final payoff. The x-axis keeps original cost
  units; the table is not normalized again at each intervention. These checks
  are separate conditions, not extra repetitions of the primary curve.
- **Trace and proof consistency:** frozen prompts, randomized schedules, raw
  attempts, invalid/missing outputs and exact comparisons are retained. Lean
  uses the actual transformed, role-specific table, including the BoS mirror.
  It proves payoff statements, not a model's reasoning or intentions.

The canonical choices implement the retained parts of the [parameterization review](sweep-design.md).
Its cited normalization and controlled-comparison rationale draws on
[Gächter et al. (2024), §5.1](https://docs.iza.org/dp16814.pdf), while neutral
presentation and representation checks are informed by
[Akata et al. (2025)](https://hcai-munich.com/pubs/Akata2025Games.pdf) and
[Herr et al. (2024)](https://arxiv.org/abs/2407.04467). Our exact costs, counts
and toy reward values are design choices, not a literature consensus.

## Prepare the four canonical games without paid calls

```sh
python3 prepare_threshold_studies.py runs/threshold-plans
# Optional: a different directory, scripted responses, separate 2D figures.
python3 prepare_threshold_studies.py runs/threshold-check --simulate --figures
```

The first command writes four canonical plans plus a manifest of hashes,
source provenance, counts and request ceilings. The second exercises them
with synthetic actors and separate 2D figures. Outputs stay in ignored `runs/`;
they are software checks, not observations about LLM behavior. Existing plans
are never overwritten. Figures require the optional analysis packages.

| Software-pilot plan (default two repetitions/block) | Conditions | Maximum synthetic requests |
| --- | ---: | ---: |
| PD, including separate representation checks | 18 | 288 |
| Stag Hunt | 12 | 192 |
| Chicken | 12 | 192 |
| BoS, both directions and representation checks | 36 | 576 |

These are software-pilot counts, not a research sample or permission to spend.
The default suite prepares 1,248 synthetic requests with two repetitions/block.
The [historical live protocol](controlled-validation-protocol.md) documents a
separate sample; any new live plan must explicitly freeze its current scope,
endpoints, repetitions and remaining spending allowance.

Individual canonical plans now default to v2:

```sh
python3 experiment.py plan runs/pd-check --game pd --repetitions 2
python3 experiment.py run runs/pd-check
python3 experiment.py report runs/pd-check --plot
python3 experiment.py proofs runs/pd-check --check
```

For bounded live collection, `threshold_validation.py plan` now prepares only
canonical studies and retains the existing shared-ledger budget controls.
Direct oversight paid collection and old mixed-suite collection are blocked
before credentials or network requests. Historical plans can still be inspected
and analyzed. Notebook execution remains an explicitly offline prototype.
The [source standard](design-sources.md) must be satisfied before a sequential
study is restored. No paid calls were made during this scope correction.

## AISI status: all three stages remain open

Reassessed 19 November 2026 after correcting an overly generous completion
summary. The source is the **existing** detailed Months 1–6 timeline in the
[AISI project document](https://docs.google.com/document/d/1NDQEa96_60jxY9EErIWxu6jisrLZxhHVAPT6WHK5qr8/edit?tab=t.0),
under its heading “Work Timeline [Updated]”. The proposal itself has not changed.
The broader methodology also promises empirical validation; runnable collectors
and synthetic checks do not satisfy that promise.

**Implemented** below means code and calculations exist for stated assumptions.
**Validated** would require the relevant live data and completed analysis.
We should not report a number of completed months or a completion percentage:
the stages overlap, their requirements differ in effort, and validation remains open.

### Earlier evidence: what can and cannot carry over

| Artifact | What it supports | Credit toward the selected study |
| --- | --- | --- |
| Original T/S grid: 1,350 valid paired games | Historical behavior across different zero-cost payoff tables | Does not test an intervention cost on fixed starting games. No credit for completing the new cost sweeps. |
| 9 November oversight study: 3,660 main decisions | Historical conditional responses to imposed defense at its recorded settings | Some conditions overlap exactly, but this is not a newly collected v2 study and does not validate a published oversight design or the canonical cost controls. Kept as a historical comparison; the selected validation remains open. |
| v2 synthetic runs, passing software tests and Lean certificates | Collection plumbing, exact payoff comparisons and formal statements about those tables | No live LLM evidence, no proof of internal model reasoning, no real-world safety validation. |

The old data are not made numerically false by changing the design. The error
was counting them as completion of the newly selected validation. A direct
comparison found all 132 distinct neutral defense request variants (11 defenses
× 4 presentation blocks × 3 historical model specifications) unchanged in the
retained basic-defense planner. That establishes a narrow overlap within the
custom prototype, not validation of the active paper experiments. Any later reuse must be explicitly identified by
condition, prompt, model/provider and settings, kept separate from fresh data,
and declared before analysis; it must not masquerade as a fresh replication.

### Months 1–3 — base model built in part; validation open

| Requirement in the project document | Actual position | What closes it |
| --- | --- | --- |
| Formalize the human-defense / AI cooperate-or-attack game | [Executable custom rules](oversight.md) exist but are on hold under the source standard. | Choose a defensible published design or explicitly mapped adaptation; reconcile monitoring/detection with the chosen rules. |
| Express resource value, attack costs and harm penalties | Explicit functions exist only for the custom prototype. | Re-derive the payoffs and parameter meanings for the accepted design; prototype numbers are not measured utilities. |
| Solve deterministic Nash and Stackelberg cases | Exact code covers pure strategies on the declared defense grid and both follower tie conventions; finite-case tests exist. | Present the derivation and limits for this specification. Mixed or hidden commitments would require additional work if claimed. |
| Derive threshold inequalities | Exact equalities and strict/tied comparisons exist for the declared payoffs. | Tie each claim to its assumptions. Use the implemented payoff comparison, not the proposal's unsupported illustrative inequality `v > p − c`. |
| Toy simulations and basic LLM-driven agents | Scripted baselines and a collector exist; custom-game paid collection is blocked. **Current validation has not run.** | First resolve the design source, then freeze the sample, pilot, collect and analyze responses, failures and controls. |
| First blog | The repository links the earlier LessWrong post. Its coverage of the revised research claims has not been established. | Check/update its claims and distinguish historical findings from results still to be collected. An existing post alone does not close the revised evidence requirement. |

**Stage status: open.** Some mathematical/software tasks are implemented, but
that does not justify saying the first three months are finished. The four
canonical cost studies are our additional chosen paper design, not four games
explicitly mandated in the original Months 1–3 list. All four also await live
validation; their unrun status cannot be hidden inside the base-model milestone.

### Months 3–5 — separate applications implemented; live validation remains open

The [game catalogue](../games/README.md) records the implemented private PD /
Stag Hunt extensions and the sequential audit game. Their exact solvers and
native Inspect checks are software results, not live LLM validation. Off-switch
remains requested and still needs a faithful published experimental setup.

| Requirement | Actual position | What remains |
| --- | --- | --- |
| Incomplete information / distributional utilities | Separate PD / Stag Hunt games have fixed private reward profiles and matched revealed/hidden conditions. The sequential audit game also has finite private rewards. Exact solvers and Inspect checks exist. | Freeze and run bounded LLM validation; assess information effects and failures. Broader uncertainty settings are not covered. |
| Safety margins | Private-game dominance bounds and audit all-type deterrence intervals are implemented. | Empirically test these conditional predictions and their assumptions; a positive toy payoff gap is not a real-world safety guarantee. |
| Paperclip, off-switch and audit mappings | The sequential audit game maps a two-target subcase of published Audit Games. Resource/paperclip and Lab Notebook Audit are removed. Off-switch remains requested but is not currently implemented. | Complete a faithful published off-switch setup and validate the audit application. Removing a prototype does not complete or cancel an AISI deliverable. |
| Configurable benchmark scaffold | Canonical collectors, separate private-game reporting, native Inspect tasks and scripted baselines exist. | The new Inspect runner now freezes one-variable schedules and enforces a shared budget with restart support. Select the final models/repetitions, pass live compatibility pilots, then collect and analyze choices. |
| Second blog | No completed current-scope deliverable verified. | Produce it from the eventual uncertainty/margin results with limits stated. |

Native Inspect integration is implemented and tested for the audit game and
private PD / Stag Hunt. The canonical collectors retain their own JSON logs.
Inspect is not a named requirement in the original Months 1–3 list.

### Months 5–6 — collection tools ready; substantive deliverables open

| Requirement | Actual position | What remains |
| --- | --- | --- |
| Fragility measure | No completed, agreed measure with supporting results. | Specify the outcome, parameter units and how ties/multiple equilibria or abrupt switches are handled; derive and test the measure or the proposal's justified statistical fallback. |
| Sweeps below, near and above thresholds | v2 schedules, controls and separate 2D analysis are implemented. | Run the selected live studies and analyze uncertainty, presentation effects, invalid outputs and disagreements with predictions. Do not infer a precise behavioral threshold from sparse cells. |
| Unequal reasoning depths | Not implemented as a controlled comparison. | Vary reasoning effort while holding model and payoff settings fixed where supported; record the actual settings and resource use. Different model names do not isolate reasoning depth. |
| Statistical defection monitoring | Choice-rate intervals exist, but no evaluated alert/detection procedure. | Define an alert rule and evaluate false alarms and missed changes on separate data. |
| Theory, codebase and Paper 1 | Working code and methods notes exist; a finished theory contribution and paper are not established. | Consolidate proofs, empirical results, limitations and reproducible artifacts; complete and submit the paper. |

### Revised order of work and completion gates

1. **Resolve application provenance.** Map a suitable published sequential game
   or experimental environment to the AISI requirements. Document every change
   before admitting or restoring it. Keep the original deliverables unchanged.
2. **Validate the four canonical cost studies.** Freeze a canonical-only live
   plan and remaining budget, pass the pilot, then collect the declared sample.
   Report uncertainty, failures and inconclusive findings. The mixed archived
   suites stay blocked and historical results stay separate.
3. **Validate the implemented audit and private-information games.** Their
   exact solvers, information boundaries and scripted baselines exist; bounded
   live model studies remain unrun. Off-switch implementation remains separate
   unfinished work under the published-experiment requirement.
4. **Extend to uncertainty and robustness.** Specify the uncertainty model and
   safety margins, test mistaken beliefs, define fragility, compare reasoning
   effort and evaluate a monitoring rule on separate data.
5. **Finish the deliverables.** Reconcile application coverage with the original
   AISI plan, write the blogs and complete the theory/paper/reproduction package.

No paid experiments or new results were produced by this scope correction.
