# Months 3–5: choosing a defensible experiment

19 November 2026. **Literature and infrastructure review; no new game or LLM
results.** This is a proposed implementation route through the existing
[AISI plan](https://docs.google.com/document/d/1NDQEa96_60jxY9EErIWxu6jisrLZxhHVAPT6WHK5qr8/edit),
not a replacement timeline. The four canonical games do not complete this stage.

## Recommendation in plain language

Start with **one security/audit game family**: a defender commits to a checking
policy; an attacker knows its own rewards; the defender only knows the possible
reward profiles and their probabilities. Ask how much protection is needed when
the defender does not know exactly how rewarding an attack would be.

There are published foundations for the uncertainty, the checking rules and an
attack-or-abstain experiment. They are **different sources**. Combining them into
an LLM study would be our documented adaptation, not a reproduction of one paper.
First reproduce reference cases, then add the smallest justified extension.

The concrete recommended starting point is the published **Audit Games model
with punishment held fixed and its no-violation option retained**. Then add a
small finite set of private reward profiles using the Bayesian security-game
formulation below. This makes the baseline and our uncertainty extension
separately testable. The human deterrence experiment supplies an empirical
comparison to examine, rather than silently becoming the same protocol.

The original Off-Switch Game is a useful complementary candidate: the AI is
uncertain whether an action helps a human, and can ask the human to decide.
It is not the same uncertainty as a defender facing an attacker. Its previous
implementation stays removed. Bargaining offers the clearest reusable game code
found here, but is a weaker match to our safety question.

## What needs to be uncertain?

- **Hidden incentives:** the attacker knows its reward table; the defender knows
  a distribution over possible tables. This directly addresses the plan's
  uncertainty about the opponent's utilities. A “type” means one possible table,
  not another player or a different model size.
- **Hidden outcome:** both know there is a 40% chance of a check, but do not know
  whether this particular attempt will be checked. This is randomness; alone it
  does not establish hidden-incentive research.
- **Uncertain shared value:** an AI does not know whether its proposed action
  benefits the human. This is the uncertainty in the published off-switch model.

Stating point rewards in a prompt does not reveal or change a model's true
internal objective. Our empirical claim would concern responses to *assigned
incentives*, with that limitation explicit.

## Shortlist and source-to-design mapping

| Candidate | Published setup and information | What it contributes | What it does not supply |
| --- | --- | --- | --- |
| Bayesian Stackelberg security game | Defender announces a randomized allocation of guards. Attacker knows its own reward type and sees the allocation probabilities, not the realized guard locations. Defender knows the type distribution. | Direct mathematical foundation for hidden opponent rewards and commitment. | A ready LLM experiment; some versions require an attack, so target switching is not deterrence. |
| Audit Games | Auditor chooses checking probabilities and punishment; the other player chooses a violation target or the documented no-violation option. | A published checking/punishment model, including abstention. | The base model is not itself a hidden-type LLM study. |
| Original Off-Switch Game | Robot can act, stop or defer. Human knows the action's utility; robot has a belief about it. Both have the same utility. | A direct AI-control application of uncertainty. | An adversary with hidden selfish rewards, or an executable LLM benchmark. |
| Hidden-value bargaining | Two players negotiate an allocation of items; each sees its own item values. | Published human dialogue experiment and reusable game engine. | A natural definition of safety failure; disagreement is not automatically harmful defection. |
| AI Control / ControlArena | An untrusted agent does a task; a trusted model and limited auditing try to catch deliberate subversion. | Existing agent/monitor infrastructure built on Inspect. | Hidden reward distributions or incentive thresholds merely by selecting “attack” mode. |

### 1. Hidden rewards: the theoretical foundation

[Paruchuri et al., AAMAS 2008, §§2–3](https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf)
give an exact finite-type commitment formulation, DOBSS. The defender selects a
distribution over actions, anticipating each possible attacker's best response.
The optimization selects the response most favorable to the defender among
equally good attacker responses. Our implementation must make that convention
explicit and examine unfavorable ties too. A simultaneous Nash solver is not a
substitute for this commitment calculation.

[Kiekintveld, Marecki and Tambe, AAMAS 2011, §§3 and 5](https://www.ifaamas.org/Proceedings/aamas2011/papers/C7_G75.pdf)
extend this family to continuous payoff distributions, including uniform and
Gaussian examples. Their computational experiments vary uncertainty while
comparing coverage policies, including uniform coverage and a policy based on
mean payoffs. Continuous calculations use approximations; they are not a general
exact solver. This is a particularly direct source for the AISI distributional
utilities requirement.

**Our proposed first implementation:** a small finite-type reference case before
continuous distributions. No author-maintained, licensed, ready-to-run DOBSS
package was verified in this search. Implementing and checking the published
finite formulation remains work. Do not treat an unverified third-party script
as a reference solver.

### 2. Checking and deterrence: rules and an empirical precedent

[Blocki et al., *Audit Games*, §2 and the dummy-target discussion](https://arxiv.org/html/1303.0356)
model both checking probabilities and punishment. A violation's expected reward
combines its unchecked reward with its checked reward minus punishment. A dummy
target represents no violation, with zero payoff and no punishment. The auditor
also pays a cost for setting punishment. Fixing punishment simplifies the
optimization; jointly choosing it and coverage is more difficult. Adding private
reward types would be our extension of this source.

[Ridinger et al., *Risk Analysis* 2016, *Attacker Deterrence and Perceived Risk in
a Stackelberg Security Game*](https://doi.org/10.1111/risa.12547)
provide a human experiment with an explicit **do not attack** choice. It uses
five doors, one or two guards, and fixed versus rotating guarding descriptions
with equivalent attack probabilities. It measures attack/abstention behavior.
This is a concrete empirical precedent for deterrence, not an experiment in
private reward types or LLM behavior. The publisher abstract and indexed
experimental-design text were accessible; the university PDF download returned
404. Obtain the full instructions and payoff schedule before claiming a faithful
implementation. No runnable author experiment was verified.

[Nguyen et al., AAAI 2013, “A Simulated Security Game” and experimental sections](https://ix.cs.uoregon.edu/~thanhhng/publications/ConfPaper/AAAI2013_SUQR.pdf)
use a guards-and-treasures task, showing subjects coverage probabilities and
rewards/penalties. They compare models of imperfect reward maximization.
Subjects select a target to attack, so that protocol alone cannot establish
abstention thresholds. Its response-model comparison is relevant; its fitted
human coefficients must not be reused as LLM coefficients.

**Our proposed adaptation:** separate the source reproduction from a hidden-type
audit extension. Document changed player population, prompts, reward profiles,
information access, feedback, and sampling schedule. Preserve a genuine
no-violation action if the outcome is “attack stops.” A programmed defender and
LLM attacker can isolate the response experiment first; an LLM defender is a
separate later condition. Code can evaluate a defender's uncertainty even when
the defender is not itself an LLM.

### 3. Off-switch: requested application, faithful implementation pending

[Hadfield-Menell et al., IJCAI 2017, §§2–4](https://aima.eecs.berkeley.edu/~russell/papers/ijcai17-offswitch.pdf)
specify shared utility, robot uncertainty, and a better-informed human. The
robot compares acting immediately, stopping, and deferring to the human. Their
Gaussian/Boltzmann example varies uncertainty and human decision noise; in their
notation, zero noise is rational and larger noise approaches random decisions.

A faithful starting point would reproduce the action-value comparisons and a
published figure using the paper's human policy. Replacing the human with an
LLM would then be an explicit experimental adaptation. The old symmetric-error
policy and added consultation fee are not the original model. No runnable
author benchmark was verified in this review. Off-switch remains requested;
selecting and implementing a faithful published experimental setup is unfinished.

### 4. Bargaining: useful existing code, weaker safety fit

[Lewis et al., EMNLP 2017, §2.2](https://aclanthology.org/D17-1259/)
study negotiation over three item types with private valuations, and release
human dialogues and code. The original
[repository](https://github.com/facebookresearch/end-to-end-negotiator) is
archived; its actual LICENSE file states CC BY-NC 4.0, despite the GitHub API
returning `NOASSERTION` for license detection.

[OpenSpiel's bargaining implementation](https://github.com/google-deepmind/open_spiel/tree/4956843d7375e29a4c986425c66f897d7ac15340/open_spiel/games/bargaining)
explicitly cites that design. It provides structured offers/acceptance, terminal
rewards and tests. Its player-specific information state includes that player's
values and offer history, rather than the opponent's values. It defaults to ten
turns; discounting and random termination are configurable. This structured game
is not a recreation of the original natural-language dialogue protocol.
OpenSpiel's game catalogue labels it **lightly tested**. We inspected code, but
did not install or execute it. Generic OpenSpiel algorithms do not automatically
solve our Bayesian commitment problem.

### 5. ControlArena: an oversight framework, not the incentive model

[Greenblatt et al., ICML 2024](https://proceedings.mlr.press/v235/greenblatt24a.html)
evaluate control protocols using programming tasks and deliberately subversive
policies, with trusted models and limited auditing. This supplies a concrete
agent/monitor evaluation approach; it does not derive our payoff thresholds.

[ControlArena](https://control-arena.aisi.org.uk/evaluation.html) already creates
Inspect tasks from environments, policies, monitors and honest/attack modes. It
can evaluate alternative monitors on saved trajectories. It is a useful later
route to realistic tool-using agents, but setting an attack policy is not evidence
that attacks arise at a rational incentive threshold. Start with plain Inspect
for the small numeric game; add ControlArena when an accepted task needs its
agent/monitor machinery.

## What the threshold and safety margin would mean

**Proposed mathematical specification, not an implemented result:** for a fixed
checking policy, compute each reward type's expected payoff for every available
action. Define its margin as:

```text
margin = payoff from abstaining − highest expected payoff from any violation
```

A positive margin makes abstention strictly better for that type under expected
payoff maximization. Zero is a tie. A negative margin means at least one
violation pays more. It does not predict an LLM's exact attack probability.

For a single target with no-violation payoff zero, let `r` be the unchecked
reward, `s` the checked reward before punishment, `x` the punishment, and `q`
the checking probability. The audit payoff comparison gives:

```text
expected violation payoff = (1 − q) r + q (s − x)
tie at q* = r / (r − s + x), when the denominator is positive
```

This is our algebraic restatement of the published payoff rule, not a new theorem.
Check zero/negative denominators, ties, and whether the crossing lies in `[0,1]`;
do not silently clip an impossible threshold. With multiple targets, all
violations must be compared and the checking allocation must satisfy the
resource constraint. Deterring every target/type may be impossible.

The uncertainty extension must distinguish three claims:

1. **Known distribution:** weight type-specific responses by their stated
   probabilities. Report ties as a range unless a tie rule is assumed.
2. **Bounded uncertainty:** take the smallest margin across an explicit set of
   possible reward profiles. A positive minimum is a conditional guarantee for
   maximizing agents in that set only.
3. **Mistaken beliefs:** design a policy using one distribution, evaluate it
   under another. This measures sensitivity; it is not covered by the first
   guarantee. Unbounded payoff distributions may prevent any finite worst-case
   deterrence guarantee.

Compare a policy using mean rewards, one using the declared distribution, and
one protecting against the specified worst case. The last comparison is our
proposed research treatment, not a claimed replication of all cited papers.
Separate attack frequency, successful harmful outcomes and defender welfare.
A caught attack is still an attempted attack.

For parameterization, keep punishment and reward units fixed while varying a
feasible checking allocation; do not vary all target probabilities independently
of the guard budget. Study distribution width separately, holding its mean
fixed. Subtracting an action-independent baseline from every outcome can put
abstention at zero, and a common positive scale preserves best responses. Do not
renormalize each experimental condition separately and erase the uncertainty
treatment. Numerical scaling need not preserve an LLM's observed choices or a
fixed-noise behavioral model.

## Inspect: concrete integration plan

[Inspect logs](https://inspect.aisi.org.uk/eval-logs.html) provide native `.eval`
files, transcript events, model calls, scores and metadata, with a viewer and a
`read_eval_log` API. We should use those native records and export a compact
analysis table keyed by run/sample IDs. The existing custom JSON files remain
historical evidence; they do not become native Inspect runs retroactively.

Proposed flow:

```text
frozen game instance + private reward type
    → defender sees only its permitted information and commits to a policy
    → attacker sees that policy and its own permitted reward information
    → attacker chooses an action
    → seeded environment resolves any random check
    → deterministic scorer calculates payoffs, best responses and margin
    → Inspect saves calls/events; analysis produces separate 2D plots
```

In Inspect terminology a **solver** runs the interaction; our **mathematical
solver** computes the predictions. These are separate components. A model must
not grade its own payoff correctness when exact scoring is available.

| Component to build | Required behavior |
| --- | --- |
| Dataset | Stable instance/sample IDs; declared prior and actual type; public/private fields; seed; payoff/source version. Evaluator truth stays out of unauthorized prompts. |
| Player views | Separate message histories. Explicitly allowlisted public actions cross the boundary; private reasoning and hidden types do not. No shared full-state prompt. |
| Roles | Bind every LLM role and provider explicitly. Inspect records roles, but an unspecified role can fall back to the default model. Reject missing bindings in our adapter. |
| Action handling | Legal structured actions; record raw output, parse result, invalid/missing responses and interruptions. No silent conversion of failures into abstention. |
| Scoring | Expected and realized payoffs, predicted best-response set, ties, chosen-action payoff loss, attack and harmful-outcome indicators. Score against information available at the decision. |
| Reproducibility | Game/code/prompt hashes; model/provider identity; requested and effective settings; token use; timing; costs or explicitly unknown costs; retry/caching history. |
| Boundaries and failures | Offline checks for hidden-information leakage, tie cases, infeasible deterrence, seeded outcomes, role separation and partial/failed records. |

The role behavior is documented in
[Inspect's model-role guide](https://inspect.aisi.org.uk/models.html#model-roles).
Role names alone do not enforce information boundaries; those are our code's job.

[Inspect's reasoning support](https://inspect.aisi.org.uk/reasoning.html)
records reasoning content exposed by providers as `ContentReasoning`, and
reasoning-token counts where available. Some providers expose summaries or no
readable reasoning. These records do not reveal inaccessible internal thinking
or prove that an explanation caused a choice. Score behavior first; use exposed
reasoning as secondary evidence. Record visibility and keep private reasoning
out of opponents' prompts. Later reasoning-effort comparisons belong to the
Months 5–6 robustness work; effort labels are not uniform across providers.

[Inspect's task cost limit](https://inspect.aisi.org.uk/setting-limits.html)
is per sample and requires configured cost data. It does not replace a shared
study spending ledger. Before paid collection, integrate the total budget,
all model roles and retries, maximum-call costs, and billing reconciliation.
Keep initial failures even if a declared retry succeeds; automatic retries must
not selectively erase bad outcomes.

## Bounded sequence of work

1. **Reproduce a source.** Implement the fixed-punishment Audit Games subcase
   and verify its payoff/commitment calculations. Resolve the empirical
   instructions before claiming replication. Output: source-to-code mapping,
   reference cases, independent solver checks and documented tie conventions.
2. **Add uncertainty explicitly.** Start with a small finite set of reward
   profiles, then test one distribution-width change with its mean held fixed.
   Output: information diagram, type-specific predictions, feasible/infeasible
   safety margins, and a comparison with treating mean rewards as certain.
3. **Connect Inspect offline.** Use scripted policies and mocked model outputs
   first. Output: native logs, deterministic scoring, leakage/failure tests and
   a compact export. An Inspect package installed locally is not integration.
4. **Freeze a small LLM study.** First isolate attacker responses to programmed
   policies; add an LLM defender only as a distinct condition. Fix source rules,
   types, prompts and model settings; vary checking around calculated boundaries.
   Use separate 2D panels by type/model/uncertainty level, not a large all-parameter
   sweep. Choose repetition counts from pilot precision and budget, keep the
   pilot separate, and retain invalid responses. Do not import human effect sizes
   or count repeated API responses as independent model populations.
5. **Close the AISI deliverables with evidence.** Publish the configurable
   benchmark, uncertainty/margin results and second blog. Explicitly account for
   the paperclip/resource, off-switch and audit application mappings requested in
   the original plan. One security experiment alone does not check off all three.

## What this review completes

Completed: primary-source shortlist, explicit adaptation boundaries, code/license
inspection, and an Inspect integration specification. Repository snapshots and
readiness notes are in [the infrastructure audit](months3-5-infrastructure.md).

Still open: final application specification, accepted game implementation,
uncertainty/robust-margin solvers, tested Inspect adapter, empirical validation
and the remaining application mappings. No paid calls, model results, source
reproduction or Months 3–5 completion are claimed by this review.
