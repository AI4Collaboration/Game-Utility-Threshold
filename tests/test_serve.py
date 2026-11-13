"""Small checks that the HTTP view faithfully exposes the one-shot model."""

from fractions import Fraction as F
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from gut import Game
import serve
from gut.oversight import Oversight


def query(s="-0.5", t="2", z="0"):
    return {"s": [s], "t": [t], "z": [z]}


def oversight_query(**changes):
    return {k: [str(v)] for k, v in {**Oversight().__dict__, "d": "0.3", **changes}.items()}


class AdapterTests(unittest.TestCase):
    def test_oversight_api_keeps_exact_values_and_map_agrees(self):
        result = serve.oversight_state(oversight_query())
        self.assertEqual(result["thresholds"]["d"]["root"]["exact"], "2/7")
        self.assertEqual(result["selected"]["best"], ["cooperate"])
        self.assertEqual(result["first_strict_defense"]["exact"], "3/10")
        self.assertEqual(result["equilibria"]["stackelberg_favorable"][0]["d"]["exact"], "3/10")
        for cell in result["map"]["cells"]:
            game = Oversight(v=cell["v"]["exact"], p=cell["p"]["exact"])
            self.assertEqual(cell["best"], list(game.best_responses(F(3, 10))))
        zero = serve.oversight_state(oversight_query(**{k: 0 for k in Oversight.__dataclass_fields__}))
        self.assertIsNone(zero["thresholds"]["d"]["root"])
        self.assertIsNone(zero["first_strict_defense"])
        self.assertEqual(zero["first_weak_defense"]["exact"], "0")

    def test_oversight_simulation_is_labeled_and_retains_payoffs(self):
        for baseline in ("always_cooperate", "always_attack", "payoff_maximizer"):
            result = serve.oversight_simulation(oversight_query(baseline=baseline, tie="attack", scope="all"))
            self.assertTrue(result["synthetic"])
            self.assertEqual(len(result["records"]), 11)
            for row in result["records"]:
                human, ai = Oversight().payoff(row["d"]["exact"], row["action"])
                self.assertEqual(F(row["human"]["exact"]), human)
                self.assertEqual(F(row["ai"]["exact"]), ai)
        result = serve.oversight_simulation(oversight_query(p=0, d="0.5", baseline="payoff_maximizer", tie="attack", scope="selected"))
        self.assertEqual(result["summary"]["rounds"], 1)
        self.assertEqual(result["records"][0]["action"], "attack")
        self.assertEqual(result["records"][0]["ai_regret"]["exact"], "0")

    def test_oversight_rejects_invalid_inputs(self):
        for key in Oversight.__dataclass_fields__:
            for value in ("-1", "1001", "NaN", "Infinity", "1e999", "1e-99", ""):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    serve.oversight_state(oversight_query(**{key: value}))
        for value in ("0.05", "1.1", "-0.1"):
            with self.assertRaises(ValueError):
                serve.oversight_state(oversight_query(d=value))
        with self.assertRaises(ValueError):
            serve.oversight_state({**oversight_query(), "d": ["0", "1"]})
        for key, value in (("scope", "random"), ("tie", "random"), ("baseline", "unknown")):
            args = dict(scope="all", tie="cooperate", baseline="always_attack")
            args[key] = value
            with self.assertRaises(ValueError):
                serve.oversight_simulation(oversight_query(**args))

    def test_both_post_paths_match_game_before_at_and_after_each_threshold(self):
        for s, t in (("-0.5", "2"), ("-1", "1.5")):
            game = Game(s=s, t=t)
            thresholds = game.thresholds()
            for z in ("0", "0.499", "0.5", "0.75", "0.999", "1", "1.001"):
                with self.subTest(s=s, t=t, z=z):
                    result = serve.analyze(query(s, t, z))
                    self.assertEqual(result["matrices"]["baseline"], game.matrix())
                    self.assertEqual(result["matrices"]["adjusted"], game.matrix(z))
                    self.assertEqual(result["region"]["label"], serve.REGIONS[game.region(z)][0])
                    for index, key in enumerate(("against_c", "against_d")):
                        margin = game.margins(z)[index]
                        response = "cooperate" if margin > 0 else "defect" if margin < 0 else "tie"
                        self.assertEqual(result["margins"][key], {
                            "exact": str(margin), "value": float(margin), "response": response})
                        self.assertEqual(F(result["thresholds"][key]["exact"]), thresholds[index])
                        points = result["plot"]["series"][index]["points"]
                        self.assertIn({"x": float(thresholds[index]), "y": 0.0}, points)

    def test_invalid_and_duplicate_query_values_are_rejected(self):
        for invalid in ("NaN", "Infinity", "-Infinity", "1e999", "", "true"):
            for key in ("s", "t", "z"):
                with self.subTest(invalid=invalid, key=key), self.assertRaises(ValueError):
                    serve.analyze({**query(), key: [invalid]})
        for invalid in ({"s": ["-0.5"], "t": ["2"]},
                        {**query(), "q": ["0.5"]},
                        {**query(), "s": ["-0.5", "-1"]},
                        query(s="0"), query(t="1"), query(z="-1")):
            with self.subTest(query=invalid), self.assertRaises(ValueError):
                serve.analyze(invalid)


