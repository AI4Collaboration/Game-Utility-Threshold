"""Repeated play, agent strategies, tournaments, and threshold sweeps."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import exp
from random import Random
from typing import Mapping, Protocol

from .base import Player, Profile, TwoByTwoGame
from .scenarios import CanonicalScenario, ScenarioThresholdReport


@dataclass(frozen=True)
class RoundResult:
    round_index: int
    row_action: str
    column_action: str
    row_utility: float
    column_utility: float
    utilitarian_welfare: float
    row_regret: float
    column_regret: float
    is_nash: bool
    pareto_efficient: bool
    catastrophic: bool

    @property
    def profile(self) -> Profile:
        return (self.row_action, self.column_action)


@dataclass(frozen=True)
class RoundContext:
    game: TwoByTwoGame
    player: Player
    round_index: int
    history: tuple[RoundResult, ...]


class GameStrategy(Protocol):
    def choose(self, context: RoundContext, rng: Random) -> str: ...


class CooperativeStrategy:
    def choose(self, context: RoundContext, rng: Random) -> str:
        _ = rng
        return context.game.cooperative_action


class CompetitiveStrategy:
    def choose(self, context: RoundContext, rng: Random) -> str:
        _ = rng
        return context.game.competitive_action


@dataclass(frozen=True)
class RandomStrategy:
    competitive_probability: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.competitive_probability <= 1.0:
            raise ValueError("competitive_probability must be between zero and one")

    def choose(self, context: RoundContext, rng: Random) -> str:
        if rng.random() < self.competitive_probability:
            return context.game.competitive_action
        return context.game.cooperative_action


@dataclass(frozen=True)
class ExpectedUtilityStrategy:
    """Best respond to a fixed belief about the opponent's competitive action."""

    opponent_competitive_probability: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.opponent_competitive_probability <= 1.0:
            raise ValueError("opponent_competitive_probability must be between zero and one")

    def choose(self, context: RoundContext, rng: Random) -> str:
        _ = rng
        game = context.game
        belief = {
            game.cooperative_action: 1.0 - self.opponent_competitive_probability,
            game.competitive_action: self.opponent_competitive_probability,
        }
        values = {
            action: sum(
                probability * game.utility(context.player, action, opponent_action)
                for opponent_action, probability in belief.items()
            )
            for action in game.actions
        }
        # Favor the cooperative action at exact indifference; the tie-break is
        # explicit and stable across runs.
        if values[game.cooperative_action] >= values[game.competitive_action]:
            return game.cooperative_action
        return game.competitive_action


@dataclass(frozen=True)
class QuantalResponseStrategy:
    """A soft best response that exposes bounded-rationality temperature."""

    opponent_competitive_probability: float = 0.5
    beta: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.opponent_competitive_probability <= 1.0:
            raise ValueError("opponent_competitive_probability must be between zero and one")
        if self.beta <= 0:
            raise ValueError("beta must be positive")

    def choose(self, context: RoundContext, rng: Random) -> str:
        game = context.game
        probability_competitive = self.opponent_competitive_probability
        belief = {
            game.cooperative_action: 1.0 - probability_competitive,
            game.competitive_action: probability_competitive,
        }
        values = {
            action: sum(
                probability * game.utility(context.player, action, opponent_action)
                for opponent_action, probability in belief.items()
            )
            for action in game.actions
        }
        maximum = max(values.values())
        weights = {action: exp(self.beta * (value - maximum)) for action, value in values.items()}
        cooperative_probability = weights[game.cooperative_action] / sum(weights.values())
        return game.cooperative_action if rng.random() < cooperative_probability else game.competitive_action


class MixedNashStrategy:
    """Play the player's role-specific mixed equilibrium, with a rational fallback."""

    def choose(self, context: RoundContext, rng: Random) -> str:
        game = context.game
        equilibrium = game.mixed_equilibrium()
        mixed = equilibrium[context.player] if equilibrium is not None else None
        if mixed is not None:
            return game.actions[0] if rng.random() < mixed[game.actions[0]] else game.actions[1]
        dominant = game.dominant_actions(context.player)
        if len(dominant) == 1:
            return dominant[0]
        return ExpectedUtilityStrategy().choose(context, rng)


class TitForTatStrategy:
    """Cooperate first, then copy the opponent's previous action."""

    def choose(self, context: RoundContext, rng: Random) -> str:
        _ = rng
        if not context.history:
            return context.game.cooperative_action
        previous = context.history[-1]
        return previous.column_action if context.player == "row" else previous.row_action


class GrimTriggerStrategy:
    """Cooperate until any observed competitive action, then compete forever."""

    def choose(self, context: RoundContext, rng: Random) -> str:
        _ = rng
        for result in context.history:
            opponent_action = result.column_action if context.player == "row" else result.row_action
            if opponent_action == context.game.competitive_action:
                return context.game.competitive_action
        return context.game.cooperative_action


@dataclass(frozen=True)
class MatchResult:
    game_id: str
    row_strategy: str
    column_strategy: str
    rounds: tuple[RoundResult, ...]

    @property
    def row_total_utility(self) -> float:
        return sum(result.row_utility for result in self.rounds)

    @property
    def column_total_utility(self) -> float:
        return sum(result.column_utility for result in self.rounds)

    @property
    def mean_welfare(self) -> float:
        return sum(result.utilitarian_welfare for result in self.rounds) / len(self.rounds)

    @property
    def catastrophe_rate(self) -> float:
        return sum(result.catastrophic for result in self.rounds) / len(self.rounds)

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "row_strategy": self.row_strategy,
            "column_strategy": self.column_strategy,
            "round_count": len(self.rounds),
            "row_total_utility": self.row_total_utility,
            "column_total_utility": self.column_total_utility,
            "mean_welfare": self.mean_welfare,
            "catastrophe_rate": self.catastrophe_rate,
            "rounds": [asdict(result) for result in self.rounds],
        }


