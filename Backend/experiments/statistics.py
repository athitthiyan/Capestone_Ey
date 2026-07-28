from __future__ import annotations

import math
import random
from statistics import mean
from typing import Callable


def bootstrap_ci(values: list[float], statistic: Callable[[list[float]], float] = mean, *, seed: int = 20260728, samples: int = 2000) -> dict:
    if not values:
        return {"estimate": None, "lower": None, "upper": None, "samples": 0}
    rng = random.Random(seed); draws = []
    for _ in range(samples):
        draws.append(statistic([rng.choice(values) for _ in values]))
    draws.sort()
    return {"estimate": statistic(values), "lower": draws[int(.025 * samples)], "upper": draws[min(samples - 1, int(.975 * samples))], "samples": samples, "seed": seed}


def mcnemar_test(labels: list[int], first: list[int], second: list[int]) -> dict:
    if not (len(labels) == len(first) == len(second)) or not labels:
        raise ValueError("paired non-empty inputs must have equal lengths")
    b = sum(a == y and c != y for y, a, c in zip(labels, first, second))
    c = sum(a != y and c_ == y for y, a, c_ in zip(labels, first, second))
    n = b + c
    if n == 0:
        return {"discordant_first_only": b, "discordant_second_only": c, "p_value": 1.0}
    tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2**n)
    return {"discordant_first_only": b, "discordant_second_only": c, "p_value": min(1.0, 2 * tail), "test": "exact two-sided McNemar/binomial"}


def permutation_mean_difference(first: list[float], second: list[float], *, seed: int = 20260728, samples: int = 5000) -> dict:
    if not first or not second:
        raise ValueError("both samples are required")
    rng = random.Random(seed); observed = mean(first) - mean(second); pooled = first + second; extreme = 0
    for _ in range(samples):
        shuffled = pooled[:]; rng.shuffle(shuffled)
        diff = mean(shuffled[: len(first)]) - mean(shuffled[len(first) :])
        extreme += abs(diff) >= abs(observed)
    return {"mean_difference": observed, "p_value": (extreme + 1) / (samples + 1), "samples": samples, "seed": seed}


def stratified_bootstrap_ci(values: list[float], strata: list[str], *, seed: int = 20260728,
                            samples: int = 2000) -> dict:
    if not values or len(values) != len(strata):
        raise ValueError("equally sized non-empty values and strata required")
    groups = {name: [v for v, s in zip(values, strata) if s == name] for name in set(strata)}
    rng = random.Random(seed); estimates = []
    for _ in range(samples):
        draw = [rng.choice(group) for group in groups.values() for _ in group]
        estimates.append(mean(draw))
    estimates.sort()
    return {"estimate": mean(values), "lower": estimates[int(.025 * samples)],
            "upper": estimates[min(samples - 1, int(.975 * samples))], "samples": samples,
            "seed": seed, "stratified": True}
