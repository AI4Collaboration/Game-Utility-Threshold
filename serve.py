"""Read-only local view of the post's two conditional payoff comparisons."""

import argparse
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gut.game import Game
from gut.canonical import example
from gut.oversight import ACTIONS, DEFENSES, Oversight, exact_json

ROOT = Path(__file__).resolve().parent
REGIONS = {
    "defection_dominant": ("Defection pays against either action", "This is the strict Prisoner's Dilemma region."),
    "cooperation_dominant": ("Cooperation pays against either action", "Both conditional thresholds have been crossed."),
    "chicken": ("Chicken: opposite actions pay", "Cooperate against D; defect against C."),
    "stag_hunt": ("Stag Hunt: matching actions pay", "Cooperate against C; defect against D."),
    "boundary": ("At a threshold", "At least one comparison is an exact tie. Both actions are optimal in that comparison."),
}


def number(text, low, high):
    if len(text) > 32:
        raise ValueError("Use a short decimal number.")
    try:
        value = Decimal(text)
        if not value.is_finite() or not low <= value <= high:
            raise ValueError(f"Value must be between {low} and {high}.")
        if not -12 <= value.as_tuple().exponent <= 12:
            raise ValueError("Use at most 12 decimal places.")
        return Fraction(value)
    except InvalidOperation as exc:
        raise ValueError("Enter a decimal number.") from exc


def analyze(query):
    """Small UI adapter; every payoff and threshold comes from Game."""
    if set(query) != {"s", "t", "z"} or any(len(v) != 1 for v in query.values()):
        raise ValueError("Supply exactly one s, t and z.")
    s = number(query["s"][0], Decimal("-10"), Decimal("-0.001"))
    t = number(query["t"][0], Decimal("1.001"), Decimal("10"))
    z = number(query["z"][0], Decimal("0"), Decimal("20"))
    game = Game(t=t, s=s)
    thresholds = game.thresholds()
    maximum = max(Fraction(3, 2), max(thresholds)*Fraction(13, 10), z*Fraction(11, 10))
    coordinates = sorted({maximum*i/60 for i in range(61)} | set(thresholds) | {z})
    series = [{"key": key, "label": label,
               "points": [{"x": float(x), "y": float(game.margins(x)[i])} for x in coordinates]}
              for i, (key, label) in enumerate((("against_c", "Against C"), ("against_d", "Against D")))]
    values = [p["y"] for line in series for p in line["points"]]
    pad = max((max(values)-min(values))*0.12, 0.1)
    def record(value):
        return {"value": float(value), "exact": str(value)}
    margins = {key: {**record(margin), "response": "cooperate" if margin > 0 else "defect" if margin < 0 else "tie"}
               for key, margin in zip(("against_c", "against_d"), game.margins(z))}
    label, description = REGIONS[game.region(z)]
    return {
        "inputs": {"s": float(s), "t": float(t), "z": float(z)},
        "matrices": {"baseline": game.matrix(), "adjusted": game.matrix(z)},
        "margins": margins,
        "thresholds": dict(zip(("against_c", "against_d"), map(record, thresholds))),
        "region": {"label": label, "description": description},
        "plot": {"x_min": 0, "x_max": float(maximum), "y_min": min(values)-pad,
                 "y_max": max(values)+pad, "series": series},
    }


def canonical_state(query):
    if set(query) != {"game", "z"} or any(len(v) != 1 for v in query.values()):
        raise ValueError("Supply exactly one game and z.")
    game = example(query["game"][0])
    z = number(query["z"][0], Decimal("0"), Decimal("20"))
    comparisons = []
    for role in ("row", "column"):
        for i, (margin, threshold) in enumerate(zip(game.margins(role, z), game.thresholds(role))):
            comparisons.append({"role": role, "against": game.actions[i], "margin": str(margin),
                                "value": float(margin), "threshold": str(threshold), "tie_at": float(threshold),
                                "best": game.actions[0] if margin > 0 else game.actions[1] if margin < 0 else "tie"})
    maximum = max(Fraction(3, 2), z*Fraction(11, 10),
                  *(t*Fraction(6, 5) for role in ("row", "column") for t in game.thresholds(role)))
    lines = [{"role": row["role"], "against": row["against"], "start": -row["tie_at"],
              "end": float(maximum)-row["tie_at"]} for row in comparisons]
    values = [v for line in lines for v in (line["start"], line["end"])]
    def exact(matrix):
        return [[[str(v) for v in cell] for cell in row] for row in matrix]
    return {"name": game.name, "actions": game.actions, "description": game.explanation, "z": float(z),
            "baseline": game.matrix(), "adjusted": game.matrix(z), "comparisons": comparisons,
            "baseline_exact": exact(game.matrix()), "adjusted_exact": exact(game.matrix(z)),
            "stable_outcomes": [game.actions[i]+game.actions[j] for i, j in game.stable_outcomes(z)],
            "plot": {"xmax": float(maximum), "ymin": min(values)-0.2, "ymax": max(values)+0.2, "lines": lines}}


def oversight_inputs(query, simulation=False):
    keys = set(Oversight.__dataclass_fields__) | {"d"}
    if simulation:
        keys |= {"baseline", "tie", "scope"}
    if set(query) != keys or any(len(values) != 1 for values in query.values()):
        raise ValueError("Supply exactly one value for each oversight input.")
    game = Oversight(**{key: number(query[key][0], Decimal(0), Decimal(1000))
                       for key in Oversight.__dataclass_fields__})
    d = number(query["d"][0], Decimal(0), Decimal(1))
    if d not in DEFENSES:
        raise ValueError("Choose defense 0, 0.1, …, 1 (eleven available levels).")
    return game, d


