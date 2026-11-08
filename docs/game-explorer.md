# Threshold Tide: the local game explorer

Threshold Tide is an interactive way to understand the repository's four
two-player games. Choose a game, change one incentive and see how its expected
points change. You can also play short local rounds against a random opponent.

From the repository directory, run:

```bash
python3 serve_game_explorer.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) in your browser. Stop the server
with `Ctrl+C` in the terminal. The explorer needs Python 3.11 or newer and a
browser, with no extra packages, build step, API keys or model calls. It does not use the research collection
budget. Games run locally; this is not a web multiplayer service.

If port 8765 is already in use, run `python3 serve_game_explorer.py --port 8766`
and open `http://127.0.0.1:8766` instead.

## Start with a payoff table

Choose Prisoner's Dilemma, Chicken, Stag Hunt or protocol coordination
(Battle of the Sexes). Each game has two players and two possible actions.
The payoff matrix lists the points both players receive for each pair of
choices. In **Explore outcomes**, click a cell or choose both players' moves
to inspect that joint outcome. This does not add a practice round to the log.

Use **Payoff set** to compare the Paper 1 study with the repository's
application scenarios. Paper 1 fixes mutual-cooperation points at 1 and
mutual-defection points at 0 for its symmetric games. Protocol coordination
keeps a separate asymmetric table: both players want to match, but they
prefer different matching outcomes. Scenario presets use their own action
names and reward scales.

Select **Your point of view**. The first and second numbers in a payoff pair belong
to the row and column players respectively. Changing roles is especially
important in protocol coordination, because the preferred protocol and
decision boundary differ between players.

## Change one thing

Under **Change one thing**, choose the variable for the curve, then move its
slider or enter a value. Other payoff parameters automatically return to the
selected preset when you change experiments. The inactive payoff changes do
not carry over. The available interventions have different meanings:

| Game | Intervention |
| --- | --- |
| Prisoner's Dilemma | Cost whenever a player chooses the second action |
| Chicken | Cost whenever a player escalates |
| Stag Hunt | Bonus whenever a player chooses the first action |
| Protocol coordination | Bonus to both players whenever their protocols match, for either matching outcome |

For the Paper 1 PD preset, the action-cost experiment gives `-0.25` points
for cooperating against defection (`S`); the other PD experiments use `-0.5`.
This deliberate change is shown in the preset note and comes from the
research design.

The opponent-chance control, `q`, is the probability that the random opponent
chooses its first action. For example, `q=0.75` means a 75% chance of that
action on each round. It is an input you set, not a prediction of what another
person or model will do.

The expected-point curves average the two possible opponent actions using
that probability. The calculated crossing, when one exists, marks equal
expected points for your two actions. At equality, either action maximizes
your points. If the lines do not meet in the displayed range, the interface
says **No switch in this range**. If they coincide throughout, it reports
that there is no single switching point.
These curves are calculations from the table, not fitted model behavior or
statistical confidence intervals. The calculation uses exact fractions;
displayed decimals may be rounded. An approximate decimal for a fractional
crossing need not give an exact tie.

For a quick example, choose Paper 1 Prisoner's Dilemma, **Cost of second
action**, and a 50% opponent chance. At cost `0.25`, defection earns more
expected points; at `0.375` the choices tie; at `0.5`, cooperation earns more.

## Play and inspect local rounds

Switch to **Play a round** and choose your action. The other player's move
is drawn independently from `q` before your choice; the round reveals both
actions and their points. Use **Next round** to prepare another turn.
A random opponent can
produce an unlikely outcome; one round's higher reward does not establish
which action has the higher expected reward.

Use **Your practice rounds** to inspect earlier choices and outcomes. The panel
shows the latest eight rounds; the exports contain every round still in the
session history. Download JSON
for a structured record or CSV for a table you can open in a spreadsheet.
Both exports include each round's settings, payoff matrix, starting preset,
role, choices and rewards, and are labeled illustrative. Keep the settings and payoff units with
the outcomes; totals from different games or presets are not a common
performance scale. History lives only in the current page, so download it
before closing or reloading. **Clear** removes the practice history.

## What the display does and does not establish

- In strict, one-shot Prisoner's Dilemma, defecting (D) gives more points against
  either opponent action. Varying its payoffs while staying inside that strict
  game does not create a selfish switch to cooperation. An intervention can
  create a crossing by changing those incentives.
- An intervention can also change the game's classification. The original
  game name describes the starting problem, not necessarily every changed
  table.
- Normalizing a payoff table preserves mathematical comparisons of expected
  points. It does not prove that a language model responds identically to
  differently written numbers.
- Local clicks and random draws are examples, not research observations.
  They do not establish how an AI behaves, whether cooperation is safe, or
  whether an intervention works in an actual application.

For research collection and uncertainty rules, use the separate
[Paper 1 protocol](research/paper-one-protocol.md). This explorer does not
replace its frozen designs, repeated independent model observations or audit.

The visual direction is an original undersea lobby with dark panels and
cyan/pink accents, inspired by the atmosphere of
[Puffer Party](https://krillion.io/party). Threshold Tide uses its own branding
and original local artwork.

## Verification

On 8 November 2026, the complete suite passed **425 tests and 340 subtests**;
the existing Lean check was skipped because its toolchain is unavailable.
The explorer adds 110 tests for constructor parity, both player roles, exact
crossings and ties, input validation, and the local HTTP service.

Browser checks covered all four games, the two preset sources, the PD cost
tie at `0.375`, canonical Chicken and Stag Hunt crossings, the two distinct
coordination-game crossings, outcome previews, and practice rounds from
either player role. Downloaded JSON and CSV were parsed and checked against
their saved payoff matrices. Invalid numeric entries keep play disabled,
including after changing role; older responses cannot overwrite newer settings.

The desktop view and a 390 × 844 phone viewport were inspected, including
long decimal payoffs and the responsive chart. No horizontal page overflow
or browser errors were present in the checked states. These checks establish
software behavior, not empirical research findings.
