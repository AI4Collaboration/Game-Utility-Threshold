"""Explicit, machine-readable validity checks for the research game catalog."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Iterable, Literal, Mapping

from .base import Profile, TwoByTwoGame
from .scenarios import SCENARIOS, CanonicalScenario
from .uncertainty import UncertainPayoffGame
from .uncertain_scenarios import uncertain_scenario_from_id

Relation = Literal[">", ">=", "<", "<=", "=="]


@dataclass(frozen=True)
class ValidationCheck:
    """One auditable numeric inequality or structural claim."""

    subject: str
    category: str
    check_id: str
    expression: str
    observed: Mapping[str, object]
    passed: bool
    margin: float | None = None
    explanation: str = ""

    def record(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "category": self.category,
            "check_id": self.check_id,
            "expression": self.expression,
            "observed": dict(self.observed),
            "margin": self.margin,
            "passed": self.passed,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class CatalogValidationReport:
    """Complete validation result for all built-in research scenarios."""

    checks: tuple[ValidationCheck, ...]

    @property
    def failures(self) -> tuple[ValidationCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)

    @property
    def valid(self) -> bool:
        return not self.failures

    def require_valid(self) -> None:
        if self.valid:
            return
        failed = ", ".join(
            f"{check.subject}:{check.check_id}" for check in self.failures
        )
        raise ValueError(f"game catalog validation failed: {failed}")

    def record(self) -> dict[str, object]:
        subjects = sorted({check.subject for check in self.checks})
        categories = sorted({check.category for check in self.checks})
        return {
            "schema_version": 1,
            "valid": self.valid,
            "check_count": len(self.checks),
            "failure_count": len(self.failures),
            "subject_count": len(subjects),
            "subjects": subjects,
            "categories": categories,
            "checks": [check.record() for check in self.checks],
        }


def _numeric_check(
    subject: str,
    category: str,
    check_id: str,
    left_label: str,
    left: float,
    relation: Relation,
    right_label: str,
    right: float,
    explanation: str,
    *,
    tolerance: float = 1e-9,
) -> ValidationCheck:
    finite = isfinite(left) and isfinite(right)
    signed_difference = left - right
    if relation == ">":
        passed = finite and signed_difference > tolerance
        margin = signed_difference
    elif relation == ">=":
        passed = finite and signed_difference >= -tolerance
        margin = signed_difference
    elif relation == "<":
        passed = finite and -signed_difference > tolerance
        margin = -signed_difference
    elif relation == "<=":
        passed = finite and -signed_difference >= -tolerance
        margin = -signed_difference
    else:
        absolute_error = abs(signed_difference)
        passed = finite and isclose(left, right, abs_tol=tolerance)
        margin = tolerance - absolute_error
    return ValidationCheck(
        subject=subject,
        category=category,
        check_id=check_id,
        expression=f"{left_label} {relation} {right_label}",
        observed={left_label: left, right_label: right},
        passed=passed,
        margin=margin,
        explanation=explanation,
    )


def _structural_check(
    subject: str,
    check_id: str,
    expression: str,
    passed: bool,
    observed: Mapping[str, object],
    explanation: str,
    *,
    category: str = "strategic_structure",
) -> ValidationCheck:
    return ValidationCheck(
        subject=subject,
        category=category,
        check_id=check_id,
        expression=expression,
        observed=observed,
        passed=passed,
        explanation=explanation,
    )


def _profiles(values: Iterable[Profile]) -> list[list[str]]:
    return [list(profile) for profile in sorted(values)]


def _symmetric_values(
    game: TwoByTwoGame, player: Literal["row", "column"]
) -> dict[str, float]:
    first, second = game.actions
    return {
        "R": game.utility(player, first, first),
        "S": game.utility(player, first, second),
        "T": game.utility(player, second, first),
        "P": game.utility(player, second, second),
    }


def _ordering_checks(
    subject: str,
    player: str,
    values: Mapping[str, float],
    ordering: tuple[str, ...],
    explanation: str,
) -> list[ValidationCheck]:
    return [
        _numeric_check(
            subject,
            "payoff_inequality",
            f"{player}_{left}_gt_{right}",
            f"{player}.{left}",
            values[left],
            ">",
            f"{player}.{right}",
            values[right],
            explanation,
        )
        for left, right in zip(ordering, ordering[1:])
    ]


def validate_game_family(
    game: TwoByTwoGame, *, subject: str | None = None
) -> tuple[ValidationCheck, ...]:
    """Validate a payoff matrix against the defining claims of its family."""
    subject = subject or game.game_id
    checks: list[ValidationCheck] = []
    finite = all(
        isfinite(value)
        for payoff in game.payoffs.values()
        for value in (payoff.row, payoff.column)
    )
    checks.append(
        _structural_check(
            subject,
            "finite_payoffs",
            "all eight payoff entries are finite",
            finite,
            {"finite_entries": sum(
                isfinite(value)
                for payoff in game.payoffs.values()
                for value in (payoff.row, payoff.column)
            ), "total_entries": 8},
            "NaN and infinite utilities make thresholds and comparisons invalid.",
            category="numeric_sanity",
        )
    )
    first, second = game.actions
    first_diagonal = (first, first)
    second_diagonal = (second, second)
    diagonals = {first_diagonal, second_diagonal}
    off_diagonals = {(first, second), (second, first)}

    if game.family in {"prisoners_dilemma", "chicken", "stag_hunt"}:
        checks.append(
            _structural_check(
                subject,
                "symmetric_matrix",
                "matrix is symmetric under exchange of players",
                game.is_symmetric,
                {"is_symmetric": game.is_symmetric},
                "These three canonical families use role-symmetric payoffs.",
            )
        )

    if game.family == "prisoners_dilemma":
        for player in ("row", "column"):
            values = _symmetric_values(game, player)
            checks.extend(
                _ordering_checks(
                    subject,
                    player,
                    values,
                    ("T", "R", "P", "S"),
                    "Prisoner's Dilemma requires temptation > reward > punishment > sucker.",
                )
            )
            checks.append(
                _numeric_check(
                    subject,
                    "payoff_inequality",
                    f"{player}_repeated_game_efficiency",
                    f"2*{player}.R",
                    2.0 * values["R"],
                    ">",
                    f"{player}.T+{player}.S",
                    values["T"] + values["S"],
                    "Sustained mutual cooperation must beat alternating exploitation.",
                )
            )
        expected_nash = {second_diagonal}
        checks.extend(
            (
                _structural_check(
                    subject,
                    "unique_defection_nash",
                    "pure Nash equilibria = {(second, second)}",
                    set(game.pure_nash_equilibria()) == expected_nash,
                    {
                        "actual": _profiles(game.pure_nash_equilibria()),
                        "expected": _profiles(expected_nash),
                    },
                    "Strict defection incentives should produce one inefficient equilibrium.",
                ),
                _structural_check(
                    subject,
                    "strict_defection_dominance",
                    "second action is strictly dominant for both players",
                    all(
                        game.dominant_actions(player, strict=True) == (second,)
                        for player in ("row", "column")
                    ),
                    {
                        "row": list(game.dominant_actions("row", strict=True)),
                        "column": list(game.dominant_actions("column", strict=True)),
                        "expected": [second],
                    },
                    "The competitive action must dominate against either opponent action.",
                ),
                _structural_check(
                    subject,
                    "mutual_cooperation_welfare_optimum",
                    "(first, first) is the unique utilitarian optimum",
                    game.welfare_optimal_profiles("utilitarian") == (first_diagonal,),
                    {
                        "actual": _profiles(
                            game.welfare_optimal_profiles("utilitarian")
                        ),
                        "expected": _profiles({first_diagonal}),
                    },
                    "The dilemma requires individually dominated cooperation to be jointly best.",
                ),
            )
        )
    elif game.family == "chicken":
        for player in ("row", "column"):
            values = _symmetric_values(game, player)
            checks.extend(
                _ordering_checks(
                    subject,
                    player,
                    values,
                    ("T", "R", "S", "P"),
                    "Chicken requires temptation > mutual restraint > yielding loss > crash.",
                )
            )
        checks.append(
            _structural_check(
                subject,
                "anti_coordination_nash",
                "pure Nash equilibria are exactly the off-diagonals",
                set(game.pure_nash_equilibria()) == off_diagonals,
                {
                    "actual": _profiles(game.pure_nash_equilibria()),
                    "expected": _profiles(off_diagonals),
                },
                "Chicken should reward unilateral escalation but punish mutual escalation.",
            )
        )
    elif game.family == "stag_hunt":
        for player in ("row", "column"):
            values = _symmetric_values(game, player)
            checks.extend(
                _ordering_checks(
                    subject,
                    player,
                    values,
                    ("R", "T", "P", "S"),
                    "Stag Hunt requires reward > safe-against-cooperation > mutual safety > failed cooperation.",
                )
            )
        checks.extend(
            (
                _structural_check(
                    subject,
                    "coordination_nash",
                    "pure Nash equilibria are exactly the two diagonals",
                    set(game.pure_nash_equilibria()) == diagonals,
                    {
                        "actual": _profiles(game.pure_nash_equilibria()),
                        "expected": _profiles(diagonals),
                    },
                    "The game must preserve both payoff-dominant and safe equilibria.",
                ),
                _structural_check(
                    subject,
                    "cooperation_payoff_dominant",
                    "(first, first) is the unique utilitarian optimum",
                    game.welfare_optimal_profiles("utilitarian") == (first_diagonal,),
                    {
                        "actual": _profiles(
                            game.welfare_optimal_profiles("utilitarian")
                        ),
                        "expected": _profiles({first_diagonal}),
                    },
                    "Joint high-assurance cooperation must be payoff dominant.",
                ),
            )
        )
    elif game.family == "battle_of_the_sexes":
        row = {
            "preferred": game.utility("row", first, first),
            "concession": game.utility("row", second, second),
            "mismatch_1": game.utility("row", first, second),
            "mismatch_2": game.utility("row", second, first),
        }
        column = {
            "preferred": game.utility("column", second, second),
            "concession": game.utility("column", first, first),
            "mismatch_1": game.utility("column", first, second),
            "mismatch_2": game.utility("column", second, first),
        }
        for player, values in (("row", row), ("column", column)):
            checks.extend(
                (
                    _numeric_check(
                        subject,
                        "payoff_inequality",
                        f"{player}_preferred_gt_concession",
                        f"{player}.preferred",
                        values["preferred"],
                        ">",
                        f"{player}.concession",
                        values["concession"],
                        "Each player must strictly prefer a different coordinated outcome.",
                    ),
                    _numeric_check(
                        subject,
                        "payoff_inequality",
                        f"{player}_concession_gt_mismatch_1",
                        f"{player}.concession",
                        values["concession"],
                        ">",
                        f"{player}.mismatch_1",
                        values["mismatch_1"],
                        "Either coordinated outcome must beat protocol mismatch.",
                    ),
                    _numeric_check(
                        subject,
                        "payoff_inequality",
                        f"{player}_concession_gt_mismatch_2",
                        f"{player}.concession",
                        values["concession"],
                        ">",
                        f"{player}.mismatch_2",
                        values["mismatch_2"],
                        "Either coordinated outcome must beat protocol mismatch.",
                    ),
                    _numeric_check(
                        subject,
                        "payoff_equality",
                        f"{player}_symmetric_mismatch_cost",
                        f"{player}.mismatch_1",
                        values["mismatch_1"],
                        "==",
                        f"{player}.mismatch_2",
                        values["mismatch_2"],
                        "The canonical parameterization assigns the same cost to either mismatch direction.",
                    ),
                )
            )
        checks.append(
            _structural_check(
                subject,
                "opposed_coordination_nash",
                "pure Nash equilibria are exactly the two diagonals",
                set(game.pure_nash_equilibria()) == diagonals,
                {
                    "actual": _profiles(game.pure_nash_equilibria()),
                    "expected": _profiles(diagonals),
                },
                "The game must contain two efficient equilibria with opposed focal preferences.",
            )
        )
    else:
        checks.append(
            _structural_check(
                subject,
                "known_family",
                "family has a registered validation specification",
                False,
                {"family": game.family},
                "Unknown game families cannot inherit canonical inequality claims.",
                category="catalog_integrity",
            )
        )
    return tuple(checks)


def validate_uncertain_game(
    game: UncertainPayoffGame, *, subject: str | None = None
) -> tuple[ValidationCheck, ...]:
    """Validate every latent state and the probability-weighted expected game."""
    subject = subject or game.game_id
    checks: list[ValidationCheck] = [
        _numeric_check(
            subject,
            "probability",
            "state_probabilities_sum_to_one",
            "sum(state_probability)",
            sum(state.probability for state in game.states),
            "==",
            "one",
            1.0,
            "Latent payoff states must define a normalized distribution.",
        ),
        _structural_check(
            subject,
            "multiple_latent_states",
            "number of latent states >= 2",
            len(game.states) >= 2,
            {"state_count": len(game.states)},
            "A research uncertainty model should contain genuine payoff uncertainty.",
            category="probability",
        ),
    ]
    for state in game.states:
        checks.append(
            _numeric_check(
                f"{subject}:state:{state.state_id}",
                "probability",
                "positive_state_probability",
                "state_probability",
                state.probability,
                ">",
                "zero",
                0.0,
                "Every declared latent state must have positive probability mass.",
            )
        )
        checks.extend(
            validate_game_family(
                state.game,
                subject=f"{subject}:state:{state.state_id}",
            )
        )
    checks.extend(
        validate_game_family(game.expected_game(), subject=f"{subject}:expected")
    )
    return tuple(checks)


def _risk_profile(scenario: CanonicalScenario) -> Profile:
    first, second = scenario.actions
    if scenario.family in {"prisoners_dilemma", "chicken"}:
        return second, second
    return first, second


def _catalog_semantic_checks(
    scenario: CanonicalScenario, uncertain: UncertainPayoffGame
) -> tuple[ValidationCheck, ...]:
    """Validate scenario-specific claims layered on the canonical family."""
    subject = f"scenario:{scenario.scenario_id}"
    checks: list[ValidationCheck] = []
    first, second = scenario.actions
    expected_catastrophes: set[Profile]
    if scenario.family == "prisoners_dilemma":
        expected_catastrophes = set()
    elif scenario.family == "chicken":
        expected_catastrophes = {(second, second)}
    else:
        expected_catastrophes = set(scenario.game().miscoordination_profiles)
    checks.append(
        _structural_check(
            subject,
            "canonical_catastrophe_semantics",
            "catastrophic profiles match the scenario's declared failure mode",
            set(scenario.game().catastrophic_profiles) == expected_catastrophes,
            {
                "actual": _profiles(scenario.game().catastrophic_profiles),
                "expected": _profiles(expected_catastrophes),
            },
            "Catastrophe labels must follow the scenario narrative rather than action names alone.",
            category="scenario_semantics",
        )
    )
    if scenario.family == "stag_hunt":
        values = _symmetric_values(scenario.game(), "row")
        checks.append(
            _numeric_check(
                subject,
                "scenario_semantics",
                "safe_equilibrium_risk_dominant",
                "P-S",
                values["P"] - values["S"],
                ">",
                "R-T",
                values["R"] - values["T"],
                "The scenario describes local lockdown as the risk-dominant fallback.",
            )
        )
    if scenario.family == "battle_of_the_sexes":
        threshold = scenario.parameters.preferred_action_belief_threshold()
        checks.extend(
            (
                _numeric_check(
                    subject,
                    "threshold_sanity",
                    "preferred_belief_threshold_positive",
                    "preferred_action_belief_threshold",
                    threshold,
                    ">",
                    "zero",
                    0.0,
                    "A non-degenerate mixed equilibrium requires an interior threshold.",
                ),
                _numeric_check(
                    subject,
                    "threshold_sanity",
                    "preferred_belief_threshold_below_half",
                    "one_half",
                    0.5,
                    ">",
                    "preferred_action_belief_threshold",
                    threshold,
                    "The preferred outcome's larger payoff should lower the belief needed to insist on it.",
                ),
            )
        )

    probabilities = [state.probability for state in uncertain.states]
    for index, (earlier, later) in enumerate(
        zip(probabilities, probabilities[1:])
    ):
        checks.append(
            _numeric_check(
                subject,
                "uncertainty_ordering",
                f"severity_probability_nonincreasing_{index}",
                f"state_{index}.probability",
                earlier,
                ">=",
                f"state_{index + 1}.probability",
                later,
                "The catalog orders states from more common/less severe to rarer/more severe.",
            )
        )

    risk_profile = _risk_profile(scenario)
    risk_payoffs = [
        min(state.game.payoff(risk_profile).row, state.game.payoff(risk_profile).column)
        for state in uncertain.states
    ]
    for index, (earlier, later) in enumerate(
        zip(risk_payoffs, risk_payoffs[1:])
    ):
        checks.append(
            _numeric_check(
                subject,
                "uncertainty_ordering",
                f"severity_loss_strictly_worsens_{index}",
                f"state_{index}.failure_payoff",
                earlier,
                ">",
                f"state_{index + 1}.failure_payoff",
                later,
                "The designated failure outcome must become strictly worse with latent severity.",
            )
        )

    catastrophe_markers = [
        float(risk_profile in state.game.catastrophic_profiles)
        for state in uncertain.states
    ]
    for index, (earlier, later) in enumerate(
        zip(catastrophe_markers, catastrophe_markers[1:])
    ):
        checks.append(
            _numeric_check(
                subject,
                "uncertainty_ordering",
                f"catastrophe_marker_nondecreasing_{index}",
                f"state_{index + 1}.catastrophic",
                later,
                ">=",
                f"state_{index}.catastrophic",
                earlier,
                "More severe states cannot remove the catalog's designated catastrophe label.",
            )
        )
    return tuple(checks)


def audit_research_catalog() -> CatalogValidationReport:
    """Audit every built-in deterministic and uncertain research test case."""
    checks: list[ValidationCheck] = []
    checks.append(
        _structural_check(
            "catalog",
            "one_scenario_per_supported_family",
            "registered families = four supported canonical families",
            {scenario.family for scenario in SCENARIOS.values()}
            == {
                "prisoners_dilemma",
                "chicken",
                "stag_hunt",
                "battle_of_the_sexes",
            },
            {"families": sorted(scenario.family for scenario in SCENARIOS.values())},
            "The Phase 1 catalog should exercise every implemented strategic family.",
            category="catalog_integrity",
        )
    )
    for scenario_id, scenario in sorted(SCENARIOS.items()):
        checks.extend(
            validate_game_family(
                scenario.game(), subject=f"scenario:{scenario_id}:canonical"
            )
        )
        uncertain = uncertain_scenario_from_id(scenario_id)
        checks.extend(
            validate_uncertain_game(
                uncertain, subject=f"scenario:{scenario_id}:uncertain"
            )
        )
        checks.extend(_catalog_semantic_checks(scenario, uncertain))
    return CatalogValidationReport(tuple(checks))
