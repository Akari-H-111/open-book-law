"""Reciprocal rank fusion."""

RRF_K = 60


def reciprocal_rank_fusion(rankings, k=RRF_K, depth=1000):
    """Fuse lists of docids, best first, by the sum of 1 / (k + rank). Ties go to the smaller docid."""
    scores = {}
    for ranking in rankings:
        for rank, docid in enumerate(ranking, start=1):
            scores[docid] = scores.get(docid, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda docid: (-scores[docid], docid))[:depth]
