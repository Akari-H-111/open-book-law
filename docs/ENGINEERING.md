# Engineering guide

This guide is for engineers and researchers who want to study, reproduce, verify or fork Open Book. Teachers and students can start with the [website](https://akari-h-111.github.io/open-book-law/) and [`docs/TEACHING.md`](TEACHING.md) instead.

**Read this first.** AI models wrote all of the code, and no person has checked the code or the results yet. [`docs/AI_ASSISTANCE.md`](AI_ASSISTANCE.md) has the full record. So treat the code as unreviewed. The project is built so that you can check it: every number comes from a stored run file through a committed script.

## Contents

1. [Repository map](#1-repository-map)
2. [How a number is made](#2-how-a-number-is-made)
3. [What a run file holds](#3-what-a-run-file-holds)
4. [Three levels of reproduction](#4-three-levels-of-reproduction)
5. [Verify a release](#5-verify-a-release)
6. [Tests and CI](#6-tests-and-ci)
7. [Fork and extend](#7-fork-and-extend)
8. [Rules that protect the results](#8-rules-that-protect-the-results)
9. [Known limits](#9-known-limits)

## 1. Repository map

| Path | What it holds |
|---|---|
| `open_book_law/retrieval/` | `bm25.py`: BM25 written by hand, with the index in NumPy arrays. `dense.py`: E5 encoding and exact dot-product search, with no vector database. `fusion.py`: reciprocal rank fusion |
| `open_book_law/reader/` | `mlx_reader.py`: a local MLX model as a reader, which scores each answer letter by its next-token probability. `prompts.py`: the prompts, with a version that each run file records. `samples.py`: which questions a run uses |
| `open_book_law/agent/` | `loop.py`: a plain agent loop with a budget of 5 tool calls. `tools.py`: search, read and check status. `mcp_server.py`: the same tools over MCP |
| `open_book_law/us/` | Loaders for the two public datasets and the good-law questions. `authority.py`: a dated store of which decision cites which, and which had been overruled on a given date |
| `open_book_law/experiments/` | One script per kind of run (`us_retrieval`, `us_reader`, `us_rollout`, `us_goodlaw`, `us_agent`, `us_finetune`). Four summary scripts apply the plan to the run files (`us_select`, `us_verdicts`, `us_hypotheses`, `us_answers`) |
| `open_book_law/evalx.py` | Metrics and statistics written by hand: recall, paired bootstrap, exact McNemar test, Holm correction, Wilson interval |
| `open_book_law/runlog.py` | Writes and reads run files. A run file cannot be overwritten |
| `open_book_law/prep/` | One-time data preparation and audits: the table of overruled decisions, the Supreme Court opinions, the citation extractor, the good-law question generator, the label audit and the error sample |
| `results/runs/<suite>/` | One JSON file per run, and for search runs a gzip file with the top 100 of each ranking |
| `results/summary/` | Summaries that the summary scripts write |
| `results/data_audit/` | Counts from the data audits. IDs and counts only |
| `data/` | Small committed inputs: pinned model revisions, fixed samples and splits, and the parsed table of overruled decisions |
| `docs/` | The plan, the results, the records and the guides. [`docs/README.md`](README.md) lists them |
| `site/` | The website. Static files only |
| `tools/` | `build_site_data.py` and `make_release.py`, the queue scripts that ran long jobs, and scripts that ran AI workers |
| `tests/` | Automated tests |
| `.github/workflows/` | `verify.yml` checks every push. `pages.yml` publishes the site after `verify` passes |

**Two standards of code.** The core is everything in `open_book_law/` outside `prep/`, about 3,200 lines. `AGENTS.md` limits its size, so that one person could explain every line. `prep/` has about 1,800 lines of one-time preparation, and it is held to a lower standard: a reader should know what each file does and why. The author cannot yet explain the core line by line.

## 2. How a number is made

```text
downloaded data (outside git, in $OBL_DATA)
        │
        ▼
experiment script ──► run file in results/runs/<suite>/<run id>.json
        │                     (settings, code commit, data hashes, one row per question)
        ▼
summary scripts ──► results/summary/*.json, docs/RESULTS.md, docs/REPRODUCTION.md
        │
        ▼
tools/build_site_data.py ──► site/data.js ──► the website
```

- An experiment script runs one configuration and writes one run file. It never writes question text or passage text.
- The summary scripts read only run files and the committed inputs in `data/`. They need no downloaded data and no model.
  - `us_select` applies the selection rules of section 3.4 of the plan, on validation questions only.
  - `us_verdicts` applies section 5 (the reproduction targets) and writes the tables of `docs/REPRODUCTION.md`.
  - `us_hypotheses` applies sections 4 and 6 (the 11 tests) and writes the table of `docs/RESULTS.md`.
  - `us_answers` is post hoc and sets no verdict.
- When a target or a test has several runs, the earliest run decides. So a rerun cannot replace a result.
- `tools/build_site_data.py` uses only the standard library and writes the same bytes on every run.

## 3. What a run file holds

Every run file is one JSON object with these keys:

| Key | Content |
|---|---|
| `run_id` | The first 16 hex digits of the SHA-256 of `config`. It is also the file name |
| `suite` | The folder: for example `us_reader`, `us_goodlaw`, `us_downstream`, or `us_smoke` for short trial runs |
| `config` | The full settings: dataset, split, reader or retriever, library, condition, prompt version, and a `rerun` counter |
| `git` | The commit of the code, and whether the working tree had changes |
| `data_sha256` | The SHA-256 of every data file that the run read. Data paths start with `$OBL_DATA/` |
| `model` | The model ID and its pinned revision |
| `metrics` | The aggregate results |
| `per_query` | One row per question: the question ID, the predicted answer, whether it was right, the probability of each answer letter, and the IDs of the passages that the reader saw |
| `utc_time`, `elapsed_seconds`, `throughput` | When the run finished and how fast it was |

Two notes for readers of old run files:

- The commit IDs in `git` point into the project's private history. The public repository starts from a single commit. [`docs/RELEASE_NOTES.md`](RELEASE_NOTES.md) lists the private commits and times of the plan.
- Three run files have a `run_id` that no longer equals the hash of their `config`. [`docs/PATHS.md`](PATHS.md) explains this.

A small example reads the two runs of test H1 and recomputes their accuracy:

```python
import json

for run_id in ["37b2a24e08bf9b8c", "5feb10aa4a385948"]:
    with open(f"results/runs/us_reader/{run_id}.json", encoding="utf-8") as f:
        run = json.load(f)
    answers = run["per_query"]
    accuracy = 100 * sum(a["correct"] for a in answers) / len(answers)
    print(run["config"]["condition"], run["config"]["library"], round(accuracy, 2))
```

The first run had no library. The second used the encyclopedia. The second accuracy minus the first is the H1 difference in `docs/RESULTS.md`.

## 4. Three levels of reproduction

### Level 1: rebuild every result from the run files

Time: a few minutes. Needs: git, Python 3.11 or newer, NumPy, and about 300 MB of disk space. No exam data, no model, no graphics card.

```bash
git clone https://github.com/Akari-H-111/open-book-law.git
cd open-book-law
python3 -m venv .venv
.venv/bin/pip install numpy
ok=yes
for m in us_answers us_verdicts us_select us_hypotheses; do
  .venv/bin/python -m open_book_law.experiments.$m || ok=no
done
.venv/bin/python -I tools/build_site_data.py || ok=no
test -z "$(git status --porcelain)" || ok=no
echo "Same results: $ok"
```

The last line prints `Same results: yes` only if every script ran and no tracked file changed. Then you rebuilt, byte for byte:

- four summary files in `results/summary/`: `us_housing_answers.json`, `us_repro.json`, `us_selection.json` and `us_hypotheses.json`;
- the tables in `docs/RESULTS.md` and `docs/REPRODUCTION.md`;
- `site/data.js`.

This level does not rerun any experiment. It starts from the stored run files. It also does not rebuild `results/summary/us_error_sample.json`, the files in `results/data_audit/` or the two review samples, because those need the downloaded data.

On Windows, use `.venv\Scripts\python` and run the four modules one by one.

### Level 2: rebuild the release files

Time: a few minutes. Needs: level 1.

```bash
git checkout v1.0.0
.venv/bin/python -I tools/make_release.py v1.0.0 --verify && cat dist/SHA256SUMS
```

The checksums must equal the `SHA256SUMS` file of the release. Section 5 explains why they can.

### Level 3: run the experiments again

Time: days. Needs: a Mac with Apple Silicon (the readers use MLX), about 16 GB of memory, tens of gigabytes of disk space, and the datasets. **We did not repeat this level for this guide.** The steps below describe how the original runs were made.

1. **Environment.** The project keeps its virtual environment at `~/venvs/open-book-law`, and the `Makefile` expects it there. `requirements-lock.txt` holds the exact versions. The `Makefile` runs Python with `-I`, which ignores the current folder, so the project itself must be installed too:

   ```bash
   python3 -m venv ~/venvs/open-book-law
   ~/venvs/open-book-law/bin/pip install -r requirements-lock.txt
   ~/venvs/open-book-law/bin/pip install --no-deps -e .
   ```
2. **Data folder.** Set `OBL_DATA` to a folder outside the repository, or make `data_local/` in the repository a link to it.
3. **Datasets.** Get these from their sources, under their own terms:

   | Folder under `$OBL_DATA` | Files | Source |
   |---|---|---|
   | `barexam_qa/` | `qa.csv`, `train.csv`, `validation.csv`, `test.csv`, `passages.tsv.zip` | `reglab/barexam_qa` on Hugging Face |
   | `housing_qa/` | `questions.json.zip`, `statutes.tsv.zip` | `reglab/housing_qa` on Hugging Face |
   | `conan_overruled/` | The table of overruled decisions as CSV | Constitution Annotated |

   `make goodlaw-data` then downloads the U.S. Reports volumes of the Caselaw Access Project and builds the derived files. Each run file records the SHA-256 of every data file that it read, so you can check that your files are the same.
4. **Models.** `data/model_revisions.json` pins the revision of every model. The code loads models from the local Hugging Face cache only, with `trust_remote_code=False`. So each model must be in the cache first. This short script downloads one model at its pinned revision:

   ```python
   import json
   from huggingface_hub import snapshot_download

   model_id = "mlx-community/Meta-Llama-3-8B-Instruct-4bit"
   with open("data/model_revisions.json", encoding="utf-8") as f:
       pin = json.load(f)[model_id]
   snapshot_download(model_id, revision=pin["revision"], allow_patterns=pin["patterns"])
   ```

   The model IDs are in `READERS` in `open_book_law/reader/mlx_reader.py` and in `MODELS` in `open_book_law/retrieval/dense.py`.
5. **Runs.** Each experiment script takes its settings as arguments. For example:

   ```bash
   make us-retrieval DATASET=mbe RETRIEVER=bm25
   make us-reader ARGS="--dataset mbe --reader llama8 --condition closed"
   ```

   The files `tools/queue_*.txt` list the exact arguments of the original runs, in order. `tools/run_queue.sh` runs one queue file, one job at a time.
6. **Good-law questions.** `make goodlaw-questions` calls Claude models through the Claude command-line tool. New questions will differ from the original ones, because the models do not give the same text twice. The original questions are not in the repository, apart from the sample of 30 in `docs/review/goodlaw_sample.md`.

A rerun with the same settings needs `--rerun 1` (or a higher number), because a run file cannot be overwritten. The summary scripts still take the earliest run.

## 5. Verify a release

A release has three files: the site as a zip, a full snapshot of the repository as a zip, and `SHA256SUMS`.

1. **The download is unchanged.** In the folder with the downloaded files:

   ```bash
   shasum -a 256 -c SHA256SUMS
   ```

   Each line must end in `OK`.
2. **The files match the tagged code.** Run level 2 above. `tools/make_release.py` reads every file from git's stored objects for the commit, not from the working tree. It stores them without compression, in sorted order, with one fixed date and the file modes from git. So the same commit gives the same bytes on every computer.
3. **The snapshot is whole, and its results rebuild.** Each zip holds a `MANIFEST.sha256` with a checksum for every file inside it. The full snapshot is not a git repository, so use these steps in place of level 1. Start in the unzipped folder `open-book-v1.0.0`:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install numpy
   ok=yes
   for m in us_answers us_verdicts us_select us_hypotheses; do
     .venv/bin/python -m open_book_law.experiments.$m || ok=no
   done
   .venv/bin/python -I tools/build_site_data.py || ok=no
   shasum -a 256 -c MANIFEST.sha256 > /dev/null || ok=no
   echo "Same results: $ok"
   ```

   The scripts rewrite the summaries, the results tables and `site/data.js`. Then the manifest check compares every file of the snapshot with its recorded checksum.

Before it writes anything, `make_release.py` stops if the tag points to another commit, if a tracked file has local changes, if `site/data.js` is not what the build script writes, or if any committed file contains a local machine path.

## 6. Tests and CI

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

- The tests use small made-up inputs and fake models. They need no downloaded data.
- A test skips when its library is missing. With only NumPy and pytest, the tests that need MLX, PyTorch or NLTK skip, and no test file is skipped as a whole.
- `tests/test_site.py` checks the website: every page has the same navigation, every local link works, and no page loads anything from another site.
- `.github/workflows/verify.yml` runs on every push. It runs the tests, then the scripts of level 1, and fails if a file under `results/summary/`, a results document or a file under `site/` changed or appeared. It does not rerun experiments and does not build the release files.
- `.github/workflows/pages.yml` publishes `site/` only after `verify` passed on the same commit.
- `ruff check .` is the linter, with the settings in `pyproject.toml`.

## 7. Fork and extend

The license is MIT. Please keep the rules of section 8 in a fork, or say clearly that you changed them.

**A new reader model.**
1. Add a short name and the model ID to `READERS` in `open_book_law/reader/mlx_reader.py`.
2. Pin its revision and file patterns in `data/model_revisions.json`.
3. If its chat template needs a special opening, see `ANSWER_OPENING` in `open_book_law/reader/prompts.py`. A change of wording needs a new `PROMPT_VERSION`.
4. Try it with `--limit 10`. Such a run goes to the `us_smoke` suite and uses validation questions only.

**A new library.** Add a name and its set of passage sources to `LIBRARIES` in `open_book_law/us/barexam.py`. Then run `us_retrieval` with `--library <name>`.

**A new search method.** `open_book_law/experiments/us_retrieval.py` chooses the retriever. BM25 and the dense search both return a ranked list of passage IDs for each question, and `runlog.write_run` stores it.

**A new test.**
1. Write the claim, the measure and the threshold into `docs/PREREGISTRATION.md` as a dated amendment, before the run.
2. Add its threshold to `THRESHOLDS` and its comparison to `main` in `open_book_law/experiments/us_hypotheses.py`. The Holm correction then covers it as well.
3. `tools/build_site_data.py` exports every test of the summary, so `site/data.js` picks it up. Add its plain-language text and its group to `TESTS` in `site/app.js`, or the website cannot show it.
4. Check the fixed text that counts tests: "11 tests" appears on the site, in `README.md` and in the lesson material.

**Another country's law.** The loaders in `open_book_law/us/` turn a dataset into questions with `qid`, `query`, `answer` and a split. A new loader with the same shape can reuse the search, the reader and the statistics.

**The website.** Edit the HTML files in `site/` by hand. There is no build step for pages. Results must come from `site/data.js`: add a field in `tools/build_site_data.py`, then show it with a `data-bind` attribute or in `site/app.js`.

## 8. Rules that protect the results

These rules are in `AGENTS.md` and the plan. They matter more than any single result.

- **Run files are append-only.** A rerun writes a new file. The one recorded exception is in [`docs/PATHS.md`](PATHS.md).
- **No exam question text and no passage text in git.** Only IDs, metrics and short quotations with their sources.
- **Every number in a document comes from a file under `results/` that a committed script produced.**
- **Selection uses validation questions only.** Test questions do not reach a model or a retriever until the plan says so.
- **No test-set decision changes after a test-set result.** Later work is labelled "post hoc".
- **Negative results and failed attempts stay.** For example, the failed grid of test H6 is still in `results/runs/us_finetune/`.
- **Labels made by AI are called "silver".** They are never called expert labels.

## 9. Known limits

- **No human review.** No person has reviewed the code or checked the results. Other AI models reviewed parts of the code, and `docs/EXECUTION_LEDGER.md` records what they found.
- **Apple Silicon only.** The reader uses MLX. The dense search uses PyTorch on the Apple GPU (`DEVICE = "mps"` in `open_book_law/retrieval/dense.py`). BM25 and the statistics need only NumPy.
- **A private history.** The public repository starts from one commit. The times of the plan and its amendments are listed in the release notes, but you cannot check them from the public repository alone.
- **Ties in dense search.** Dense search keeps a bounded number of candidates before it applies the fixed tie order. If more candidates than that share one exact score, the result can depend on how the data was split into blocks. The effect was not measured.
- **Fine-tuning runs cannot be repeated exactly.** Training seeded NumPy but not PyTorch at first. The plan records this in Amendment 8.
- **Open questions.** [`docs/STATUS.md`](STATUS.md) lists what did not run and which causes are still unknown.
