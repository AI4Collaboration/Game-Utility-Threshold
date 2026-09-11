import shutil
import subprocess
import unittest
from pathlib import Path

from utility_threshold.core import (
    GameParams,
    GameState,
    attack_utility,
    human_utility,
    q_of_d,
    safety_margin,
    threshold_action,
)


ROOT = Path(__file__).resolve().parents[1]
LEAN_ROOT = ROOT / "lean"


class LeanPythonParityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lake"), "Lake is not installed")
    def test_phase_one_grid_matches_lean_exactly(self) -> None:
        process = subprocess.run(
            ["lake", "exe", "parity_check"],
            cwd=LEAN_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        observed = {
            (int(v), int(d)): {
                "detection_rate": int(detection_rate),
                "attack_utility": int(attack),
                "safety_margin": int(margin),
                "human_utility": int(human),
                "action": action,
            }
            for line in process.stdout.splitlines()
            for v, d, detection_rate, attack, margin, human, action in [line.split(",")]
        }

        params = GameParams()
        expected = {}
        for v in (1, 2, 4, 6, 8):
            for d in (0, 2, 4, 6, 8):
                state = GameState(v=float(v), d=float(d))
                action = threshold_action(state, params)
                expected[(v, d)] = {
                    "detection_rate": round(20 * q_of_d(d)),
                    "attack_utility": round(20 * attack_utility(state, params)),
                    "safety_margin": round(20 * safety_margin(state, params)),
                    "human_utility": round(20 * human_utility(action, state, params)),
                    "action": action,
                }

        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
