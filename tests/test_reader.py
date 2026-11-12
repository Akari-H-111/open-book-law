"""Reader plumbing with fake models and tokenizers: no weights and no real data."""

import gzip
import json

import numpy as np
import pytest

from open_book_law import runlog
from open_book_law.experiments import us_finetune, us_reader, us_retrieval
from open_book_law.reader import mlx_reader, prompts


class FakeTokenizer:
    """One id per word. A space before a capital makes it a different token, as in byte-level tokenizers."""

    chat_template = None
    eos_token_ids = {0}
    vocab = {"A": 1, " A": 2, "B": 3, " B": 4, "Yes": 5, "No": 7, " No": 8, " Yes": 6}

    def encode(self, text, add_special_tokens=True):
        return [self.vocab[text]] if text in self.vocab else [ord(c) + 100 for c in text]

    def decode(self, ids):
        return "".join(chr(i - 100) if i >= 100 else "?" for i in ids)


class FakeModel:
    """Returns the same next-token logits at every position, and counts the positions it has seen."""

    layers = []

    def __init__(self, logits):
        self.mx = mx = pytest.importorskip("mlx.core")
        self.logits = mx.array(logits, dtype=mx.float32)
        self.seen = []

    def __call__(self, inputs, cache=None):
        self.seen.append(inputs.shape[1])
        return self.mx.broadcast_to(self.logits, (1, inputs.shape[1], self.logits.size))


def test_label_token_ids_keep_both_forms_and_skip_longer_forms():
    tokenizer = FakeTokenizer()
    assert mlx_reader.label_token_ids(tokenizer, ("A", "B")) == {"A": [1, 2], "B": [3, 4]}
    tokenizer.vocab = {"A": 1, "B": 3}
    assert mlx_reader.label_token_ids(tokenizer, ("A", "B")) == {"A": [1], "B": [3]}
    with pytest.raises(ValueError):
        mlx_reader.label_token_ids(tokenizer, ("Maybe",))


def test_labels_may_not_share_a_token():
    tokenizer = FakeTokenizer()
    tokenizer.vocab = {"A": 1, "B": 1}
    with pytest.raises(ValueError):
        mlx_reader.label_token_ids(tokenizer, ("A", "B"))


def test_label_probabilities_sum_both_forms_of_each_label():
    logits = np.log(np.array([0.5, 0.1, 0.1, 0.2, 0.1]))
    probabilities, mass = mlx_reader.label_probabilities(logits, {"A": [1, 2], "B": [3]})
    assert mass == pytest.approx(0.4)
    assert probabilities["A"] == pytest.approx(0.5)
    assert probabilities["B"] == pytest.approx(0.5)


def test_score_labels_uses_the_next_token_only_after_a_long_prompt(monkeypatch):
    monkeypatch.setattr(mlx_reader, "PREFILL_CHUNK", 4)
    model = FakeModel(np.log([0.1, 0.6, 0.1, 0.1, 0.1]))
    probabilities, _ = mlx_reader.score_labels(model, list(range(10)), {"A": [1], "B": [3]})
    assert probabilities["A"] == pytest.approx(6 / 7)
    assert model.seen == [4, 4, 1, 1]


def test_generate_stops_at_the_token_limit_or_at_the_end_token():
    model = FakeModel([0.0, 0.0, 0.0, 9.0])
    assert mlx_reader.generate(model, FakeTokenizer(), [5, 6], max_new_tokens=3)[1:] == (3, False)
    model = FakeModel([9.0, 0.0, 0.0, 0.0])
    assert mlx_reader.generate(model, FakeTokenizer(), [5, 6], max_new_tokens=3)[1:] == (0, True)


def test_truncation_cuts_and_reports():
    tokenizer = FakeTokenizer()
    assert prompts.truncate_context(tokenizer, ["ab", "cd"], budget=10) == ("ab\n\ncd", False)
    assert prompts.truncate_context(tokenizer, ["abcdef", "gh"], budget=3) == ("abc", True)


def test_prompt_uses_the_chat_template_and_disables_thinking_for_qwen3():
    class Chat(FakeTokenizer):
        chat_template = "template"
        calls = []

        def apply_chat_template(self, messages, tokenize, add_generation_prompt, **extra):
            self.calls.append(extra)
            return f"[{messages[0]['content']}]"

    tokenizer = Chat()
    ids = prompts.prompt_ids(tokenizer, "hi\nAnswer:", "qwen3")
    prompts.prompt_ids(tokenizer, "hi\nAnswer:", "llama8")
    assert tokenizer.calls[:2] == [{"enable_thinking": False}, {}]
    assert tokenizer.decode(ids) == "[hi]Answer: **"
    assert tokenizer.decode(prompts.prompt_ids(tokenizer, "hi\nAnswer:", "llama8")) == "[hi]Answer:"
    assert tokenizer.decode(prompts.prompt_ids(tokenizer, "hi\nRule:", "qwen3")) == "[hi]Rule:"


