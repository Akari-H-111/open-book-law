You are an implementation worker on the Open Book project in <repo>. A conductor session will review everything you do and re-run your checks, so report honestly: state what you ran and what you did not.

Read AGENTS.md and docs/PREREGISTRATION.md Part I first, including Amendments 1 and 2. They bind you. Read the existing code in open_book_law/ (evalx.py, runlog.py, retrieval/, us/, experiments/us_retrieval.py, experiments/us_verdicts.py) and follow its style. Keep it small: this task should add about 700 lines or fewer, and the project owner must be able to explain every function without AI help.

Another worker is writing open_book_law/us/overruled.py, us/caselaw.py, us/authority.py and experiments/us_goodlaw_*.py, and a long encoding job is running from the same checkout. Commit only your own paths with explicit `git add <path>`, never `git add -A`. If git reports a lock, wait a little and retry. Do not edit files while they would change a running job's behaviour: the encoding job has already loaded its code, so edits are safe, but do not delete anything under DATA_ROOT.

You own: open_book_law/reader/, open_book_law/experiments/us_reader.py, us_rollout.py, us_finetune.py, us_select.py, us_hypotheses.py, edits to experiments/us_retrieval.py, experiments/us_verdicts.py and runlog.py, tests/test_reader*.py, tests/test_us_select.py, data/housing_reader_sample.json, data/housing_state_splits.json, results/summary/us_selection.json, results/summary/us_hypotheses.json, and Makefile targets appended at the end.

Weights are in the Hugging Face cache, pinned in data/model_revisions.json. Load with local files only at the pinned revision. Never set trust_remote_code. The paper's text is at $OBL_DATA/reasoning.txt; Appendices E and I and sections 5.3 and 5.4 matter here.

**The GPU is busy.** A multi-hour encoding job is using it. You may run short smoke tests only: at most about 10 questions per configuration, on `validation` only, for measuring speed and checking the plumbing. Never run a reader on `train` or `test`. Do not start any full run: leave exact commands for the conductor.

## 1. Reader
- `reader/mlx_reader.py`: load an MLX model and return the probability of each answer letter from one forward pass after the prompt, using the next-token distribution (the paper's method for Llama). Handle tokenizers where the letter token may be " A" or "A": record which token ids were used, and test it. Also provide a short greedy `generate` for rollouts.
- `reader/prompts.py`: closed-book and with-context prompts for `mbe` (four options) and `housing` (Yes or No; the dataset card suggests "Consider statutory law for {state} in the year 2021. {question}\n\nAnswer \"Yes\" or \"No\".\nAnswer:"). Use the tokenizer's chat template if the model has one. Truncate context to a fixed token budget and record how many contexts were cut. Prompts are chosen on `validation` and then frozen by a version string in the run file.
- For Qwen3, disable thinking mode. Report if a model needs anything unusual.

## 2. Reader experiment: experiments/us_reader.py
`--dataset mbe|housing --reader llama8|qwen3|phi4 --condition closed|gold|retrieved --retriever X --library Y --k K --split S --sample path --limit N`.
- `retrieved` reads an existing rank file, filters to the library's sources, takes the top k and joins passages. For the `doctrine`, `cases` and `real` libraries you need rankings over those subsets: read section 3.2, and make `us_retrieval.py --library` work for them with BM25 and dense search over a subset of existing vectors, with no new encoding.
- Resumable: append to a partial JSONL under DATA_ROOT/derived/reader_partial/ and write the final run file with per-question records (qid, predicted letter, correct, probabilities, docids used, truncation flag). No question or passage text in run files. Log questions per second.
- Smoke runs go to a suite named `us_smoke`.

## 3. Rank file policy (Amendment 2)
Change runlog and us_retrieval so that the top 100 goes to git at results/runs/<suite>/<run_id>.rank.tsv.gz, and the top 1000 goes to DATA_ROOT/derived/ranks/<run_id>.tsv.gz. Metrics are computed before the cut. The running encoding jobs finish with the old code, so handle both forms when reading.

## 4. Other retrieval pieces
- `us_retrieval.py --retriever hybrid --from RUN_A RUN_B`: reciprocal rank fusion of two existing rankings (k = 60), with no encoding. Fuse over the full top 1000 when available.
- `--scope all-states` for `housing` with dense retrievers: search all states at once with a memory-mapped matrix in chunks, and record the share of top-10 passages from another state, for H5.
- `us_rollout.py`: generate structured reasoning rollouts with the paper's Table 13 and Table 14 prompts, with a local model (temperature 0, max 256 new tokens). Text is cached under DATA_ROOT/derived/rollouts/. `us_retrieval.py --rollout PATH` searches with the expanded query; read the paper for how it combines query and rollout, and write down what it says. Note that the paper used GPT-3.5, so this is a replication with another generator.

## 5. Fine-tuning: experiments/us_finetune.py
A short hand-written torch loop on MPS for `e5-small`: multiple-negatives ranking loss (cross-entropy over query-passage dot products with in-batch negatives), L2-normalized average pooling, temperature fixed at 0.01 unless the validation run suggests otherwise. Data: `housing` question and gold statute pairs from training states. Write data/housing_state_splits.json from seed 20261103: 60% train, 10% validation, 30% test by state, among states with questions. Save the model under DATA_ROOT/derived/models/. Log loss, time and validation R@10, and save the settings. Evaluation encodes only test-state statutes with the tuned model and with zero-shot `e5-small` vectors. Also report results for question groups not seen in training. Smoke test with a tiny subset only.

## 6. Samples and selection
- data/housing_reader_sample.json: 2,000 questions stratified by state, seed 20261103 (Amendment 2). Do not look at any reader output before writing it.
- `us_select.py`: applies section 3.4 mechanically from `validation` run files and writes results/summary/us_selection.json: the best dense model, k, the best real library, `best-open`. Show `pending` when runs are missing. It must never read `train` or `test` records.

## 7. Verdicts
- Extend us_verdicts.py with R3 and R4. R4 has no verdict, only a comparison with a note that the published set includes private questions.
- `us_hypotheses.py`: computes H1 to H6 mechanically from run files on the confirmatory set: difference, 95% paired bootstrap, exact McNemar for accuracy, Holm across the family (H7 to H10 stay `pending` for now), and the verdict rule. Show `pending` when runs are missing. Write results/summary/us_hypotheses.json, and generate a table between AUTO markers in docs/RESULTS.md. Do not write any conclusion prose.

## 8. Tests
Tiny examples: letter probability extraction with a fake model, prompt truncation, library filtering, hybrid fusion from rank files, sample determinism, state split determinism, the fine-tune loss on tiny tensors, hypothesis verdict logic on synthetic per-question data, including cases that fail the rule. `make test` and `make lint` must pass.

## When you are done
Everything committed. End your final message with a short factual report: what ran, the speed of each reader on smoke runs (say how busy the GPU was), peak memory if measured, the exact commands left for the conductor in the recommended order with estimated hours, and every doubt or defect. If something blocks you, say so and stop.
