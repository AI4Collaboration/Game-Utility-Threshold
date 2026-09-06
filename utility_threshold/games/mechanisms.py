"""Executable mechanism design for constraints, penalties, and transfers."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from types import MappingProxyType
from typing import Mapping, Protocol

from .base import Payoff, Player, Profile, SymmetricTwoByTwoGame


@dataclass(frozen=True)
class MechanismApplication:
    """A game after zero or more mechanisms, including a complete audit trail.

    Mechanisms may break symmetry or restrict an action, so adjusted payoffs and
    permitted actions live here rather than being forced back into the symmetric
    base-game class.
    """

    base_game: SymmetricTwoByTwoGame
    payoffs: Mapping[Profile, Payoff]
    permitted_actions: Mapping[Player, tuple[str, ...]]
    mechanism_trace: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if set(self.payoffs) != set(self.base_game.profiles):
            raise ValueError("mechanism payoffs must cover every base-game profile")
        if set(self.permitted_actions) != {"row", "column"}:
            raise ValueError("permitted_actions must specify row and column")
        for player, actions in self.permitted_actions.items():
            if not actions or not set(actions) <= set(self.base_game.actions):
                raise ValueError(f"{player} must retain at least one valid action")
        object.__setattr__(self, "payoffs", MappingProxyType(dict(self.payoffs)))
        object.__setattr__(
            self,
            "permitted_actions",
            MappingProxyType({player: tuple(actions) for player, actions in self.permitted_actions.items()}),
        )
        object.__setattr__(
            self,
            "mechanism_trace",
            tuple(MappingProxyType(dict(entry)) for entry in self.mechanism_trace),
        )

    @classmethod
    def baseline(cls, game: SymmetricTwoByTwoGame) -> MechanismApplication:
        return cls(
            base_game=game,
            payoffs=game.payoffs,
            permitted_actions={"row": game.actions, "column": game.actions},
            mechanism_trace=(),
        )

    @property
    def actions(self) -> tuple[str, str]:
        return self.base_game.actions

    @property
    def cooperative_action(self) -> str:
        return self.base_game.cooperative_action

    @property
    def competitive_action(self) -> str:
        return self.base_game.competitive_action

    @property
    def allowed_profiles(self) -> tuple[Profile, ...]:
        return tuple(
            profile
            for profile in self.base_game.profiles
            if profile[0] in self.permitted_actions["row"]
            and profile[1] in self.permitted_actions["column"]
        )

    def payoff(self, profile: Profile) -> Payoff:
        try:
            return self.payoffs[profile]
        except KeyError as exc:
            raise ValueError(f"unknown profile {profile!r}") from exc

    def utility(self, player: Player, own_action: str, opponent_action: str) -> float:
        profile = (own_action, opponent_action) if player == "row" else (opponent_action, own_action)
        payoff = self.payoff(profile)
        return payoff.row if player == "row" else payoff.column

    def best_responses(self, player: Player, opponent_action: str, tolerance: float = 1e-9) -> tuple[str, ...]:
        if opponent_action not in self.permitted_actions["column" if player == "row" else "row"]:
            raise ValueError("opponent action is not permitted by the mechanism")
        values = {
            action: self.utility(player, action, opponent_action)
            for action in self.permitted_actions[player]
        }
        best = max(values.values())
        return tuple(action for action, value in values.items() if value >= best - tolerance)

    def is_nash(self, profile: Profile, tolerance: float = 1e-9) -> bool:
        if profile not in self.allowed_profiles:
            return False
        return (
            profile[0] in self.best_responses("row", profile[1], tolerance)
            and profile[1] in self.best_responses("column", profile[0], tolerance)
        )

    def pure_nash_equilibria(self, tolerance: float = 1e-9) -> tuple[Profile, ...]:
        return tuple(profile for profile in self.allowed_profiles if self.is_nash(profile, tolerance))

    def outcome_records(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for profile in self.base_game.profiles:
            base = self.base_game.payoff(profile)
            adjusted = self.payoff(profile)
            records.append({
                "profile": profile,
                "permitted": profile in self.allowed_profiles,
                "base_payoff": {"row": base.row, "column": base.column},
                "adjusted_payoff": {"row": adjusted.row, "column": adjusted.column},
                "payoff_delta": {
                    "row": adjusted.row - base.row,
                    "column": adjusted.column - base.column,
                },
                "catastrophic": profile in self.base_game.catastrophic_profiles,
            })
        return records

    def record(self) -> dict[str, object]:
        return {
            "base_game_id": self.base_game.game_id,
            "actions": self.actions,
            "permitted_actions": dict(self.permitted_actions),
            "allowed_profiles": self.allowed_profiles,
            "pure_nash_equilibria": self.pure_nash_equilibria(),
            "mechanism_trace": [dict(entry) for entry in self.mechanism_trace],
            "outcomes": self.outcome_records(),
        }


MechanismInput = SymmetricTwoByTwoGame | MechanismApplication


def as_application(game: MechanismInput) -> MechanismApplication:
    return game if isinstance(game, MechanismApplication) else MechanismApplication.baseline(game)


class Mechanism(Protocol):
    mechanism_id: str

    def apply(self, game: MechanismInput) -> MechanismApplication: ...


def _with_adjustments(
    source: MechanismInput,
    adjustments: Mapping[Profile, Payoff],
    trace: Mapping[str, object],
    *,
    permitted_actions: Mapping[Player, tuple[str, ...]] | None = None,
) -> MechanismApplication:
    application = as_application(source)
    if set(adjustments) != set(application.base_game.profiles):
        raise ValueError("adjustments must cover every profile")
    return MechanismApplication(
        base_game=application.base_game,
        payoffs={
            profile: Payoff(
                application.payoff(profile).row + adjustments[profile].row,
                application.payoff(profile).column + adjustments[profile].column,
            )
            for profile in application.base_game.profiles
        },
        permitted_actions=permitted_actions or application.permitted_actions,
        mechanism_trace=application.mechanism_trace + (trace,),
    )


@dataclass(frozen=True)
class BindingCommitment:
    """Remove actions that conflict with a binding pre-play commitment."""

    row_action: str | None = None
    column_action: str | None = None
    mechanism_id: str = "binding_commitment"

    def apply(self, game: MechanismInput) -> MechanismApplication:
        application = as_application(game)
        commitments: dict[Player, str | None] = {"row": self.row_action, "column": self.column_action}
        permitted: dict[Player, tuple[str, ...]] = {}
        for player, commitment in commitments.items():
            if commitment is not None:
                if commitment not in application.permitted_actions[player]:
                    raise ValueError(f"committed action {commitment!r} is unavailable to {player}")
                permitted[player] = (commitment,)
            else:
                permitted[player] = application.permitted_actions[player]
        zero = {profile: Payoff(0.0, 0.0) for profile in application.base_game.profiles}
        return _with_adjustments(
            application,
            zero,
            {
                "mechanism_id": self.mechanism_id,
                "row_commitment": self.row_action,
                "column_commitment": self.column_action,
                "effect": "actions inconsistent with a commitment are removed",
            },
            permitted_actions=permitted,
        )


@dataclass(frozen=True)
class ContractPenalty:
    """Expected penalties for detected and enforced deviations from an agreed profile."""

    agreed_profile: Profile
    penalty: float
    deviation_detection_probability: float = 1.0
    false_positive_probability: float = 0.0
    enforcement_probability: float = 1.0
    mechanism_id: str = "contract_with_penalties"

    def __post_init__(self) -> None:
        if self.penalty < 0:
            raise ValueError("penalty must be non-negative")
        for name, value in (
            ("deviation_detection_probability", self.deviation_detection_probability),
            ("false_positive_probability", self.false_positive_probability),
            ("enforcement_probability", self.enforcement_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")

    @property
    def expected_deviation_penalty(self) -> float:
        return self.penalty * self.deviation_detection_probability * self.enforcement_probability

    @property
    def expected_false_positive_penalty(self) -> float:
        return self.penalty * self.false_positive_probability * self.enforcement_probability

    def apply(self, game: MechanismInput) -> MechanismApplication:
        application = as_application(game)
        if self.agreed_profile not in application.allowed_profiles:
            raise ValueError("agreed profile must be allowed by prior mechanisms")
        adjustments: dict[Profile, Payoff] = {}
        for profile in application.base_game.profiles:
            row_deviates = profile[0] != self.agreed_profile[0]
            column_deviates = profile[1] != self.agreed_profile[1]
            adjustments[profile] = Payoff(
                -(self.expected_deviation_penalty if row_deviates else self.expected_false_positive_penalty),
                -(self.expected_deviation_penalty if column_deviates else self.expected_false_positive_penalty),
            )
        return _with_adjustments(application, adjustments, {
            "mechanism_id": self.mechanism_id,
            "agreed_profile": self.agreed_profile,
            "penalty": self.penalty,
            "deviation_detection_probability": self.deviation_detection_probability,
            "false_positive_probability": self.false_positive_probability,
            "enforcement_probability": self.enforcement_probability,
            "expected_deviation_penalty": self.expected_deviation_penalty,
            "expected_false_positive_penalty": self.expected_false_positive_penalty,
        })


@dataclass(frozen=True)
class SidePaymentMechanism:
    """Profile-contingent transfers or externally funded subsidies."""

    transfers: Mapping[Profile, Payoff]
    require_budget_balance: bool = True
    mechanism_id: str = "side_payments"

    def apply(self, game: MechanismInput) -> MechanismApplication:
        application = as_application(game)
        if set(self.transfers) != set(application.base_game.profiles):
            raise ValueError("transfers must cover every profile")
        if self.require_budget_balance:
            for profile, transfer in self.transfers.items():
                if not isclose(transfer.row + transfer.column, 0.0, abs_tol=1e-9):
                    raise ValueError(f"transfers at {profile!r} are not budget balanced")
        transfers = {profile: Payoff(value.row, value.column) for profile, value in self.transfers.items()}
        external_budget = {
            profile: transfers[profile].row + transfers[profile].column
            for profile in application.base_game.profiles
        }
        return _with_adjustments(application, transfers, {
            "mechanism_id": self.mechanism_id,
            "require_budget_balance": self.require_budget_balance,
            "transfers": [
                {
                    "profile": profile,
                    "row_transfer": transfers[profile].row,
                    "column_transfer": transfers[profile].column,
                    "external_budget": external_budget[profile],
                }
                for profile in application.base_game.profiles
            ],
        })


def zero_transfers(game: SymmetricTwoByTwoGame) -> dict[Profile, Payoff]:
    return {profile: Payoff(0.0, 0.0) for profile in game.profiles}


def exploitation_transfer(game: SymmetricTwoByTwoGame, amount: float) -> SidePaymentMechanism:
    """Make a competitive player compensate a cooperative player off diagonal."""
    if amount < 0:
        raise ValueError("transfer amount must be non-negative")
    cooperative = game.cooperative_action
    competitive = game.competitive_action
    transfers = zero_transfers(game)
    transfers[(cooperative, competitive)] = Payoff(amount, -amount)
    transfers[(competitive, cooperative)] = Payoff(-amount, amount)
    return SidePaymentMechanism(transfers, require_budget_balance=True)


def cooperation_subsidy(game: SymmetricTwoByTwoGame, amount: float) -> SidePaymentMechanism:
    """Externally fund each cooperative action by ``amount`` at every profile."""
    if amount < 0:
        raise ValueError("subsidy amount must be non-negative")
    transfers = {
        profile: Payoff(
            amount if profile[0] == game.cooperative_action else 0.0,
            amount if profile[1] == game.cooperative_action else 0.0,
        )
        for profile in game.profiles
    }
    return SidePaymentMechanism(transfers, require_budget_balance=False, mechanism_id="cooperation_subsidy")
