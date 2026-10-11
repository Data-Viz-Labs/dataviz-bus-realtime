"""Real-time MQTT feed through AWS IoT Core (HTTPS data plane; subscribers use MQTT).

Topics, per line:

    madrid/lines/{line_id}/state   retained, every ``state_every_s``: buses + people waiting
    madrid/lines/{line_id}/calls   not retained, each tick with stop calls on that line

IoT Core bills messages in 5 KB increments, so payloads are compact JSON with rounded
coordinates. The schema is documented in ``docs/api/asyncapi.yaml``.
"""

from datetime import datetime, timedelta
import json
import logging

from sim.engine import StopCall, TickResult
from sim.network import Line

log = logging.getLogger(__name__)

Message = tuple[str, dict, bool]  # (topic, payload, retain)


def _call(c: StopCall) -> dict:
    return {
        "time": c.time.isoformat(timespec="milliseconds"), "bus_id": c.bus_id, "stop_id": c.stop_id,
        "direction": c.direction, "terminal": c.terminal, "alighted": c.alighted, "boarded": c.boarded,
        "passengers_after": c.passengers_after, "left_behind": c.left_behind,
        "leg_minutes": None if c.leg_minutes is None else round(c.leg_minutes, 1),
    }


class MqttPublisher:
    """Publishes per-line state and stop calls with an ``iot-data`` client.

    ``capacities`` maps bus id to capacity; buses missing from it use their snapshot's capacity.
    """

    def __init__(self, client, lines: dict[str, Line], capacities: dict[str, int] | None = None,
                 prefix: str = "madrid", state_every_s: float = 5.0):
        self.client = client
        self.capacities = capacities or {}
        self.prefix = prefix
        self.state_every = timedelta(seconds=state_every_s)
        self._stops = {line_id: [s.stop_id for s in line.stops] for line_id, line in lines.items()}
        self._last_state: datetime | None = None

    def topic(self, line_id: str, kind: str) -> str:
        return f"{self.prefix}/lines/{line_id}/{kind}"

    def messages(self, result: TickResult) -> list[Message]:
        out: list[Message] = []
        now = result.time.isoformat()
        if self._last_state is None or result.time - self._last_state >= self.state_every:
            self._last_state = result.time
            buses: dict[str, list[dict]] = {line_id: [] for line_id in self._stops}
            for b in result.buses:
                capacity = self.capacities.get(b.bus_id, b.capacity)
                buses.setdefault(b.line_id, []).append({
                    "id": b.bus_id, "direction": b.direction, "lat": round(b.lat, 5), "lon": round(b.lon, 5),
                    "passengers": b.passengers, "load": round(b.passengers / capacity, 3) if capacity else 0.0,
                    "state": b.state, "next_stop_id": b.next_stop_id,
                })
            for line_id, line_buses in buses.items():
                waiting = {s: n for s in self._stops.get(line_id, []) if (n := result.waiting.get(s, 0)) > 0}
                out.append((self.topic(line_id, "state"),
                            {"time": now, "line_id": line_id, "buses": line_buses, "waiting": waiting}, True))
        calls: dict[str, list[dict]] = {}
        for c in result.calls:
            calls.setdefault(c.line_id, []).append(_call(c))
        for line_id, line_calls in calls.items():
            out.append((self.topic(line_id, "calls"), {"time": now, "line_id": line_id, "calls": line_calls}, False))
        return out

    def publish(self, result: TickResult) -> int:
        """Publish this tick's messages; returns how many were accepted."""
        sent = 0
        for topic, payload, retain in self.messages(result):
            try:
                self.client.publish(topic=topic, qos=0, retain=retain,
                                    payload=json.dumps(payload, separators=(",", ":")).encode())
                sent += 1
            except Exception as e:  # one rejected message must not stop the others
                log.warning("MQTT publish to %s failed: %s", topic, e)
        return sent
