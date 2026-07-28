from __future__ import annotations

from collections import Counter, defaultdict


def percentage_agreement(first: list, second: list) -> float:
    if not first or len(first) != len(second):
        raise ValueError("paired non-empty ratings required")
    return sum(a == b for a, b in zip(first, second)) / len(first)


def cohens_kappa(first: list, second: list, weights: str | None = None) -> float:
    agreement = percentage_agreement(first, second); categories = sorted(set(first) | set(second))
    if weights is None:
        expected = sum(first.count(c) / len(first) * second.count(c) / len(second) for c in categories)
        return (agreement - expected) / (1 - expected) if expected != 1 else 1.0
    if weights not in {"linear", "quadratic"}:
        raise ValueError("weights must be linear or quadratic")
    span = max(1, len(categories) - 1); index = {c: i for i, c in enumerate(categories)}
    weight = lambda a, b: (abs(index[a] - index[b]) / span) ** (2 if weights == "quadratic" else 1)
    observed = sum(weight(a, b) for a, b in zip(first, second)) / len(first)
    expected = sum(weight(a, b) * first.count(a) * second.count(b) for a in categories for b in categories) / len(first) ** 2
    return 1 - observed / expected if expected else 1.0


def fleiss_kappa(ratings: dict[str, list]) -> float:
    if not ratings or len({len(v) for v in ratings.values()}) != 1:
        raise ValueError("each item needs the same number of ratings")
    n = len(next(iter(ratings.values())))
    if n < 2:
        raise ValueError("at least two reviewers required")
    categories = sorted({r for values in ratings.values() for r in values})
    counts = {item: Counter(values) for item, values in ratings.items()}
    p_bar = sum((sum(counts[item][c] ** 2 for c in categories) - n) / (n * (n - 1)) for item in ratings) / len(ratings)
    totals = defaultdict(int)
    for values in ratings.values():
        for value in values: totals[value] += 1
    p_e = sum((totals[c] / (len(ratings) * n)) ** 2 for c in categories)
    return (p_bar - p_e) / (1 - p_e) if p_e != 1 else 1.0
