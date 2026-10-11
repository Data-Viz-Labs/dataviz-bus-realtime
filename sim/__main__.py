"""Run the simulation locally, without AWS, and print a health summary.

    python -m sim --hours 2 --start 07:00 --seed 1 [--jsonl out.jsonl]
"""

import argparse
from dataclasses import asdict
from datetime import datetime, time
import json
from pathlib import Path
import sys

from sim.config import build_world
from sim.report import Summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m sim")
    p.add_argument("--lines", default="data/lines.yaml")
    p.add_argument("--network", default="data/network.json")
    p.add_argument("--hours", type=float, default=2.0)
    p.add_argument("--start", default="07:00", help="simulated start time HH:MM")
    p.add_argument("--tick", type=float, default=5.0, help="tick length in simulated seconds")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--jsonl", type=Path, help="write one JSON line per tick")
    args = p.parse_args(argv)

    start = datetime.combine(datetime.now().date(), time.fromisoformat(args.start))
    world = build_world(args.lines, args.network, start=start, seed=args.seed)
    summary = Summary(world)
    out = args.jsonl.open("w") if args.jsonl else None
    for _ in range(int(args.hours * 3600 / args.tick)):
        result = world.step(args.tick)
        summary.add(result)
        if out:
            out.write(json.dumps(asdict(result), default=str) + "\n")
    if out:
        out.close()
    print(summary.render())
    return 0 if summary.healthy() else 1


if __name__ == "__main__":
    sys.exit(main())
