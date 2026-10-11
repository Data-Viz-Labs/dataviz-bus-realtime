"""AWS adapters: Amazon Location (tracker + stop geofences) and S3 (live snapshot + state).

Kept apart from the engine so the simulation runs and tests without AWS.
"""

from datetime import UTC, datetime, timedelta
import json
import logging

from sim.engine import TickResult, World
from sim.network import Line

log = logging.getLogger(__name__)

BATCH_POSITIONS = 10  # BatchUpdateDevicePosition limit
BATCH_GEOFENCES = 10  # BatchPutGeofence limit


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class LocationPublisher:
    """Writes positions of the tracked lines' buses to an Amazon Location tracker.

    A moving bus is written every ``heartbeat_s``. With ``stop_calls`` (needed for stop
    geofences) every stop call is also written, at the stop's coordinates, so the tracker
    sees the ENTER. Writes and geofence evaluations are billed per position: the tracked
    lines and the heartbeat are the cost knobs.
    """

    def __init__(self, client, tracker_name: str, heartbeat_s: float = 120.0,
                 lines: set[str] | None = None, stop_calls: bool = False):
        self.client = client
        self.tracker_name = tracker_name
        self.heartbeat = timedelta(seconds=heartbeat_s)
        self.lines = lines  # None = every line
        self.stop_calls = stop_calls
        self._last: dict[str, datetime] = {}

    def _tracked(self, line_id: str) -> bool:
        return self.lines is None or line_id in self.lines

    def updates(self, result: TickResult) -> list[dict]:
        out = []
        if self.stop_calls:
            for c in result.calls:
                if self._tracked(c.line_id):
                    out.append(self._update(c.bus_id, c.time, c.lat, c.lon, c.line_id, c.passengers_after, c.direction))
                    self._last[c.bus_id] = c.time
        for b in result.buses:
            if not self._tracked(b.line_id):
                continue
            last = self._last.get(b.bus_id)
            if last is None or result.time - last >= self.heartbeat:
                out.append(self._update(b.bus_id, result.time, b.lat, b.lon, b.line_id, b.passengers, b.direction))
                self._last[b.bus_id] = result.time
        return out

    @staticmethod
    def _update(bus_id, at, lat, lon, line_id, passengers, direction) -> dict:
        return {
            "DeviceId": bus_id,
            "SampleTime": at,
            "Position": [round(lon, 6), round(lat, 6)],
            # The tracker stores at most three properties per position.
            "PositionProperties": {"line": line_id, "passengers": str(passengers), "direction": str(direction)},
        }

    def publish(self, result: TickResult) -> int:
        updates = self.updates(result)
        for batch in _chunks(updates, BATCH_POSITIONS):
            resp = self.client.batch_update_device_position(TrackerName=self.tracker_name, Updates=batch)
            for err in resp.get("Errors", []):
                log.warning("position rejected for %s: %s", err.get("DeviceId"), err.get("Error"))
        return len(updates)


def stop_geofences(lines: dict[str, Line], radius_m: float) -> dict[str, dict]:
    """One circular geofence per stop, keyed by stop id."""
    fences = {}
    for line in lines.values():
        for s in line.stops:
            fences[s.stop_id] = {"Circle": {"Center": [s.lon, s.lat], "Radius": radius_m}}
    return fences


def sync_geofences(client, collection: str, lines: dict[str, Line], radius_m: float = 25.0) -> int:
    """Create geofences for stops that do not have one yet. Returns how many were created."""
    existing = set()
    for page in client.get_paginator("list_geofences").paginate(CollectionName=collection):
        existing.update(e["GeofenceId"] for e in page["Entries"])
    missing = [(sid, geo) for sid, geo in stop_geofences(lines, radius_m).items() if sid not in existing]
    for batch in _chunks(missing, BATCH_GEOFENCES):
        resp = client.batch_put_geofence(
            CollectionName=collection,
            Entries=[{"GeofenceId": sid, "Geometry": geo} for sid, geo in batch],
        )
        for err in resp.get("Errors", []):
            log.warning("geofence %s rejected: %s", err.get("GeofenceId"), err.get("Error"))
    return len(missing)


def snapshot_payload(result: TickResult) -> dict:
    """What the map polls: every bus and the people waiting at each stop."""
    return {
        "time": result.time.isoformat(),
        "buses": [
            {"id": b.bus_id, "line": b.line_id, "lat": round(b.lat, 6), "lon": round(b.lon, 6),
             "passengers": b.passengers, "direction": b.direction, "next_stop_id": b.next_stop_id}
            for b in result.buses
        ],
        "waiting": {k: v for k, v in result.waiting.items() if v},
    }


class SiteStore:
    """The site bucket: ``live/`` is public through CloudFront."""

    SNAPSHOT, CONFIG = "live/snapshot.json", "live/config.json"

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def _put(self, key: str, payload: dict, max_age: int) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=json.dumps(payload, separators=(",", ":")).encode(),
                               ContentType="application/json", CacheControl=f"public, max-age={max_age}")

    def put_snapshot(self, result: TickResult) -> None:
        self._put(self.SNAPSHOT, snapshot_payload(result), max_age=5)

    def put_config(self, region: str, map_key: str | None, api_url: str | None = None) -> None:
        self._put(self.CONFIG, {"region": region, "mapKey": map_key, "apiUrl": api_url}, max_age=300)


class DataStore:
    """The private data bucket: ``history/`` (Parquet, read through Athena/the API) and
    ``private/`` (world state for restarts, the scenario and the end of the generated history)."""

    STATE, SCENARIO, UNTIL = "private/world.json", "private/scenario.json", "private/history_until.json"

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get_json(self, key: str) -> dict | None:
        from botocore.exceptions import ClientError  # botocore is only needed when running on AWS

        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise
        return json.loads(body)

    def save_state(self, world: World) -> None:
        payload = {"saved_at": datetime.now(UTC).isoformat(), "world": world.to_state()}
        self.put(self.STATE, json.dumps(payload, separators=(",", ":")).encode())

    def load_state(self, max_age: timedelta) -> dict | None:
        saved = self.get_json(self.STATE)
        if not saved or datetime.now(UTC) - datetime.fromisoformat(saved["saved_at"]) > max_age:
            return None
        return saved["world"]

    def history_until(self) -> datetime | None:
        marker = self.get_json(self.UNTIL)
        return datetime.fromisoformat(marker["until"]) if marker else None
