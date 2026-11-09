"""Deterministic, observed-defense oversight game. All decisions use fractions.

The human commits to d in {0, .1, ..., 1}; the AI observes d and chooses
cooperate or attack. Defense protects fraction d of resources and harm and
enforces penalty p*d deterministically (not a detection probability).
Payoffs are (human, AI). Penalties are burned, not transferred to the human.
This is an explicit toy specification, not an empirically calibrated model.
"""

from dataclasses import dataclass, fields
from fractions import Fraction as F
from math import prod

ACTIONS = ("cooperate", "attack")
DEFENSES = tuple(F(i, 10) for i in range(11))


@dataclass(frozen=True)
class Oversight:
    v: F = F(4)   # AI value per captured resource
    r: F = F(1)   # resource quantity available before defense
    a: F = F(1)   # fixed attack cost, paid even at full defense
    p: F = F(3)   # penalty at full defense
    b: F = F(1)   # AI reward for cooperation
    w: F = F(2)   # human benefit from cooperation
    h: F = F(6)   # human harm at zero defense
    c: F = F(2)   # human cost at full defense

    def __post_init__(self):
        for field in fields(self):
            value = F(str(getattr(self, field.name)))
            if value < 0:
                raise ValueError("Payoff parameters must be nonnegative.")
            object.__setattr__(self, field.name, value)

    def payoff(self, d, action):
        d = F(str(d))
        if not 0 <= d <= 1 or action not in ACTIONS:
            raise ValueError("Defense must be in [0, 1]; action must be cooperate or attack.")
        if action == "cooperate":
            return self.w-self.c*d, self.b
        return -self.h*(1-d)-self.c*d, self.v*self.r*(1-d)-self.a-self.p*d

    def margin(self, d):
        """AI cooperation payoff minus attack payoff; zero is an exact tie."""
        return self.payoff(d, "cooperate")[1]-self.payoff(d, "attack")[1]

    def best_responses(self, d):
        margin = self.margin(d)
        return ("cooperate",) if margin > 0 else ("attack",) if margin < 0 else ACTIONS

    def thresholds(self, d):
        """Affine margins as a parameter varies, holding all others fixed.

        A zero slope gives a constant comparison, never a divide-by-zero.
        Roots outside the parameter domain are retained and labeled.
        """
        d = F(str(d))
        self.payoff(d, "cooperate")  # validate defense
        specifications = {
            "d": (self.b+self.a-self.v*self.r, self.v*self.r+self.p, F(1)),
            "v": (self.b+self.a+self.p*d, -self.r*(1-d), None),
            "a": (self.b+self.p*d-self.v*self.r*(1-d), F(1), None),
            "p": (self.b+self.a-self.v*self.r*(1-d), d, None),
        }
        result = {}
        for name, (intercept, slope, upper) in specifications.items():
            root = -intercept/slope if slope else None
            result[name] = {
                "root": root, "intercept": intercept, "slope": slope,
                "in_domain": root is not None and root >= 0 and (upper is None or root <= upper),
                "cooperate_when": "above" if slope > 0 else "below" if slope < 0 else
                    "always" if intercept > 0 else "never" if intercept < 0 else "always_tied",
            }
        return result

    def equilibria(self, defenses=DEFENSES):
        """All pure Nash / subgame-perfect outcomes of the *sequential* game.

        An AI strategy specifies a response at EVERY defense. For a candidate
        (d, action), that action must maximize AI payoff at d. At every other
        defense choose any response giving the human no more than at d.
        For subgame perfection, also restrict those off-path responses to AI
        best responses. Independent allowed response sets encode ALL supporting
        pure strategies, avoiding exponential enumeration. A witness is included.

        Stackelberg commits to one grid defense, with best/worst human payoff
        among tied AI best responses. No hidden or mixed commitment is assumed.
        """
        defenses = tuple(F(str(d)) for d in defenses)
        if not defenses or len(set(defenses)) != len(defenses):
            raise ValueError("Use a nonempty list of distinct defense levels.")
        best = [self.best_responses(d) for d in defenses]

        def outcome(i, action):
            human, ai = self.payoff(defenses[i], action)
            return {"d": defenses[i], "action": action, "human": human, "ai": ai}

        def enumerate_outcomes(credible):
            results = []
            for i, d in enumerate(defenses):
                for action in best[i]:
                    human = self.payoff(d, action)[0]
                    allowed = [([action] if j == i else
                                [a for a in (best[j] if credible else ACTIONS)
                                 if self.payoff(other, a)[0] <= human])
                               for j, other in enumerate(defenses)]
                    if all(allowed):
                        results.append({**outcome(i, action), "responses": allowed,
                                        "witness": [a[0] for a in allowed],
                                        "strategy_count": prod(map(len, allowed))})
            return results

        def commitment(optimistic):
            candidates = []
            for i, d in enumerate(defenses):
                choose = max if optimistic else min
                score = choose(self.payoff(d, a)[0] for a in best[i])
                candidates.extend(outcome(i, a) for a in best[i] if self.payoff(d, a)[0] == score)
            optimum = max(row["human"] for row in candidates)
            return [row for row in candidates if row["human"] == optimum]

        return {"defenses": defenses, "nash": enumerate_outcomes(False),
                "subgame_perfect": enumerate_outcomes(True),
                "stackelberg_favorable": commitment(True),
                "stackelberg_unfavorable": commitment(False)}

    def simulate(self, defenses, baseline, tie_action="cooperate"):
        """Independent, deterministic toy rounds; no learning or LLM calls."""
        if baseline not in ("always_cooperate", "always_attack", "payoff_maximizer"):
            raise ValueError("Unknown baseline.")
        if tie_action not in ACTIONS:
            raise ValueError("Choose cooperate or attack for exact ties.")
        records = []
        for i, d in enumerate(defenses):
            d = F(str(d))
            if d not in DEFENSES:
                raise ValueError("Use one of the 11 defense levels.")
            best = self.best_responses(d)
            action = ("cooperate" if baseline == "always_cooperate" else "attack"
                      if baseline == "always_attack" else best[0] if len(best) == 1 else tie_action)
            human, ai = self.payoff(d, action)
            records.append({"round": i+1, "d": d, "action": action, "human": human, "ai": ai,
                            "best_responses": best, "is_best_response": action in best,
                            "ai_regret": max(self.payoff(d, a)[1] for a in ACTIONS)-ai,
                            "remaining_harm": self.h*(1-d) if action == "attack" else F(0)})
        return records


def exact_json(value):
    """Preserve fractions alongside decimal coordinates used only for drawing."""
    if isinstance(value, F):
        return {"exact": str(value), "value": float(value)}
    if isinstance(value, dict):
        return {key: exact_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact_json(item) for item in value]
    return value
