import math

import pytest

from open_book_law import evalx


def test_rank_metrics_by_hand():
    ranked = ["a", "b", "c", "d"]
    relevant = {"b", "d", "z"}
    assert evalx.recall_at_k(ranked, relevant, 2) == pytest.approx(1 / 3)
    assert evalx.recall_at_k(ranked, relevant, 4) == pytest.approx(2 / 3)
    assert evalx.hit_at_k(ranked, relevant, 1) == 0.0
    assert evalx.hit_at_k(ranked, relevant, 2) == 1.0
    assert evalx.all_at_k(ranked, relevant, 4) == 0.0
    assert evalx.all_at_k(ranked, {"a", "c"}, 3) == 1.0
    assert evalx.mrr_at_k(ranked, relevant, 10) == 0.5
    assert evalx.mrr_at_k(ranked, relevant, 1) == 0.0


def test_bootstrap_is_deterministic_and_paired():
    a = [1.0, 0.3, 0.7, 0.2, 0.9, 0.4, 0.8, 0.6, 0.1, 0.5]
    b = [0.5, 0.25, 0.1, 0.0, 0.85, 0.15, 0.35, 0.6, 0.05, 0.45]
    first = evalx.paired_bootstrap(a, b, n_resamples=2000, seed=7)
    assert first == evalx.paired_bootstrap(a, b, n_resamples=2000, seed=7)
    assert first != evalx.paired_bootstrap(a, b, n_resamples=2000, seed=8)
    assert first[0] == pytest.approx(0.22)
    assert first[1] <= first[0] <= first[2]
    assert evalx.paired_bootstrap(a, a, n_resamples=100) == (0.0, 0.0, 0.0)


def test_bootstrap_chunks_do_not_change_the_count():
    difference, low, high = evalx.paired_bootstrap([1, 0], [0, 0], n_resamples=1001, chunk=100)
    assert (difference, low, high) == (0.5, 0.0, 1.0)


def test_mcnemar_exact_values():
    # 5 discordant pairs, split 1 and 4: p = 2 * (1 + 5) / 32 = 0.375.
    a = [True] * 1 + [False] * 4 + [True] * 3
    b = [False] * 1 + [True] * 4 + [True] * 3
    assert evalx.mcnemar_exact(a, b) == (1, 4, 0.375)
    # An even split gives p = 1 after the cap.
    assert evalx.mcnemar_exact([True, False], [False, True])[2] == 1.0
    assert evalx.mcnemar_exact([True], [True]) == (0, 0, 1.0)
    # All 10 go one way: p = 2 / 1024.
    assert evalx.mcnemar_exact([True] * 10, [False] * 10)[2] == pytest.approx(2 / 1024)


def test_mcnemar_large_counts_do_not_overflow():
    _, _, p = evalx.mcnemar_exact([True] * 2000 + [False] * 2000, [False] * 2000 + [True] * 2000)
    assert p == 1.0


def test_holm_by_hand():
    # Sorted 0.01, 0.03, 0.04: times 3, 2, 1 gives 0.03, 0.06, 0.06 after the running maximum.
    assert evalx.holm([0.04, 0.01, 0.03]) == pytest.approx([0.06, 0.03, 0.06])
    assert evalx.holm([0.9, 0.8]) == pytest.approx([1.0, 1.0])
    assert evalx.holm([]) == []


def test_wilson_by_hand():
    # Standard example: 8 of 10.
    z = evalx.Z_95
    p, n = 0.8, 10
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    assert evalx.wilson(8, 10) == pytest.approx((centre - margin, centre + margin))
    assert evalx.wilson(8, 10) == pytest.approx((0.4902, 0.9433), abs=1e-3)
    assert evalx.wilson(0, 10)[0] == 0.0
    assert evalx.wilson(10, 10)[1] == pytest.approx(1.0)
    assert evalx.wilson(0, 0) == (0.0, 1.0)
