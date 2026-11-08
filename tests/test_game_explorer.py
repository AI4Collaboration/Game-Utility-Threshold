"""Scientific invariants and the local explorer's HTTP isolation contract."""

from decimal import Decimal
from fractions import Fraction
from http.client import HTTPConnection
import json
from pathlib import Path
import threading

import pytest

from serve_game_explorer import ExplorerServer, MAX_BODY_BYTES, strict_json
from utility_threshold.game_explorer import analyze, catalog
from utility_threshold.games.scenarios import SCENARIOS
from utility_threshold.research_design import default_config, game_at, matrix_record


def request(**updates):
    return {"game": "prisoners_dilemma", "basis": "paper", "axis": "q",
            "value": 0.5, "q": 0.5, "role": "row", **updates}


def flat(matrix):
    return [v for row in matrix for pair in row for v in pair]


def test_catalog_defaults_and_all_declared_axes_are_usable():
    metadata = catalog()
    assert metadata["data_status"] == "THEORY ONLY"
    assert analyze(metadata["defaults"])["axis"] == "temptation"
    assert len(metadata["games"]) == 4
    for game in metadata["games"]:
        for basis, preset in game["bases"].items():
            for axis in preset["axes"]:
                for x in (axis["min"], axis["default"], axis["max"]):
                    result = analyze(request(game=game["id"], basis=basis, axis=axis["id"], value=x))
                    assert result["schema_version"] == 1
                    assert result["data_status"] == "THEORY ONLY"
                    assert len(result["curve"]["points"]) >= 101
                    # All public values are standard JSON and finite.
                    json.dumps(result, allow_nan=False)
    metadata["games"][0]["actions"][0] = "edited"
    assert catalog()["games"][0]["actions"][0] == "Cooperate"


@pytest.mark.parametrize("scenario", list(SCENARIOS.values()), ids=list(SCENARIOS))
@pytest.mark.parametrize("intervention", [0, 0.1, 0.375, 1])
def test_canonical_constructor_matrix_and_catastrophe_parity(scenario, intervention):
    result = analyze(request(game=scenario.family, basis="canonical", axis="intervention", value=intervention))
    original = scenario.game(intervention)
    assert flat(result["matrix"]) == pytest.approx(flat(matrix_record(original)))
    assert result["action_ids"] == list(original.actions)
    for cell in result["cells"]:
        profile = tuple(original.actions[cell[side]] for side in ("row", "column"))
        assert cell["catastrophic"] == (profile in original.catastrophic_profiles)
        assert cell["pure_equilibrium"] == original.is_nash(profile)


@pytest.mark.parametrize("arm", default_config([])["arms"], ids=lambda arm: arm["arm_id"])
def test_paper_presets_reproduce_research_design(arm):
    aliases = {"t": "temptation", "s": "exploitation", "action_cost": "intervention", "q": "q"}
    for value in arm["values"]:
        result = analyze(request(game=arm["family"], axis=aliases[arm["axis"]], value=value, q=arm["q"]))
        assert flat(result["matrix"]) == pytest.approx(flat(matrix_record(game_at(arm, value))))


@pytest.mark.parametrize("basis", ["paper", "canonical"])
@pytest.mark.parametrize("q", [0, 0.25, 0.5, 0.75, 1])
def test_strict_pd_payoff_ranges_never_create_a_selfish_switch(basis, q):
    pd = catalog()["games"][0]
    for axis in pd["bases"][basis]["axes"]:
        if axis["id"] == "intervention":
            continue
        result = analyze(request(basis=basis, axis=axis["id"], value=axis["default"], q=q))
        assert result["threshold"]["kind"] in {"none", "outside"}
        assert not result["threshold"]["inside_range"]
        assert all(point["best_actions"] == [1] and point["margin"] < 0
                   for point in result["curve"]["points"])


@pytest.mark.parametrize("game,basis,role,root", [
    ("chicken", "paper", "row", "1/2"),
    ("stag_hunt", "paper", "row", "1/2"),
    ("chicken", "canonical", "row", "21/23"),
    ("stag_hunt", "canonical", "row", "2/3"),
    ("battle_of_the_sexes", "paper", "row", "11/23"),
    ("battle_of_the_sexes", "paper", "column", "12/23"),
    ("battle_of_the_sexes", "canonical", "row", "11/23"),
    ("battle_of_the_sexes", "canonical", "column", "12/23"),
])
def test_q_crossings_include_exact_rational_ties(game, basis, role, root):
    result = analyze(request(game=game, basis=basis, role=role))
    threshold = result["threshold"]
    assert threshold["kind"] == "crossing"
    assert threshold["exact"] == root
    point = next(p for p in result["curve"]["points"] if p["exact_x"] == root)
    assert point["tie"] and point["best_actions"] == [0, 1]
    assert point["exact"]["first"] == point["exact"]["second"]
    assert point["exact"]["margin"] == "0"


