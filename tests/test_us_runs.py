"""Run files, the verdict rules, suite routing, and the dense store with a fake encoder."""

import gzip
import json

import numpy as np
import pytest

from open_book_law import runlog
from open_book_law.experiments import us_retrieval, us_verdicts
from open_book_law.reader import samples
from open_book_law.retrieval import dense


def fake_run(tmp_path, config=None, rankings=None):
    data = tmp_path / "data.bin"
    data.write_bytes(b"abc")
    return runlog.write_run(
        "us_test",
        config or {"a": 1},
        [data],
        {"id": "m", "revision": None},
        {"all": {}},
        [{"qid": "q"}],
        1.5,
        {"docs": 2},
        rankings or {"q": ["d1", "d2"]},
        runs_dir=tmp_path,
    )


def test_run_file_contents_and_rankings(tmp_path):
    path = fake_run(tmp_path)
    record = json.loads(path.read_text())
    assert record["run_id"] == runlog.run_id({"a": 1}) == path.stem
    assert len(record["git"]["commit"]) == 40
    assert isinstance(record["git"]["dirty"], bool)
    assert list(record["data_sha256"].values()) == [
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    ]
    with gzip.open(path.with_name(f"{path.stem}.rank.tsv.gz"), "rt") as f:
        assert f.read() == "qid\tdocid\trank\nq\td1\t1\nq\td2\t2\n"


