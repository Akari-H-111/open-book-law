from open_book_law.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_by_hand():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    # b: 1/62 + 1/61. a: 1/61. d: 1/62. c: 1/63.
    assert fused == ["b", "a", "d", "c"]


def test_rrf_uses_k():
    rankings = [["a", "x", "y", "b"], ["p", "q", "r", "b"]]
    # With k = 1, a scores 1/2 and b (rank 4 twice) scores 2/5. With k = 60, a scores 1/61 and b scores 2/64.
    assert reciprocal_rank_fusion(rankings, k=1)[0] == "a"
    assert reciprocal_rank_fusion(rankings, k=60)[0] == "b"


def test_rrf_depth_and_ties():
    assert reciprocal_rank_fusion([["b"], ["a"]]) == ["a", "b"]
    assert reciprocal_rank_fusion([["a", "b", "c"]], depth=2) == ["a", "b"]
