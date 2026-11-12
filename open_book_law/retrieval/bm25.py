"""BM25 written by hand, with an inverted index held in numpy arrays.

score(d, q) = sum over query tokens t of idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
idf(t) = log((N - df + 0.5) / (df + 0.5) + 1)

A token repeated in the query counts once per occurrence. We understand that Lucene does the same, untested.
"""

import re
from array import array
from collections import Counter

import numpy as np

WORD = re.compile(r"\w+")
POSSESSIVE = re.compile(r"['’]s\b")
LUCENE_ENGLISH_STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that the their then there "
    "these they this to was will with".split()
)
TIE_SEED = 20261103


def plain_tokens(text):
    return WORD.findall(text.lower())


def make_porter_tokens():
    """Diagnostic tokenizer: lowercase, drop possessives, Lucene's stopwords, Porter stemmer."""
    from nltk.stem.porter import PorterStemmer

    stem = PorterStemmer(mode=PorterStemmer.ORIGINAL_ALGORITHM).stem
    cache = {}

    def tokens(text):
        out = []
        for word in WORD.findall(POSSESSIVE.sub("", text.lower())):
            if word not in LUCENE_ENGLISH_STOPWORDS:
                stemmed = cache.get(word)
                if stemmed is None:
                    stemmed = cache[word] = stem(word)
                out.append(stemmed)
        return out

    return tokens


def get_tokenizer(name):
    if name == "plain":
        return plain_tokens
    if name == "porter":
        return make_porter_tokens()
    raise ValueError(f"unknown tokenizer {name}")


def neutral_tie_order(n, seed=TIE_SEED):
    """A fixed random order for ties. The pool file lists gold passages first, so its order is not neutral."""
    return np.random.default_rng(seed).permutation(n)


def top_k(scores, k, tie, positive_only=False):
    """Return (positions, scores) of the k best scores, best first. Equal scores go in `tie` order."""
    if scores.size > k:
        threshold = np.partition(scores, scores.size - k)[scores.size - k]
        candidates = np.flatnonzero(scores >= threshold)
    else:
        candidates = np.arange(scores.size)
    if positive_only:
        candidates = candidates[scores[candidates] > 0]
    order = np.lexsort((tie[candidates], -scores[candidates]))[:k]
    picked = candidates[order]
    return picked, scores[picked]


def build_index(texts, tokenizer="plain", k1=0.9, b=0.4):
    """Build the index from an iterable of strings. Arrays hold the many postings in little memory."""
    tokens = get_tokenizer(tokenizer)
    vocab = {}
    doc_lengths = array("I")
    terms, docs, tfs = array("I"), array("I"), array("I")
    for doc, text in enumerate(texts):
        counts = Counter(tokens(text))
        doc_lengths.append(sum(counts.values()))
        for term, tf in counts.items():
            terms.append(vocab.setdefault(term, len(vocab)))
            docs.append(doc)
            tfs.append(tf)

    n_docs = len(doc_lengths)
    term_ids = np.frombuffer(terms, dtype=np.uint32)
    order = np.argsort(term_ids, kind="stable")
    df = np.bincount(term_ids, minlength=len(vocab))
    lengths = np.frombuffer(doc_lengths, dtype=np.uint32).astype(np.float64)
    average_length = float(lengths.mean())
    return {
        "tokens": tokens,
        "k1": k1,
        "vocab": vocab,
        "offsets": np.concatenate(([0], np.cumsum(df))),
        "postings_doc": np.frombuffer(docs, dtype=np.uint32)[order],
        "postings_tf": np.frombuffer(tfs, dtype=np.uint32)[order],
        "idf": np.log((n_docs - df + 0.5) / (df + 0.5) + 1),
        "norm": k1 * (1 - b + b * lengths / average_length),
        "average_length": average_length,
        "tie": neutral_tie_order(n_docs),
        "buffer": np.zeros(n_docs, dtype=np.float64),
    }


def score_all(index, query):
    """Scores of all documents for one query. The array is reused by the next call."""
    scores = index["buffer"]
    scores[:] = 0.0
    k1 = index["k1"]
    for term, query_tf in Counter(index["tokens"](query)).items():
        term_id = index["vocab"].get(term)
        if term_id is None:
            continue
        start, end = index["offsets"][term_id], index["offsets"][term_id + 1]
        docs = index["postings_doc"][start:end]
        tf = index["postings_tf"][start:end].astype(np.float64)
        scores[docs] += query_tf * index["idf"][term_id] * tf * (k1 + 1) / (tf + index["norm"][docs])
    return scores


def search(index, query, k=1000):
    """Positions of the top k matching documents, best first, with their scores."""
    return top_k(score_all(index, query), k, index["tie"], positive_only=True)