def test_run_file_refuses_to_overwrite(tmp_path):
    path = fake_run(tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        fake_run(tmp_path)
    assert path.read_bytes() == before
    assert fake_run(tmp_path, config={"a": 1, "rerun": 1}) != path


def test_rankings_are_cut_at_100_in_git_and_1000_in_the_data_folder(tmp_path):
    path = fake_run(tmp_path, rankings={"q": [f"d{i}" for i in range(1500)]})
    with gzip.open(path.with_name(f"{path.stem}.rank.tsv.gz"), "rt") as f:
        assert sum(1 for _ in f) == 101
    with gzip.open(tmp_path / "ranks" / f"{path.stem}.tsv.gz", "rt") as f:
        assert sum(1 for _ in f) == 1001


def test_run_id_ignores_key_order():
    assert runlog.run_id({"a": 1, "b": 2}) == runlog.run_id({"b": 2, "a": 1})


def args_for(*extra):
    return us_retrieval.parse_args(["--dataset", "mbe", "--retriever", "bm25", *extra])


def test_suite_routing():
    assert us_retrieval.suite_for(args_for()) == "us_retrieval"
    assert us_retrieval.suite_for(args_for("--limit", "5")) == "us_smoke"
    assert us_retrieval.suite_for(args_for("--tokenizer", "porter")) == "us_diagnostics"
    assert us_retrieval.suite_for(args_for("--tokenizer", "porter", "--limit", "5")) == "us_smoke"


def housing_args(*extra):
    return us_retrieval.parse_args(["--dataset", "housing", "--retriever", "bm25", *extra])


def test_sampled_states_have_their_own_suite_and_never_reach_the_reproduction_suite():
    assert us_retrieval.suite_for(housing_args("--states", "10")) == "us_states"
    assert us_retrieval.suite_for(housing_args("--states", "10", "--limit", "5")) == "us_smoke"
    with pytest.raises(SystemExit):
        args_for("--states", "10")


def test_sampled_states_are_the_same_for_every_retriever():
    states = [f"s{i}" for i in range(48)]
    chosen = samples.choose_states(states, 10)
    assert len(set(chosen)) == 10 and set(chosen) <= set(states)
    assert chosen == samples.choose_states(list(reversed(states)), 10)


def test_only_the_rows_of_sampled_states_are_encoded_and_searched(monkeypatch):
    rows = [{"idx": str(i), "text": f"t{i}", "state": "ohio" if i < 3 else "iowa"} for i in range(5)]

    def iter_states():
        yield "ohio", rows[:3]
        yield "iowa", rows[3:]

    monkeypatch.setattr(us_retrieval.samples, "iter_passages", lambda dataset: iter(rows))
    monkeypatch.setattr(us_retrieval.housing, "iter_states", iter_states)
    assert list(us_retrieval.passage_texts("housing", {"iowa"})) == ["t3", "t4"]
    assert len(list(us_retrieval.passage_texts("housing"))) == 5
    groups = list(us_retrieval.iter_groups(housing_args("--states", "1"), [{"pool": "iowa"}]))
    assert [(name, docids) for name, docids, _, _ in groups] == [("iowa", ["3", "4"])]


def test_verdict_on_sampled_states_says_so_and_lists_the_same_states(tmp_path):
    states = {"states": ["iowa", "ohio"]}
    hits = {10: 45.75, 100: 74.61, 1000: 86.65}
    for retriever in ("e5-base", "bm25", "e5-small"):
        run = verdict_run("housing", retriever, hits, retriever, suite_config=states)
        write_run_file(tmp_path, "us_states", run)
    summary = us_verdicts.make_summary(tmp_path)
    by_id = {t["id"]: t for t in summary["targets"]}
    assert by_id["R2c"]["verdict"] == "reproduced"
    assert by_id["R2c"]["on_sampled_states"] == ["iowa", "ohio"]
    assert by_id["R2a"]["verdict"] == by_id["R2b"]["verdict"] == "pending"
    assert {r["retriever"] for r in summary["same_states"]} == {"e5-base", "bm25", "e5-small"}
    assert "Runs on the sampled states" in us_verdicts.markdown_table(summary)


def test_score_query_and_aggregate():
    question = {"qid": "q", "gold": {"a", "b"}, "pool": "ohio"}
    record = us_retrieval.score_query(question, ["x", "a"] + ["y"] * 200 + ["b"])
    assert record["hit@1"] == 0.0
    assert record["hit@10"] == 1.0
    assert record["all@100"] == 0.0
    assert record["all@1000"] == 1.0
    assert record["recall@10"] == 0.5
    assert record["mrr@10"] == 0.5
    assert record["group"] == "ohio"
    summary = us_retrieval.aggregate([record, {**record, "hit@10": 0.0}])
    assert summary["hit@10"] == 50.0
    assert summary["questions"] == 2


def verdict_run(dataset, retriever, hits, run_id="r", when="2026-11-03T00:00:00+00:00", suite_config=None):
    return {
        "run_id": run_id,
        "utc_time": when,
        "git": {"commit": "c"},
        "config": {
            "dataset": dataset,
            "retriever": retriever,
            "library": us_verdicts.LIBRARY[dataset],
            **(suite_config or {}),
        },
        "metrics": {
            "all": {
                "questions": 1,
                "hit@1": 0.0,
                "mrr@10": 0.0,
                "all@10": 0.0,
                "all@100": 0.0,
                "all@1000": 0.0,
                **{f"hit@{k}": v for k, v in hits.items()},
            }
        },
    }


def write_run_file(runs_dir, suite, run):
    (runs_dir / suite).mkdir(parents=True, exist_ok=True)
    (runs_dir / suite / f"{run['run_id']}.json").write_text(json.dumps(run))


def test_verdict_limits_on_each_dataset():
    published = {10: 10.0, 100: 20.0, 1000: 30.0}
    judge = us_verdicts.judge
    assert judge("mbe", published, {"hit@10": 11.0, "hit@100": 22.0, "hit@1000": 27.0})[1] == "reproduced"
    assert (
        judge("mbe", published, {"hit@10": 11.5, "hit@100": 20.0, "hit@1000": 30.0})[1] == "partly reproduced"
    )
    assert (
        judge("mbe", published, {"hit@10": 12.0, "hit@100": 24.0, "hit@1000": 36.0})[1] == "partly reproduced"
    )
    assert judge("mbe", published, {"hit@10": 12.1, "hit@100": 20.0, "hit@1000": 30.0})[1] == "diverged"
    assert judge("housing", published, {"hit@10": 12.0, "hit@100": 23.0, "hit@1000": 33.0})[1] == "reproduced"
    assert (
        judge("housing", published, {"hit@10": 14.0, "hit@100": 26.0, "hit@1000": 36.0})[1]
        == "partly reproduced"
    )
    assert judge("housing", published, {"hit@10": 10.0, "hit@100": 20.0, "hit@1000": 36.5})[1] == "diverged"


def test_no_run_means_pending(tmp_path):
    summary = us_verdicts.make_summary(tmp_path)
    assert len(summary["targets"]) == 8
    assert {t["verdict"] for t in summary["targets"]} == {"pending"}
    assert "pending" in us_verdicts.markdown_table(summary)


def test_the_earliest_run_decides_and_diagnostics_do_not_replace_it(tmp_path):
    good = {10: 0.75, 100: 2.26, 1000: 8.79}
    bad = {10: 50.0, 100: 50.0, 1000: 50.0}
    write_run_file(
        tmp_path, "us_retrieval", verdict_run("mbe", "bm25", bad, "first", "2026-11-03T01:00:00+00:00")
    )
    write_run_file(
        tmp_path, "us_retrieval", verdict_run("mbe", "bm25", good, "second", "2026-11-03T02:00:00+00:00")
    )
    write_run_file(
        tmp_path,
        "us_diagnostics",
        verdict_run("mbe", "bm25", good, "diag", suite_config={"tokenizer": "porter"}),
    )
    write_run_file(tmp_path, "us_smoke", verdict_run("mbe", "e5-small", good, "smoke"))
    summary = us_verdicts.make_summary(tmp_path)
    by_id = {t["id"]: t for t in summary["targets"]}
    assert by_id["R1a"]["verdict"] == "diverged"
    assert by_id["R1a"]["run_id"] == "first"
    assert by_id["R1a"]["later_runs"] == ["second"]
    assert by_id["R1a"]["diagnostics"][0]["run_id"] == "diag"
    assert by_id["R1b"]["verdict"] == "pending"


def test_update_document_replaces_only_the_marked_part(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("before\n<!-- AUTO:BEGIN -->\nold\n<!-- AUTO:END -->\nafter\n")
    us_verdicts.update_document("new\n", path)
    assert path.read_text() == "before\n<!-- AUTO:BEGIN -->\nnew\n<!-- AUTO:END -->\nafter\n"
    path.write_text("no markers")
    with pytest.raises(ValueError):
        us_verdicts.update_document("new\n", path)


class FakeTokenizer:
    """Tokenizes by words. It turns each text into counts over a tiny vocabulary."""

    calls = 0

    def __call__(self, texts, max_length, padding, truncation, return_tensors):
        import torch

        FakeTokenizer.calls += 1
        ids = [[1 + (sum(map(ord, word)) % 7) for word in text.split()][:max_length] for text in texts]
        width = max(map(len, ids))
        padded = [row + [0] * (width - len(row)) for row in ids]
        mask = [[1] * len(row) + [0] * (width - len(row)) for row in ids]
        return {"input_ids": torch.tensor(padded), "attention_mask": torch.tensor(mask)}


class FakeModel:
    """Maps each token id to a fixed vector, in place of a real encoder."""

    device = "cpu"

    class config:
        hidden_size = 8

    def __init__(self):
        import torch

        self.table = torch.eye(8)

    def __call__(self, input_ids, attention_mask):
        class Output:
            pass

        output = Output()
        output.last_hidden_state = self.table[input_ids]
        return output


def test_store_is_resumable_and_encodes_identical_text_once(tmp_path):
    pytest.importorskip("torch")
    texts = ["alpha beta", "gamma", "alpha beta", "delta epsilon zeta", "eta", "theta iota"]
    tokenizer, model = FakeTokenizer(), FakeModel()
    stats = dense.encode_store(tokenizer, model, texts[:3], 6, tmp_path, "c", 2, block_size=2)
    assert stats["encoded"] == 2
    progress = json.loads((tmp_path / "c.progress.json").read_text())
    assert progress == {"rows": 2, "consumed": 3, "complete": True}

    # Pretend the run stopped after that block: a later run consumes only the remaining items.
    progress["complete"] = False
    (tmp_path / "c.progress.json").write_text(json.dumps(progress))
    with open(tmp_path / "c.sha1.bin", "ab") as f:
        f.write(b"x" * 20)  # a partial write that the progress file does not cover must be dropped
    stats = dense.encode_store(tokenizer, model, texts, 6, tmp_path, "c", 2, block_size=2)
    assert stats["encoded"] == 3

    vectors, row_of = dense.load_store(tmp_path, "c")
    assert len(row_of) == 5
    rows = dense.rows_for_texts(texts, row_of)
    assert rows[0] == rows[2]
    assert len(set(rows.tolist())) == 5
    for text, row in zip(texts, rows, strict=True):
        direct = dense.encode_batch(tokenizer, model, [f"passage: {text}"])[0]
        assert np.allclose(vectors[row], direct, atol=1e-3)
        assert np.linalg.norm(direct) == pytest.approx(1.0)


def test_dense_run_encodes_searches_and_writes_a_run_file(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    rows = [
        {"idx": f"d{i}", "text": f"word{i} common", "source": "wex", "state": "ohio" if i < 4 else "iowa"}
        for i in range(8)
    ]

    def iter_states():
        yield "ohio", rows[:4]
        yield "iowa", rows[4:]

    question = {"qid": "q", "query": "word5 common", "gold": {"d5"}, "pool": "iowa", "split": "validation"}
    monkeypatch.setattr(us_retrieval.samples, "load_questions", lambda *args: [question])
    monkeypatch.setattr(us_retrieval.samples, "iter_passages", lambda dataset: iter(rows))
    monkeypatch.setattr(us_retrieval.samples, "data_files", lambda dataset: [])
    monkeypatch.setattr(us_retrieval.barexam, "iter_pool", lambda library: iter(rows))
    monkeypatch.setattr(us_retrieval.barexam, "POOL_SIZE", 8)
    monkeypatch.setattr(us_retrieval.housing, "iter_states", iter_states)
    monkeypatch.setattr(dense, "store_dir", lambda retriever: tmp_path / "stores" / retriever)
    monkeypatch.setattr(dense, "load_model", lambda *args: (FakeTokenizer(), FakeModel()))
    monkeypatch.setattr(runlog, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runlog, "RANKS_DIR", tmp_path / "ranks")

    us_retrieval.main(["--dataset", "mbe", "--retriever", "e5-base"])
    run = runlog.load_runs("us_retrieval")[0]
    assert run["metrics"]["all"]["questions"] == 1
    assert sorted(runlog.read_rankings(run["run_id"])[0]["q"]) == [f"d{i}" for i in range(8)]
    # The extra row is the shape of the stores already on disk.
    assert dense.load_store(tmp_path / "stores" / "e5-base", "mbe")[0].shape == (9, 8)

    us_retrieval.main(["--dataset", "housing", "--retriever", "e5-base", "--states", "1"])
    run = runlog.load_runs("us_states")[0]
    assert run["config"]["states"] == ["iowa"]
    assert sorted(runlog.read_rankings(run["run_id"])[0]["q"]) == ["d4", "d5", "d6", "d7"]
    assert dense.load_store(tmp_path / "stores" / "e5-base", "housing-1-states")[0].shape == (4, 8)


def test_the_first_full_dense_scotus_run_creates_the_store_and_a_smoke_run_cannot(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    rows = [
        {"id": f"{case}:0:0", "case_id": case, "opinion_type": "majority", "text": f"word{case} common"}
        for case in ("old", "new", "other")
    ]
    question = {"qid": "q", "query": "wordnew common", "old_id": "old", "new_id": "new"}
    monkeypatch.setattr(us_retrieval.samples, "load_questions", lambda *args: [question])
    monkeypatch.setattr(us_retrieval.samples, "iter_passages", lambda dataset: iter(rows))
    monkeypatch.setattr(us_retrieval.samples, "data_files", lambda dataset: [])
    monkeypatch.setattr(us_retrieval.goodlaw, "POOL_SIZE", 3)
    monkeypatch.setattr(us_retrieval.goodlaw, "read_questions", lambda: ([question], []))
    monkeypatch.setattr(dense, "store_dir", lambda retriever: tmp_path / "stores" / retriever)
    monkeypatch.setattr(dense, "load_model", lambda *args: (FakeTokenizer(), FakeModel()))
    monkeypatch.setattr(runlog, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(runlog, "RANKS_DIR", tmp_path / "ranks")

    with pytest.raises(RuntimeError):
        us_retrieval.main(["--dataset", "scotus", "--retriever", "e5-small", "--limit", "5"])
    assert not (tmp_path / "stores").exists()

    us_retrieval.main(["--dataset", "scotus", "--retriever", "e5-small"])
    run = runlog.load_runs("us_downstream")[0]
    assert run["metrics"]["all"]["questions"] == 1
    assert dense.load_store(tmp_path / "stores" / "e5-small", "scotus")[0].shape == (4, 8)
    assert runlog.read_rankings(run["run_id"])[0]["q"][0] == "new:0:0"


def test_incomplete_store_is_refused(tmp_path):
    (tmp_path / "c.progress.json").write_text(json.dumps({"rows": 1, "consumed": 1, "complete": False}))
    with pytest.raises(RuntimeError):
        dense.load_store(tmp_path, "c")


def test_search_store_matches_brute_force():
    rng = np.random.default_rng(1)
    vectors = rng.normal(size=(500, 16)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    queries = vectors[:3]
    rows = np.arange(100, 500)
    expected = np.argsort(-(queries @ vectors[rows].T), axis=1)[:, :20]
    for chunk in (7, 50, 1000):
        results = dense.search_store(queries, vectors, rows, k=20, chunk=chunk)
        for row, (positions, scores) in zip(expected, results, strict=True):
            assert positions.tolist() == row.tolist()
            assert np.all(np.diff(scores) <= 0)


def test_search_store_with_small_pool():
    vectors = np.eye(3, dtype=np.float32)
    results = dense.search_store(vectors[:1], vectors, np.arange(3), k=1000, chunk=2)
    assert results[0][0][0] == 0
    assert sorted(results[0][0].tolist()) == [0, 1, 2]


def test_portable_paths_leave_out_this_machine():
    assert runlog.portable(runlog.DATA_ROOT / "a" / "b.csv") == "$OBL_DATA/a/b.csv"
    assert runlog.portable(runlog.REPO_ROOT / "data" / "x.json") == "data/x.json"
    assert runlog.portable(runlog.DATA_ROOT.resolve() / "a.csv") == "$OBL_DATA/a.csv"
