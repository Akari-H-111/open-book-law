import math

import numpy as np
import pytest

from open_book_law.retrieval import bm25

DOCS = ["the cat sat", "the dog sat on the mat", "cats and dogs", "a cat, a cat, a CAT"]


def hand_score(tf, dl, df, n_docs, avgdl, k1=0.9, b=0.4):
    idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
    return idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))


def test_plain_tokens():
    assert bm25.plain_tokens("A cat's, CAT-like 42!") == ["a", "cat", "s", "cat", "like", "42"]


def test_score_matches_hand_calculation():
    index = bm25.build_index(DOCS)
    # Lengths are 3, 6, 3 and 6, so the average is 4.5. "cat" is in documents 0 and 3 (df = 2).
    assert index["average_length"] == 4.5
    scores = bm25.score_all(index, "cat").copy()
    assert scores[0] == pytest.approx(hand_score(1, 3, 2, 4, 4.5))
    assert scores[1] == 0.0
    assert scores[2] == 0.0
    assert scores[3] == pytest.approx(hand_score(3, 6, 2, 4, 4.5))


def test_multiple_terms_add_and_repeats_count_per_occurrence():
    index = bm25.build_index(DOCS)
    one = bm25.score_all(index, "sat").copy()
    other = bm25.score_all(index, "mat").copy()
    both = bm25.score_all(index, "sat mat").copy()
    assert both == pytest.approx(one + other)
    assert bm25.score_all(index, "sat sat").copy() == pytest.approx(2 * one)


def test_scores_with_other_parameters():
    index = bm25.build_index(DOCS, k1=1.5, b=0.75)
    assert bm25.score_all(index, "dog")[1] == pytest.approx(hand_score(1, 6, 1, 4, 4.5, k1=1.5, b=0.75))


def test_search_order_and_only_matching_documents():
    index = bm25.build_index(DOCS)
    positions, scores = bm25.search(index, "cat", k=10)
    assert sorted(positions.tolist()) == [0, 3]
    assert scores[0] >= scores[1]
    assert bm25.search(index, "unknownword", k=10)[0].size == 0


def test_top_k_breaks_ties_in_the_given_order():
    scores = np.array([1.0, 2.0, 2.0, 2.0, 0.5])
    positions, _ = bm25.top_k(scores, 2, np.array([0, 3, 1, 2, 4]))
    assert positions.tolist() == [2, 3]
    positions, _ = bm25.top_k(scores, 2, np.array([0, 1, 3, 2, 4]))
    assert positions.tolist() == [1, 3]
    assert bm25.top_k(np.array([0.0, 1.0]), 5, np.array([0, 1]), positive_only=True)[0].tolist() == [1]


def test_neutral_tie_order_is_fixed():
    assert np.array_equal(bm25.neutral_tie_order(50), bm25.neutral_tie_order(50))
    assert sorted(bm25.neutral_tie_order(50).tolist()) == list(range(50))


def test_porter_tokens_stem_and_drop_stopwords():
    pytest.importorskip("nltk")
    tokens = bm25.make_porter_tokens()
    assert tokens("The court's rulings and the running of it") == ["court", "rule", "run"]
    index = bm25.build_index(["the rulings", "dogs"], tokenizer="porter")
    assert bm25.search(index, "ruling", k=5)[0].tolist() == [0]
