"""Long-running simulator service (the Fargate task).

Runs the world in real time. Every few seconds it publishes the live snapshot the map reads
(S3, behind CloudFront); the buses of the tracked lines also go to an Amazon Location
tracker. Configuration comes from the environment:

    SITE_BUCKET          bucket served by CloudFront            (required)
    TRACKER_NAME         Amazon Location tracker                (required)
    TRACKED_LINES        lines written to the tracker: ids, "all" or "" (none). Default "27"
    GEOFENCE_COLLECTION  stop geofences; when set, stop calls are written too (optional)
    MAP_KEY_NAME         Amazon Location API key for the map    (optional)
    LINES_FILE           data/lines.yaml
    NETWORK_FILE         data/network.json (street geometry; optional)
    LINES                comma-separated subset of lines to simulate (default: all)
    TICK_SECONDS         5     simulation step
    SNAPSHOT_SECONDS     5     how often the map snapshot is written
    HEARTBEAT_SECONDS    120   max time between two tracker writes of a bus
    STATE_SECONDS        60    how often the world is saved for restarts
    RESUME_MAX_MINUTES   15    older saved state is discarded on start-up
    TIMEZONE             Europe/Madrid (drives the time-of-day demand profile)
    SEED                 random seed (optional)
"""

from datetime import datetime, timedelta
import logging
import os
import signal
import time
from zoneinfo import ZoneInfo

import boto3

from sim.aws import LocationPublisher, SiteStore, sync_geofences
from sim.config import build_world

log = logging.getLogger("sim.service")


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit(f"missing required environment variable {name}")
    return value


def id_set(value: str) -> set[str]:
    return {x.strip() for x in value.split(",") if x.strip()}


class Every:
    """True once per ``seconds`` of simulated time."""

    def __init__(self, seconds: float):
        self.period, self.last = timedelta(seconds=seconds), None

    def due(self, now: datetime) -> bool:
        if self.last is None or now - self.last >= self.period:
            self.last = now
            return True
        return False


def main() -> None:
    logging.basicConfig(level=env("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    tz = ZoneInfo(env("TIMEZONE", "Europe/Madrid"))
    tick = float(env("TICK_SECONDS", "5"))
    seed = os.environ.get("SEED")
    world = build_world(
        env("LINES_FILE", "data/lines.yaml"), env("NETWORK_FILE", "data/network.json"),
        start=datetime.now(tz).replace(microsecond=0), seed=int(seed) if seed else None,
        only_lines=id_set(env("LINES", "")) or None,
    )

    location, s3 = boto3.client("location"), boto3.client("s3")
    site = SiteStore(s3, env("SITE_BUCKET"))
    tracked = env("TRACKED_LINES", "27").strip()
    collection = os.environ.get("GEOFENCE_COLLECTION")
    publisher = None
    if tracked:
        lines = None if tracked == "all" else id_set(tracked) & set(world.lines)
        publisher = LocationPublisher(location, env("TRACKER_NAME"), float(env("HEARTBEAT_SECONDS", "120")),
                                      lines=lines, stop_calls=bool(collection))
        if collection:
            scope = world.lines if lines is None else {k: v for k, v in world.lines.items() if k in lines}
            log.info("geofences created: %d", sync_geofences(location, collection, scope))

    key_name = os.environ.get("MAP_KEY_NAME")
    site.put_config(location.meta.region_name, location.describe_key(KeyName=key_name)["Key"] if key_name else None)
    if saved := site.load_state(timedelta(minutes=float(env("RESUME_MAX_MINUTES", "15")))):
        world.restore(saved)
        log.info("resumed saved state")
    log.info("simulating %d lines, %d buses; tracker: %s", len(world.lines), len(world.buses), tracked or "off")

    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    snapshot_every = Every(float(env("SNAPSHOT_SECONDS", "5")))
    state_every = Every(float(env("STATE_SECONDS", "60")))
    deadline = time.monotonic()
    while not stopping:
        result = world.step(tick)
        try:
            if snapshot_every.due(result.time):
                site.put_snapshot(result)
            written = publisher.publish(result) if publisher else 0
            if state_every.due(result.time):
                site.save_state(world)
                log.info("t=%s tracker_writes=%d on_board=%d waiting=%d", f"{result.time:%H:%M:%S}", written,
                         sum(b.passengers for b in result.buses), sum(result.waiting.values()))
        except Exception:  # keep simulating through transient AWS errors
            log.exception("publishing failed")
        deadline += tick
        time.sleep(max(0.0, deadline - time.monotonic()))
    site.save_state(world)
    log.info("state saved, stopping")


if __name__ == "__main__":
    main()
