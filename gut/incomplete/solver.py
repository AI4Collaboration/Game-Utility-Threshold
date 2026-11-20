"""Exact equilibrium sets for 2 actions, a public row player and private column types.

Harsanyi (1967–68), https://doi.org/10.1287/mnsc.14.3.159.
Independent small-game solver, not a reproduction of a published algorithm.
An equilibrium component is a row-probability interval and a box of column
probabilities intersected with a constraint on their prior-weighted mean.
This representation retains mixed equilibria, continua and endpoint ties.
"""

from fractions import Fraction as F
from gut.commitment import rational


def line(gaps):
    """C minus D given opponent cooperates with probability p."""
    return gaps[1], gaps[0] - gaps[1]


def at(gaps, p):
    b, m = line(gaps)
    return b + m*p


def mean_interval(bounds, priors):
    return tuple(sum((p*b[i] for p, b in zip(priors, bounds)), F(0)) for i in (0, 1))


def feasible_mean(row_gaps, x, bounds, priors):
    low, high = mean_interval(bounds, priors)
    b, m = line(row_gaps)
    if x not in (0, 1):
        if m:
            low, high = max(low, -b/m), min(high, -b/m)
        elif b:
            return None
    else:
        # x=1 needs gap >=0; x=0 needs gap <=0.
        sign = 1 if x == 1 else -1
        b, m = sign*b, sign*m
        if m > 0:
            low = max(low, -b/m)
        elif m < 0:
            high = min(high, -b/m)
        elif b < 0:
            return None
    return (low, high) if low <= high else None


def witness(bounds, priors, target):
    values = [b[0] for b in bounds]
    remaining = target - sum(p*v for p, v in zip(priors, values))
    for i, p in enumerate(priors):
        addition = min(bounds[i][1]-values[i], remaining/p)
        values[i] += addition
        remaining -= p*addition
    assert remaining == 0
    return tuple(values)


def solve(row_gaps, column_gaps, priors):
    """All Bayesian Nash equilibria, including mixed and degenerate sets.

    row_gaps is independent of the actual column type (private values).
    All types must have positive probability. Probabilities are rational.
    No claim that LLMs select, or even reach, an equilibrium.
    """
    row_gaps = tuple(map(rational, row_gaps))
    column_gaps = tuple(tuple(map(rational, row)) for row in column_gaps)
    priors = tuple(map(rational, priors))
    if (len(row_gaps) != 2 or not column_gaps or any(len(g) != 2 for g in column_gaps)
            or len(priors) != len(column_gaps) or any(p <= 0 for p in priors) or sum(priors) != 1):
        raise ValueError("Use two action gaps and matching positive type probabilities summing to one.")
    points = {F(0), F(1)}
    for gaps in column_gaps:
        b, m = line(gaps)
        if m and 0 < -b/m < 1:
            points.add(-b/m)
    points = sorted(points)
    cells = [(x, x, False) for x in points]
    cells += [(a, b, True) for a, b in zip(points, points[1:])]
    components = []
    for low, high, open_ends in cells:
        x = (low+high)/2
        bounds = tuple((F(1), F(1)) if at(g, x) > 0 else
                       (F(0), F(0)) if at(g, x) < 0 else (F(0), F(1)) for g in column_gaps)
        q = feasible_mean(row_gaps, x, bounds, priors)
        if q is None:
            continue
        # Exact marginal projections; the weighted-mean constraint still couples them.
        projected = []
        for i, (p, bound) in enumerate(zip(priors, bounds)):
            other = mean_interval(bounds[:i]+bounds[i+1:], priors[:i]+priors[i+1:])
            projected.append((max(bound[0], (q[0]-other[1])/p),
                              min(bound[1], (q[1]-other[0])/p)))
        components.append({"row_c": (low, high), "row_open_ends": open_ends,
                           "column_c": tuple(projected), "mean_column_c": q,
                           "witness": {"row_c": x, "column_c": witness(bounds, priors, sum(q)/2)}})
    assert components, "A finite Bayesian game must have an equilibrium."
    return components


def is_equilibrium(row_gaps, column_gaps, priors, x, ys):
    """Independent best-response residual check for a proposed policy profile."""
    x, ys = rational(x), tuple(map(rational, ys))
    if len(ys) != len(priors) or any(not 0 <= p <= 1 for p in (x, *ys)):
        return False
    q = sum(p*y for p, y in zip(priors, ys))
    def optimal(prob, gap):
        return (prob == 1 or gap <= 0) and (prob == 0 or gap >= 0)
    return optimal(x, at(row_gaps, q)) and all(optimal(y, at(g, x)) for y, g in zip(ys, column_gaps))
