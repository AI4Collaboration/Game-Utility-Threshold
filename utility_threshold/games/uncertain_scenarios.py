"""Research-ready latent payoff states for the two concrete AI-safety games."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from .chicken import ChickenParameters, chicken
from .prisoners_dilemma import PrisonersDilemmaParameters, prisoners_dilemma
from .scenarios import AUTONOMOUS_ESCALATION, FRONTIER_DEPLOYMENT_RACE
from .uncertainty import PayoffState, UncertainPayoffGame


def frontier_deployment_uncertainty(*, intervention: float = 0.0) -> UncertainPayoffGame:
    """Unknown commercial upside and safety severity in a deployment race.

    The three states preserve the Prisoner's Dilemma ordering while changing
    the temptation to race and the harm from simultaneous unsafe deployment.
    Only the systemic-failure state classifies mutual racing as catastrophic.
    """

    scenario = FRONTIER_DEPLOYMENT_RACE
    cooperative, competitive = scenario.actions
    specifications = (
        (
            "contained_competition",
            0.55,
            PrisonersDilemmaParameters(temptation=4.5, reward=3.2, punishment=1.2, sucker=0.2),
            "Commercial advantage is modest and duplicated safety failures remain containable.",
            False,
        ),
        (
            "major_safety_failure",
            0.30,
            PrisonersDilemmaParameters(temptation=6.0, reward=3.0, punishment=-2.0, sucker=-3.0),
            "First-mover upside is high and mutual racing causes a major but recoverable failure.",
            False,
        ),
        (
            "systemic_failure",
            0.15,
            PrisonersDilemmaParameters(temptation=8.0, reward=2.0, punishment=-20.0, sucker=-25.0),
            "Unsafe deployment creates cascading systemic harm; mutual racing is catastrophic.",
            True,
        ),
    )
    states: list[PayoffState] = []
    for state_id, probability, parameters, description, catastrophic in specifications:
        game = prisoners_dilemma(
            parameters,
            intervention=intervention,
            actions=scenario.actions,
            game_id=f"{scenario.scenario_id}_{state_id}",
            name=f"{scenario.name}: {state_id.replace('_', ' ').title()}",
            description=description,
        )
        if catastrophic:
            game = replace(game, catastrophic_profiles=frozenset({(competitive, competitive)}))
        states.append(
            PayoffState(
                state_id=state_id,
                probability=probability,
                game=game,
                description=description,
                parameters={
                    "temptation": parameters.temptation,
                    "reward": parameters.reward,
                    "punishment": parameters.punishment,
                    "sucker": parameters.sucker,
                    "intervention": intervention,
                    "mutual_race_catastrophic": float(catastrophic),
                },
            )
        )
    return UncertainPayoffGame(
        game_id=f"{scenario.scenario_id}_uncertain",
        name=f"{scenario.name} with latent severity",
        states=tuple(states),
    )


def autonomous_escalation_uncertainty(*, intervention: float = 0.0) -> UncertainPayoffGame:
    """Unknown crisis severity and escalation-control failure in Chicken."""

    scenario = AUTONOMOUS_ESCALATION
    _, competitive = scenario.actions
    specifications = (
        (
            "contained_crisis",
            0.55,
            ChickenParameters(temptation=5.0, reward=3.2, sucker=1.2, catastrophe=-5.0),
            "Escalation is damaging but existing controls contain the incident.",
            False,
        ),
        (
            "severe_crisis",
            0.30,
            ChickenParameters(temptation=7.0, reward=3.0, sucker=0.0, catastrophe=-30.0),
            "Mutual escalation causes a severe cross-domain incident.",
            True,
        ),
        (
            "runaway_escalation",
            0.15,
            ChickenParameters(temptation=10.0, reward=2.0, sucker=-2.0, catastrophe=-100.0),
            "Automated reactions become uncontrollable and mutual escalation is catastrophic.",
            True,
        ),
    )
    states: list[PayoffState] = []
    for state_id, probability, parameters, description, catastrophic in specifications:
        game = chicken(
            parameters,
            intervention=intervention,
            actions=scenario.actions,
            game_id=f"{scenario.scenario_id}_{state_id}",
            name=f"{scenario.name}: {state_id.replace('_', ' ').title()}",
            description=description,
        )
        if not catastrophic:
            game = replace(game, catastrophic_profiles=frozenset())
        states.append(
            PayoffState(
                state_id=state_id,
                probability=probability,
                game=game,
                description=description,
                parameters={
                    "temptation": parameters.temptation,
                    "reward": parameters.reward,
                    "sucker": parameters.sucker,
                    "catastrophe": parameters.catastrophe,
                    "intervention": intervention,
                    "mutual_escalation_catastrophic": float(catastrophic),
                },
            )
        )
    return UncertainPayoffGame(
        game_id=f"{scenario.scenario_id}_uncertain",
        name=f"{scenario.name} with latent crisis severity",
        states=tuple(states),
    )


UNCERTAIN_SCENARIOS: dict[str, Callable[..., UncertainPayoffGame]] = {
    FRONTIER_DEPLOYMENT_RACE.scenario_id: frontier_deployment_uncertainty,
    AUTONOMOUS_ESCALATION.scenario_id: autonomous_escalation_uncertainty,
}


def uncertain_scenario_from_id(scenario_id: str, *, intervention: float = 0.0) -> UncertainPayoffGame:
    try:
        factory = UNCERTAIN_SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown uncertain scenario {scenario_id!r}; choose from {sorted(UNCERTAIN_SCENARIOS)}"
        ) from exc
    return factory(intervention=intervention)
