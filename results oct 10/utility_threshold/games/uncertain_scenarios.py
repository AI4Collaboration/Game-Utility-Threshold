"""Research-ready latent payoff states for the concrete AI-safety games."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from .battle_of_the_sexes import BattleOfTheSexesParameters, battle_of_the_sexes
from .chicken import ChickenParameters, chicken
from .prisoners_dilemma import PrisonersDilemmaParameters, prisoners_dilemma
from .scenarios import (
    AUTONOMOUS_ESCALATION,
    CROSS_LAB_INCIDENT_RESPONSE,
    FRONTIER_DEPLOYMENT_RACE,
    INCIDENT_RESPONSE_PROTOCOL,
)
from .stag_hunt import StagHuntParameters, stag_hunt
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


def cross_lab_incident_response_uncertainty(
    *, intervention: float = 0.0
) -> UncertainPayoffGame:
    """Unknown exploit severity and reciprocal readiness in the assurance game."""

    scenario = CROSS_LAB_INCIDENT_RESPONSE
    cooperative, safe = scenario.actions
    specifications = (
        (
            "false_alarm",
            0.45,
            StagHuntParameters(4.0, 3.0, 2.0, 0.5),
            "The alert is containable; unilateral information sharing has limited downside.",
            False,
        ),
        (
            "active_cross_platform_exploit",
            0.35,
            StagHuntParameters(7.0, 4.0, 1.0, -8.0),
            "A live exploit rewards joint containment and punishes an unmatched open response.",
            True,
        ),
        (
            "cascading_ecosystem_compromise",
            0.20,
            StagHuntParameters(12.0, 5.0, -4.0, -40.0),
            "Compromise is cascading; failed unilateral containment creates systemic exposure.",
            True,
        ),
    )
    states: list[PayoffState] = []
    for state_id, probability, parameters, description, catastrophic in specifications:
        game = stag_hunt(
            parameters,
            intervention=intervention,
            actions=scenario.actions,
            game_id=f"{scenario.scenario_id}_{state_id}",
            name=f"{scenario.name}: {state_id.replace('_', ' ').title()}",
            description=description,
        )
        catastrophic_profiles = (
            frozenset({(cooperative, safe), (safe, cooperative)})
            if catastrophic
            else frozenset()
        )
        game = replace(game, catastrophic_profiles=catastrophic_profiles)
        states.append(
            PayoffState(
                state_id,
                probability,
                game,
                description,
                {
                    "mutual_cooperation": parameters.mutual_cooperation,
                    "safe_against_cooperation": parameters.safe_against_cooperation,
                    "mutual_safety": parameters.mutual_safety,
                    "failed_cooperation": parameters.failed_cooperation,
                    "intervention": intervention,
                    "mismatch_catastrophic": float(catastrophic),
                },
            )
        )
    return UncertainPayoffGame(
        game_id=f"{scenario.scenario_id}_uncertain",
        name=f"{scenario.name} with latent exploit severity",
        states=tuple(states),
    )


def incident_response_protocol_uncertainty(
    *, intervention: float = 0.0
) -> UncertainPayoffGame:
    """Unknown incident severity in an asymmetric protocol-selection conflict."""

    scenario = INCIDENT_RESPONSE_PROTOCOL
    specifications = (
        (
            "routine_vulnerability",
            0.50,
            BattleOfTheSexesParameters(4.0, 3.0, -1.0),
            "The vulnerability is routine; a protocol mismatch delays containment.",
            False,
        ),
        (
            "active_exploitation",
            0.35,
            BattleOfTheSexesParameters(7.0, 4.0, -18.0),
            "Active exploitation makes simultaneous incompatible responses catastrophic.",
            True,
        ),
        (
            "cascading_supply_chain_exploit",
            0.15,
            BattleOfTheSexesParameters(12.0, 7.0, -60.0),
            "A supply-chain exploit cascades while the labs execute incompatible protocols.",
            True,
        ),
    )
    states: list[PayoffState] = []
    for state_id, probability, parameters, description, catastrophic in specifications:
        game = battle_of_the_sexes(
            parameters,
            intervention=intervention,
            actions=scenario.actions,
            game_id=f"{scenario.scenario_id}_{state_id}",
            name=f"{scenario.name}: {state_id.replace('_', ' ').title()}",
            description=description,
        )
        game = replace(
            game,
            catastrophic_profiles=(
                frozenset(game.miscoordination_profiles)
                if catastrophic
                else frozenset()
            ),
        )
        states.append(
            PayoffState(
                state_id,
                probability,
                game,
                description,
                {
                    "preferred_coordination": parameters.preferred_coordination,
                    "concession_coordination": parameters.concession_coordination,
                    "miscoordination": parameters.miscoordination,
                    "coordination_bonus": intervention,
                    "mismatch_catastrophic": float(catastrophic),
                },
            )
        )
    return UncertainPayoffGame(
        game_id=f"{scenario.scenario_id}_uncertain",
        name=f"{scenario.name} with latent incident severity",
        states=tuple(states),
    )


UNCERTAIN_SCENARIOS: dict[str, Callable[..., UncertainPayoffGame]] = {
    FRONTIER_DEPLOYMENT_RACE.scenario_id: frontier_deployment_uncertainty,
    AUTONOMOUS_ESCALATION.scenario_id: autonomous_escalation_uncertainty,
    CROSS_LAB_INCIDENT_RESPONSE.scenario_id: cross_lab_incident_response_uncertainty,
    INCIDENT_RESPONSE_PROTOCOL.scenario_id: incident_response_protocol_uncertainty,
}


def uncertain_scenario_from_id(scenario_id: str, *, intervention: float = 0.0) -> UncertainPayoffGame:
    try:
        factory = UNCERTAIN_SCENARIOS[scenario_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown uncertain scenario {scenario_id!r}; choose from {sorted(UNCERTAIN_SCENARIOS)}"
        ) from exc
    return factory(intervention=intervention)
