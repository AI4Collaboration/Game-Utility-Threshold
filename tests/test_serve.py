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


def query(s="-0.5", t="2", z="0"):
    return {"s": [s], "t": [t], "z": [z]}


class AdapterTests(unittest.TestCase):
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
            (root / ".env").write_text("private fixture value")
            (root / "report/index.html").symlink_to(root / ".env")
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
