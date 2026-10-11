"""docs/api/asyncapi.yaml documents exactly what MqttPublisher sends."""

from datetime import UTC, datetime

import pytest
import yaml

from sim.config import build_world
from sim.mqtt import MqttPublisher
from tests.conftest import MINI_YAML, REPO

SPEC = yaml.safe_load((REPO / "docs" / "api" / "asyncapi.yaml").read_text())


def ref(node: dict) -> dict:
    """Follow local ``$ref``s ("#/a/b") until a concrete node."""
    while "$ref" in node:
        target = SPEC
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


@pytest.fixture(scope="module")
def messages():
    world = build_world(MINI_YAML, None, start=datetime(2026, 10, 12, 8, tzinfo=UTC), seed=1)
    publisher = MqttPublisher(None, world.lines)
    out = []
    for _ in range(60):
        out += publisher.messages(world.step(5))
    return out


def channel_for(topic: str) -> dict:
    for channel in SPEC["channels"].values():
        prefix, suffix = channel["address"].split("{line_id}")
        if topic.startswith(prefix) and topic.endswith(suffix) and "/" not in topic[len(prefix):-len(suffix)]:
            return channel
    raise AssertionError(f"no channel documents {topic}")


def check(schema: dict, value) -> None:
    schema = ref(schema)
    if schema.get("type") == "object" and "properties" in schema:
        assert set(value) == set(schema["required"]) == set(schema["properties"])
        for key, sub in schema["properties"].items():
            check(sub, value[key])
    elif schema.get("type") == "array":
        for item in value:
            check(schema["items"], item)


def test_spec_shape():
    assert SPEC["asyncapi"] == "3.0.0"
    assert {s["protocol"] for s in SPEC["servers"].values()} == {"wss", "mqtts"}
    assert all(op["action"] == "receive" for op in SPEC["operations"].values())


def test_every_published_message_matches_its_channel(messages):
    seen = set()
    for topic, payload, retain in messages:
        channel = channel_for(topic)
        (message,) = channel["messages"].values()
        check(ref(message)["payload"], payload)
        assert ("**retained**" in channel["description"]) == retain
        seen.add(channel["address"])
    assert seen == {c["address"] for c in SPEC["channels"].values()}


def test_examples_match_schemas():
    for message in SPEC["components"]["messages"].values():
        for example in message["examples"]:
            check(message["payload"], example["payload"])
