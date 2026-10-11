"""Aggregate tick results into the numbers that tell whether the simulation is sane."""

from dataclasses import dataclass, field

from sim.engine import TickResult, World


@dataclass
class Summary:
    world: World
    ticks: int = 0
    occupancy_sum: float = 0.0
    boarded: int = 0
    alighted: int = 0
    arrivals: int = 0
    max_waiting: int = 0
    visited: set[str] = field(default_factory=set)
    last_waiting: int = 0

    def add(self, r: TickResult) -> None:
        self.ticks += 1
        self.occupancy_sum += sum(b.passengers / b.capacity for b in r.buses) / len(r.buses)
        self.arrivals += r.arrivals
        for c in r.calls:
            self.boarded += c.boarded
            self.alighted += c.alighted
            self.visited.add(c.stop_id)
        self.last_waiting = sum(r.waiting.values())
        self.max_waiting = max(self.max_waiting, self.last_waiting)

    @property
    def mean_occupancy(self) -> float:
        return self.occupancy_sum / self.ticks if self.ticks else 0.0

    @property
    def unvisited(self) -> list[str]:
        all_stops = {s.stop_id for line in self.world.lines.values() for s in line.stops}
        return sorted(all_stops - self.visited)

    def healthy(self) -> bool:
        # Night service is legitimately near-empty, so the floor only catches "nobody ever boards".
        return 0.02 <= self.mean_occupancy <= 0.85 and not self.unvisited

    def render(self) -> str:
        on_board = sum(b.passengers for b in self.world.buses.values())
        return "\n".join([
            f"simulated ticks     : {self.ticks} (until {self.world.clock:%H:%M})",
            f"mean occupancy      : {self.mean_occupancy:.0%}",
            f"arrived / boarded   : {self.arrivals} / {self.boarded}",
            f"alighted / on board : {self.alighted} / {on_board}",
            f"waiting now / max   : {self.last_waiting} / {self.max_waiting}",
            f"unvisited stops     : {', '.join(self.unvisited) or 'none'}",
            f"status              : {'OK' if self.healthy() else 'UNHEALTHY'}",
        ])
