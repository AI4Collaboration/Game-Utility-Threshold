"""Four fixed examples sharing one exact payoff operation, not four engines."""

from dataclasses import dataclass
from fractions import Fraction

from .game import Game, penalized_matrix

PD_COSTS = ("0", "1/4", "9/20", "1/2", "11/20", "3/4", "19/20", "1", "21/20", "5/4")


@dataclass(frozen=True)
class Example:
    name: str
    actions: tuple[str, str]
    baseline: tuple
    costs: tuple[str, ...]
    explanation: str

    def matrix(self, cost=0):
        return penalized_matrix(self.baseline, cost)

    def perspective(self, role, cost=0):
        """Rows = YOUR actions; columns = OTHER actions; own points first."""
        table = self.matrix(cost)
        if role == "row":
            return table
        if role == "column":
            return tuple(tuple((table[j][i][1], table[j][i][0]) for j in range(2)) for i in range(2))
        raise ValueError("role must be row or column")

    def margins(self, role, cost=0):
        table = self.perspective(role, cost)
        return tuple(table[0][j][0] - table[1][j][0] for j in range(2))

    def thresholds(self, role):
        return tuple(-v for v in self.margins(role))

    def stable_outcomes(self, cost=0):
        """Pure Nash outcomes: neither player gains by changing alone; retain ties."""
        row, column = self.margins("row", cost), self.margins("column", cost)
        return tuple((i, j) for i in range(2) for j in range(2)
                     if (1-2*i)*row[j] >= 0 and (1-2*j)*column[i] >= 0)


EXAMPLES = {
    "pd": Example("Prisoner's Dilemma", ("C", "D"), Game(t=2, s="-0.5").matrix(), PD_COSTS,
                  "At baseline, D pays more against either action. The cost can change that."),
    "stag_hunt": Example("Stag Hunt", ("C", "D"), Game(t="0.5", s="-0.5").matrix(), PD_COSTS,
                         "At baseline, matching pays: C against C, D against D. Both prefer mutual C to mutual D."),
    "chicken": Example("Chicken", ("C", "D"), Game(t="1.5", s="0.5").matrix(), PD_COSTS,
                       "At baseline, opposite actions pay: D against C, C against D. Mutual D is worst."),
    "battle_of_sexes": Example("Battle of the Sexes", ("X", "Y"),
                              tuple(tuple(tuple(Fraction(v) for v in cell) for cell in row)
                                    for row in (((2, 1), (0, 0)), ((0, 0), (1, 2)))),
                              ("0", "1/2", "19/20", "1", "21/20", "3/2", "39/20", "2", "41/20", "9/4"),
                              "Both want to match, but the row player prefers XX and the column player prefers YY. "
                              "The shared cost of Y favors X; neither action is called defection."),
}


def example(key):
    if key not in EXAMPLES:
        raise ValueError(f"unknown game: {key}")
    return EXAMPLES[key]


def controlled_conditions(key):
    """Version 2: fixed baselines, focused costs, separately identified controls.

    Keep EXAMPLES.costs unchanged so old frozen plans remain reproducible.
    The BoS mirror changes the substantive intervention, not just its label.
    """
    spec = example(key)
    costs = spec.costs if key in ("pd", "battle_of_sexes") else PD_COSTS[:6]
    targets = (1, 0) if key == "battle_of_sexes" else (1,)
    conditions = []
    for target in targets:
        ties = {abs(t) for role in ("row", "column") for t in spec.thresholds(role)
                if (t >= 0 if target == 1 else t <= 0)}
        checks = {Fraction(0), Fraction(costs[-1]), *ties}
        for representation, scale, offset in (("original", "1", "0"),
                                               ("scale10", "10", "0"),
                                               ("offset5", "1", "5")):
            for index, z in enumerate(costs):
                if representation != "original" and Fraction(z) not in checks:
                    continue
                conditions.append({"id": f"cost{target}-{representation}-z{index:02}",
                    "z": z, "cost_action": target, "representation": representation,
                    "scale": scale, "offset": offset,
                    "purpose": "primary" if representation == "original" else "representation_control"})
    return conditions


def controlled_matrix(key, condition, role="row"):
    """Subtract cost first, then transform EVERY final payoff into display units."""
    spec = example(key)
    z, scale, offset = (Fraction(condition[k]) for k in ("z", "scale", "offset"))
    target = condition["cost_action"]
    if z < 0 or scale <= 0 or type(target) is not int or target not in (0, 1):
        raise ValueError("Invalid cost, scale or targeted action")
    matrix = tuple(tuple(tuple(scale*(cell[p] - z*((i, j)[p] == target)) + offset
                               for p in (0, 1)) for j, cell in enumerate(row))
                   for i, row in enumerate(spec.baseline))
    if role == "row":
        return matrix
    if role == "column":
        return tuple(tuple((matrix[j][i][1], matrix[j][i][0]) for j in (0, 1)) for i in (0, 1))
    raise ValueError("role must be row or column")
