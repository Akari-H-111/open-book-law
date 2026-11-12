# Execution ledger

This page records what happened during long runs and anything that a run file alone would not show.

## 2026-11-03

- **Machine:** MacBook Air M2 (no fan), 16 GB memory, Apple GPU through MPS. Long jobs run one at a time from `tools/run_queue.sh`, with `caffeinate`.
- **`e5-small` on `mbe` started at 17:05 with code from before the simplification.** It finishes after the simplification, so its run file records a later commit than the code that produced it. The storage format did not change: old and new `dense.py` wrote byte-identical stores on a synthetic test. Its configuration also keeps fields that were later removed. While it ran, other workers used the same GPU for short smoke tests, so its speed is not a clean measurement.
- **The simplification changed no recorded result.** A BM25 rerun on `mbe` with the shorter code (`317a517377ea44f6`) matched `064ab92f0a8e8c80` byte for byte across 1,195,000 rows. An earlier rerun (`788ba5c164c2a3ce`) matched too. New retrieval runs get new run ids for the same settings, because the configuration fields changed.
- **Code size.** The simplification took the code from 4,729 to 4,066 lines, against a target of 2,800. Further cuts would have removed things that the plan requires or made the code harder to read. So one-time data preparation moved to `open_book_law/prep/`, about 1,500 lines. This does not make the project smaller. It marks what must be defended line by line and what must be understood at the level of design.
- **Good-law pilot.** The conductor read the five pilot questions before generating the rest. They stay in the test (Amendment 3).

## 2026-11-04

- **Independent review.** OpenAI `gpt-6.1-terra` read the core code and reported 7 defects. The conductor confirmed each in the code. Six went to a fix worker (`docs/worker_briefs/w7_fixes.md`). No confirmatory reader had run, so no reported result depended on them.
- **Known limit, not fixed.** Dense search keeps a bounded number of candidates per chunk before applying the seeded tie order. If more candidates than that share one exact score, the kept ones depend on partitioning. Exact ties come mainly from identical passage text, and the effect should be small. It was not measured.
- **`e5-small` on `mbe` differs from the paper.** R@10 0.92, R@100 4.10, R@1000 12.80, against published 0.59, 2.68, 9.29. The R@1000 gap exceeds the limit, so the cause must be investigated and recorded. It has not been yet.
- **Good-law questions are built.** From 291 pairs with text, Claude Opus 5.5 marked 22 unsuitable, 8 failed the deterministic checks, and Claude Sonnet 5.5 rejected 34. That leaves 227 questions, of which 32 target a partial overruling. Counts are in `results/data_audit/goodlaw_audit.json`. The generator logged 64 command-line errors, mostly from a usage limit that stopped it once. It resumed, and the counts above are from the final state. Questions stay labelled "AI-written, not human-verified" until the project author reviews the sample.
- **`e5-small` verdict.** The rule in section 5.1 gives "partly reproduced" for R1b, not "diverged": R@1000 is 3.51 points high, inside twice the 3-point limit. An earlier ledger line read this too strongly. The cause of the higher recall is still unknown. `e5-base` (R1c) is "reproduced".
- **Reading of good-law questions.** Beyond the five pilot questions, the conductor read three random questions and the start of the review sample, to check quality. No reader or retriever has seen any of the questions, and the selection and verdict rules were already fixed.
- **Best dense model.** `us_select` chose `e5-base` by R@100 on validation (5.65 against 4.84), with 124 questions.
- **Primer cases checked.** A script compared the 11 overruling pairs named in `docs/US_BAR_FROM_SCRATCH.zh-TW.md` with `data/overruled_pairs.jsonl`. All 11 are in the table. The primer gave 356 for `Johnson v. Louisiana` where the table gives 366, so the primer now quotes the table and explains the difference. The other legal claims in that guide are only as checked as the review in `docs/review/primer_factcheck_codex.md`.
- **Selection so far.** `us_select` chose k = 1 (40.32, 38.71 and 35.48 for k = 1, 3 and 5) and `qwen3` as the best open reader (54.03 against 42.74 for `phi4`). These come from 124 validation questions, so the differences are small and noisy.
- **Library selected.** `us_select` chose `doctrine` on validation at k = 1 (41.94, against 40.32 for both `cases` and `real`). That is a gap of 2 of 124 questions, so the choice is weak. H1 and H3 use it, and H2 tests `doctrine` against `cases` on its own.
- **Runs beyond the rules.** The confirmatory queue also runs `real` and a BM25 comparison, for reporting only. Neither sets a verdict.
- **Machine freeze.** The machine stopped responding and was restarted at about 15:07, while `llama8` read the `cases` library on confirmatory questions. The last answer (789 of 1,071) was written at 15:06:58, and all 789 lines parse. The cause is not established. Memory pressure is the leading suspect: reports at 05:13 and 09:21 show Python at 11.6 GB on this 16 GB machine.
- **Reader memory cap.** After the freeze, `load_reader` limits the MLX buffer cache to 1 GB. On 10 validation questions (`ad0912ed268ab6ba`), all label probabilities matched the earlier uncapped run exactly (largest difference 0.0). Peak footprint was 7.3 GB, but 10 questions cannot show long-run growth. The `cases` run resumes from its partial file, so its run file records the later commit, while the first 789 answers came from the earlier code.
- **Slower long runs.** `llama8` on confirmatory questions read at 0.27 questions/s closed, 0.094 gold and 0.109 `doctrine`, against 0.30, 0.20 and 0.16 on short earlier runs. The cause was not measured.
- **Resume defect fixed.** A review of the Taiwan copy of `runlog.py` found that a line cut short by a crash stayed in the partial file, so the next answer would join it and break a later resume. `read_partial` now cuts that line. The freeze at 15:07 did not trigger this: all 789 lines parsed.

