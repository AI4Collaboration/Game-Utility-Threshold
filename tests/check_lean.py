"""Integration check: compile evidence and ensure a false claim is rejected."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gut.experiment import collect, save_plan
from gut.proofs import LEAN, export_proofs


def main():
    lake = os.environ.get("LAKE", "lake")
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp) / "run"
        save_plan(run, repetitions=1)
        collect(run)
        result = export_proofs(run, check=True, lake=lake)
        assert result["verified"] and result["mapped_choices"] == 40
        false = Path(tmp) / "FalseClaim.lean"
        false.write_text("import AgentProof\nopen AgentProof\n"
                         "example : Dominant ⟨20, -10, 40, 0⟩ .first := by decide\n")
        process = subprocess.run([lake, "env", "lean", str(false)], cwd=LEAN, capture_output=True, text=True)
        assert process.returncode != 0 and "error" in process.stdout.lower(), process.stdout
    print("Lean verified recorded choices and rejected a false dominance claim")


if __name__ == "__main__":
    main()
