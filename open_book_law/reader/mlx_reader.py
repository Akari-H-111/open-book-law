"""A local MLX model as a reader: the probability of each answer label, and short greedy generation.

The paper's method for Llama: take the next-token distribution after the prompt and keep the most likely
answer letter. A label can be one token in two forms, "A" and " A", so a label's score sums both forms.
"""

import numpy as np

from open_book_law.runlog import model_pin

READERS = {
    "llama8": "mlx-community/Meta-Llama-3-8B-Instruct-4bit",
    "qwen3": "mlx-community/Qwen3-8B-4bit",
    "phi4": "mlx-community/Phi-4-mini-instruct-4bit",
}
PREFILL_CHUNK = 512
CACHE_LIMIT_BYTES = 1 << 30  # MLX keeps freed buffers. This bounds them on a 16 GB machine.


def load_reader(name):
    """Load weights and tokenizer from the local cache at the pinned revision. Returns (model, tokenizer).

    The file patterns are the pinned download patterns, so that files never fetched do not count as missing.
    """
    import mlx.core as mx
    from huggingface_hub import snapshot_download
    from mlx_lm import load

    mx.set_cache_limit(CACHE_LIMIT_BYTES)
    pin = model_pin(READERS[name])
    path = snapshot_download(
        READERS[name], revision=pin["revision"], allow_patterns=pin["patterns"], local_files_only=True
    )
    return load(path, trust_remote_code=False)


def label_token_ids(tokenizer, labels):
    """For each label, the ids of its one-token forms, with and without a leading space. Both are recorded.

    A form that takes more than one token is skipped, because its first token says nothing about the label.
    """
    result = {}
    for label in labels:
        ids = [tokenizer.encode(form, add_special_tokens=False) for form in (label, f" {label}")]
        result[label] = sorted({form[0] for form in ids if len(form) == 1})
        if not result[label]:
            raise ValueError(f"label {label!r} has no one-token form in this tokenizer")
    shared = [i for a in labels for b in labels if a < b for i in set(result[a]) & set(result[b])]
    if shared:
        raise ValueError(f"labels share token ids: {shared}")
    return result


def label_probabilities(logits, token_ids):
    """From next-token logits, return (each label's probability among the labels, the labels' total mass)."""
    logits = np.asarray(logits, dtype=np.float64)
    probabilities = np.exp(logits - logits.max())
    probabilities /= probabilities.sum()
    masses = {label: float(probabilities[ids].sum()) for label, ids in token_ids.items()}
    total = sum(masses.values())
    if total == 0.0:
        return {label: 1.0 / len(masses) for label in masses}, 0.0
    return {label: mass / total for label, mass in masses.items()}, total


def next_token_logits(model, ids, cache=None):
    """Logits after `ids`. Chunks keep the output head from running on every position of a long prompt."""
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    cache = make_prompt_cache(model) if cache is None else cache
    for start in range(0, len(ids) - 1, PREFILL_CHUNK):
        model(mx.array([ids[start : min(start + PREFILL_CHUNK, len(ids) - 1)]]), cache=cache)
        mx.eval([c.state for c in cache])
    logits = model(mx.array([ids[-1:]]), cache=cache)[0, -1].astype(mx.float32)
    mx.eval(logits)
    return np.array(logits, copy=True)


def score_labels(model, ids, token_ids):
    return label_probabilities(next_token_logits(model, ids), token_ids)


def generate(model, tokenizer, ids, max_new_tokens=256):
    """Greedy generation, which is temperature 0. Returns (text, tokens made, whether an end token came)."""
    from mlx_lm.models.cache import make_prompt_cache

    cache = make_prompt_cache(model)
    made, stopped, current = [], False, ids
    while len(made) < max_new_tokens:
        token = int(np.argmax(next_token_logits(model, current, cache)))
        if token in tokenizer.eos_token_ids:
            stopped = True
            break
        made.append(token)
        current = [token]
    return tokenizer.decode(made), len(made), stopped
