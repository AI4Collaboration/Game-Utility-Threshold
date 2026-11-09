"""The post's symmetric, one-shot, two-action game.

The row player's payoff table is [[R, S], [T, P]]; the column player's
table is its transpose. A nonnegative cost k is paid only by a player who
chooses D. Numbers are exact fractions: the float 0.1 means decimal 1/10.

Normalization uses the ORIGINAL gap R-P. The same transformation must scale
the intervention cost by that gap; we do not renormalize an adjusted game.
"""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

Number = int | float | str | Decimal | Fraction


def _fraction(value: Number, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal, Fraction)):
        raise ValueError(f"{name} must be a finite number")
    try:
        # str(float) captures the declared decimal rather than its binary
        # storage approximation. Fraction also rejects NaN and infinities.
        return Fraction(str(value)) if isinstance(value, float) else Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc


def _cost(value: Number) -> Fraction:
    result = _fraction(value, "k")
    if result < 0:
        raise ValueError("k must be nonnegative")
    return result


def penalized_matrix(baseline: tuple, cost: Number = 0) -> tuple:
    """Subtract one shared cost only from the actor choosing action index 1."""
    cost = _cost(cost)
    return tuple(tuple((baseline[i][j][0] - i*cost, baseline[i][j][1] - j*cost)
                       for j in range(2)) for i in range(2))


@dataclass(frozen=True)
class Game:
    """A symmetric payoff table with R>P, before any cost is added.

    T and S may span all four incentive regions. Strict Prisoner's Dilemma
    additionally requires T>R>P>S; it is a subset of the accepted tables.
    """

    t: Number
    s: Number
    r: Number = 1
    p: Number = 0

    def __post_init__(self):
        for name in ("t", "r", "p", "s"):
            object.__setattr__(self, name, _fraction(getattr(self, name), name))
        if self.r <= self.p:
            raise ValueError("normalization requires R>P")

    def matrix(self, k: Number = 0) -> tuple:
        """Return four (row points, column points) pairs in C,D order."""
        return penalized_matrix((((self.r, self.r), (self.s, self.t)),
                                 ((self.t, self.s), (self.p, self.p))), k)

    def margins(self, k: Number = 0) -> tuple[Fraction, Fraction]:
        """C minus D points against an opponent choosing C, then D."""
        k = _cost(k)
        return self.r-self.t+k, self.s-self.p+k

    def thresholds(self) -> tuple[Fraction, Fraction]:
        """Exact tie costs against C, then D; a negative tie is infeasible."""
        return self.t-self.r, self.p-self.s

    def region(self, k: Number = 0) -> str:
        """Classify incentive signs; any exact tie is an explicit boundary.

        Chicken and Stag Hunt name the respective incentive regions here,
        rather than imposing an additional complete ranking of all payoffs.
        """
        against_c, against_d = self.margins(k)
        if against_c == 0 or against_d == 0:
            return "boundary"
        if against_c < 0:
            return "defection_dominant" if against_d < 0 else "chicken"
        return "stag_hunt" if against_d < 0 else "cooperation_dominant"

    def response_to_defection(self, k: Number = 0) -> str:
        """Compare actions conditional on the opponent choosing D."""
        margin = self.margins(k)[1]
        return "cooperate" if margin > 0 else "defect" if margin < 0 else "tie"

    def normalized(self) -> "Game":
        """Set the baseline R=1,P=0 by subtracting P and dividing by R-P."""
        gap = self.r-self.p
        return Game(t=(self.t-self.p)/gap, s=(self.s-self.p)/gap)

    def normalize_cost(self, k: Number) -> Fraction:
        """Express an original-unit cost in normalized baseline units."""
        return _cost(k)/(self.r-self.p)


BASELINE_PD = Game(t=5, r=3, p=1, s=0)


def pd_grid() -> tuple[Game, ...]:
    """The 625 strict PD tables: 25 equally spaced S and T values each.

    S ranges from -1 to -0.05; T ranges from 1.05 to 2. R=1 and P=0.
    Ordering is increasing S, then increasing T. These are theory cases,
    not model observations or a newly collected empirical dataset.
    """
    step = Fraction(19, 480)
    return tuple(Game(t=Fraction(21, 20)+j*step, s=-1+i*step)
                 for i in range(25) for j in range(25))


def grid_counts(k: Number = 0) -> dict[str, int]:
    """Count conditional responses to D on the theory grid; retain ties."""
    k = _cost(k)
    counts = {"cooperate": 0, "defect": 0, "tie": 0}
    for game in pd_grid():
        counts[game.response_to_defection(k)] += 1
    return counts
