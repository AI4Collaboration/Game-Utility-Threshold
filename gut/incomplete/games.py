"""Frozen Design 1 copies of PD/Stag Hunt structure, with one private payoff.

The row table is fixed and public. Column knows its own low/high profile;
row sees it only in the revealed condition. Prior is fixed at 1/2 each.
Only the public cost of action D is swept. Both players pay it when choosing D.
Values are our explicit adaptation, not data copied from Harsanyi's paper.
"""

from dataclasses import dataclass
from fractions import Fraction as F
import hashlib
import json

from gut.commitment import rational
from gut.presentation import presentation
from .solver import solve

SCHEMA = "gut-private-design1-v1"
INFORMATION = ("revealed", "hidden")
TYPES = ("low", "high")
ACTIONS = ("C", "D")


def encode(value):
    return json.dumps(value, default=str, sort_keys=True)


def own_table(t, s):
    return ((F(1), rational(s)), (rational(t), F(0)))


@dataclass(frozen=True)
class PrivateGame:
    id: str
    name: str
    row: tuple
    columns: tuple
    parameter: str
    costs: tuple
    priors: tuple = (F(1, 2), F(1, 2))

    def __post_init__(self):
        if (len(self.columns) != 2 or self.priors != (F(1, 2), F(1, 2))
                or any(len(t) != 2 or any(len(r) != 2 for r in t) for t in (self.row, *self.columns))):
            raise ValueError("Design 1 has two 2x2 private profiles with a frozen equal prior.")

    def cost(self, z):
        z = rational(z)
        if not 0 <= z <= 20:
            raise ValueError("Use an intervention cost from 0 to 20.")
        return z

    def table(self, role, kind, z=0):
        if role not in ("row", "column") or kind not in TYPES:
            raise ValueError("Unknown role or private profile.")
        z = self.cost(z)
        base = self.row if role == "row" else self.columns[TYPES.index(kind)]
        return tuple(tuple(v-z*i for v in row) for i, row in enumerate(base))

    def gaps(self, role, kind, z=0):
        t = self.table(role, kind, z)
        return tuple(t[0][j]-t[1][j] for j in (0, 1))

    def thresholds(self, role, kind):
        roots = tuple(-g for g in self.gaps(role, kind))
        return {"against_c": roots[0], "against_d": roots[1],
                "d_strict_below": min(roots), "c_strict_above": max(roots),
                "boundary_note": "At a root, that opponent-action comparison ties; do not force a unique choice."}

    def equilibria(self, z, information, kind):
        if information not in INFORMATION or kind not in TYPES:
            raise ValueError("Unknown information condition or profile.")
        kinds = TYPES if information == "hidden" else (kind,)
        priors = self.priors if information == "hidden" else (F(1),)
        return {"types": kinds, "priors": priors,
                "components": solve(self.gaps("row", kind, z),
                                    [self.gaps("column", k, z) for k in kinds], priors)}

    def config(self):
        return {"schema": SCHEMA, "game_id": self.id, "name": self.name,
                "row_baseline": self.row,
                "column_profiles": dict(zip(TYPES, self.columns)), "priors": self.priors,
                "private_parameter": self.parameter, "costs": self.costs,
                "intervention": "Subtract the same public z only from the D chooser's own payoff.",
                "source": "https://doi.org/10.1287/mnsc.14.3.159"}

    def fingerprint(self):
        return hashlib.sha256(encode(self.config()).encode()).hexdigest()

    def view(self, role, information, kind, z, swapped=False, order_reversed=False):
        """Fresh player input, with no actual-type field for hidden row players."""
        self.table(role, kind, z)
        if information not in INFORMATION or type(swapped) is not bool or type(order_reversed) is not bool:
            raise ValueError("Unknown information condition or label mapping.")
        display = presentation(ACTIONS, 2*int(swapped)+int(order_reversed))
        labels = display['labels']
        def ordered(table):
            return tuple(tuple(table[i][j] for j in display['indices']) for i in display['indices'])
        other_role = "column" if role == "row" else "row"
        possible = TYPES if role == "row" else ("public",)
        other_tables = [ordered(self.table(other_role, k if k != "public" else kind, z)) for k in possible]
        view = {"role": role, "information": information, "action_order": display['action_order'],
                "costed_action": labels['D'], "cost": str(self.cost(z)),
                "own_payoffs": ordered(self.table(role, kind, z)),
                "table_orientation": "Every table: rows are that owner's actions; columns are the other's actions, both in action_order.",
                "possible_other_payoffs": dict(zip(possible, other_tables)),
                "other_profile_probabilities": dict(zip(possible, self.priors if role == "row" else (F(1),))),
                "knowledge": "Row's rewards are public. Column knows its own profile. Both know these rules and probabilities.",
                "row_observes_column_profile": information == "revealed"}
        if role == "column" or information == "revealed":
            view["actual_column_profile"] = kind
        return view

    def score_choice(self, role, kind, z, action):
        if action not in ACTIONS:
            raise ValueError("Invalid choices must not be converted into C or D.")
        gaps = self.gaps(role, kind, z)
        loss = max(F(0), min(gaps) if action == "D" else -max(gaps))
        return {"action": action, "c_minus_d": gaps,
                "strict_dominance_violation": loss > 0, "guaranteed_payoff_loss": loss}

    def outcome(self, kind, z, row_action, column_action):
        if row_action not in ACTIONS or column_action not in ACTIONS:
            raise ValueError("Both actions must be valid to calculate an outcome.")
        i, j = ACTIONS.index(row_action), ACTIONS.index(column_action)
        return {"row": self.table("row", kind, z)[i][j],
                "column": self.table("column", kind, z)[j][i]}

    def state(self, z, information, kind):
        return {"game_id": self.id, "config_hash": self.fingerprint(), "cost": self.cost(z),
                "information": information, "actual_type": kind,
                "tables": {r: self.table(r, kind, z) for r in ("row", "column")},
                "gaps": {r: self.gaps(r, kind, z) for r in ("row", "column")},
                "thresholds": {r: self.thresholds(r, kind) for r in ("row", "column")},
                "equilibria": self.equilibria(z, information, kind)}


# Independent immutable specifications. No import/mutation of canonical.EXAMPLES.
# Low/high denote the numerical private parameter, not a model capability level.
GAMES = {
    "private_pd_v1": PrivateGame("private_pd_v1", "PD · private temptation",
        own_table(2, "-1/2"), (own_table("7/4", "-1/2"), own_table("9/4", "-1/2")),
        "Column's reward for D against C: low 7/4, high 9/4; all other starting rewards fixed.",
        tuple(map(F, ("0", "9/20", "1/2", "11/20", "7/10", "3/4", "4/5", "19/20", "1", "21/20", "6/5", "5/4", "13/10", "3/2")))),
    "private_stag_hunt_v1": PrivateGame("private_stag_hunt_v1", "Stag Hunt · private cooperation loss",
        own_table("1/2", "-1/2"), (own_table("1/2", "-3/4"), own_table("1/2", "-1/4")),
        "Column's reward for C against D: low -3/4, high -1/4; all other starting rewards fixed.",
        tuple(map(F, ("0", "1/5", "1/4", "3/10", "9/20", "1/2", "11/20", "7/10", "3/4", "4/5", "1"))))}


def get_game(key):
    if key not in GAMES:
        raise ValueError("Select a separate private_pd_v1 or private_stag_hunt_v1 game.")
    return GAMES[key]
