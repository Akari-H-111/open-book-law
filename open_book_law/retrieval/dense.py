"""E5 encoding and exact dot-product search, with no vector database.

A store is a directory DATA_ROOT/derived/embeddings/<model>/ with, for each collection of passages:
  <collection>.npy            float16 vectors, unit length before rounding
  <collection>.sha1.bin       20-byte SHA-1 of each text, in the same row order
  <collection>.progress.json  rows written and source items consumed

Identical text is encoded once. Encoding is resumable: vectors and hashes reach the disk before the
progress file changes, so a crash loses at most the block in progress.
"""

import hashlib
import itertools
import json
import os
import time

import numpy as np

from open_book_law.paths import DERIVED_DIR
from open_book_law.retrieval.bm25 import neutral_tie_order, top_k

MODELS = {
    "e5-small": "intfloat/e5-small-v2",
    "e5-base": "intfloat/e5-base-v2",
    "e5-large": "intfloat/e5-large-v2",
}
BATCH_SIZES = {"e5-small": 64, "e5-base": 32, "e5-large": 16}
DEVICE = "mps"
MAX_LENGTH = 512
BLOCK_SIZE = 20_000
# Equal scores can straddle a chunk boundary, so each chunk keeps a few more than k before the final sort.
TIE_SLACK = 100


def store_dir(retriever):
    return DERIVED_DIR / "embeddings" / retriever


def load_model(model_id, revision=None):
    """Load tokenizer and weights from the local cache. A fine-tuned model is a path with no revision."""
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, local_files_only=True)
    model = AutoModel.from_pretrained(
        model_id, revision=revision, local_files_only=True, trust_remote_code=False, use_safetensors=True
    )
    return tokenizer, model.to(DEVICE).eval()


def pooled_vectors(tokenizer, model, texts, max_length=MAX_LENGTH):
    """Average pooling and L2 normalization, as the E5 model cards specify. Texts carry their prefix."""
    import torch

    batch = tokenizer(texts, max_length=max_length, padding=True, truncation=True, return_tensors="pt")
    batch = {key: value.to(model.device) for key, value in batch.items()}
    hidden = model(**batch).last_hidden_state
    mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
    return torch.nn.functional.normalize(pooled, p=2, dim=1)


def encode_batch(tokenizer, model, texts):
    import torch

    with torch.inference_mode():
        return pooled_vectors(tokenizer, model, texts).float().cpu().numpy()


def encode_queries(tokenizer, model, queries, batch_size=32):
    parts = []
    for start in range(0, len(queries), batch_size):
        parts.append(
            encode_batch(tokenizer, model, [f"query: {q}" for q in queries[start : start + batch_size]])
        )
    return np.concatenate(parts).astype(np.float32)


def store_paths(directory, collection):
    return (
        directory / f"{collection}.npy",
        directory / f"{collection}.sha1.bin",
        directory / f"{collection}.progress.json",
    )


def read_progress(path):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"rows": 0, "consumed": 0, "complete": False}