def test_approximate_nonterminating_root_is_not_falsely_a_tie():
    for role, root in (("row", Fraction(11, 23)), ("column", Fraction(12, 23))):
        result = analyze(request(game="battle_of_the_sexes", value=float(root), role=role))
        assert not result["expected"]["tie"]
        assert Fraction(result["expected"]["exact"]["margin"]) != 0
        assert any(p["tie"] for p in result["curve"]["points"])


def test_column_role_uses_opponent_first_action_not_opponent_preference():
    at_zero = analyze(request(game="battle_of_the_sexes", role="column", value=0, q=0.9))
    at_one = analyze(request(game="battle_of_the_sexes", role="column", value=1, q=0.1))
    assert at_zero["q"] == 0
    assert at_zero["expected"]["exact"] == {"first": "-8", "second": "4", "margin": "-12"}
    assert at_one["q"] == 1
    assert at_one["expected"]["exact"] == {"first": "3", "second": "-8", "margin": "11"}


def test_pd_intervention_pilot_boundary_and_exact_nearby_distinctions():
    at = analyze(request(axis="intervention", value=0.375))
    assert at["baseline"]["params"]["sucker"] == -0.25
    assert at["threshold"]["exact"] == "3/8"
    assert at["expected"]["tie"]
    above = analyze(request(axis="intervention", value=Decimal("0.37500000000000000000001")))
    below = analyze(request(axis="intervention", value=Decimal("0.37499999999999999999999")))
    assert above["expected"]["best_actions"] == [0]
    assert below["expected"]["best_actions"] == [1]
    assert above["expected"]["exact"]["margin"] == "1/100000000000000000000000"


def test_inactive_parameters_reset_instead_of_silently_combining_axes():
    analyze(request(axis="temptation", value=2.75))
    analyze(request(axis="exploitation", value=-1))
    normal = analyze(request())
    assert normal["params"]["temptation"] == 1.5
    assert normal["params"]["sucker"] == -0.5
    assert normal["params"]["intervention"] == 0
    assert normal["matrix"] == normal["baseline"]["matrix"]
    intervention = analyze(request(axis="intervention", value=0.5))
    assert intervention["params"]["sucker"] == -0.25
    assert intervention["baseline"]["matrix"][1][1] == [0, 0]
    assert intervention["matrix"][1][1] == [-0.5, -0.5]


@pytest.mark.parametrize("game,expected", [
    ("prisoners_dilemma", [[[1, 1], [-0.25, 1.25]], [[1.25, -0.25], [-0.25, -0.25]]]),
    ("chicken", [[[1, 1], [0.5, 1.25]], [[1.25, 0.5], [-0.25, -0.25]]]),
    ("stag_hunt", [[[1.25, 1.25], [-0.25, 0.5]], [[0.5, -0.25], [0, 0]]]),
    ("battle_of_the_sexes", [[[4.25, 3.25], [-8, -8]], [[-8, -8], [3.25, 4.25]]]),
])
def test_each_intervention_retains_its_distinct_meaning(game, expected):
    assert analyze(request(game=game, axis="intervention", value=0.25))["matrix"] == expected


def test_current_game_classification_changes_with_intervention():
    assert analyze(request())["regime"]["quadrant"] == "competition_dominant"
    assert analyze(request(axis="intervention", value=0.3))["regime"]["quadrant"] == "anti_coordination"
    assert analyze(request(axis="intervention", value=0.25))["regime"]["quadrant"] == "boundary"
    result = analyze(request(axis="intervention", value=0.6))
    assert result["regime"]["quadrant"] == "cooperation_dominant"
    assert result["pure_equilibria"] == [[0, 0]]
    assert result["cells"][3]["deviation_gain"]["row"] == 0.35


def test_exact_regime_avoids_rounded_boundary_classification():
    above = analyze(request(axis="intervention", value=Decimal("0.25000000000000000001")))
    below = analyze(request(axis="intervention", value=Decimal("0.24999999999999999999")))
    assert above["regime"]["quadrant"] == "anti_coordination"
    assert below["regime"]["quadrant"] == "competition_dominant"


def test_crossings_outside_range_are_not_clamped_to_endpoint():
    result = analyze(request(game="chicken", basis="canonical", axis="intervention", value=0))
    assert result["threshold"]["kind"] == "outside"
    assert result["threshold"]["exact"] == "-19/2"
    assert not result["threshold"]["inside_range"]
    assert not any(p["tie"] for p in result["curve"]["points"])


def test_extreme_outside_crossing_stays_exact_without_nonfinite_json():
    result = analyze(request(axis="temptation", value=1.5, q=Decimal("1e-400")))
    assert result["threshold"]["kind"] == "outside"
    assert result["threshold"]["value"] is None
    assert Fraction(result["threshold"]["exact"]) < 0
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("game", ["chicken", "stag_hunt"])
def test_intervention_explanations_distinguish_starting_and_current_game(game):
    result = analyze(request(game=game, axis="intervention", value=1))
    assert result["explanation"].startswith("Before the intervention:")
    assert "After the intervention: The first action earns more points against either opponent action." in result["explanation"]


