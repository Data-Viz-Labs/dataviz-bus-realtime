"""MQTT feed: topics, payload shapes and sizes, and iot-data publish calls against a stub."""

from datetime import UTC, datetime
import json

import boto3
from botocore.stub import Stubber
import pytest

from sim.config import build_world
from sim.mqtt import MqttPublisher
from tests.conftest import LINES_YAML, MINI_YAML


def iot_data():
    return boto3.client("iot-data", region_name="eu-west-1", endpoint_url="https://example-ats.iot.eu-west-1.amazonaws.com",
                        aws_access_key_id="x", aws_secret_access_key="x")


@pytest.fixture
def world():
    return build_world(MINI_YAML, None, start=datetime(2026, 10, 12, 8, tzinfo=UTC), seed=1)


def test_state_topics_are_retained_and_complete(world):
    msgs = MqttPublisher(iot_data(), world.lines).messages(world.step(5))
    states = {t: (p, r) for t, p, r in msgs if t.endswith("/state")}
    assert set(states) == {f"madrid/lines/{line}/state" for line in ("A", "B", "C")}
    payload, retain = states["madrid/lines/C/state"]
    assert retain and payload["line_id"] == "C" and {b["id"] for b in payload["buses"]} == {"C-01", "C-02"}
    bus = payload["buses"][0]
    assert set(bus) == {"id", "direction", "lat", "lon", "passengers", "load", "state", "next_stop_id"}
    assert bus["load"] == round(bus["passengers"] / 40, 3)
    assert set(payload["waiting"]) <= {"L1", "L2", "L3", "L4"} and all(n > 0 for n in payload["waiting"].values())


def test_state_is_time_gated_and_calls_are_not_retained(world):
    publisher = MqttPublisher(iot_data(), world.lines, state_every_s=30)
    results = [world.step(5) for _ in range(60)]
    msgs = [m for r in results for m in publisher.messages(r)]
    assert sum(t.endswith("/state") for t, _, _ in msgs) == 3 * 10  # 300 s / 30 s, 3 lines
    calls = [(t, p, r) for t, p, r in msgs if t.endswith("/calls")]
    assert calls and not any(r for _, _, r in calls)
    assert sum(len(p["calls"]) for _, p, _ in calls) == sum(len(r.calls) for r in results)
    topic, payload, _ = calls[0]
    assert topic == f"madrid/lines/{payload['line_id']}/calls"
    assert set(payload["calls"][0]) == {"time", "bus_id", "stop_id", "direction", "terminal", "alighted", "boarded",
                                        "passengers_after", "left_behind", "leg_minutes"}


def test_capacity_override(world):
    payload = next(p for t, p, _ in MqttPublisher(iot_data(), world.lines, {"C-01": 1}).messages(world.step(5))
                   if t.endswith("C/state"))
    bus = next(b for b in payload["buses"] if b["id"] == "C-01")
    assert bus["load"] == bus["passengers"]  # may exceed 1


def test_publish_sends_compact_json_and_survives_failures(world):
    iot = iot_data()
    publisher = MqttPublisher(iot, world.lines)
    result = world.step(5)
    expected = MqttPublisher(iot, world.lines).messages(result)
    with Stubber(iot) as stub:
        stub.add_client_error("publish", "ThrottlingException", http_status_code=429)
        for topic, payload, retain in expected[1:]:
            body = json.dumps(payload, separators=(",", ":")).encode()
            stub.add_response("publish", {}, {"topic": topic, "qos": 0, "retain": retain, "payload": body})
        assert publisher.publish(result) == len(expected) - 1
        stub.assert_no_pending_responses()


def test_real_network_payloads_stay_small():
    world = build_world(LINES_YAML, None, start=datetime(2026, 10, 12, 8, tzinfo=UTC), seed=1)
    publisher = MqttPublisher(iot_data(), world.lines)
    biggest_state = biggest_calls = 0
    for _ in range(12):
        for topic, payload, _ in publisher.messages(world.step(5)):
            size = len(json.dumps(payload, separators=(",", ":")))
            if topic.endswith("/state"):
                biggest_state = max(biggest_state, size)
            else:
                biggest_calls = max(biggest_calls, size)
    assert biggest_state < 10_000  # IoT Core limit is 128 KB; billed per 5 KB
    assert biggest_calls < 5_000
