"""Export recorded choices as exact Lean statements; checking is explicit."""

from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
import subprocess

from .experiment import observations
from .canonical import example

LEAN = Path(__file__).resolve().parents[1] / "lean"


def exact_table(z, game="pd", role="row"):
    matrix = example(game).perspective(role, z)
    values = [matrix[i][j][0] for i in range(2) for j in range(2)]
    denominator = lcm(*(v.denominator for v in values))
    return denominator, [int(v*denominator) for v in values]


def comparison(value):
    return "better" if value > 0 else "worse" if value < 0 else "tied"


def export_proofs(directory, *, check=False, lake="lake"):
    directory = Path(directory)
    plan, choices, pairs = observations(directory)
    game = plan.get("game", "pd")
    partners = {p["id"]: p for p in pairs}
    output = directory / "proofs"
    output.mkdir(exist_ok=True)
    source = ["import AgentProof", "set_option warningAsError true", "open AgentProof", "namespace RecordedChoices"]
    mapping = []
    for index, choice in enumerate(choices):
        row = {"id": choice["id"], "status": choice["status"], "action": choice["action"],
               "z": choice["z"], "role": choice["role"], "block": choice["block"]}
        if choice["action"] is not None:
            a = choice["action"]
            name = f"choice_{index}"
            denominator, table = exact_table(choice["z"], game, choice["role"])
            margins = [table[2*a+j]-table[2*(1-a)+j] for j in (0, 1)]
            outcomes = list(map(comparison, margins))
            selected = ".first" if a == 0 else ".second"
            integer = lambda n: f"({n})"  # Only validated integers enter generated Lean.
            source += [f"def {name}_table : Payoffs := ⟨{', '.join(map(integer, table))}⟩",
                       f"def {name} : Certificate {name}_table {selected} := {{",
                       f"  againstFirst := .{outcomes[0]}, againstSecond := .{outcomes[1]}",
                       "  first_correct := by decide", "  second_correct := by decide", "}"]
            dominant = all(m >= 0 for m in margins)
            source += [f"theorem {name}_dominance : {'¬ ' if not dominant else ''}Dominant {name}_table {selected} := by decide",
                       f"#print axioms {name}", f"#print axioms {name}_dominance"]
            partner = partners[choice["pair"]]["column" if choice["role"] == "row" else "row"]
            if partner is not None:
                opponent = ".first" if partner == 0 else ".second"
                source += [f"theorem {name}_observed : {'¬ ' if margins[partner] < 0 else ''}BestResponse {name}_table {selected} {opponent} := by decide",
                           f"#print axioms {name}_observed"]
            row.update(certificate=f"RecordedChoices.{name}", semantic_action=example(game).actions[a],
                       denominator=denominator, payoff_integers=table,
                       against_first=outcomes[0], against_second=outcomes[1], dominant=dominant,
                       observed_opponent=partner, observed_comparison=outcomes[partner] if partner is not None else None,
                       selected_minus_alternative=[str(Fraction(m, denominator)) for m in margins])
        mapping.append(row)
    source += ["end RecordedChoices", ""]
    path = output / "Choices.lean"
    path.write_text("\n".join(source))
    result = {"plan_sha256": plan["sha256"], "mode": plan["mode"], "model": plan["model"], "game": game,
              "records_sha256": sha256((directory / "records.jsonl").read_bytes()).hexdigest()
              if (directory / "records.jsonl").exists() else None,
              "source_sha256": sha256(path.read_bytes()).hexdigest(),
              "core_sha256": sha256((LEAN / "AgentProof.lean").read_bytes()).hexdigest(),
              "toolchain": (LEAN / "lean-toolchain").read_text().strip(),
              "verified": False, "mapped_choices": sum("certificate" in row for row in mapping),
              "unmapped_choices": sum("certificate" not in row for row in mapping)}
    (output / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n")
    result["mapping_sha256"] = sha256((output / "mapping.json").read_bytes()).hexdigest()
    manifest = output / "verification.json"
    manifest.write_text(json.dumps(result, indent=2) + "\n")
    if check:
        log = []
        try:
            version = subprocess.run([lake, "env", "lean", "--version"], cwd=LEAN, text=True, capture_output=True, check=True)
            if "version 4.33.1" not in version.stdout:
                raise ValueError("Lean version does not match the pinned toolchain")
            log.append(version.stdout)
            for command in ([lake, "build"], [lake, "env", "lean", str(path.resolve())]):
                process = subprocess.run(command, cwd=LEAN, text=True, capture_output=True)
                log.extend([process.stdout, process.stderr])
                if process.returncode or "sorryAx" in process.stdout or "_native" in process.stdout:
                    raise ValueError("Lean verification failed; see proofs/lean-check.log")
        finally:
            (output / "lean-check.log").write_text("\n".join(log))
        result["verified"] = True
        manifest.write_text(json.dumps(result, indent=2) + "\n")
    return result