class HTTPTests(unittest.TestCase):
    def test_local_page_api_and_file_isolation(self):
        with TemporaryDirectory() as directory, patch.object(serve, "ROOT", Path(directory)):
            root = Path(directory)
            (root / "web").mkdir()
            (root / "report").mkdir()
            (root / "web/index.html").write_text("<h1>Thresholds</h1>")
            (root / "web/oversight.html").write_text("<h1>Oversight</h1>")
            (root / "web/oversight.js").write_text("'use strict';")
            (root / "web/games.html").write_text("<h1>Games</h1>")
            (root / "web/results.html").write_text("<h1>Results</h1>")
            (root / "web/game-engine.js").write_text("globalThis.GutEngine = {};")
            (root / "web/science.html").write_text("<h1>Science audit</h1>")
            (root / "web/science.css").write_text("body{margin:0}")
            (root / "web/science.js").write_text("'use strict';")
            (root / "web/science-engine.js").write_text("globalThis.ScienceGame = {};")
            (root / "data/oversight/2026-11-09/analysis").mkdir(parents=True)
            (root / "data/oversight/2026-11-09/analysis/report.html").write_text("<h1>Validation</h1>")
            (root / ".env").write_text("private fixture value")
            (root / "report/index.html").symlink_to(root / ".env")
            (root / "_site/docs").mkdir(parents=True)
            (root / "_site/docs/methods.md").write_text("Public methods")
            (root / "_site/unlisted.txt").write_text("Not published")
            (root / "_site/private.txt").symlink_to(root / ".env")
            (root / "_site/site-manifest.json").write_text(json.dumps({
                "schema": "gut-pages-v1", "files": {
                    "docs/methods.md": "fixture", "private.txt": "fixture", "../.env": "fixture"}}))
            with ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()

                def get(path, raw_target=False):
                    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                    try:
                        if raw_target:
                            # Bypass only the client's URL parsing to exercise
                            # the server's malformed-request handling.
                            connection.putrequest("GET", path, skip_host=True)
                            connection.putheader("Host", f"127.0.0.1:{server.server_port}")
                            connection.endheaders()
                        else:
                            connection.request("GET", path)
                        response = connection.getresponse()
                        return response.status, dict(response.getheaders()), response.read()
                    finally:
                        connection.close()

                try:
                    status, headers, body = get("/")
                    self.assertEqual(status, 200)
                    self.assertEqual(body, b"<h1>Thresholds</h1>")
                    self.assertEqual(headers["Cache-Control"], "no-store")
                    status, _, body = get("/api/game?s=-0.5&t=2&z=0.5")
                    self.assertEqual(status, 200)
                    result = json.loads(body)
                    self.assertEqual(result["margins"]["against_d"]["response"], "tie")
                    self.assertEqual(result["thresholds"]["against_d"]["exact"], "1/2")
                    status, _, body = get("/api/canonical?game=battle_of_sexes&z=1")
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body)["stable_outcomes"], ["XX", "YY"])
                    self.assertEqual(get("/api/canonical?game=unknown&z=0")[0], 400)
                    params = "v=4&r=1&a=1&p=3&b=1&w=2&h=6&c=2&d=0.3"
                    status, _, body = get("/api/oversight?"+params)
                    self.assertEqual(status, 200)
                    self.assertEqual(json.loads(body)["selected"]["best"], ["cooperate"])
                    status, _, body = get("/api/oversight/simulate?"+params+"&baseline=always_attack&tie=attack&scope=all")
                    self.assertEqual(status, 200)
                    self.assertTrue(json.loads(body)["synthetic"])
                    self.assertEqual(get("/api/oversight?"+params+"&d=0")[0], 400)
                    self.assertEqual(get("/api/oversight?")[0], 400)
                    self.assertEqual(get("/oversight")[0], 200)
                    self.assertEqual(get("/science")[0], 200)
                    for page in ("science.html", "science.js", "science-engine.js"):
                        self.assertEqual(get("/"+page)[0], 200)
                    self.assertIn("text/css", get("/science.css")[1]["Content-Type"])
                    for page in ("index.html", "games.html", "oversight.html", "results.html", "game-engine.js"):
                        self.assertEqual(get("/"+page)[0], 200)
                    status, headers, _ = get("/oversight.js")
                    self.assertEqual(status, 200)
                    self.assertIn("text/javascript", headers["Content-Type"])
                    self.assertEqual(get("/validation/report.html")[0], 200)
                    self.assertEqual(get("/docs/methods.md")[2], b"Public methods")
                    self.assertEqual(get("/site-manifest.json")[0], 200)
                    for path in ("/private.txt", "/unlisted.txt", "/_site/site-manifest.json"):
                        self.assertEqual(get(path)[0], 404)
                    self.assertEqual(get("/validation/../../.env")[0], 404)
                    for path in ("/.env", "/../.env", "/%2e%2e/.env", "/web/index.html", "/report/index.html"):
                        status, _, body = get(path)
                        self.assertEqual(status, 404)
                        self.assertNotIn(b"private fixture value", body)
                    for path in ("/api/game?s=-0.5&t=2&z=NaN",
                                 "/api/game?s=-0.5&s=-1&t=2&z=0",
                                 "/api/game?s=-0.5&t=2&cost=0"):
                        status, _, body = get(path)
                        self.assertEqual(status, 400)
                        self.assertIn("error", json.loads(body))
                    self.assertEqual(get("http://[", raw_target=True)[0], 400)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
