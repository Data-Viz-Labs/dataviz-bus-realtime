"""Passenger demand: time-of-day arrival rates and per-queue Poisson arrivals."""

import math
import random

# (start_hour, multiplier): night, morning rush, mid-morning, lunch, afternoon, evening rush, night
_PROFILE = [(0, 0.2), (6, 1.5), (9, 0.6), (12, 1.2), (15, 0.8), (18, 1.4), (21, 0.2)]


def time_multiplier(hour: int) -> float:
    if not 0 <= hour <= 23:
        raise ValueError(f"hour must be in 0..23, got {hour}")
    return next(m for start, m in reversed(_PROFILE) if hour >= start)


def poisson(rng: random.Random, lam: float) -> int:
    if lam < 0:
        raise ValueError(f"lambda must be >= 0, got {lam}")
    if lam == 0:
        return 0
    if lam > 30:  # normal approximation, Knuth's loop underflows for large lambda
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def binomial(rng: random.Random, n: int, p: float) -> int:
    if p >= 1:
        return n
    return sum(rng.random() < p for _ in range(n))