## 2026-11-04: correction on the size of prep/

Earlier entries say that `prep/` has about 1,500 lines. It has 1,816. `AGENTS.md` now says about 1,800. The two audit files `us_label_audit.py` and `us_error_sample.py` stay in `prep/`, because they sample and audit and set no verdict.

## 2026-11-12: local paths removed before publication

- **What.** Every tracked file lost the paths of the author's machine. Data paths are now written `$OBL_DATA/...`. `docs/PATHS.md` lists the rules and all 133 files that a script changed.
- **Run files.** This was the one edit to run files. It changed only where files were stored, and no number. Three run files changed in `config.rollout`, so their run ids no longer equal the hash of their stored `config`. `docs/PATHS.md` names them.
- **Check.** The four summary scripts of `make reproduce` rewrote every summary, and `git diff` showed no change. No model ran.

## 2026-11-12: documents moved out of the public tree

- **What.** By the author's decision, these left the tracked tree before publication: the research inventory and the topic decision record, the two study guides in Traditional Chinese, the four Codex reviews in `docs/review/`, and the six worker briefs that produced the study guides. Earlier entries of this ledger still name some of them.
- **Where they are now.** They are in the author's private folder, with their own local history. The full history of the main repository also keeps them. They are not published.
- **Why.** They were planning and study notes for the author, not part of the research record.

## 2026-11-12: last edits before publication

- **The handoff left the public tree.** `docs/HANDOFF.md` held working notes for AI sessions, including private plans. It is now in the author's private folder. `docs/STATUS.md` replaces it for readers.
- **Six worker briefs were edited.** These are the only changes to a brief after it ran:
  - `w2`: a temporary local path to a copy of the paper's text became "a local copy of the paper's text".
  - `w3`, `w4`, `w5` and `w6`: the words "in an interview" became "without AI help". The rule itself did not change: the owner must be able to explain the code.
  - `w8`: two sentences about private planning were replaced with the marker "[Removed before publication: one sentence of private planning.]".
- **Why.** The author decided to keep planning for job applications private.

## 2026-11-12: the first run of the checks on GitHub

- **What failed.** The `verify` workflow failed on its first run. Two tests of the dense search failed on Linux, because `us_retrieval.py` cleared the cache of the Apple GPU without asking whether that GPU exists.
- **Fix.** The call now runs only when the Apple GPU is available. No result depends on it: the call only frees memory.
- **What this means for the release.** The public repository was a few minutes old and had no release yet. Its single commit and the tag `v1.0.0` were replaced with the fixed version before the release was made.
