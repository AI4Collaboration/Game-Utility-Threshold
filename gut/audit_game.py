"""Two-target, one-inspection subcase of Blocki et al., Audit Games, §2.

https://arxiv.org/html/1303.0356
Punishment is fixed per game. The documented no-violation option is included.
Our extension: finite private reward types with a publicly known prior, using
the Bayesian commitment structure of Paruchuri et al. (AAMAS 2008).
Demo numbers are ours, NOT values reproduced from a published experiment.
"""

from dataclasses import dataclass
from fractions import Fraction as F

from gut.commitment import CommitmentGame, crossings, rational, value

ACTIONS = ("abstain", "target_a", "target_b")
SCHEMA = "gut-audit-game-v2"


@dataclass(frozen=True)
class RewardType:
    name: str
    prior: F
    unchecked: tuple
    checked: tuple

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Each reward type needs a name.")
        object.__setattr__(self, "prior", rational(self.prior))
        for field in ("unchecked", "checked"):
            object.__setattr__(self, field, tuple(map(rational, getattr(self, field))))
        if len(self.unchecked) != 2 or len(self.checked) != 2:
            raise ValueError("Exactly two target rewards are required.")
        if any(u <= a for u, a in zip(self.unchecked, self.checked)):
            raise ValueError("Unchecked rewards must exceed checked rewards, as in the source model.")


