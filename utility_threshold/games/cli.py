"""Command-line experiments for the implemented canonical games."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .base import format_payoff_matrix
from .beliefs import ActionBelief
from .decision import (
    CARACriterion,
    ExpectedValueCriterion,
    LowerCVaRCriterion,
    MaximinCriterion,
    MeanVarianceCriterion,
    ProspectValueCriterion,
    StateActionBelief,
    analyze_decision,
)
from .institutional_simulation import (
    FixedInstitutionalStrategy,
    InstitutionalRules,
    RiskAwareInstitutionalStrategy,
    play_institutional_match,
)
from .institutions import MechanismStack, NonBindingCommunication, TrustedMediator
from .mechanisms import BindingCommitment, ContractPenalty
from .scenarios import SCENARIOS, ScenarioThresholdReport, scenario_from_id
from .simulation import default_strategies, play_match, round_robin, threshold_sweep
from .thresholds import InterventionPolicy
from .treatments import treatment_design, treatment_subsidy
from .uncertain_scenarios import uncertain_scenario_from_id


def _report_record(report: ScenarioThresholdReport) -> dict[str, object]:
    return report.record()


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

    uncertain = subparsers.add_parser(
        "uncertain", help="analyze a player decision over latent payoff states"
    )
    uncertain.add_argument("--scenario", choices=sorted(SCENARIOS), default="frontier_deployment_race")
    uncertain.add_argument("--intervention", type=float, default=0.0)
    uncertain.add_argument("--player", choices=("row", "column"), default="row")
    uncertain.add_argument("--opponent-competitive-probability", type=float, default=0.5)
    uncertain.add_argument(
        "--risk-criterion",
        choices=("expected", "mean_variance", "cara", "cvar", "maximin", "prospect"),
        default="expected",
    )
    uncertain.add_argument("--risk-aversion", type=float, default=0.2)
    uncertain.add_argument("--tail-probability", type=float, default=0.1)

    institutional = subparsers.add_parser(
        "institutional-match",
        help="run latent-state repeated play with realized mechanisms and monitoring",
    )
    institutional.add_argument("--scenario", choices=sorted(SCENARIOS), default="frontier_deployment_race")
    institutional.add_argument("--intervention", type=float, default=0.0)
    institutional.add_argument(
        "--mechanism",
        action="append",
        choices=("communication", "commitment", "contract", "side_payment", "mediator"),
        default=[],
        help="repeat to compose treatments in the supplied order",
    )
    institutional.add_argument(
        "--row", choices=("risk_aware", "cooperative", "competitive"), default="risk_aware"
    )
    institutional.add_argument(
        "--column", choices=("risk_aware", "cooperative", "competitive"), default="risk_aware"
    )
    institutional.add_argument(
        "--risk-criterion",
        choices=("expected", "mean_variance", "cara", "cvar", "maximin", "prospect"),
        default="expected",
    )
    institutional.add_argument("--risk-aversion", type=float, default=0.2)
    institutional.add_argument("--tail-probability", type=float, default=0.1)
    institutional.add_argument("--contract-penalty", type=float, default=4.0)
    institutional.add_argument("--detection-probability", type=float, default=0.85)
    institutional.add_argument("--false-positive-probability", type=float, default=0.05)
    institutional.add_argument("--enforcement-probability", type=float, default=0.9)
    institutional.add_argument("--side-payment", type=float, default=2.0)
    institutional.add_argument("--communication-credibility", type=float, default=0.8)
    institutional.add_argument("--monitoring-true-positive-rate", type=float, default=0.85)
    institutional.add_argument("--monitoring-false-positive-rate", type=float, default=0.1)
    institutional.add_argument("--rounds", type=int, default=100)
    institutional.add_argument("--seed", type=int, default=0)
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


def _risk_criterion(args: argparse.Namespace):
    if args.risk_criterion == "expected":
        return ExpectedValueCriterion()
    if args.risk_criterion == "mean_variance":
        return MeanVarianceCriterion(args.risk_aversion)
    if args.risk_criterion == "cara":
        return CARACriterion(args.risk_aversion)
    if args.risk_criterion == "cvar":
        return LowerCVaRCriterion(args.tail_probability)
    if args.risk_criterion == "maximin":
        return MaximinCriterion()
    return ProspectValueCriterion(loss_aversion=max(args.risk_aversion, 1e-9))


def _institutional_strategy(name: str, criterion):
    if name == "risk_aware":
        return RiskAwareInstitutionalStrategy(criterion=criterion)
    return FixedInstitutionalStrategy(name)


def _mechanism_stack(args: argparse.Namespace, game):
    design = treatment_design(game)
    target = design.target_profile
    payoff_mechanisms = []
    communication = None
    mediator = None
    for mechanism in args.mechanism:
        if mechanism == "communication":
            communication = NonBindingCommunication(
                target[0],
                target[1],
                row_credibility=args.communication_credibility,
                column_credibility=args.communication_credibility,
            )
        elif mechanism == "commitment":
            payoff_mechanisms.append(BindingCommitment(target[0], target[1]))
        elif mechanism == "contract":
            payoff_mechanisms.append(
                ContractPenalty(
                    target,
                    penalty=args.contract_penalty,
                    deviation_detection_probability=args.detection_probability,
                    false_positive_probability=args.false_positive_probability,
                    enforcement_probability=args.enforcement_probability,
                )
            )
        elif mechanism == "side_payment":
            payoff_mechanisms.append(treatment_subsidy(game.expected_game(), args.side_payment))
        elif mechanism == "mediator":
            mediator = TrustedMediator(
                design.mediator_distribution,
                objective=design.mediator_objective,
            )
    return MechanismStack(tuple(payoff_mechanisms), communication, mediator)


def run_command(args: argparse.Namespace) -> dict[str, object]:
    scenario = scenario_from_id(args.scenario)
    if args.command == "uncertain":
        uncertain_game = uncertain_scenario_from_id(
            args.scenario, intervention=args.intervention
        )
        opponent_belief = ActionBelief.binary(
            uncertain_game.cooperative_action,
            uncertain_game.competitive_action,
            args.opponent_competitive_probability,
        )
        joint_belief = StateActionBelief.independent(uncertain_game, opponent_belief)
        analysis = analyze_decision(
            uncertain_game,
            args.player,
            opponent_belief,
            _risk_criterion(args),
            joint_belief=joint_belief,
        )
        return {
            "scenario": scenario.record(),
            "uncertain_game": uncertain_game.record(),
            "decision_analysis": analysis.record(),
        }
    if args.command == "institutional-match":
        uncertain_game = uncertain_scenario_from_id(
            args.scenario, intervention=args.intervention
        )
        criterion = _risk_criterion(args)
        stack = _mechanism_stack(args, uncertain_game)
        rules = InstitutionalRules(
            stack=stack,
            monitoring_true_positive_rate=args.monitoring_true_positive_rate,
            monitoring_false_positive_rate=args.monitoring_false_positive_rate,
        )
        result = play_institutional_match(
            uncertain_game,
            _institutional_strategy(args.row, criterion),
            _institutional_strategy(args.column, criterion),
            rules=rules,
            rounds=args.rounds,
            seed=args.seed,
            row_name=args.row,
            column_name=args.column,
        )
        return {
            "scenario": scenario.record(),
            "uncertain_game": uncertain_game.record(),
            "institutional_match": result.record(),
        }
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