def test_prompts_hold_the_options_and_the_state():
    question = {"query": "Q?", "answer": "b", **{f"choice_{c}": c.upper() + "!" for c in "abcd"}}
    text = prompts.question_text("mbe", question)
    assert "A. A!\n" in text and "D. D!" in text and text.endswith("Answer:")
    assert prompts.gold_label("mbe", question) == "B"
    housing = {"state": "Ohio", "question": "Q?", "query": "Q?", "answer": "No"}
    assert "statutory law for Ohio in the year 2021" in prompts.question_text("housing", housing)
    assert prompts.rollout_text("housing", housing).count("Ohio") == 2


def test_housing_answer_forms_change_the_request_the_labels_and_the_gold():
    housing = {"state": "Ohio", "question": "Q?", "answer": "No"}
    assert prompts.question_text("housing", housing).endswith('Answer "Yes" or "No".\nAnswer:')
    assert prompts.labels("housing") == ("Yes", "No") and prompts.gold_label("housing", housing) == "No"
    same_request = prompts.question_text("housing", housing, "yes-no-scored-y-n")
    assert same_request == prompts.question_text("housing", housing)
    assert prompts.labels("housing", "yes-no-scored-y-n") == ("Y", "N")
    assert prompts.gold_label("housing", housing, "y-n") == "N"
    assert prompts.question_text("housing", housing, "y-n").endswith('Answer "Y" or "N".\nAnswer:')
    assert prompts.labels("mbe", "y-n") == ("A", "B", "C", "D")


def test_only_a_diagnostic_answer_form_enters_the_config():
    base = ["--dataset", "housing", "--reader", "llama8", "--condition", "closed", "--split", "all"]
    assert "answer_form" not in us_reader.make_config(us_reader.parse_args(base), None)
    args = us_reader.parse_args([*base, "--answer-form", "y-n"])
    assert us_reader.make_config(args, None)["answer_form"] == "y-n"


def test_library_filter_takes_the_first_k_within_the_sources():
    passages = {"a": ("t", "mbe"), "b": ("t", "wex"), "c": ("t", "caselaw"), "d": ("t", "wex")}
    order = ["a", "b", "c", "d"]
    assert us_reader.filter_library(order, passages, "doctrine", 5) == ["b", "d"]
    assert us_reader.filter_library(order, passages, "real", 2) == ["b", "c"]
    assert us_reader.filter_library(order, passages, "full", 1) == ["a"]
    assert us_reader.filter_library(order, passages, "within-state", 2) == ["a", "b"]


def test_partial_file_drops_a_last_line_that_a_crash_cut_short(tmp_path):
    path = tmp_path / "partial.jsonl"
    assert runlog.read_partial(path) == {}
    path.write_text('{"qid": "a"}\n{"qid": "b"}\n{"qid": "c"')
    assert sorted(runlog.read_partial(path)) == ["a", "b"]


def test_smoke_runs_stay_on_validation():
    us_reader.parse_args(["--dataset", "mbe", "--reader", "phi4", "--condition", "closed", "--limit", "5"])
    with pytest.raises(SystemExit):
        us_reader.parse_args(
            [
                "--dataset",
                "mbe",
                "--reader",
                "phi4",
                "--condition",
                "closed",
                "--limit",
                "5",
                "--split",
                "all",
            ]
        )


def write_ranks(tmp_path, suite, rid, rankings, config, empty=()):
    """Like a run file. A query in `empty` matched nothing, so it is listed but has no rank rows."""
    (tmp_path / suite).mkdir(parents=True, exist_ok=True)
    per_query = [{"qid": qid} for qid in [*rankings, *empty]]
    run = {"run_id": rid, "config": config, "per_query": per_query}
    (tmp_path / suite / f"{rid}.json").write_text(json.dumps(run))
    with gzip.open(tmp_path / suite / f"{rid}.rank.tsv.gz", "wt") as f:
        f.write("qid\tdocid\trank\n")
        for qid, docids in rankings.items():
            for i, docid in enumerate(docids, start=1):
                f.write(f"{qid}\t{docid}\t{i}\n")


def test_read_rankings_prefers_the_deep_file_and_falls_back_to_git(tmp_path):
    write_ranks(tmp_path, "s", "old", {"q": ["a", "b"]}, {})
    assert runlog.read_rankings("old", runs_dir=tmp_path) == ({"q": ["a", "b"]}, 2)
    deep = tmp_path / "ranks" / "old.tsv.gz"
    deep.parent.mkdir()
    with gzip.open(deep, "wt") as f:
        f.write("qid\tdocid\trank\nq\ta\t1\nq\tb\t2\nq\tc\t3\n")
    assert runlog.read_rankings("old", runs_dir=tmp_path)[1] == 3


def test_a_query_without_matches_keeps_its_question_with_an_empty_ranking(tmp_path):
    write_ranks(tmp_path, "s", "r", {"q": ["a"]}, {}, empty=["nothing"])
    rankings, depth = runlog.read_rankings("r", runs_dir=tmp_path)
    assert rankings == {"q": ["a"], "nothing": []} and depth == 1
    runlog.require_questions([{"qid": "q"}, {"qid": "nothing"}], rankings, "r")


