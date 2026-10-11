"""AWS adapters against botocore stubs: request shapes only, no network."""

from datetime import UTC, datetime, timedelta
import io
import json

import boto3
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
import pytest

from sim.aws import LocationPublisher, SiteStore, snapshot_payload, stop_geofences, sync_geofences
from sim.config import build_world
from tests.conftest import MINI_YAML


def client(service):
    return boto3.client(service, region_name="eu-west-1", aws_access_key_id="x", aws_secret_access_key="x")


@pytest.fixture
def world():
    return build_world(MINI_YAML, None, start=datetime(2026, 10, 12, 8, tzinfo=UTC), seed=1)


def test_publisher_sends_each_tracked_bus_in_batches_of_ten(world):
    loc = client("location")
    result = world.step(5)
    expected = LocationPublisher(loc, "buses").updates(result)
    assert {u["DeviceId"] for u in expected} == set(world.buses)
    assert all(len(u["PositionProperties"]) <= 3 for u in expected)
    publisher = LocationPublisher(loc, "buses")
    with Stubber(loc) as stub:
        for _ in range(0, len(expected), 10):
            stub.add_response("batch_update_device_position", {"Errors": []}, {"TrackerName": "buses", "Updates": ANY})
        assert publisher.publish(result) == len(expected)
        stub.assert_no_pending_responses()


def test_only_tracked_lines_are_written(world):
    publisher = LocationPublisher(client("location"), "buses", lines={"C"})
    assert {u["DeviceId"] for u in publisher.updates(world.step(5))} == {"C-01", "C-02"}


def test_heartbeat_and_stop_calls(world):
    quiet = LocationPublisher(client("location"), "buses", heartbeat_s=600)
    calls = LocationPublisher(client("location"), "buses", heartbeat_s=600, stop_calls=True)
    for p in (quiet, calls):
        p.updates(world.step(5))
    results = [world.step(5) for _ in range(60)]
    assert sum(len(quiet.updates(r)) for r in results) == 0  # within the heartbeat
    stop_calls = sum(len(r.calls) for r in results)
    assert stop_calls > 0 and sum(len(calls.updates(r)) for r in results) == stop_calls


def test_geofences_are_only_created_for_missing_stops(world):
    loc = client("location")
    fences = stop_geofences(world.lines, 25)
    assert len(fences) == 12 and fences["C2"]["Circle"]["Radius"] == 25
    with Stubber(loc) as stub:
        stub.add_response("list_geofences", {"Entries": [{
            "GeofenceId": "A1", "Geometry": {}, "Status": "ACTIVE",
            "CreateTime": datetime(2026, 1, 1), "UpdateTime": datetime(2026, 1, 1),
        }]})
        stub.add_response("batch_put_geofence", {"Successes": [], "Errors": []})
        stub.add_response("batch_put_geofence", {"Successes": [], "Errors": []})
        assert sync_geofences(loc, "stops", world.lines) == 11


def test_snapshot_is_public_and_short_lived(world):
    s3 = client("s3")
    result = world.step(5)
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, {
            "Bucket": "site", "Key": "live/snapshot.json", "Body": ANY,
            "ContentType": "application/json", "CacheControl": "public, max-age=5",
        })
        SiteStore(s3, "site").put_snapshot(result)
    payload = snapshot_payload(result)
    assert len(payload["buses"]) == 7 and set(payload["buses"][0]) == {"id", "line", "lat", "lon", "passengers",
                                                                          "direction"}


def body(payload: dict) -> StreamingBody:
    raw = json.dumps(payload).encode()
    return StreamingBody(io.BytesIO(raw), len(raw))


def test_state_round_trip_and_expiry(world):
    s3 = client("s3")
    store = SiteStore(s3, "site")
    fresh = {"saved_at": datetime.now(UTC).isoformat(), "world": world.to_state()}
    stale = {"saved_at": (datetime.now(UTC) - timedelta(hours=2)).isoformat(), "world": world.to_state()}
    with Stubber(s3) as stub:
        stub.add_response("put_object", {}, {"Bucket": "site", "Key": "state/world.json", "Body": ANY,
                                             "ContentType": "application/json"})
        store.save_state(world)
        stub.add_response("get_object", {"Body": body(fresh)})
        assert store.load_state(timedelta(minutes=15)) == world.to_state()
        stub.add_response("get_object", {"Body": body(stale)})
        assert store.load_state(timedelta(minutes=15)) is None
        stub.add_client_error("get_object", "NoSuchKey", http_status_code=404)
        assert store.load_state(timedelta(minutes=15)) is None