@pytest.mark.parametrize("updates", [
    {"game": "unknown"}, {"basis": "all"}, {"axis": "all"}, {"role": "player"},
    {"game": []}, {"axis": []}, {"role": None}, {"basis": 1},
    {"value": True}, {"value": "0.5"}, {"q": False}, {"value": float("nan")},
    {"value": float("inf")}, {"q": float("-inf")}, {"value": -0.1}, {"q": 1.1},
    {"game": "chicken", "axis": "temptation"}, {"axis": "temptation", "value": 1},
    {"axis": "exploitation", "value": 0}, {"axis": "intervention", "value": -1},
    {"value": Decimal("1e-999999")}, {"value": 10**400},
])
def test_invalid_analysis_values_are_rejected(updates):
    with pytest.raises(ValueError):
        analyze(request(**updates))


@pytest.mark.parametrize("payload", [None, [], {}, {"game": "chicken"}, request(extra=1)])
def test_analysis_requires_exact_six_field_schema(payload):
    with pytest.raises(ValueError):
        analyze(payload)


@pytest.mark.parametrize("raw", [
    b'{"q":0,"q":1}', b'{"q":NaN}', b'{"q":Infinity}', b'{"q":1e999}',
    b'{"q":1e-999999}', b'{"q":'+b'1'*129+b'}', b'\xff', b'{',
])
def test_strict_json_rejects_ambiguous_or_unbounded_numbers(raw):
    with pytest.raises((ValueError, UnicodeError)):
        strict_json(raw)


def test_strict_json_preserves_declared_decimal_values():
    assert strict_json(b'{"q":0.10000000000000001}')["q"] == Decimal("0.10000000000000001")


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "web"
    root.mkdir()
    (root / "index.html").write_text("<h1>Explorer</h1>")
    (root / "app.js").write_text("'use strict';")
    (root / "styles.css").write_text("body { color: white }")
    (root / "ocean.svg").write_text("<svg/>")
    (root / ".env").write_text("private inside root")
    (tmp_path / "secret.txt").write_text("private outside root")
    (root / "favicon.svg").symlink_to(tmp_path / "secret.txt")
    httpd = ExplorerServer(("127.0.0.1", 0), root)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def http(server, method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_http_catalog_analysis_and_content_headers(server):
    status, headers, body = http(server, "GET", "/api/catalog")
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert json.loads(body)["data_status"] == "THEORY ONLY"
    status, headers, body = http(server, "POST", "/api/analyze", json.dumps(request()),
                                 {"Content-Type": "application/json"})
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body)["expected"]["exact"]["margin"] == "-1/2"
    for path in ("/", "/index.html", "/app.js", "/styles.css", "/ocean.svg"):
        assert http(server, "GET", path)[0] == 200
    status, headers, body = http(server, "HEAD", "/index.html")
    assert status == 200 and body == b""
    assert int(headers["Content-Length"]) > 0


@pytest.mark.parametrize("path", [
    "/.env", "/../secret.txt", "/%2e%2e/secret.txt", "/web/", "/README.md",
    "/utility_threshold/core.py", "/favicon.svg", "/api/analyze", "/index.html/../.env",
])
def test_http_never_serves_nonallowlisted_or_escaped_files(server, path):
    status, _, body = http(server, "GET", path)
    assert status == 404
    assert b"private" not in body


def test_http_rejects_remote_hosts_origins_and_wrong_media_type(server):
    payload = json.dumps(request())
    assert http(server, "GET", "/api/catalog", headers={"Host": "example.com"})[0] == 403
    assert http(server, "POST", "/api/analyze", payload,
                {"Content-Type": "application/json", "Origin": "https://example.com"})[0] == 403
    assert http(server, "POST", "/api/analyze", payload,
                {"Content-Type": "text/plain"})[0] == 415
    assert http(server, "POST", "/anything", payload,
                {"Content-Type": "application/json"})[0] == 404
    port = server.server_address[1]
    assert http(server, "POST", "/api/analyze", payload,
                {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"})[0] == 200


@pytest.mark.parametrize("body", [
    b'{}', b'[]', b'{"value":0,"value":1}', b'{"value":NaN}', b'{"value":1e999}',
    b'\xff', b'['*1100 + b']'*1100,
])
def test_http_returns_clean_validation_errors(server, body):
    status, _, result = http(server, "POST", "/api/analyze", body, {"Content-Type": "application/json"})
    assert status == 400
    assert "error" in json.loads(result)


def test_http_limits_body_size_and_binding(server):
    assert http(server, "POST", "/api/analyze", b' '* (MAX_BODY_BYTES+1),
                {"Content-Type": "application/json"})[0] == 413
    with pytest.raises(ValueError, match="bind"):
        ExplorerServer(("0.0.0.0", 0), Path("."))
