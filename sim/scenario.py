"""Scenario: the hidden story behind the data — line loads, Madrid's calendar and random events.

A scenario is generated once per history generation from a fresh secret seed, so reading this
code tells you *what kind* of things can happen, never *when* or *where* they happened: dates,
venues, intensities, the line targets and the overloaded line are all drawn at random. The
generated scenario (the answer key) is only stored privately.

At any instant it yields ``Factors``: a city-wide demand multiplier, per-line demand and speed
multipliers, per-stop demand multipliers for event areas, suspended lines and per-line maximum
load. Both the microsimulation (``World.conditions``) and the hourly model in ``sim.backfill``
read them, so the two tiers of history tell the same story.
"""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
import random

from sim.network import Line, distance_m

SOL = (40.4169, -3.7035)  # Puerta del Sol, the centre

# Demand per hour relative to the network calibration (weekday 08:00 = 1.6, the morning peak).
WEEKDAY = [0.05, 0.03, 0.02, 0.02, 0.05, 0.3, 0.9, 1.5, 1.6, 1.1, 0.7, 0.7,
           0.85, 1.0, 1.1, 0.9, 0.95, 1.2, 1.45, 1.3, 0.9, 0.6, 0.4, 0.2]
SATURDAY = [0.15, 0.1, 0.05, 0.03, 0.03, 0.1, 0.25, 0.4, 0.55, 0.7, 0.85, 0.95,
            1.0, 0.95, 0.85, 0.8, 0.85, 0.9, 0.95, 0.9, 0.75, 0.6, 0.45, 0.3]
SUNDAY = [0.2, 0.12, 0.06, 0.03, 0.03, 0.08, 0.15, 0.25, 0.35, 0.5, 0.65, 0.8,
          0.85, 0.8, 0.7, 0.65, 0.7, 0.75, 0.8, 0.75, 0.6, 0.45, 0.3, 0.2]
RUSH = 1.6

# Venues (public landmarks). Each event picks one of its candidates at random.
VENUES = {
    "las_ventas": (40.4320, -3.6634),
    "bernabeu": (40.4531, -3.6883),
    "metropolitano": (40.4362, -3.5995),
    "vallecas": (40.3919, -3.6589),
    "wizink": (40.4240, -3.6716),
    "ifema": (40.4636, -3.6163),
    "villaverde": (40.3420, -3.6950),
    "chueca": (40.4229, -3.6976),
    "gran_via": (40.4200, -3.7058),
    "paseo_prado": (40.4130, -3.6930),
    "castellana": (40.4300, -3.6895),
    "retiro": (40.4153, -3.6844),
    "malasana": (40.4260, -3.7040),
    "sol": SOL,
    "plaza_mayor": (40.4155, -3.7074),
}

# Fixed public holidays in Madrid (month, day); Easter Thursday/Friday are added per year.
HOLIDAYS = [(1, 1), (1, 6), (5, 1), (5, 2), (5, 15), (8, 15), (10, 12), (11, 1), (11, 9), (12, 6), (12, 8), (12, 25)]
SEASON = {1: 0.95, 2: 1.0, 3: 1.0, 4: 0.97, 5: 1.0, 6: 0.95, 7: 0.75, 8: 0.55, 9: 0.92, 10: 1.0, 11: 1.0, 12: 0.95}