@dataclass(frozen=True)
class AuditGame:
    types: tuple
    punishment: F = F(1, 2)
    punishment_cost: F = F(1, 10)
    defender_unchecked: tuple = (F(-1), F(-6, 5))
    defender_checked: tuple = (F(-1, 10), F(-1, 5))

    def __post_init__(self):
        object.__setattr__(self, "types", tuple(self.types))
        for field in ("punishment", "punishment_cost"):
            object.__setattr__(self, field, rational(getattr(self, field)))
        for field in ("defender_unchecked", "defender_checked"):
            object.__setattr__(self, field, tuple(map(rational, getattr(self, field))))
        if not 0 <= self.punishment <= 1 or self.punishment_cost <= 0:
            raise ValueError("Punishment must be in [0,1] and its setting cost strictly positive.")
        if (not self.types or len({t.name for t in self.types}) != len(self.types)
                or any(t.prior < 0 for t in self.types) or sum(t.prior for t in self.types) != 1):
            raise ValueError("Use distinct types with nonnegative priors summing to one.")
        if len(self.defender_unchecked) != 2 or len(self.defender_checked) != 2:
            raise ValueError("Exactly two defender target rewards are required.")
        if any(a <= u for a, u in zip(self.defender_checked, self.defender_unchecked)):
            raise ValueError("A detected violation must be better for the defender than an undetected one.")

    def type(self, name):
        for kind in self.types:
            if kind.name == name:
                return kind
        raise ValueError("Unknown private reward type.")

    def commitment(self):
        leader, follower = [], []
        cost = self.punishment_cost * self.punishment
        for kind in self.types:
            follower.append(((0, kind.checked[0]-self.punishment, kind.unchecked[1]),
                             (0, kind.unchecked[0], kind.checked[1]-self.punishment)))
            leader.append(((-cost, self.defender_checked[0]-cost, self.defender_unchecked[1]-cost),
                           (-cost, self.defender_unchecked[0]-cost, self.defender_checked[1]-cost)))
        return CommitmentGame([t.prior for t in self.types], follower, leader)

    def evaluate(self, q):
        result = self.commitment().evaluate(q)
        for kind, row in zip(self.types, result["types"]):
            row["name"] = kind.name
            row["margin"] = -max(row["follower"][1:])
            row["best_responses"] = tuple(ACTIONS[a] for a in row["best_responses"])
        result["worst_margin"] = min(t["margin"] for t in result["types"])
        result["attack_probability"] = {
            "lower": sum((t["prior"] for t in result["types"] if "abstain" not in t["best_responses"]), F(0)),
            "upper": sum((t["prior"] for t in result["types"] if any(a != "abstain" for a in t["best_responses"])), F(0))}
        return result

    def safe_region(self, slack=0):
        """Exact closed interval where all declared types prefer abstention
        weakly by at least slack. Includes zero-prior types in the robust set.
        With slack zero, boundaries may be ties, NOT guaranteed abstention.
        """
        slack = rational(slack)
        if slack < 0:
            raise ValueError("Requested safety slack must be nonnegative.")
        low, high = F(0), F(1)
        engine = self.commitment()
        for kind in range(len(self.types)):
            for intercept, slope in engine.lines("follower", kind)[1:]:
                if slope == 0:
                    if intercept > -slack:
                        return {"feasible": False, "slack": slack, "interval": None}
                elif slope > 0:
                    high = min(high, (-slack-intercept)/slope)
                else:
                    low = max(low, (-slack-intercept)/slope)
        return {"feasible": low <= high, "slack": slack,
                "interval": (low, high) if low <= high else None}

    def safety_optimum(self):
        engine = self.commitment()
        lines = [line for k in range(len(self.types)) for line in engine.lines("follower", k)[1:]]
        scores = {q: -max(value(line, q) for line in lines) for q in crossings(lines)}
        best = max(scores.values())
        return {"margin": best, "witnesses": sorted(q for q, score in scores.items() if score == best),
                "strict_deterrence_feasible": best > 0}

    def thresholds(self):
        """Type/target checking-probability roots. Never clip infeasible roots."""
        return [{"type": t.name, "target": ACTIONS[i+1],
                 "checking_probability": t.unchecked[i]/(t.unchecked[i]-t.checked[i]+self.punishment),
                 "in_domain": 0 <= t.unchecked[i]/(t.unchecked[i]-t.checked[i]+self.punishment) <= 1}
                for t in self.types for i in range(2)]

    def mean_game(self):
        """A descriptive average only, never the revealed-information condition."""
        mean = RewardType("mean", 1,
                          tuple(sum(t.prior*t.unchecked[i] for t in self.types) for i in range(2)),
                          tuple(sum(t.prior*t.checked[i] for t in self.types) for i in range(2)))
        return AuditGame((mean,), self.punishment, self.punishment_cost,
                         self.defender_unchecked, self.defender_checked)

    def information_game(self, information, name):
        """Defender's information at commitment; realized rewards never change."""
        kind = self.type(name)
        if information == 'hidden':
            return self
        if information != 'revealed':
            raise ValueError('Use revealed or hidden information.')
        return AuditGame((RewardType(kind.name, 1, kind.unchecked, kind.checked),),
                         self.punishment, self.punishment_cost,
                         self.defender_unchecked, self.defender_checked)

    def coverage_grid(self, distance=F(1, 50)):
        """Only q varies: include exact response boundaries and their neighbors."""
        distance = rational(distance)
        if not 0 < distance < 1:
            raise ValueError('Use a boundary distance between zero and one.')
        roots = {F(0), F(1), F(1, 2)}
        engine = self.commitment()
        for k in range(len(self.types)):
            for q in crossings(engine.lines('follower', k)):
                if len(engine.evaluate(q)['types'][k]['best_responses']) > 1:
                    roots.add(q)
        return tuple(sorted({q+d for q in roots for d in (-distance, F(0), distance)
                             if 0 <= q+d <= 1}))

    def defender_view(self):
        """Public prior and possible tables; never the drawn private type."""
        return {"schema": SCHEMA, "actions": ACTIONS, "punishment": str(self.punishment),
                "punishment_cost": str(self.punishment_cost),
                "defender_unchecked": list(map(str, self.defender_unchecked)),
                "defender_checked": list(map(str, self.defender_checked)),
                "possible_types": [{"name": t.name, "prior": str(t.prior),
                                    "unchecked": list(map(str, t.unchecked)),
                                    "checked_before_punishment": list(map(str, t.checked))} for t in self.types]}

    def attacker_view(self, q, name):
        q = self.evaluate(q)["q"]
        kind = self.type(name)
        return {"public_rules": self.defender_view(), "private_type": kind.name,
                "checking_probabilities": [str(q), str(1-q)]}

    def sample(self, q, name, action, rng):
        """Exactly one seeded inspection; checking does not undo a violation.
        Draw occurs after the choice and is absent from both player views.
        Punishment-setting cost is paid even when the attacker abstains.
        """
        q = self.evaluate(q)["q"]
        kind = self.type(name)
        if action not in ACTIONS:
            raise ValueError("Unknown action; invalid outputs are not abstention.")
        inspected = 0 if rng.randrange(q.denominator) < q.numerator else 1
        defender = -self.punishment_cost*self.punishment
        attacker, caught = F(0), False
        if action != "abstain":
            target = ACTIONS.index(action)-1
            caught = target == inspected
            attacker = kind.checked[target]-self.punishment if caught else kind.unchecked[target]
            defender += self.defender_checked[target] if caught else self.defender_unchecked[target]
        return {"inspected_target": ACTIONS[inspected+1], "action": action,
                "violation": action != "abstain", "caught": caught,
                "undetected_violation": action != "abstain" and not caught,
                "defender_payoff": defender, "attacker_payoff": attacker}


def demo_game(setting="hidden", punishment="1/2", spread="3/10", actual_type="high"):
    """Fixed low/high population; revealed conditions condition on an actual type.

    `known` is a UI compatibility alias for `revealed`. It no longer substitutes
    a mean-reward agent. Experiments start from the full hidden population and
    match BOTH information conditions on each exact same realized reward type.
    """
    spread = rational(spread)
    if setting not in ("known", "revealed", "hidden") or not 0 <= spread <= F(7, 20):
        raise ValueError("Use revealed/hidden and spread in [0, 0.35].")
    checked, mean = (F(-1, 2), F(-3, 5)), (F(1, 2), F(2, 5))
    types = tuple(RewardType(name, F(1, 2), tuple(v+sign*spread for v in mean), checked)
                  for name, sign in (("low", -1), ("high", 1)))
    game = AuditGame(types, punishment=punishment)
    return game if setting == 'hidden' else game.information_game('revealed', actual_type)
