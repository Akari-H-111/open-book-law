"""Metrics and statistics, written by hand. Rankings are lists of docids, best first."""

import math

import numpy as np

Z_95 = 1.959963984540054


def recall_at_k(ranked, relevant, k):
    """Share of the relevant documents found in the top k."""
    return len(relevant.intersection(ranked[:k])) / len(relevant)


def hit_at_k(ranked, relevant, k):
    """1 if at least one relevant document is in the top k. The paper's upper bound on housing."""
    return float(not relevant.isdisjoint(ranked[:k]))


def all_at_k(ranked, relevant, k):
    """1 if every relevant document is in the top k. The paper's lower bound on housing."""
    return float(relevant.issubset(ranked[:k]))


def mrr_at_k(ranked, relevant, k):
    """Reciprocal rank of the first relevant document in the top k, or 0."""
    for i, docid in enumerate(ranked[:k]):
        if docid in relevant:
            return 1.0 / (i + 1)
    return 0.0


def paired_bootstrap(a, b, n_resamples=10_000, seed=20261103, chunk=500):
    """Percentile bootstrap over questions for mean(a) - mean(b). Returns (difference, low, high)."""
    diffs = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = []
    for start in range(0, n_resamples, chunk):
        size = min(chunk, n_resamples - start)
        picks = rng.integers(0, len(diffs), size=(size, len(diffs)))
        means.append(diffs[picks].mean(axis=1))
    low, high = np.percentile(np.concatenate(means), [2.5, 97.5])
    return float(diffs.mean()), float(low), float(high)


def mcnemar_exact(a_correct, b_correct):
    """Two-sided exact McNemar test on paired booleans. Returns (a only, b only, p)."""
    a_only = sum(1 for x, y in zip(a_correct, b_correct, strict=True) if x and not y)
    b_only = sum(1 for x, y in zip(a_correct, b_correct, strict=True) if y and not x)
    n = a_only + b_only
    if n == 0:
        return 0, 0, 1.0
    tail = sum(math.comb(n, i) for i in range(min(a_only, b_only) + 1))
    # Python divides two big integers without overflow and rounds only the final result.
    return a_only, b_only, min(1.0, 2 * tail / 2**n)


def holm(p_values):
    """Holm step-down adjusted p-values, in the input order."""
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for position, i in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - position) * p_values[i]))
        adjusted[i] = running
    return adjusted


def wilson(successes, n, z=Z_95):
    """Wilson score interval for a proportion. Returns (low, high)."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)