def easter(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    return date(year, month, (h + l_ - 7 * m + 114) % 31 + 1)


@dataclass
class Event:
    kind: str
    start: datetime
    end: datetime
    demand: float = 1.0  # multiplier for demand at affected stops (or city-wide)
    speed: float = 1.0  # multiplier for speed of affected lines (or all)
    venue: str | None = None  # None: city-wide
    radius_m: float = 900.0
    lines: list[str] = field(default_factory=list)  # explicit lines (incidents)
    suspend: str = ""  # "", "all" or "some"


@dataclass
class Factors:
    city: float
    line_demand: dict[str, float]
    line_speed: dict[str, float]
    stop_demand: dict[str, float]
    suspended: set[str]
    max_load: dict[str, float]


@dataclass
class Scenario:
    seed: int
    start: date
    end: date
    line_target: dict[str, float]  # weekday rush mean load per line
    line_max_load: dict[str, float]
    overloaded_line: str
    events: list[Event]
    line_factor: dict[str, float] = field(default_factory=dict)  # demand multipliers that reach the targets
    rain_days: list[str] = field(default_factory=list)
    # derived, not serialised
    _stops_near: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _lines_near: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _by_day: dict[date, list[Event]] = field(default_factory=dict, repr=False)
    _days: dict[date, tuple] = field(default_factory=dict, repr=False)

    # --- serialisation (the private answer key) ---

    def to_json(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        d["start"], d["end"] = self.start.isoformat(), self.end.isoformat()
        for e in d["events"]:
            e["start"], e["end"] = e["start"].isoformat(), e["end"].isoformat()
        return d

    @classmethod
    def from_json(cls, d: dict, lines: dict[str, Line]) -> "Scenario":
        events = [Event(**{**e, "start": datetime.fromisoformat(e["start"]), "end": datetime.fromisoformat(e["end"])})
                  for e in d["events"]]
        s = cls(d["seed"], date.fromisoformat(d["start"]), date.fromisoformat(d["end"]), d["line_target"],
                d["line_max_load"], d["overloaded_line"], events, d.get("line_factor", {}), d.get("rain_days", []))
        s.index(lines)
        return s

    def index(self, lines: dict[str, Line]) -> None:
        """Precompute which stops/lines each venue touches and events per day."""
        stops = {s.stop_id: s for line in lines.values() for s in line.stops}
        for e in self.events:
            if e.venue and e.venue not in self._stops_near:
                center = VENUES[e.venue]
                near = [sid for sid, s in stops.items() if distance_m(center, (s.lat, s.lon)) <= e.radius_m]
                if not near:  # nothing in range: the closest few stops still feel it
                    near = sorted(stops, key=lambda sid: distance_m(center, (stops[sid].lat, stops[sid].lon)))[:4]
                self._stops_near[e.venue] = near
                near_set = set(near)
                self._lines_near[e.venue] = [lid for lid, ln in lines.items()
                                             if near_set & {s.stop_id for s in ln.stops}]
        self._by_day = {}
        for e in self.events:
            d = e.start.date()
            while d <= e.end.date():
                self._by_day.setdefault(d, []).append(e)
                d += timedelta(days=1)

    # --- calendar ---

    def holidays(self, year: int) -> set[date]:
        e = easter(year)
        return {date(year, m, d) for m, d in HOLIDAYS} | {e - timedelta(days=3), e - timedelta(days=2)}

    def day_type(self, d: date) -> str:
        if d.weekday() == 6 or d in self.holidays(d.year):
            return "sunday"
        return "saturday" if d.weekday() == 5 else "weekday"

    def school_day(self, d: date) -> bool:
        if d.weekday() >= 5 or d in self.holidays(d.year):
            return False
        if (d.month, d.day) >= (6, 21) and (d.month, d.day) < (9, 8):
            return False
        if (d.month, d.day) >= (12, 22) or (d.month, d.day) <= (1, 7):
            return False
        e = easter(d.year)
        return not (e - timedelta(days=8) <= d <= e + timedelta(days=1))

    def season(self, d: date) -> float:
        s = SEASON[d.month]
        if (d.month, d.day) >= (12, 22) or (d.month, d.day) <= (1, 6):
            s = 0.8
        e = easter(d.year)
        if e - timedelta(days=7) <= d <= e + timedelta(days=1):
            s = min(s, 0.8)
        return s

    # --- factors at an instant ---

    def _day(self, d: date) -> tuple:
        """Calendar facts of a day, cached: (profile, season, school day, rain, line demand)."""
        if d not in self._days:
            if len(self._days) > 64:
                self._days.clear()
            profile = {"weekday": WEEKDAY, "saturday": SATURDAY, "sunday": SUNDAY}[self.day_type(d)]
            jitter = random.Random(f"{self.seed}:{d.isoformat()}")
            line_demand = {lid: f * jitter.uniform(0.9, 1.1) for lid, f in sorted(self.line_factor.items())}
            self._days[d] = (profile, self.season(d), self.school_day(d), d.isoformat() in self.rain_days, line_demand)
        return self._days[d]

    def factors(self, t: datetime) -> Factors:
        t = t.replace(tzinfo=None)
        d = t.date()
        profile, season, school, rain, base_demand = self._day(d)
        h = t.hour + t.minute / 60
        i = int(h) % 24
        city = profile[i] + (profile[(i + 1) % 24] - profile[i]) * (h - int(h))
        city *= season / RUSH
        speed_all = 1.0
        if school and (8 <= h < 9.5 or 16.5 <= h < 18):
            city *= 1.08
            speed_all *= 0.85
        elif d.weekday() < 5 and not school:
            speed_all *= 1.05
        if rain:
            city *= 1.1
            speed_all *= 0.88

        line_demand = dict(base_demand)
        line_speed = {lid: speed_all for lid in self.line_factor}
        stop_demand: dict[str, float] = {}
        suspended: set[str] = set()
        for e in self._by_day.get(d, []):
            if not e.start <= t < e.end:
                continue
            if e.suspend == "all":
                suspended |= set(self.line_factor)
            elif e.suspend == "some":
                pick = random.Random(f"{self.seed}:{e.start.isoformat()}")
                suspended |= {lid for lid in sorted(self.line_factor) if pick.random() < 0.6}
            if e.venue:
                for sid in self._stops_near[e.venue]:
                    stop_demand[sid] = stop_demand.get(sid, 1.0) * e.demand
                for lid in self._lines_near[e.venue]:
                    line_speed[lid] = line_speed.get(lid, 1.0) * e.speed
            elif e.lines:
                for lid in e.lines:
                    line_speed[lid] = line_speed.get(lid, 1.0) * e.speed
                    line_demand[lid] = line_demand.get(lid, 1.0) * e.demand
            else:
                city *= e.demand
                for lid in line_speed:
                    line_speed[lid] *= e.speed
        return Factors(city, line_demand, line_speed, stop_demand, suspended, self.line_max_load)


# --- generation -------------------------------------------------------------------------------

def centrality(lines: dict[str, Line]) -> dict[str, float]:
    """1 for the line whose stops are closest to Sol on average, 0 for the farthest."""
    dist = {lid: sum(distance_m(SOL, (s.lat, s.lon)) for s in ln.stops) / len(ln.stops) for lid, ln in lines.items()}
    lo, hi = min(dist.values()), max(dist.values())
    return {lid: 1 - (v - lo) / (hi - lo or 1) for lid, v in dist.items()}


def _at(d: date, hour: float) -> datetime:
    return datetime.combine(d, time()) + timedelta(hours=hour)


def _random_day(rng: random.Random, start: date, end: date, weekday: int | None = None) -> date:
    d = start + timedelta(days=rng.randrange(max(1, (end - start).days)))
    if weekday is not None:
        d += timedelta(days=(weekday - d.weekday()) % 7)
    return d


def generate(lines: dict[str, Line], start: date, end: date, seed: int | None = None) -> Scenario:
    """Draw line targets, the overloaded peripheral line and every event between start and end."""
    if seed is None:
        seed = random.SystemRandom().randrange(2**63)
    rng = random.Random(seed)
    central = centrality(lines)
    target = {lid: round(min(0.75, max(0.2, 0.30 + 0.25 * c + rng.uniform(-0.05, 0.05))), 3)
              for lid, c in central.items()}
    # by rank, not distance: one far-out line (the airport) would otherwise leave few candidates
    peripheral = sorted(sorted(central, key=central.get)[: max(3, len(central) * 2 // 5)])
    overloaded = rng.choice(peripheral)
    target[overloaded] = round(rng.uniform(0.9, 1.0), 3)
    max_load = {lid: 1.0 for lid in lines}
    max_load[overloaded] = 1.2

    events: list[Event] = []
    rain: list[str] = []
    ids = sorted(lines)
    for year in range(start.year, end.year + 1):
        def window(m1, d1, m2, d2, year=year):
            return date(year, m1, d1), date(year, m2, d2)

        # Snowstorm: three days of cut traffic, once a year in winter.
        d0 = _random_day(rng, *window(1, 2, 2, 25))
        sev = rng.uniform(0.15, 0.35)
        events += [
            Event("snowstorm", _at(d0, 0), _at(d0 + timedelta(days=2), 0), demand=sev, speed=0.05, suspend="all"),
            Event("snowstorm", _at(d0 + timedelta(days=2), 0), _at(d0 + timedelta(days=3), 0),
                  demand=sev + 0.3, speed=0.5, suspend="some"),
        ]
        # National day: parade on the Castellana in the morning.
        d = date(year, 10, 12)
        events.append(Event("national_day_parade", _at(d, 9.5), _at(d, 14), demand=rng.uniform(1.6, 2.4),
                            speed=0.3, venue="castellana", radius_m=1500))
        # Bullfighting season: half of the Sundays from spring to autumn, plus a ~4-week fair.
        d = _random_day(rng, *window(3, 10, 3, 25), weekday=6)
        while d <= date(year, 10, 15):
            if rng.random() < 0.5:
                k = rng.uniform(2.0, 3.5)
                events += [
                    Event("bullfight", _at(d, 17.5), _at(d, 19), demand=k, speed=0.8, venue="las_ventas"),
                    Event("bullfight", _at(d, 20.5), _at(d, 21.75), demand=k * 1.2, speed=0.8, venue="las_ventas"),
                ]
            d += timedelta(days=7)
        fair = _random_day(rng, *window(5, 3, 5, 12))
        for n in range(rng.randint(21, 30)):
            d = fair + timedelta(days=n)
            k = rng.uniform(1.8, 3.0)
            events += [Event("bullfight_fair", _at(d, 18), _at(d, 19), demand=k, speed=0.8, venue="las_ventas"),
                       Event("bullfight_fair", _at(d, 21), _at(d, 22), demand=k * 1.2, speed=0.8, venue="las_ventas")]
        # Pride: a week of evenings around Chueca, a Saturday parade that cuts the centre.
        sat = _random_day(rng, *window(6, 26, 7, 12), weekday=5)
        for n in range(-3, 2):
            d = sat + timedelta(days=n)
            events.append(Event("pride", _at(d, 19), _at(d, 24), demand=rng.uniform(1.5, 2.2), speed=0.85,
                                venue="chueca", radius_m=800))
        events.append(Event("pride_parade", _at(sat, 17), _at(sat, 23.5), demand=rng.uniform(2.0, 3.0), speed=0.35,
                            venue=rng.choice(["paseo_prado", "gran_via"]), radius_m=1400))
        # Carnival weekend.
        d = _random_day(rng, *window(2, 1, 3, 3), weekday=5)
        events.append(Event("carnival", _at(d, 17), _at(d, 22), demand=rng.uniform(1.4, 1.9), speed=0.7,
                            venue="retiro", radius_m=1000))
        # Halloween night.
        d = date(year, 10, 31)
        events.append(Event("halloween", _at(d, 20), _at(d, 24), demand=rng.uniform(1.5, 2.0), speed=0.9,
                            venue=rng.choice(["malasana", "gran_via"]), radius_m=900))
        # Holy Week processions on Thursday and Friday evenings.
        e = easter(year)
        for d in (e - timedelta(days=3), e - timedelta(days=2)):
            events.append(Event("procession", _at(d, 19), _at(d, 23), demand=rng.uniform(1.3, 1.7), speed=0.6,
                                venue=rng.choice(["sol", "plaza_mayor"]), radius_m=900))
        # Football: Sundays only (simplification), season from late August to May.
        d = date(year, 1, 1)
        while d.year == year:
            if d.weekday() == 6 and not (5, 26) <= (d.month, d.day) <= (8, 15):
                for venue in rng.sample(["bernabeu", "metropolitano", "vallecas"], rng.choice([1, 1, 2])):
                    ko = rng.choice([14, 16.25, 18.5, 21])
                    k = rng.uniform(2.5, 4.0)
                    events += [Event("football", _at(d, ko - 1.5), _at(d, ko), demand=k, speed=0.7, venue=venue),
                               Event("football", _at(d, ko + 1.75), _at(d, min(ko + 3, 23.9)), demand=k * 1.2,
                                     speed=0.7, venue=venue)]
            d += timedelta(days=1)
        # Concerts: three Friday-to-Sunday runs per quarter.
        for q in range(4):
            q_start = date(year, 3 * q + 1, 1)
            q_end = date(year + (q == 3), (3 * q + 3) % 12 + 1, 1) - timedelta(days=3)
            fridays = [q_start + timedelta(days=n) for n in range((q_end - q_start).days)
                       if (q_start + timedelta(days=n)).weekday() == 4]
            for fri in sorted(rng.sample(fridays, 3)):
                venue = rng.choice(["wizink", "metropolitano", "bernabeu", "ifema"])
                k = rng.uniform(2.0, 4.0)
                for n in range(3):
                    d = fri + timedelta(days=n)
                    events += [Event("concert", _at(d, 18.5), _at(d, 20.5), demand=k, speed=0.8, venue=venue),
                               Event("concert", _at(d, 23), _at(d, 23.99), demand=k * 1.3, speed=0.8, venue=venue)]
        # Four-day summer festival, Wednesday to Saturday.
        wed = _random_day(rng, *window(7, 1, 7, 20), weekday=2)
        venue = rng.choice(["villaverde", "ifema"])
        for n in range(4):
            d = wed + timedelta(days=n)
            events += [Event("festival", _at(d, 16.5), _at(d, 20), demand=rng.uniform(2.5, 4.0), speed=0.75,
                             venue=venue, radius_m=1500),
                       Event("festival", _at(d, 23), _at(d, 23.99), demand=rng.uniform(3.0, 5.0), speed=0.75,
                             venue=venue, radius_m=1500)]
        # Heat waves: quieter afternoons.
        for _ in range(rng.randint(1, 2)):
            d0 = _random_day(rng, *window(6, 20, 8, 20))
            for n in range(rng.randint(4, 7)):
                d = d0 + timedelta(days=n)
                events.append(Event("heatwave", _at(d, 13), _at(d, 19), demand=rng.uniform(0.75, 0.9)))
        # Random incidents: breakdowns, accidents and multi-day roadworks on one line, protests downtown.
        for _ in range(rng.randint(20, 35)):
            d = _random_day(rng, date(year, 1, 1), date(year, 12, 28))
            kind = rng.choice(["accident", "breakdown", "roadworks", "protest"])
            if kind == "protest":
                h = rng.uniform(11, 18)
                events.append(Event(kind, _at(d, h), _at(d, h + rng.uniform(2, 4)), demand=rng.uniform(1.2, 1.6),
                                    speed=rng.uniform(0.3, 0.6), venue=rng.choice(["sol", "gran_via", "castellana"]),
                                    radius_m=1200))
            elif kind == "roadworks":
                events.append(Event(kind, _at(d, 0), _at(d + timedelta(days=rng.randint(3, 12)), 0),
                                    speed=rng.uniform(0.6, 0.8), lines=[rng.choice(ids)]))
            else:
                h = rng.uniform(7, 21)
                events.append(Event(kind, _at(d, h), _at(d, h + rng.uniform(1, 4)), speed=rng.uniform(0.3, 0.6),
                                    lines=[rng.choice(ids)]))
        # Rain: more likely from autumn to spring.
        d = date(year, 1, 1)
        while d.year == year:
            if rng.random() < (0.05 if d.month in (6, 7, 8) else 0.16):
                rain.append(d.isoformat())
            d += timedelta(days=1)

    events = [e for e in events if e.end.date() >= start and e.start.date() <= end]
    events.sort(key=lambda e: e.start)
    s = Scenario(seed, start, end, target, max_load, overloaded, events, rain_days=sorted(rain))
    s.index(lines)
    return s


def summary(s: Scenario) -> str:
    """Counts only: printing dates would give the story away in logs."""
    kinds: dict[str, int] = {}
    for e in s.events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    span = f"{s.start} .. {s.end}"
    return f"scenario {span}: {len(s.events)} events ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})"

