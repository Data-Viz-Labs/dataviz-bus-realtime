from collections import Counter
from datetime import date, datetime, timedelta

import pytest
from sim.config import load_network
from sim.scenario import Scenario, centrality, easter, generate

from tests.conftest import LINES_YAML


@pytest.fixture(scope="module")
def lines():
    return load_network(LINES_YAML)[0]


@pytest.fixture(scope="module")
def scenario(lines):
    s = generate(lines, date(2024, 1, 1), date(2026, 12, 31), seed=11)
    s.line_factor = {lid: 1.0 for lid in lines}
    return s


def days(s: Scenario, kind: str) -> list[date]:
    return sorted({e.start.date() for e in s.events if e.kind == kind})


def test_easter():
    assert [easter(y) for y in (2024, 2025, 2026)] == [date(2024, 3, 31), date(2025, 4, 20), date(2026, 4, 5)]


def test_line_targets_follow_centrality_and_one_peripheral_line_is_overloaded(lines, scenario):
    c = centrality(lines)
    assert sorted(c, key=c.get).index(scenario.overloaded_line) < len(c) * 2 // 5  # among the 40 % farthest
    assert 0.9 <= scenario.line_target[scenario.overloaded_line] <= 1.0
    assert scenario.line_max_load[scenario.overloaded_line] == 1.2
    assert [lid for lid, m in scenario.line_max_load.items() if m > 1] == [scenario.overloaded_line]
    others = [lid for lid in lines if lid != scenario.overloaded_line]
    central = [scenario.line_target[lid] for lid in others if c[lid] > 0.7]
    peripheral = [scenario.line_target[lid] for lid in others if c[lid] < 0.3]
    assert sum(central) / len(central) > sum(peripheral) / len(peripheral) + 0.1


def test_one_three_day_snowstorm_per_year_in_winter(scenario):
    storms = [e for e in scenario.events if e.kind == "snowstorm"]
    by_year = Counter(e.start.year for e in storms if e.suspend == "all")
    assert set(by_year.values()) == {1}
    for e in storms:
        assert e.start.month in (1, 2, 3)
    assert all((e.end - e.start) in (timedelta(days=2), timedelta(days=1)) for e in storms)


def test_concerts_three_weekends_per_quarter_friday_to_sunday(scenario):
    d = days(scenario, "concert")
    assert {x.weekday() for x in d} <= {4, 5, 6}
    fridays = [x for x in d if x.weekday() == 4]
    per_quarter = Counter((x.year, (x.month - 1) // 3) for x in fridays)
    assert per_quarter and max(per_quarter.values()) <= 3 and sum(per_quarter.values()) >= 30


def test_festival_runs_wednesday_to_saturday_in_july(scenario):
    for year in (2024, 2025, 2026):
        d = [x for x in days(scenario, "festival") if x.year == year]
        assert [x.weekday() for x in d] == [2, 3, 4, 5] and all(x.month == 7 for x in d)


def test_football_only_on_sundays_outside_summer(scenario):
    d = days(scenario, "football")
    assert d and {x.weekday() for x in d} == {6}
    assert not [x for x in d if x.month in (6, 7)]


def test_fixed_calendar_events(scenario):
    assert {x for x in days(scenario, "national_day_parade")} == {date(y, 10, 12) for y in (2024, 2025, 2026)}
    assert {x for x in days(scenario, "halloween")} == {date(y, 10, 31) for y in (2024, 2025, 2026)}
    assert {x.weekday() for x in days(scenario, "procession")} == {3, 4}
    pride = days(scenario, "pride_parade")
    assert len(pride) == 3 and {x.weekday() for x in pride} == {5}


def test_dates_change_with_every_secret_seed(lines):
    a = generate(lines, date(2025, 1, 1), date(2025, 12, 31))
    b = generate(lines, date(2025, 1, 1), date(2025, 12, 31))
    assert a.seed != b.seed
    assert days(a, "concert") != days(b, "concert") or days(a, "snowstorm") != days(b, "snowstorm")


def test_factors_tell_the_story(scenario):
    def city(t):
        return scenario.factors(t).city

    weekday, saturday, sunday = datetime(2025, 10, 21, 8), datetime(2025, 10, 25, 8), datetime(2025, 10, 26, 8)
    assert city(weekday) > city(saturday) > city(sunday)
    assert city(datetime(2025, 8, 12, 8)) < 0.7 * city(datetime(2025, 10, 14, 8))  # summer
    assert city(datetime(2025, 5, 15, 8)) < city(datetime(2025, 5, 14, 8))  # local holiday
    school = scenario.factors(datetime(2025, 10, 21, 8, 30)).line_speed["27"]
    no_school = scenario.factors(datetime(2025, 7, 22, 8, 30)).line_speed["27"]
    assert school < no_school
    storm = next(e for e in scenario.events if e.kind == "snowstorm")
    assert scenario.factors(storm.start + timedelta(hours=10)).suspended == set(scenario.line_factor)
    match = next(e for e in scenario.events if e.kind == "football")
    f = scenario.factors(match.start + timedelta(minutes=30))
    assert f.stop_demand and min(f.stop_demand.values()) > 2


def test_answer_key_round_trip(lines, scenario):
    back = Scenario.from_json(scenario.to_json(), lines)
    t = datetime(2025, 6, 1, 18)
    assert back.factors(t) == scenario.factors(t)
