"""Read-only local view of the post's two conditional payoff comparisons."""

import argparse
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gut.game import Game

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
        allowed = {"/": ROOT / "web/index.html"}
        report_names = ["index.html", "summary.json", "cells.csv", "regions.csv", "theory-grid.csv"]
        report_names += [f"figure-{i}.{suffix}" for i in range(1, 6) for suffix in ("svg", "png")]
        allowed.update({f"/report/{name}": ROOT / "report" / name for name in report_names})
        path = allowed.get(url.path)
        directory = ROOT.resolve() / ("web" if url.path == "/" else "report")
        if path is None or not path.resolve().is_relative_to(directory) or not path.is_file():
            self.reply(404, b"Not found. Build the report with: python3 reproduce.py", "text/plain")
            return
        content_type = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                        ".json": "application/json", ".csv": "text/csv; charset=utf-8"}[path.suffix]
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
