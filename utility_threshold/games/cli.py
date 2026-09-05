"""Command-line experiments for the implemented canonical games."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .base import format_payoff_matrix
from .scenarios import SCENARIOS, scenario_from_id
from .simulation import default_strategies, play_match, round_robin, threshold_sweep
from .thresholds import InterventionPolicy, UtilityThresholdReport


def _report_record(report: UtilityThresholdReport) -> dict[str, object]:
    return {
        "game_id": report.game_id,
        "family": report.family,
        "intervention": report.intervention,
        "threshold_against_cooperation": report.threshold_against_cooperation,
        "threshold_against_competition": report.threshold_against_competition,
        "minimum_intervention_for_cooperation_dominance": report.minimum_intervention_for_cooperation_dominance,
        "cooperation_margin_against_cooperation": report.cooperation_margin_against_cooperation,
        "cooperation_margin_against_competition": report.cooperation_margin_against_competition,
        "regime": report.regime,
        "pure_nash_equilibria": report.pure_nash_equilibria,
        "symmetric_mixed_equilibrium": dict(report.symmetric_mixed_equilibrium) if report.symmetric_mixed_equilibrium else None,
        "symmetric_catastrophe_probability": report.symmetric_catastrophe_probability,
    }


def _add_game_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="frontier_deployment_race")
    parser.add_argument("--intervention", type=float, default=0.0, help="additional direct competitive-action cost")
    parser.add_argument("--direct-cost", type=float, default=0.0)
    parser.add_argument("--detection-probability", type=float, default=0.0)
    parser.add_argument("--sanction", type=float, default=0.0)
    parser.add_argument("--internalized-harm", type=float, default=0.0)


def _policy_from_args(args: argparse.Namespace) -> InterventionPolicy:
    return InterventionPolicy(
        direct_cost=args.intervention + args.direct_cost,
        detection_probability=args.detection_probability,
        sanction=args.sanction,
        internalized_harm=args.internalized_harm,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run complete utility-threshold game experiments")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="show matrix, equilibria, welfare, and threshold regime")
    _add_game_arguments(analyze)

    sweep = subparsers.add_parser("sweep", help="sweep the intervention through strategic regime changes")
    sweep.add_argument("--scenario", choices=sorted(SCENARIOS), default="frontier_deployment_race")
    sweep.add_argument("--start", type=float, default=0.0)
    sweep.add_argument("--stop", type=float, default=5.0)
    sweep.add_argument("--step", type=float, default=0.25)

    match = subparsers.add_parser("match", help="run one repeated match")
    _add_game_arguments(match)
    match.add_argument("--row", choices=sorted(default_strategies()), default="tit_for_tat")
    match.add_argument("--column", choices=sorted(default_strategies()), default="competitive")
    match.add_argument("--rounds", type=int, default=100)
    match.add_argument("--seed", type=int, default=0)

    tournament = subparsers.add_parser("tournament", help="run all built-in strategies against each other")
    _add_game_arguments(tournament)
    tournament.add_argument("--rounds", type=int, default=100)
    tournament.add_argument("--seed", type=int, default=0)
    return parser


def _float_range(start: float, stop: float, step: float) -> list[float]:
    if step <= 0:
        raise ValueError("step must be positive")
    if stop < start:
        raise ValueError("stop must be at least start")
    values: list[float] = []
    index = 0
    while start + index * step <= stop + 1e-12:
        values.append(round(start + index * step, 12))
        index += 1
    return values


def run_command(args: argparse.Namespace) -> dict[str, object]:
    scenario = scenario_from_id(args.scenario)
    if args.command == "analyze":
        policy = _policy_from_args(args)
        game = scenario.game(policy)
        return {
            "scenario": scenario.record(),
            "intervention_policy": policy.record(),
            "payoff_matrix": game.matrix_records(),
            "matrix_text": format_payoff_matrix(game),
            "threshold": _report_record(scenario.threshold_report(policy)),
            "pareto_efficient_profiles": game.pareto_efficient_profiles(),
            "utilitarian_optima": game.welfare_optimal_profiles("utilitarian"),
            "egalitarian_optima": game.welfare_optimal_profiles("egalitarian"),
        }
    if args.command == "sweep":
        points = threshold_sweep(scenario, _float_range(args.start, args.stop, args.step))
        return {
            "scenario": scenario.record(),
            "points": [
                {
                    "intervention": point.intervention,
                    "report": _report_record(point.report),
                    "equilibrium_welfare": point.equilibrium_welfare,
                }
                for point in points
            ],
        }
    strategies = default_strategies()
    policy = _policy_from_args(args)
    game = scenario.game(policy)
    if args.command == "match":
        result = play_match(
            game,
            strategies[args.row],
            strategies[args.column],
            rounds=args.rounds,
            seed=args.seed,
            row_name=args.row,
            column_name=args.column,
        )
        return {"scenario": scenario.record(), "intervention_policy": policy.record(), "match": result.record()}
    if args.command == "tournament":
        result = round_robin(game, strategies, rounds=args.rounds, seed=args.seed)
        return {
            "scenario": scenario.record(),
            "intervention_policy": policy.record(),
            "match_count": len(result.matches),
            "leaderboard": result.leaderboard(),
            "matches": [match.record() for match in result.matches],
        }
    raise ValueError(f"unknown command {args.command!r}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_command(args)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
