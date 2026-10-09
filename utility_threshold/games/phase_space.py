"""The R > P slice of symmetric two-action games, including ordinal ties.

The row payoff matrix is ``[[R, S], [T, P]]`` and the column payoff matrix
is its transpose. A common positive affine transformation sets R=1, P=0,
leaving coordinates s=(S-P)/(R-P), t=(T-P)/(R-P). Negative coordinates are
valid. This slice contains twelve strict payoff orders; it does not include
R=P games. Action names C/D are labels, not welfare assumptions.

Comparisons use exact equality of the supplied floating-point coordinates,
without an implicit tolerance that would turn a strict game into a tie.
Pareto and maximin results below concern pure profiles and pure actions.
Equilibrium summaries enumerate pure Nash equilibria and the isolated fully
mixed symmetric equilibrium, and separately flag boundary continua.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from .base import Payoff, SymmetricTwoByTwoGame

_PROFILES = (("C", "C"), ("C", "D"), ("D", "C"), ("D", "D"))
_LABEL_ORDER = ("R", "T", "P", "S")
_CORE_FAMILIES = {
    "T>R>P>S": "prisoners_dilemma",
    "T>R>S>P": "chicken",
    "R>T>P>S": "stag_hunt",
}


def _finite(name: str, value: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def normalize_payoffs(
    *, reward: float, punishment: float, sucker: float, temptation: float
) -> tuple[float, float]:
    """Return (s, t) under a common positive affine normalization.

    R > P is required. An action swap is not silently applied to R < P, and
    equal diagonal payoffs cannot be represented by this coordinate chart.
    """
    reward = _finite("reward", reward)
    punishment = _finite("punishment", punishment)
    sucker = _finite("sucker", sucker)
    temptation = _finite("temptation", temptation)
    if reward <= punishment:
        raise ValueError("normalization requires reward > punishment (R > P)")
    gap = _finite("reward - punishment", reward - punishment)
    s = _finite("normalized sucker", (sucker - punishment) / gap)
    t = _finite("normalized temptation", (temptation - punishment) / gap)
    return s, t


@dataclass(frozen=True)
class PhasePoint:
    """One normalized game, optionally expressed in original utility units."""

    s: float
    t: float
    reward: float = 1.0
    punishment: float = 0.0

    def __post_init__(self) -> None:
        for name in ("s", "t", "reward", "punishment"):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))
        if self.reward <= self.punishment:
            raise ValueError("PhasePoint requires reward > punishment (R > P)")
        gap = _finite("reward - punishment", self.reward - self.punishment)
        for name, value in (
            ("sucker", self.punishment + self.s * gap),
            ("temptation", self.punishment + self.t * gap),
            ("cooperation margin against C", (1.0 - self.t) * gap),
            ("cooperation margin against D", self.s * gap),
        ):
            _finite(name, value)

    @classmethod
    def from_payoffs(
        cls, *, reward: float, punishment: float, sucker: float, temptation: float
    ) -> PhasePoint:
        """Normalize a game while retaining its original utility scale."""
        s, t = normalize_payoffs(
            reward=reward, punishment=punishment, sucker=sucker, temptation=temptation
        )
        return cls(s, t, reward=reward, punishment=punishment)

    @property
    def R(self) -> float:
        return self.reward

    @property
    def P(self) -> float:
        return self.punishment

    @property
    def S(self) -> float:
        return self.P + self.s * (self.R - self.P)

    @property
    def T(self) -> float:
        return self.P + self.t * (self.R - self.P)

    @property
    def ordinal_groups(self) -> tuple[tuple[str, ...], ...]:
        """Descending payoff groups, with deterministic ordering within ties."""
        values = {"R": 1.0, "P": 0.0, "S": self.s, "T": self.t}
        return tuple(
            tuple(label for label in _LABEL_ORDER if values[label] == value)
            for value in sorted(set(values.values()), reverse=True)
        )

    @property
    def ordinal_order(self) -> str:
        return ">".join("=".join(group) for group in self.ordinal_groups)

    @property
    def family(self) -> str:
        """Name only the three conventional strict orders used by this project."""
        if any(len(group) > 1 for group in self.ordinal_groups):
            return "tie_boundary"
        return _CORE_FAMILIES.get(self.ordinal_order, "other_strict_ordinal")

    @property
    def quadrant(self) -> str:
        """Best-response class; BR ties lie on s=0 or t=1 only."""
        if self.s == 0.0 or self.t == 1.0:
            return "boundary"
        if self.t < 1.0:
            return "cooperation_dominant" if self.s > 0.0 else "coordination"
        return "anti_coordination" if self.s > 0.0 else "competition_dominant"

    @property
    def _normalized_payoffs(self) -> dict[tuple[str, str], tuple[float, float]]:
        return {
            ("C", "C"): (1.0, 1.0),
            ("C", "D"): (self.s, self.t),
            ("D", "C"): (self.t, self.s),
            ("D", "D"): (0.0, 0.0),
        }

    @property
    def pure_nash(self) -> tuple[tuple[str, str], ...]:
        payoffs = self._normalized_payoffs
        opposite = {"C": "D", "D": "C"}
        return tuple(
            (row, column)
            for row, column in _PROFILES
            if payoffs[row, column][0] >= payoffs[opposite[row], column][0]
            and payoffs[row, column][1] >= payoffs[row, opposite[column]][1]
        )

    @property
    def symmetric_mixed_cooperation(self) -> float | None:
        """Isolated interior p(C)=(P-S)/(P-S+R-T), or None.

        A scaled ratio avoids overflow when large margins have opposite signs.
        At s=0,t=1 every symmetric mixture is an equilibrium, so no isolated
        probability is reported. Boundary p=0 or p=1 belongs to pure Nash.
        """
        if self.quadrant not in ("coordination", "anti_coordination"):
            return None
        against_c, against_d = abs(1.0 - self.t), abs(self.s)
        scale = max(against_c, against_d)
        return (against_d / scale) / (against_c / scale + against_d / scale)

    @property
    def degeneracy(self) -> str:
        """Distinguish BR ties with and without non-isolated equilibria."""
        if self.s == 0.0 and self.t == 1.0:
            return "all_strategy_profiles_are_equilibria"
        if self.t == 1.0:
            return (
                "equilibrium_continuum_one_player_C"
                if self.s > 0.0
                else "boundary_indifference_no_continuum"
            )
        if self.s == 0.0:
            return (
                "equilibrium_continuum_one_player_D"
                if self.t > 1.0
                else "boundary_indifference_no_continuum"
            )
        return "none"

    @property
    def equilibrium_continuum(self) -> bool:
        return self.degeneracy in (
            "all_strategy_profiles_are_equilibria",
            "equilibrium_continuum_one_player_C",
            "equilibrium_continuum_one_player_D",
        )

    @property
    def welfare_band(self) -> str:
        """Locate S+T relative to 2P and 2R without overflowing sums."""
        mean = self.s / 2.0 + self.t / 2.0
        if mean < 0.0:
            return "off_diagonal_below_2P"
        if mean == 0.0:
            return "off_diagonal_equals_2P"
        if mean < 1.0:
            return "off_diagonal_between_2P_and_2R"
        if mean == 1.0:
            return "off_diagonal_equals_2R"
        return "off_diagonal_above_2R"

    @property
    def welfare_max_profiles(self) -> tuple[tuple[str, str], ...]:
        mean = self.s / 2.0 + self.t / 2.0
        if mean > 1.0:
            return (("C", "D"), ("D", "C"))
        if mean == 1.0:
            return (("C", "C"), ("C", "D"), ("D", "C"))
        return (("C", "C"),)

    @property
    def pareto_profiles(self) -> tuple[tuple[str, str], ...]:
        """Efficient among the four pure profiles, excluding lotteries."""
        payoffs = self._normalized_payoffs
        return tuple(
            profile
            for profile in _PROFILES
            if not any(
                other[0] >= payoffs[profile][0]
                and other[1] >= payoffs[profile][1]
                and (other[0] > payoffs[profile][0] or other[1] > payoffs[profile][1])
                for other in payoffs.values()
            )
        )

    @property
    def pure_maximin_actions(self) -> tuple[str, ...]:
        """Actions maximizing guaranteed utility; randomization is excluded."""
        guarantees = {"C": min(1.0, self.s), "D": min(self.t, 0.0)}
        best = max(guarantees.values())
        return tuple(action for action, value in guarantees.items() if value == best)

    @property
    def cooperation_margins(self) -> dict[str, float]:
        gap = self.R - self.P
        return {"opponent_C": (1.0 - self.t) * gap, "opponent_D": self.s * gap}

    @property
    def minimum_intervention_for_cooperation_dominance(self) -> float:
        """Uniform cost on D needed for weak C dominance, max(0,T-R,P-S).

        This is an additive own-action intervention in utility units. Equality
        can leave a tie; strict dominance requires both adjusted margins > 0.
        """
        return max(0.0, *(-value for value in self.cooperation_margins.values()))

    def to_game(
        self,
        *,
        actions: tuple[str, str] = ("C", "D"),
        game_id: str = "symmetric_phase_point",
    ) -> SymmetricTwoByTwoGame:
        """Construct the existing normal-form engine's symmetric game."""
        if len(actions) != 2 or len(set(actions)) != 2:
            raise ValueError("actions must contain two distinct labels")
        c, d = actions
        return SymmetricTwoByTwoGame(
            game_id=game_id,
            name=f"Symmetric game {self.ordinal_order}",
            family=self.family,
            actions=actions,
            cooperative_action=c,
            competitive_action=d,
            payoffs={
                (c, c): Payoff(self.R, self.R),
                (c, d): Payoff(self.S, self.T),
                (d, c): Payoff(self.T, self.S),
                (d, d): Payoff(self.P, self.P),
            },
            description="R > P phase-space game; C/D are action labels.",
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible parameters and explicitly scoped diagnostics."""
        return {
            "s": self.s, "t": self.t,
            "R": self.R, "P": self.P, "S": self.S, "T": self.T,
            "actions": ["C", "D"],
            "payoff_matrix": [
                [[self.R, self.R], [self.S, self.T]],
                [[self.T, self.S], [self.P, self.P]],
            ],
            "row_payoff_matrix": [[self.R, self.S], [self.T, self.P]],
            "column_payoff_matrix": [[self.R, self.T], [self.S, self.P]],
            "family": self.family,
            "quadrant": self.quadrant,
            "ordinal_order": self.ordinal_order,
            "ordinal_groups": [list(group) for group in self.ordinal_groups],
            "ties": [list(group) for group in self.ordinal_groups if len(group) > 1],
            "pure_nash": [list(profile) for profile in self.pure_nash],
            "symmetric_mixed_cooperation": self.symmetric_mixed_cooperation,
            "degeneracy": self.degeneracy,
            "equilibrium_continuum": self.equilibrium_continuum,
            "equilibrium_summary_scope": "pure Nash and isolated interior symmetric mixed; continua flagged separately",
            "welfare_max_profiles": [list(profile) for profile in self.welfare_max_profiles],
            "welfare_criterion": "sum_of_player_utilities_over_pure_profiles",
            "welfare_band": self.welfare_band,
            "turn_taking_preferred": self.welfare_band == "off_diagonal_above_2R",
            "pareto_profiles": [list(profile) for profile in self.pareto_profiles],
            "pareto_scope": "pure_profiles_only",
            "pure_maximin_actions": list(self.pure_maximin_actions),
            "cooperation_margins": self.cooperation_margins,
            "normalized_cooperation_margins": {"opponent_C": 1.0 - self.t, "opponent_D": self.s},
            "minimum_intervention_for_cooperation_dominance": self.minimum_intervention_for_cooperation_dominance,
            "normalized_minimum_intervention_for_cooperation_dominance": max(0.0, self.t - 1.0, -self.s),
            "intervention_threshold_scope": "uniform additive cost on D; weak C dominance at threshold",
        }


def build_phase_grid(
    s_values: Iterable[float],
    t_values: Iterable[float],
    *,
    reward: float = 1.0,
    punishment: float = 0.0,
) -> list[PhasePoint]:
    """Return a t-major Cartesian grid, preserving input order and duplicates."""
    s_coordinates = tuple(_finite("s", value) for value in s_values)
    t_coordinates = tuple(_finite("t", value) for value in t_values)
    # Validate anchors even when an axis is empty.
    PhasePoint(0.0, 0.0, reward=reward, punishment=punishment)
    return [
        PhasePoint(s, t, reward=reward, punishment=punishment)
        for t in t_coordinates
        for s in s_coordinates
    ]
