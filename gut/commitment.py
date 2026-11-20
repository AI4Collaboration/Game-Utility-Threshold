"""Exact commitment solver for two leader actions and finite follower types.

Structure: Paruchuri et al. (AAMAS 2008), sections 2–3.
https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf
This independently implemented breakpoint algorithm is NOT DOBSS. It solves
the two-leader-action subcase over the continuous interval q in [0, 1].
All arithmetic is rational. Unfavorable ties can produce an unattained supremum.
"""

from fractions import Fraction as F
from itertools import combinations


def rational(value):
    if isinstance(value, bool):
        raise ValueError("Booleans are not game parameters.")
    try:
        return F(str(value))
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError("Use a finite number or fraction.") from exc


def value(line, q):
    """An affine payoff is (intercept, slope)."""
    return line[0] + q * line[1]


def crossings(lines):
    points = {F(0), F(1)}
    for left, right in combinations(lines, 2):
        slope = left[1] - right[1]
        if slope:
            root = (right[0] - left[0]) / slope
            if 0 <= root <= 1:
                points.add(root)
    return points


class CommitmentGame:
    """Rows are leader actions; columns are follower actions.

    follower[type][row][action], leader[type][row][action]. q is the
    probability of row 0. Priors describe one drawn type, not simultaneous
    followers. Zero-prior types retain response predictions but no objective
    weight. Caller supplies the permitted action meanings.
    """

    def __init__(self, priors, follower, leader):
        self.priors = tuple(map(rational, priors))
        self.follower = self._matrices(follower)
        self.leader = self._matrices(leader)
        if (not self.priors or any(p < 0 for p in self.priors)
                or sum(self.priors) != 1
                or len(self.priors) != len(self.follower)
                or len(self.priors) != len(self.leader)):
            raise ValueError("Types need matching matrices and nonnegative priors summing to one.")
        self.actions = len(self.follower[0][0])
        if not self.actions or any(len(row) != self.actions
                                   for matrices in (self.follower, self.leader)
                                   for matrix in matrices for row in matrix):
            raise ValueError("All rows must have the same nonzero number of actions.")

    @staticmethod
    def _matrices(matrices):
        result = tuple(tuple(tuple(map(rational, row)) for row in m) for m in matrices)
        if any(len(m) != 2 for m in result):
            raise ValueError("This exact solver supports exactly two leader actions.")
        return result

    def lines(self, player, kind):
        matrix = (self.follower if player == "follower" else self.leader)[kind]
        return tuple((b, a-b) for a, b in zip(*matrix))

    def evaluate(self, q):
        q = rational(q)
        if not 0 <= q <= 1:
            raise ValueError("The commitment probability must be between zero and one.")
        types = []
        for kind, prior in enumerate(self.priors):
            follower = tuple(value(line, q) for line in self.lines("follower", kind))
            leader = tuple(value(line, q) for line in self.lines("leader", kind))
            best = tuple(i for i, payoff in enumerate(follower) if payoff == max(follower))
            types.append({"prior": prior, "follower": follower, "leader": leader,
                          "best_responses": best,
                          "favorable": max(leader[i] for i in best),
                          "unfavorable": min(leader[i] for i in best)})
        return {"q": q, "types": types,
                **{tie: sum(t["prior"] * t[tie] for t in types)
                   for tie in ("favorable", "unfavorable")}}

    def breakpoints(self):
        points = {F(0), F(1)}
        for kind in range(len(self.priors)):
            # Leader intersections also handle follower actions tied everywhere.
            for player in ("follower", "leader"):
                points |= crossings(self.lines(player, kind))
        return tuple(sorted(points))

    def solve(self):
        """Return optimum/supremum, attaining witnesses and one-sided limits.

        Witnesses are representative policies, not a list of every optimum.
        Within each open cell all response rankings are constant and the
        leader objective is affine. Evaluate its endpoint limits exactly.
        """
        points = self.breakpoints()
        evaluated = {q: self.evaluate(q) for q in points}
        limits = {tie: [] for tie in ("favorable", "unfavorable")}
        for low, high in zip(points, points[1:]):
            mid = (low+high)/2
            evaluated[mid] = self.evaluate(mid)
            for tie in limits:
                intercept = slope = F(0)
                choose = max if tie == "favorable" else min
                for kind, row in enumerate(evaluated[mid]["types"]):
                    lines = self.lines("leader", kind)
                    action = choose(row["best_responses"], key=lambda a: value(lines[a], mid))
                    intercept += row["prior"] * lines[action][0]
                    slope += row["prior"] * lines[action][1]
                for q, side in ((low, "right"), (high, "left")):
                    limits[tie].append({"q": q, "side": side,
                                        "value": intercept+slope*q})
        result = {"breakpoints": points}
        for tie in limits:
            supremum = max([row[tie] for row in evaluated.values()]
                           + [row["value"] for row in limits[tie]])
            witnesses = sorted(q for q, row in evaluated.items() if row[tie] == supremum)
            result[tie] = {"value": supremum, "attained": bool(witnesses),
                           "witnesses": witnesses,
                           "limits": [r for r in limits[tie] if r["value"] == supremum]}
        return result