def write_progress(path, progress):
    temporary = path.with_suffix(".tmp")
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(progress, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def is_complete(directory, collection):
    return read_progress(store_paths(directory, collection)[2])["complete"]


def open_vector_file(path, capacity, dim):
    """Create the vector file if needed and return where its data starts. A wrong shape is an error."""
    if not path.exists():
        np.lib.format.open_memmap(path, mode="w+", dtype=np.float16, shape=(capacity, dim)).flush()
    with open(path, "rb") as f:
        np.lib.format.read_magic(f)
        shape, _, _ = np.lib.format.read_array_header_1_0(f)
        if shape != (capacity, dim):
            raise ValueError(f"{path} has shape {shape}, expected {(capacity, dim)}")
        return f.tell()


def read_seen_hashes(path, rows):
    """Hashes of the stored texts. Bytes past `rows` come from a block that the progress file lacks."""
    if not path.exists():
        return set()
    with open(path, "r+b") as f:
        f.truncate(rows * 20)
        data = f.read()
    return {data[i : i + 20] for i in range(0, len(data), 20)}


def next_block(stream, seen, block_size):
    """Read up to `block_size` new texts. Returns (texts, their hashes, items consumed from the stream)."""
    block, digests, consumed = [], [], 0
    for text in stream:
        consumed += 1
        digest = hashlib.sha1(text.encode()).digest()
        if digest not in seen:
            seen.add(digest)
            block.append(text)
            digests.append(digest)
            if len(block) == block_size:
                break
    return block, digests, consumed


def write_synced(path, mode, data, offset=None):
    with open(path, mode) as f:
        if offset is not None:
            f.seek(offset)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def encode_store(tokenizer, model, texts, capacity, directory, collection, batch_size, block_size=BLOCK_SIZE):
    """Encode an iterable of passage texts into a store. Each block is sorted by length for speed."""
    directory.mkdir(parents=True, exist_ok=True)
    vector_path, hash_path, progress_path = store_paths(directory, collection)
    progress = read_progress(progress_path)
    stats = {"encoded": 0, "seconds": 0.0}
    if progress["complete"]:
        return stats
    dim = model.config.hidden_size
    data_offset = open_vector_file(vector_path, capacity, dim)
    seen = read_seen_hashes(hash_path, progress["rows"])
    stream = itertools.islice(iter(texts), progress["consumed"], None)
    while True:
        block, digests, consumed = next_block(stream, seen, block_size)
        if consumed == 0:
            break
        if block:
            # Longest first shows memory limits early.
            order = sorted(range(len(block)), key=lambda i: -len(block[i]))
            started = time.time()
            parts = []
            for start in range(0, len(order), batch_size):
                picked = order[start : start + batch_size]
                parts.append(encode_batch(tokenizer, model, [f"passage: {block[i]}" for i in picked]))
            stats["seconds"] += time.time() - started
            vectors = np.concatenate(parts).astype(np.float16)
            write_synced(vector_path, "r+b", vectors.tobytes(), data_offset + progress["rows"] * 2 * dim)
            write_synced(hash_path, "ab", b"".join(digests[i] for i in order))
        progress["rows"] += len(block)
        progress["consumed"] += consumed
        write_progress(progress_path, progress)
        stats["encoded"] += len(block)
        print(f"{collection}: {progress['rows']} rows, {progress['consumed']} consumed", flush=True)
        if str(model.device).startswith("mps"):
            import torch

            torch.mps.empty_cache()
    progress["complete"] = True
    write_progress(progress_path, progress)
    return stats


def load_store(directory, collection):
    """Return (read-only memory-mapped vectors, dict from SHA-1 digest to row)."""
    vector_path, hash_path, progress_path = store_paths(directory, collection)
    progress = read_progress(progress_path)
    if not progress["complete"]:
        raise RuntimeError(f"store {collection} in {directory} is not complete: {progress}")
    vectors = np.load(vector_path, mmap_mode="r")
    with open(hash_path, "rb") as f:
        data = f.read()
    return vectors, {data[i : i + 20]: i // 20 for i in range(0, len(data), 20)}


def rows_for_texts(texts, row_of):
    """Store row of each text, in pool order."""
    return np.fromiter((row_of[hashlib.sha1(text.encode()).digest()] for text in texts), dtype=np.int64)


def search_store(query_vectors, vectors, rows, k=1000, chunk=50_000):
    """Dot product of each query with the vectors at `rows`. Returns one (positions, scores) per query.

    Positions index `rows`, that is, the pool. Each chunk of the pool is scored against all queries at once.
    """
    n_queries, n_docs = len(query_vectors), len(rows)
    keep = min(k + TIE_SLACK, n_docs)
    best_scores = np.full((n_queries, keep), -np.inf, dtype=np.float32)
    best_docs = np.zeros((n_queries, keep), dtype=np.int64)
    for start in range(0, n_docs, chunk):
        block = np.asarray(vectors[rows[start : start + chunk]], dtype=np.float32)
        scores = query_vectors @ block.T
        merged_scores = np.concatenate((best_scores, scores), axis=1)
        merged_docs = np.concatenate(
            (best_docs, np.broadcast_to(np.arange(start, start + len(block)), scores.shape)), axis=1
        )
        picks = np.argpartition(-merged_scores, keep - 1, axis=1)[:, :keep]
        best_scores = np.take_along_axis(merged_scores, picks, axis=1)
        best_docs = np.take_along_axis(merged_docs, picks, axis=1)
    tie = neutral_tie_order(n_docs)
    results = []
    for scores, docs in zip(best_scores, best_docs, strict=True):
        picked, picked_scores = top_k(scores, min(k, n_docs), tie[docs])
        results.append((docs[picked], picked_scores))
    return results
