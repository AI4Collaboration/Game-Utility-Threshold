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
