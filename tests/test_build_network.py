import importlib.util
import json

import boto3
from botocore.stub import ANY, Stubber
import pytest

from sim.config import load_network
from sim.network import Polyline
from tests.conftest import MINI_YAML, REPO

spec = importlib.util.spec_from_file_location("build_network", REPO / "tools" / "build_network.py")
build_network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_network)


def routes_response(stops, detour_lon=0.0):
    legs = [
        {"Geometry": {"LineString": [[a.lon, a.lat], [a.lon + detour_lon, (a.lat + b.lat) / 2], [b.lon, b.lat]]},
         "TravelMode": "Car", "Type": "Vehicle"}
        for a, b in zip(stops, stops[1:], strict=False)
    ]
    return {"LegGeometryFormat": "Simple", "Notices": [], "PricingBucket": "x", "Routes": [{
        "Legs": legs, "MajorRoadLabels": [], "Summary": {"Distance": 1, "Duration": 1},
    }]}


def client():
    return boto3.client("geo-routes", region_name="eu-west-1", aws_access_key_id="x", aws_secret_access_key="x")


def test_street_geometry_offsets_land_on_each_stop():
    lines, _, _ = load_network(MINI_YAML)
    stops = lines["A"].legs[0].stops
    geo = client()
    with Stubber(geo) as stub:
        stub.add_response("calculate_routes", routes_response(stops, 0.002), {
            "Origin": ANY, "Destination": ANY, "Waypoints": ANY, "TravelMode": "Car", "LegGeometryFormat": "Simple",
        })
        leg = build_network.leg_geometry(geo, stops)
    assert len(leg["offsets"]) == len(stops)
    points = leg["geometry"]
    line = Polyline([tuple(p) for p in points])
    for stop, offset in zip(stops, leg["offsets"], strict=True):
        assert line.point_at(offset) == pytest.approx((stop.lat, stop.lon))


def test_absurd_detours_fall_back_to_straight_segments():
    lines, _, _ = load_network(MINI_YAML)
    stops = lines["A"].legs[0].stops
    geo = client()
    with Stubber(geo) as stub:
        stub.add_response("calculate_routes", routes_response(stops, 0.5))  # ~40 km sideways
        segments = build_network.route_segments(geo, stops)
    assert all(len(s) == 2 for s in segments)


def test_long_lines_are_split_into_requests_of_25_positions(tmp_path):
    lines, _, _ = load_network(MINI_YAML)
    many = lines["A"].legs[0].stops * 15  # 60 positions -> 3 overlapping windows
    geo = client()
    with Stubber(geo) as stub:
        for start in (0, 24, 48):
            stub.add_response("calculate_routes", routes_response(many[start:start + 25]))
        assert len(build_network.route_segments(geo, many)) == len(many) - 1
        stub.assert_no_pending_responses()


def test_written_network_loads_into_the_simulator(tmp_path, monkeypatch):
    geo = client()
    lines, _, _ = load_network(MINI_YAML)
    stub = Stubber(geo)
    for line in lines.values():
        for leg in line.legs:
            stub.add_response("calculate_routes", routes_response(leg.stops, 0.001))
    stub.activate()
    monkeypatch.setattr(build_network.boto3, "client", lambda *_: geo)
    out = tmp_path / "network.json"
    build_network.main(["--lines", str(MINI_YAML), "--out", str(out)])
    curved, _, _ = load_network(MINI_YAML, out)
    assert set(json.loads(out.read_text())) == {"A", "B", "C"}
    for line_id, line in curved.items():
        assert line.length > lines[line_id].length
        assert [v.stop.stop_id for v in line.visits] == [v.stop.stop_id for v in lines[line_id].visits]
