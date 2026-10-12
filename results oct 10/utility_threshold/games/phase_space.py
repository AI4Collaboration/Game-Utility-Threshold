"""Cardinal symmetric 2x2 phase space, including ties and changes of game class.

Follows Falmagne's SIAM News (2026) reduction: s=(S-P)/(R-P),
t=(T-P)/(R-P).  Positive affine transformations preserve strategic structure,
but empirical LLM behavior need not be affine invariant.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from typing import Iterable

from .base import Payoff, SymmetricTwoByTwoGame


@dataclass(frozen=True)
class SymmetricPayoffs:
    T: float = 5.0
    R: float = 3.0
    P: float = 1.0
    S: float = 0.0

    def __post_init__(self):
        if not all(isfinite(v) for v in asdict(self).values()):
            raise ValueError("Payoffs must be finite")
        if self.R <= self.P:
            raise ValueError("This coordinate chart requires R > P")

    @property
    def s(self):
        return (self.S - self.P) / (self.R - self.P)

    @property
    def t(self):
        return (self.T - self.P) / (self.R - self.P)

    def normalize(self):
        return SymmetricPayoffs(T=self.t, R=1.0, P=0.0, S=self.s)

    def affine(self, scale: float, shift: float):
        if not isfinite(scale) or scale <= 0 or not isfinite(shift):
            raise ValueError("Affine scale must be positive and both inputs finite")
        return SymmetricPayoffs(**{k: scale*v + shift for k, v in asdict(self).items()})

    def game(self):
        # The strict PD constructor deliberately rejects non-PD matrices.
        # Use the existing general game engine for transitions to other families.
        return SymmetricTwoByTwoGame(
            game_id="symmetric_phase_space", name="Symmetric payoff game",
            family=self.regime, actions=("C", "D"),
            cooperative_action="C", competitive_action="D",
            payoffs={
                ("C", "C"): Payoff(self.R, self.R),
                ("C", "D"): Payoff(self.S, self.T),
                ("D", "C"): Payoff(self.T, self.S),
                ("D", "D"): Payoff(self.P, self.P),
            },
        )

    @property
    def regime(self):
        a, b = self.R-self.T, self.S-self.P
        if abs(a) < 1e-10 or abs(b) < 1e-10:
            return "boundary"
        if a > 0 and b > 0:
            return "C_dominant"
        if a < 0 and b < 0:
            return "D_dominant"
        return "coordination" if a > 0 else "anti_coordination"

    def margin(self, opponent_cooperation: float):
        if not 0 <= opponent_cooperation <= 1:
            raise ValueError("Belief must be in [0,1]")
        q = opponent_cooperation
        return q*(self.R-self.T)+(1-q)*(self.S-self.P)

    def report(self):
        g = self.game()
        values = asdict(self)
        order = sorted(values, key=lambda k: (-values[k], k))
        groups = []
        for name in order:
            if groups and abs(values[groups[-1][-1]]-values[name]) < 1e-10:
                groups[-1].append(name)
            else:
                groups.append([name])
        worst = {"C": min(self.R, self.S), "D": min(self.T, self.P)}
        maximum = max(worst.values())
        mixed = g.symmetric_mixed_equilibrium()
        return {
            **values, "s": self.s, "t": self.t, "regime": self.regime,
            "payoff_order": ">".join("=".join(group) for group in groups),
            "strict_pd": self.T > self.R > self.P > self.S,
            "mutual_cooperation_socially_optimal": 2*self.R >= self.S+self.T,
            "pure_nash": [list(p) for p in g.pure_nash_equilibria()],
            "mixed_cooperation_probability": mixed["C"] if mixed else None,
            "pareto_profiles": [list(p) for p in g.pareto_efficient_profiles()],
            "welfare_profiles": [list(p) for p in g.welfare_optimal_profiles()],
            "pure_maximin_actions": [a for a,v in worst.items() if abs(v-maximum)<1e-10],
            "cooperation_margin_q_half": self.margin(.5),
            "cooperation_dominance_cost": max(self.T-self.R,self.P-self.S,0),
        }


def axis_values(low=-1.0, high=2.0, step=.25):
    if not all(isfinite(x) for x in (low, high, step)) or step <= 0 or high < low:
        raise ValueError("Invalid grid bounds")
    count = round((high-low)/step)
    if abs(low+count*step-high) > 1e-8:
        raise ValueError("Step must divide the range exactly")
    return [round(low+i*step, 10) for i in range(count+1)]


def phase_grid(values: Iterable[float]):
    values = tuple(values)
    return [SymmetricPayoffs(T=t, R=1, P=0, S=s) for t in values for s in values]


def one_parameter_sweeps(base=SymmetricPayoffs(), points=81):
    if points < 2:
        raise ValueError("Need at least two points")
    ranges = {"T": (-1.,7.), "R": (1.5,8.), "P": (-3.,2.5), "S": (-2.,4.)}
    return {
        name: [replace(base, **{name: lo+(hi-lo)*i/(points-1)}) for i in range(points)]
        for name,(lo,hi) in ranges.items()
    }


def score_joint(payoffs: SymmetricPayoffs, row: str | None, column: str | None):
    if row not in ("C", "D") or column not in ("C", "D"):
        return {"valid": False}
    game = payoffs.game()
    profile = (row, column)
    payoff = game.payoff(profile)
    return {
        "valid": True, "profile": list(profile),
        "cooperation_rate": (int(row=="C")+int(column=="C"))/2,
        "mutual_cooperation": row==column=="C", "mutual_defection": row==column=="D",
        "nash": game.is_nash(profile),
        "pareto": profile in game.pareto_efficient_profiles(),
        "welfare_optimal": profile in game.welfare_optimal_profiles(),
        "welfare": payoff.total,
        "normalized_welfare": (payoff.total-2*payoffs.P)/(payoffs.R-payoffs.P),
        "row_regret": game.regret(profile,"row")/(payoffs.R-payoffs.P),
        "column_regret": game.regret(profile,"column")/(payoffs.R-payoffs.P),
    }
