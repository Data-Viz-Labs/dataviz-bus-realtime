"""Local preview of the map without AWS: serves web/ plus the live/ files the simulator
service writes to S3, computed by an in-process simulation.

    python -m sim.preview [--port 8000] [--speedup 1] [--start HH:MM]
"""

import argparse
from datetime import datetime, time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time as clock

from sim.aws import snapshot_payload
from sim.config import build_world

WEB = Path(__file__).resolve().parents[1] / "web"


class Simulation:
    def __init__(self, world, tick_s: float, speedup: float):
        self.world, self.tick_s, self.speedup = world, tick_s, speedup
        self.lock = threading.Lock()
        self.last = world.step(tick_s)

    def run(self) -> None:
        while True:
            clock.sleep(self.tick_s / self.speedup)
            with self.lock:
                self.last = self.world.step(self.tick_s)

    def snapshot(self) -> dict:
        with self.lock:
            return snapshot_payload(self.last)


def handler_for(sim: Simulation):
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/live/"):
                body = sim.snapshot() if self.path.startswith("/live/snapshot") else {"region": None, "mapKey": None}
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                super().do_GET()

        def log_message(self, *args):
            pass

    return partial(Handler, directory=str(WEB))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m sim.preview")
    p.add_argument("--lines", default="data/lines.yaml")
    p.add_argument("--network", default="data/network.json")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--speedup", type=float, default=1.0, help="simulated seconds per real second")
    p.add_argument("--start", help="simulated start time HH:MM (default: now)")
    args = p.parse_args(argv)

    start = datetime.combine(datetime.now().date(), time.fromisoformat(args.start)) if args.start else None
    sim = Simulation(build_world(args.lines, args.network, start=start), tick_s=5.0, speedup=args.speedup)
    threading.Thread(target=sim.run, daemon=True).start()
    if not (WEB / "network.json").exists():
        raise SystemExit("web/network.json missing: run `make web` first")
    print(f"http://localhost:{args.port}")
    ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(sim)).serve_forever()


if __name__ == "__main__":
    main()