def test_a_question_that_the_run_never_ranked_stops_the_reader(tmp_path):
    write_ranks(tmp_path, "s", "r", {"q": ["a"]}, {})
    rankings = runlog.read_rankings("r", runs_dir=tmp_path)[0]
    with pytest.raises(SystemExit, match="lacks 1 questions"):
        runlog.require_questions([{"qid": "q"}, {"qid": "absent"}], rankings, "r")


def test_an_empty_ranking_gives_an_empty_context_and_an_old_rank_file_still_reads(tmp_path, monkeypatch):
    write_ranks(tmp_path, "s", "r", {"q": ["a", "b"]}, {"library": "full"}, empty=["nothing"])
    monkeypatch.setattr(runlog, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runlog, "RANKS_DIR", tmp_path / "ranks")
    argv = ["--dataset", "mbe", "--reader", "phi4", "--condition", "retrieved", "--k", "1"]
    args = us_reader.parse_args(argv)
    questions = [{"qid": "q"}, {"qid": "nothing"}]
    kept, candidates = us_reader.load_candidates(args, questions, "r")
    assert kept == questions and candidates == {"q": ["a"], "nothing": []}
    context, cut = prompts.truncate_context(FakeTokenizer(), [])
    assert context == "" and not cut


def test_a_reader_run_records_whether_its_ranking_used_a_rollout(tmp_path, monkeypatch):
    write_ranks(tmp_path, "s", "plain", {"q": ["a"]}, {"library": "full"})
    write_ranks(tmp_path, "s", "expanded", {"q": ["a"]}, {"library": "full", "rollout": "x.jsonl"})
    monkeypatch.setattr(runlog, "RUNS_DIR", tmp_path)
    argv = ["--dataset", "mbe", "--reader", "phi4", "--condition", "retrieved", "--retriever", "bm25"]
    args = us_reader.parse_args(argv)
    assert us_reader.make_config(args, "plain")["rollout"] is False
    assert us_reader.make_config(args, "expanded")["rollout"] is True


def test_hybrid_fuses_two_rank_files(tmp_path, monkeypatch):
    config = {"dataset": "mbe", "library": "full"}
    write_ranks(tmp_path, "s", "one", {"q": ["a", "b"], "lost": ["a"]}, config)
    write_ranks(tmp_path, "s", "two", {"q": ["b", "c"]}, config)
    monkeypatch.setattr(runlog, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runlog, "RANKS_DIR", tmp_path / "ranks")
    args = us_retrieval.parse_args(["--dataset", "mbe", "--retriever", "hybrid", "--from", "one", "two"])
    questions = [
        {"qid": "q", "gold": {"b"}, "split": "validation"},
        {"qid": "lost", "gold": {"a"}, "split": "validation"},
    ]
    rankings, records, _ = us_retrieval.run_hybrid(args, questions)
    assert rankings == {"q": ["b", "a", "c"]}
    assert [r["qid"] for r in records] == ["q"]
    assert records[0]["hit@1"] == 1.0
    assert us_retrieval.suite_for(args) == "us_downstream"


def test_new_retrieval_settings_never_reach_the_reproduction_suite():
    def suite(*extra):
        return us_retrieval.suite_for(
            us_retrieval.parse_args(["--dataset", "mbe", "--retriever", "bm25", *extra])
        )

    assert suite() == "us_retrieval"
    assert suite("--library", "doctrine") == "us_downstream"
    assert suite("--split", "validation") == "us_downstream"
    assert suite("--rollout", "x") == "us_downstream"
    assert suite("--split", "validation", "--limit", "3") == "us_smoke"


def test_rollout_is_appended_and_questions_without_one_leave(tmp_path):
    path = tmp_path / "rollouts.jsonl"
    path.write_text('{"qid": "a", "text": "rule"}\n')
    expanded = us_retrieval.expand_queries([{"qid": "a", "query": "q"}, {"qid": "b", "query": "r"}], path)
    assert expanded == [{"qid": "a", "query": "q rule"}]


def test_finetune_loss_rewards_each_query_for_its_own_passage():
    torch = pytest.importorskip("torch")
    matched = torch.eye(3)
    wrong = matched[[1, 2, 0]]
    assert us_finetune.mnr_loss(matched, matched, 0.01).item() == pytest.approx(0.0, abs=1e-6)
    assert us_finetune.mnr_loss(matched, wrong, 0.01).item() == pytest.approx(100.0, abs=1e-3)
    half = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    assert us_finetune.mnr_loss(half, half, 1.0).item() == pytest.approx(np.log(2), abs=1e-6)


def test_finetune_batches_never_repeat_a_question_or_a_statute():
    # Ten question ids in ten states share five question texts, as housing questions repeat across states.
    pairs = [{"qid": f"q{i % 10}", "query": f"x{i % 5}", "text": f"t{i % 7}"} for i in range(70)]
    batches = us_finetune.make_batches(pairs, 4, np.random.default_rng(1))
    assert all(1 < len(batch) <= 4 for batch in batches)
    for batch in batches:
        assert len({p["query"] for p in batch}) == len({p["text"] for p in batch}) == len(batch)
