"""Offline reference cases for the static site's exact browser engine.

Print JSON to stdout for check_browser_engine.cjs. No files, server, network,
credentials, or model calls are needed. Expected values come from the Python
adapters used by the local UI, independently of the JavaScript port.
"""
from collections import defaultdict
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from serve import analyze, canonical_state, oversight_simulation, oversight_state


ADAPTERS = {
    "analyze": analyze,
    "canonicalState": canonical_state,
    "oversightState": oversight_state,
    "oversightSimulation": oversight_simulation,
}
DEFAULT = dict(v="4", r="1", a="1", p="3", b="1", w="2", h="6", c="2", d="0.3")


def cases():
    result = []

    def add(name, method, values):
        pairs = list(values.items()) if isinstance(values, dict) else values
        query = defaultdict(list)
        for key, value in pairs:
            query[key].append(str(value))
        case = {"name": name, "method": method, "query": pairs}
        try:
            case["expected"] = ADAPTERS[method](query)
        except ValueError:
            case["invalid"] = True
        result.append(case)

    for s, t in (("-0.5", "2"), ("-1", "1.5"), ("-0.5", "1.5"), ("-10", "10"), ("-0.001", "1.001")):
        for z in ("0", "0.499999999999", "0.5", "0.500000000001", "1", "1.000000000001", "20"):
            add(f"PD {s}/{t}/{z}", "analyze", dict(s=s, t=t, z=z))

    for game in ("pd", "stag_hunt", "chicken", "battle_of_sexes"):
        for z in ("0", "0.499999999999", "0.5", "0.500000000001", "0.999999999999", "1", "1.000000000001", "2", "2.000000000001", "20"):
            add(f"canonical {game}/{z}", "canonicalState", dict(game=game, z=z))

    states = [{**DEFAULT, "d": str(i/10)} for i in range(11)]
    states.extend([
        # Entirely indifferent game: both responses and supporting strategies.
        {**{k: "0" for k in DEFAULT}, "d": "0.5"},
        {**DEFAULT, "v": "0", "r": "0", "p": "0"},
        # Constant strict attack / cooperation, absent feasible thresholds.
        {**DEFAULT, "r": "0", "a": "0", "b": "0", "p": "0"},
        {**DEFAULT, "v": "1000", "r": "1000", "a": "0", "p": "0", "b": "0", "d": "0"},
        {**DEFAULT, "b": "1000", "v": "0", "p": "0", "d": "1"},
        # Exact tie at .5 with distinct human payoffs and alternative tie choices.
        {**DEFAULT, "v": "4", "r": "1", "a": "1", "p": "0", "b": "1", "d": "0.5"},
        {**DEFAULT, "v": "4.000000000001", "r": "1", "a": "1", "p": "0", "b": "1", "d": "0.5"},
        {**DEFAULT, "v": "3.999999999999", "r": "1", "a": "1", "p": "0", "b": "1", "d": "0.5"},
        # Tiny and large decimal products must not turn exact signs into ties.
        {**{k: "0.000000000001" for k in DEFAULT}, "d": "0.1"},
        {**{k: "1000" for k in DEFAULT}, "d": "0.9"},
    ])
    rng = random.Random(20261109)
    for _ in range(12):
        states.append({**{k: str(rng.randrange(0, 100)/10) for k in DEFAULT if k != "d"}, "d": str(rng.randrange(11)/10)})
    for i, values in enumerate(states):
        add(f"oversight {i}", "oversightState", values)
    for values in (DEFAULT, states[11], states[16]):
        for scope in ("selected", "all"):
            for baseline in ("always_cooperate", "always_attack", "payoff_maximizer"):
                for tie in ("cooperate", "attack"):
                    add(f"simulation {len(result)}", "oversightSimulation", {**values, "scope": scope, "baseline": baseline, "tie": tie})

    for method, valid, field in (("analyze", dict(s="-0.5", t="2", z="0"), "z"),
                                 ("canonicalState", dict(game="pd", z="0"), "z"),
                                 ("oversightState", DEFAULT, "v"),
                                 ("oversightSimulation", {**DEFAULT, "scope": "all", "baseline": "payoff_maximizer", "tie": "attack"}, "v")):
        for value in ("", "NaN", "Infinity", "-1", "1001", "1/2", "0.0000000000001", "0e13", "1"*33, "hello"):
            add(f"invalid {method}/{value}", method, {**valid, field: value})
        add(f"missing {method}", method, {k: v for k, v in valid.items() if k != field})
        add(f"extra {method}", method, {**valid, "extra": "1"})
        add(f"duplicate {method}", method, list(valid.items())+[(field, valid[field])])
    add("invalid defense grid", "oversightState", {**DEFAULT, "d": "0.25"})
    add("unknown game", "canonicalState", dict(game="__proto__", z="0"))
    for values in (dict(scope="wrong"), dict(baseline="unknown"), dict(tie="invalid")):
        add("invalid simulation selector", "oversightSimulation", {**DEFAULT, "scope": "all", "baseline": "payoff_maximizer", "tie": "attack", **values})
    for value in ("1e-2", "+1.0", " 1.0 ", "0_._1", "0E-12", "-0"):
        add(f"decimal spelling {value}", "canonicalState", dict(game="pd", z=value))
    return result


if __name__ == "__main__":
    print(json.dumps(cases(), default=float, separators=(",", ":"), allow_nan=False))