def play_match(
    game: TwoByTwoGame,
    row_strategy: GameStrategy,
    column_strategy: GameStrategy,
    *,
    rounds: int = 100,
    seed: int = 0,
    row_name: str | None = None,
    column_name: str | None = None,
) -> MatchResult:
    if rounds <= 0:
        raise ValueError("rounds must be positive")
    rng = Random(seed)
    history: list[RoundResult] = []
    pareto = set(game.pareto_efficient_profiles())
    for round_index in range(rounds):
        frozen_history = tuple(history)
        row_action = row_strategy.choose(RoundContext(game, "row", round_index, frozen_history), rng)
        column_action = column_strategy.choose(RoundContext(game, "column", round_index, frozen_history), rng)
        if row_action not in game.actions or column_action not in game.actions:
            raise ValueError(f"strategy returned invalid profile {(row_action, column_action)!r}")
        profile = (row_action, column_action)
        payoff = game.payoff(profile)
        history.append(RoundResult(
            round_index=round_index,
            row_action=row_action,
            column_action=column_action,
            row_utility=payoff.row,
            column_utility=payoff.column,
            utilitarian_welfare=payoff.total,
            row_regret=game.regret(profile, "row"),
            column_regret=game.regret(profile, "column"),
            is_nash=game.is_nash(profile),
            pareto_efficient=profile in pareto,
            catastrophic=profile in game.catastrophic_profiles,
        ))
    return MatchResult(
        game_id=game.game_id,
        row_strategy=row_name or type(row_strategy).__name__,
        column_strategy=column_name or type(column_strategy).__name__,
        rounds=tuple(history),
    )


@dataclass(frozen=True)
class TournamentResult:
    game_id: str
    competitive_action: str
    matches: tuple[MatchResult, ...]

    def leaderboard(self) -> tuple[dict[str, float | str], ...]:
        accumulator: dict[str, dict[str, float]] = {}
        for match in self.matches:
            for name, utility, actions in (
                (match.row_strategy, match.row_total_utility, [result.row_action for result in match.rounds]),
                (match.column_strategy, match.column_total_utility, [result.column_action for result in match.rounds]),
            ):
                row = accumulator.setdefault(name, {"utility": 0.0, "rounds": 0.0, "competitive": 0.0, "catastrophes": 0.0})
                row["utility"] += utility
                row["rounds"] += len(match.rounds)
                row["competitive"] += sum(action == self.competitive_action for action in actions)
                row["catastrophes"] += sum(result.catastrophic for result in match.rounds)
        records = []
        for name, totals in accumulator.items():
            rounds = totals["rounds"]
            records.append({
                "strategy": name,
                "mean_utility": totals["utility"] / rounds,
                "competitive_action_rate": totals["competitive"] / rounds,
                "catastrophe_exposure_rate": totals["catastrophes"] / rounds,
            })
        return tuple(sorted(records, key=lambda row: (-float(row["mean_utility"]), str(row["strategy"]))))
def round_robin(
    game: TwoByTwoGame,
    strategies: Mapping[str, GameStrategy],
    *,
    rounds: int = 100,
    seed: int = 0,
) -> TournamentResult:
    """Play every strategy pairing, including self-play, in both role orders."""
    if not strategies:
        raise ValueError("at least one strategy is required")
    matches: list[MatchResult] = []
    names = tuple(strategies)
    for row_index, row_name in enumerate(names):
        for column_index, column_name in enumerate(names):
            matches.append(play_match(
                game,
                strategies[row_name],
                strategies[column_name],
                rounds=rounds,
                seed=seed + row_index * len(names) + column_index,
                row_name=row_name,
                column_name=column_name,
            ))
    return TournamentResult(game.game_id, game.competitive_action, tuple(matches))


@dataclass(frozen=True)
class ThresholdSweepPoint:
    intervention: float
    report: ScenarioThresholdReport
    equilibrium_welfare: tuple[float, ...]


def threshold_sweep(scenario: CanonicalScenario, interventions: list[float] | tuple[float, ...]) -> tuple[ThresholdSweepPoint, ...]:
    points: list[ThresholdSweepPoint] = []
    for intervention in interventions:
        report = scenario.threshold_report(intervention)
        game = scenario.game(intervention)
        points.append(ThresholdSweepPoint(
            intervention=intervention,
            report=report,
            equilibrium_welfare=tuple(game.welfare(profile) for profile in report.pure_nash_equilibria),
        ))
    return tuple(points)


def default_strategies() -> dict[str, GameStrategy]:
    return {
        "cooperative": CooperativeStrategy(),
        "competitive": CompetitiveStrategy(),
        "expected_utility": ExpectedUtilityStrategy(),
        "mixed_nash": MixedNashStrategy(),
        "quantal": QuantalResponseStrategy(),
        "tit_for_tat": TitForTatStrategy(),
        "grim_trigger": GrimTriggerStrategy(),
    }