def oversight_state(query):
    game, d = oversight_inputs(query)
    thresholds = game.thresholds(d)
    root = thresholds["d"]["root"]
    points = sorted(set(DEFENSES) | ({root} if thresholds["d"]["in_domain"] else set()))
    rows = [{"d": x, "human_c": game.payoff(x, "cooperate")[0],
             "human_a": game.payoff(x, "attack")[0], "ai_c": game.b,
             "ai_a": game.payoff(x, "attack")[1], "margin": game.margin(x),
             "best": game.best_responses(x)} for x in points]
    # A theoretical 21x21 parameter map, not observations. Only v and p vary.
    vmax, pmax = max(Fraction(10), game.v*Fraction(6, 5)), max(Fraction(10), game.p*Fraction(6, 5))
    cells = []
    for j in range(21):
        for i in range(21):
            v, p = vmax*i/20, pmax*j/20
            alternative = Oversight(**{**game.__dict__, "v": v, "p": p})
            cells.append({"i": i, "j": j, "v": v, "p": p,
                          "margin": alternative.margin(d), "best": alternative.best_responses(d)})
    strict = [x for x in DEFENSES if game.margin(x) > 0]
    weak = [x for x in DEFENSES if game.margin(x) >= 0]
    return exact_json({"parameters": game.__dict__, "d": d,
                       "selected": {"cooperate": game.payoff(d, "cooperate"),
                                    "attack": game.payoff(d, "attack"), "margin": game.margin(d),
                                    "best": game.best_responses(d)},
                       "thresholds": thresholds, "first_strict_defense": min(strict) if strict else None,
                       "first_weak_defense": min(weak) if weak else None,
                       "equilibria": game.equilibria(), "curve": rows,
                       "map": {"vmax": vmax, "pmax": pmax, "cells": cells}})


def oversight_simulation(query):
    game, d = oversight_inputs(query, simulation=True)
    scope = query["scope"][0]
    if scope not in ("selected", "all"):
        raise ValueError("Choose selected or all defense levels.")
    baseline, tie = query["baseline"][0], query["tie"][0]
    records = game.simulate([d] if scope == "selected" else DEFENSES, baseline, tie)
    return exact_json({"schema": "oversight-toy-v1", "synthetic": True,
                       "description": "Independent deterministic toy rounds; no learning, randomness or LLM calls.",
                       "parameters": game.__dict__, "selected_defense": d, "scope": scope,
                       "baseline": baseline, "tie_action": tie, "records": records,
                       "summary": {"rounds": len(records),
                                   "cooperate_count": sum(r["action"] == "cooperate" for r in records),
                                   "mean_human": sum(r["human"] for r in records)/len(records),
                                   "mean_ai": sum(r["ai"] for r in records)/len(records)}})


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            self.reply(403, b"Local requests only.", "text/plain")
            return
        try:
            url = urlsplit(self.path)
        except ValueError:
            self.reply(400, b"Invalid request URL.", "text/plain")
            return
        if url.path == "/api/game":
            try:
                result = analyze(parse_qs(url.query, keep_blank_values=True, max_num_fields=3))
                self.reply(200, json.dumps(result, default=float).encode(), "application/json")
            except ValueError as exc:
                self.reply(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        if url.path == "/api/canonical":
            try:
                result = canonical_state(parse_qs(url.query, keep_blank_values=True, max_num_fields=2))
                self.reply(200, json.dumps(result, default=float).encode(), "application/json")
            except ValueError as exc:
                self.reply(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        if url.path in ("/api/oversight", "/api/oversight/simulate"):
            try:
                simulation = url.path.endswith("/simulate")
                query = parse_qs(url.query, keep_blank_values=True, max_num_fields=12 if simulation else 9)
                result = oversight_simulation(query) if simulation else oversight_state(query)
                self.reply(200, json.dumps(result).encode(), "application/json")
            except ValueError as exc:
                self.reply(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        allowed = {"/": ROOT / "web/index.html", "/games": ROOT / "web/games.html",
                   "/oversight": ROOT / "web/oversight.html", "/oversight.js": ROOT / "web/oversight.js"}
        validation = ROOT / "data/oversight/2026-11-09/analysis"
        validation_names = ["report.html", "summary.json", "cells.csv", "blocks.csv", "observations.csv"]
        validation_names += [f"{name}.{extension}" for name in
                             ("sweep-defense", "framing", "presentation-blocks", "confusion")
                             for extension in ("svg", "png")]
        allowed.update({f"/validation/{name}": validation / name for name in validation_names})
        report_names = ["index.html", "summary.json", "cells.csv", "regions.csv", "theory-grid.csv"]
        report_names += [f"figure-{i}.{suffix}" for i in range(1, 6) for suffix in ("svg", "png")]
        allowed.update({f"/report/{name}": ROOT / "report" / name for name in report_names})
        path = allowed.get(url.path)
        directory = ROOT.resolve() / ("data/oversight/2026-11-09/analysis" if url.path.startswith("/validation/") else
                                      "web" if url.path in ("/", "/games", "/oversight", "/oversight.js") else "report")
        if path is None or not path.resolve().is_relative_to(directory) or not path.is_file():
            self.reply(404, b"Not found. See README for report generation commands.", "text/plain")
            return
        content_type = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                        ".json": "application/json", ".csv": "text/csv; charset=utf-8",
                        ".js": "text/javascript; charset=utf-8"}[path.suffix]
        self.reply(200, path.read_bytes(), content_type)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Open http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
