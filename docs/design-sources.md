# Which game designs belong in this study?

19 November 2026. This rule applies to **every game**, including oversight,
off-switch and future applications: use an established game, or adapt a
specific published experimental design and document the changes. A relevant
background citation alone does not establish that a design was borrowed.

## Current scope

| Game | Design basis and our changes | Decision |
| --- | --- | --- |
| Prisoner's Dilemma | Established simultaneous game: defection initially pays more against either choice, despite mutual cooperation being better than mutual defection. Our fixed table and defection-cost schedule are adaptations. | Retain; controlled LLM validation pending. |
| Stag Hunt | Established coordination game: cooperation is best against cooperation; the less demanding action is best against itself. Our cost treatment changes these incentives. | Retain; controlled LLM validation pending. |
| Chicken / Hawk–Dove | Established anti-coordination game: each prefers insisting against yielding and yielding against insisting. Our treatment penalizes insisting. | Retain; controlled LLM validation pending. |
| Battle of the Sexes | Established coordination game with different preferred shared outcomes. Our 2/1/0 table and separate costs on X and Y retain both player roles. | Retain; controlled LLM validation pending. |
| Human–AI protection/attack oversight | Our linear resource, attack, harm and penalty rules; security-game literature supplies background, not this experiment. | Custom prototype only. Excluded from new study suites; paid collection blocked. Historical data retained. |
| Lab Notebook Audit | Our eight-record generator, inclusion swap, rewards and checking budgets. Published oversight work motivates the question, but does not supply these rules. | Custom prototype only. Excluded from new study suites; offline runner only. Needs a published-design mapping or replacement. |
| Resource / paperclip game | Our two-private-value extension of the protection game. No documented published experiment supplies its full design. | Removed from code, UI, serving, build and planners. No replacement selected. |
| Off-switch | The retired implementation adapted Hadfield-Menell et al., but used two utility states, a symmetric human-error rule and an added consultation cost. | Remains removed. Any return must map the published model and explicitly justify changes. |

The four retained games share two players, two simultaneous actions, and full
knowledge of the payoff table. Players do not see the other's choice before
acting. Separate stateless LLM calls implement those choices. Our treatment
subtracts a cost from a specified action, holding the starting table fixed;
at large costs the resulting game can leave its original payoff region.
Exact tables and outcomes are in [the rules](games.md) and
[the controlled design](controlled-thresholds.md).

## What the sources actually support

- **[Herr et al. (2024), Are Large Language Models Strategic Decision Makers?, §3 and Appendix B](https://arxiv.org/html/2407.04467v3).** Studies PD and Stag Hunt with neutral action labels, varying presentation and payoffs. This supports our attention to label/order effects. Our crossed presentation blocks, cost grid and repetition counts are our choices, not their protocol.
- **[Akata et al. (2025), Playing repeated games with large language models, Nature Human Behaviour](https://doi.org/10.1038/s41562-025-02172-y).** Uses finitely repeated two-player games, including PD and Battle of the Sexes. Its agents have interaction history. Our independent one-shot experiment is not a reproduction of that repeated-game experiment.
- **[Gächter et al. (2024), The Role of Payoff Parameters for Cooperation in the One-Shot Prisoner's Dilemma, §5.1](https://docs.iza.org/dp16814.pdf).** Provides payoff-normalization and controlled-comparison methodology for human PD experiments. It informs the reduction of redundant payoff scales; it does not establish an LLM response or prescribe our intervention schedule.
- **[Polak, Yale ECON 159, Lecture 12](https://oyc.yale.edu/economics/econ-159/lecture-12).** An academic reference for Chicken/Hawk–Dove and coordination-game structure. This establishes a standard game family, not an LLM collection protocol.
- **[Korzhyk et al. (2011), Stackelberg vs. Nash in Security Games, JAIR](https://www.cs.cmu.edu/~conitzer/stackelbergJAIR11.pdf).** Studies defender commitment and attacker response in security games. Randomized allocations to targets differ from our deterministic protection rule. It was the resource game's documented background, not a source for its exact design.
- **[Hadfield-Menell et al. (2017), The Off-Switch Game, §§2–4, IJCAI](https://ijcai.org/proceedings/2017/32).** A direct source for a game in which a robot is uncertain about a shared utility and can act, stop or defer to a better-informed human. Our retired version changed the human policy from the paper's Boltzmann example to symmetric errors and added consultation cost. A new adaptation must distinguish reproduced predictions from new ones; citing this theoretical paper does not supply an LLM experimental protocol.
- **[Bowman et al. (2022), Measuring Progress on Scalable Oversight](https://arxiv.org/abs/2211.03540)** and **[Khan et al. (2024), Debating with More Persuasive LLMs Leads to More Truthful Answers, ICML](https://proceedings.mlr.press/v235/khan24a.html).** Supply concrete oversight evaluations: model-assisted judgments and debate with a less-informed judge. Neither supplies our notebook generator or single-swap task. A debate setup is a possible future design to examine, not an environment already implemented here.

This is a source audit, not a retroactive claim that every cited paper was
used when the code was first written. Publication venue or popularity alone
does not make a method suitable; its assumptions must fit our question.

For the next stage, the [Months 3–5 design review](months3-5-design-review.md)
compares published security/audit, off-switch, bargaining and AI-control setups,
including their information assumptions and reusable infrastructure. It
recommends a security/audit starting point with explicit adaptation boundaries;
it does not admit a replacement game or validate the removed prototypes.

## Before admitting or restoring a game

Record the exact paper section or released implementation and map its players,
actions, information, order of play, payoffs, treatments and measured outcomes
to ours. Identify every change and explain why it preserves the relevant
comparison. Derive the resulting thresholds, reproduce reference cases, and
test the implementation before freezing a bounded LLM study. A theoretical
model and an empirical collection protocol are different things; document both.

The current canonical solvers derive payoff differences, exact ties and pure
Nash outcomes. Lean checks canonical payoff statements. These are conditional
mathematical predictions, not a model of the percentage of LLMs choosing each
action. In regions with multiple equilibria or opponent-dependent best choices,
we must not invent a unique predicted action. Equations that work for a custom
prototype do not, by themselves, justify its experimental design.

The default offline and live-suite planners now include only the four canonical
games. Direct paid oversight collection and frozen mixed-suite collection are
blocked before credentials or network calls. Historical data and analysis remain
available. The notebook runner has no paid adapter. Resource, off-switch and
the earlier science demo are absent from the published build.

**AISI consequence:** the original project requirements have not changed.
Choosing and implementing defensible sequential and incomplete-information
applications is still unfinished Months 1–3 / Months 3–5 work. Removing a
prototype does not complete or cancel those deliverables.
