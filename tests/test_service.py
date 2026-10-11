"""The service loop wired end to end with fake AWS clients."""

import json
import os
import signal
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from sim import service
from tests.conftest import MINI_YAML


def fake_clients(scenario: dict | None):
    clients = {name: MagicMock(name=name) for name in ("location", "s3", "iot-data")}
    clients["location"].meta.region_name = "eu-west-1"
    clients["location"].describe_key.return_value = {"Key": "v1.public.key"}
    clients["location"].batch_update_device_position.return_value = {"Errors": []}

    def get_object(Bucket, Key):
        payload = {"private/scenario.json": scenario,
                   "private/history_until.json": {"until": "2000-01-01T00:00:00"} if scenario else None}.get(Key)
        if payload is None:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        body = MagicMock()
        body.read.return_value = json.dumps(payload).encode()
        return {"Body": body}

    clients["s3"].get_object.side_effect = get_object
    return clients


def run_service(monkeypatch, clients, ticks=4):
    for k, v in {"SITE_BUCKET": "site", "DATA_BUCKET": "data", "TRACKER_NAME": "buses", "TRACKED_LINES": "A",
                 "MAP_KEY_NAME": "map", "MQTT_ENDPOINT": "abc-ats.iot.eu-west-1.amazonaws.com",
                 "LINES_FILE": str(MINI_YAML), "NETWORK_FILE": "", "HISTORY_SECONDS": "10"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(service.boto3, "client", lambda name, **_: clients[name])
    calls = {"n": 0}

    def sleep(_):
        calls["n"] += 1
        if calls["n"] == ticks:
            os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(service.time, "sleep", sleep)
    previous = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGINT)
    try:
        service.main()
    finally:
        signal.signal(signal.SIGTERM, previous[0])
        signal.signal(signal.SIGINT, previous[1])


def keys_written(clients) -> list[str]:
    return [c.kwargs["Key"] for c in clients["s3"].put_object.call_args_list]


def test_service_publishes_everywhere(monkeypatch):
    clients = fake_clients(None)
    run_service(monkeypatch, clients)
    keys = keys_written(clients)
    assert "live/config.json" in keys and "live/snapshot.json" in keys
    assert "private/world.json" in keys
    assert not [k for k in keys if k.startswith("history/")]  # no generated history to continue yet
    assert clients["iot-data"].publish.call_count >= 3
    devices = {u["DeviceId"] for c in clients["location"].batch_update_device_position.call_args_list
               for u in c.kwargs["Updates"]}
    assert devices == {"A-01", "A-02", "A-03"}


def test_service_follows_the_generated_scenario_and_records_history(monkeypatch):
    from datetime import date, datetime

    from sim.config import load_network
    from sim.scenario import generate

    lines = load_network(MINI_YAML)[0]
    scenario = generate(lines, date(2025, 1, 1), date(2030, 1, 1), seed=3)
    scenario.line_factor = {lid: 1.0 for lid in lines}
    clients = fake_clients(scenario.to_json())

    class Morning(datetime):  # history is only recorded in service hours
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 14, 10, 0, tzinfo=tz)

    monkeypatch.setattr(service, "datetime", Morning)
    run_service(monkeypatch, clients, ticks=8)
    keys = keys_written(clients)
    assert any(k.startswith("history/bus_positions/dt=2026-10-14/live-") for k in keys)
