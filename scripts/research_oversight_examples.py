"""Generate deterministic, exact oversight examples without any model calls.

Run from any directory. Output is a theory demonstration, not experimental data.
All numerical inputs and calculated values retain numerator/denominator pairs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utility_threshold.core import GameParams, GameState
from utility_threshold.oversight_uncertainty import (
    ClosedInterval,
    MarginUncertainty,
    TypeDistribution,
    evaluate_private_values,
    minimum_defense_for_attack_probability,
    one_parameter_distances,
    solve_private_value_defense,
    worst_case_margin,
    worst_case_margin_at_defense,
)

DEFAULT_OUTPUT = ROOT / "results" / "research_theory" / "oversight_examples.json"


def fraction_record(value: int | float | Fraction) -> dict[str, int]:
    exact = value if isinstance(value, Fraction) else Fraction(str(value))
    return {"numerator": exact.numerator, "denominator": exact.denominator}


def build_examples() -> dict[str, object]:
    """Return fixed, fully specified examples and their exact certificates."""
    params = GameParams()
    prior = TypeDistribution.from_weights(((1, 3), (10, 1)))
    maximum = Fraction(10)
    welfare = solve_private_value_defense(prior, params, maximum)
    risk_cases = (
        ("At most one quarter attack probability", Fraction(1, 4), maximum),
        ("Eliminate attack probability within this prior", Fraction(0), maximum),
        ("Zero attack probability with insufficient defense budget", Fraction(0), Fraction(4)),
    )
    risk_results = [
        {
            "label": label,
            "result": minimum_defense_for_attack_probability(prior, params, target, budget).to_dict(),
        }
        for label, target, budget in risk_cases
    ]

    # Only defense varies. Insert all exact solver candidates so thresholds and
    # saturation are represented even when they fall between uniform grid points.
    defenses = {Fraction(index, 20) for index in range(201)}
    defenses.update(candidate.evaluation.defense for candidate in welfare.candidates)
    curve = []
    for defense in sorted(defenses):
        result = evaluate_private_values(prior, defense, params)
        minimum_margin = min(response.safety_margin for response in result.responses if response.probability > 0)
        curve.append({
            "defense": fraction_record(defense),
            "attack_probability": fraction_record(result.attack_probability),
            "unblocked_attack_probability": fraction_record(result.unblocked_attack_probability),
            "expected_human_utility": fraction_record(result.expected_human_utility),
            "minimum_margin_over_positive_probability_types": fraction_record(minimum_margin),
        })

    defense_uncertainty = {
        "v": ClosedInterval(3, 4),
        "R": ClosedInterval(1, Fraction(6, 5)),
        "g": ClosedInterval(0, Fraction(1, 5)),
        "penalty": ClosedInterval(4, 5),
        "defense": ClosedInterval(5, Fraction(26, 5)),
        "detection_slope": ClosedInterval(Fraction(7, 50), Fraction(4, 25)),
        "attack_cost_slope": ClosedInterval(Fraction(12, 25), Fraction(13, 25)),
    }
    required_margin = Fraction(1, 4)
    robust = worst_case_margin_at_defense(**defense_uncertainty, required_margin=required_margin)
    counterexample = MarginUncertainty(
        v=ClosedInterval(3, 4), R=ClosedInterval(1, Fraction(6, 5)), g=ClosedInterval(0, Fraction(1, 5)),
        penalty=ClosedInterval(4, 5), detection=ClosedInterval(Fraction(1, 2), Fraction(3, 5)),
        attack_cost=ClosedInterval(2, Fraction(21, 10)),
    )
    nominal = GameState(v=4, d=4)
    source_paths = (
        "scripts/research_oversight_examples.py",
        "utility_threshold/core.py",
        "utility_threshold/oversight_uncertainty.py",
    )
    return {
        "schema_version": 1,
        "artifact_kind": "exact_model_demonstration",
        "evidence_class": "THEORY_ONLY",
        "model_calls": 0,
        "description": (
            "Deterministic calculations under explicitly specified utilities, types, and intervals. "
            "These are not observed AI decisions, empirical success rates, or statistical confidence bounds."
        ),
        "numerical_convention": (
            "Exact rational arithmetic; every numerical input and calculated value uses a numerator/denominator pair. "
            "Floats in GameParams are interpreted by their decimal strings."
        ),
        "generator_command": "python3 scripts/research_oversight_examples.py",
        "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
        "payoff_model": {
            "attack_cost_slope": fraction_record(Fraction(1, 2)),
            "detection_slope": fraction_record(Fraction(3, 20)),
            "detection_cap": fraction_record(1),
            "follower_tie_break": "COOPERATE",
            "limitation": (
                "The same detection quantity reduces human loss and increases expected penalty; "
                "the AI resource reward remains v*R even at full detection."
            ),
        },
        "private_priority_example": {
            "inputs": {
                "game_params": {name: fraction_record(value) for name, value in asdict(params).items()},
                "type_distribution": prior.to_dict(),
                "max_defense": fraction_record(maximum),
            },
            "welfare_optimum": welfare.to_dict(),
            "risk_requirements": risk_results,
            "curve_design": {
                "varied_quantity": "defense",
                "held_fixed": "all game parameters and both type values and probabilities",
                "base_grid": "0 through 10 inclusive, step 1/20; all exact solver candidate defenses inserted",
                "display_guidance": (
                    "Use defense on a shared horizontal axis with separate panels for attack probability, "
                    "human utility, and minimum margin. Label every series THEORY ONLY."
                ),
            },
            "defense_curve": curve,
        },
        "bounded_error_example": {
            "interpretation": (
                "Every combination of the declared input intervals is admitted; cost and detection "
                "share the same actual defense. These ranges are illustrative assumptions, not fitted confidence intervals."
            ),
            "inputs": {name: interval.to_dict() for name, interval in defense_uncertainty.items()},
            "required_margin": fraction_record(required_margin),
            "certificate": robust.to_dict(),
        },
        "maximin_is_not_uniform_safety_counterexample": {
            "inputs": counterexample.to_dict(),
            "certificate": worst_case_margin(counterexample).to_dict(),
        },
        "one_parameter_fragility_example": {
            "game_params": {name: fraction_record(value) for name, value in asdict(params).items()},
            "state": {name: fraction_record(value) for name, value in asdict(nominal).items()},
            "certificate": one_parameter_distances(nominal, params).to_dict(),
        },
    }


def render_examples() -> str:
    return json.dumps(build_examples(), indent=2, sort_keys=True, allow_nan=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destination for the theory-only JSON.")
    parser.add_argument("--check", action="store_true", help="Compare with the saved artifact without changing files.")
    args = parser.parse_args(argv)
    expected = render_examples()
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
            print(f"Theory artifact is missing or differs from exact regeneration: {args.output}", file=sys.stderr)
            return 1
        print(f"Exact theory artifact reproduced: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"Wrote THEORY ONLY examples; zero model calls: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
