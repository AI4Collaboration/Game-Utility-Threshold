"""Run the Month 1--3 toy oversight-game simulation."""

from utility_threshold.agents import (
    Agent,
    CooperateBot,
    DefectBot,
    ProbabilisticThresholdBot,
    ProofCarryingThresholdBot,
    ThresholdBot,
)
from utility_threshold.core import GameParams, GameState, human_utility, safety_margin


def run_demo() -> None:
    prm = GameParams()
    agents: list[tuple[str, Agent]] = [
        ("CooperateBot", CooperateBot()),
        ("DefectBot", DefectBot()),
        ("ThresholdBot", ThresholdBot()),
        ("ProbabilisticThresholdBot", ProbabilisticThresholdBot()),
        ("ProofCarryingThresholdBot", ProofCarryingThresholdBot()),
    ]
    states = [GameState(v=v, d=d) for v in (2.0, 4.0, 6.0, 8.0) for d in (0, 2, 4, 6, 8)]

    print("name,v,d,action,margin,human_utility")
    for name, agent in agents:
        for state in states:
            action = agent.choose(state, prm)
            print(f"{name},{state.v:.1f},{state.d:.1f},{action},{safety_margin(state, prm):.3f},{human_utility(action, state, prm):.3f}")


if __name__ == "__main__":
    run_demo()
