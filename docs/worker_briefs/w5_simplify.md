You are an implementation worker on the Open Book project in <repo>. A conductor session will review everything you do and re-run your checks, so report honestly: state what you ran and what you did not.

Read AGENTS.md and docs/PREREGISTRATION.md first.

## Why this task exists
The project owner has no CS degree and must be able to explain this code without AI help. `open_book_law/` is 4,729 lines. It must shrink to about 2,800 lines before any confirmatory experiment runs, so that every run records the final code. This is the most important quality requirement left in the project. Prefer code that a careful law graduate can read: plain functions, short names that say what they are, one idea per function, comments only where the reason is not obvious. Do not make it clever or dense to save lines. Removing features and duplication is the goal, not packing more into each line.

## Targets (lines per file, roughly; the total matters most)
paths 12, evalx 77, runlog 90, bm25 150, dense 150, fusion 12, mlx_reader 110, prompts 80, samples 40, us_retrieval 230, us_reader 170, us_rollout 60, us_finetune 170, us_select 80, us_hypotheses 130, us_verdicts 150, barexam 80, housing 80, audit 130, overruled 130, caselaw 230, citations 120, authority 100, goodlaw_questions 250.

## Ideas for what to remove
- Taiwan leftovers: the empty open_book_law/exams and open_book_law/laws folders, the Taiwan targets in the Makefile, Taiwan paths in paths.py, and the Taiwan description in pyproject.toml. Taiwan lives in another repository now.
- Guards against situations that cannot happen, repeated validation, fallbacks, options nobody uses (`--limit-docs`, `--query-variant` once its diagnostics are recorded, repeated smoke-store handling), and elaborate reporting that no document reads.
- Duplicate helpers across experiments. One small shared helper module is fine if it removes more than it adds.
- Audit details that no document cites. Check docs/*.md and tests before dropping a field. If a document cites it, keep it.
- Long docstrings that repeat the code. Keep the short ones that explain a reason, such as why a choice follows the paper.

## What must not change
Behaviour of everything that has produced recorded results. Acceptance checks, which you must run and report:
1. `make test` and `make lint` pass. You may delete tests of features you removed, and you must say which. Do not weaken a test of a kept feature.
2. Re-run BM25 on `mbe` with the new code into the `us_smoke` suite (about 2 minutes, CPU only). Its full ranking must be identical to run `064ab92f0a8e8c80`. Compare with a short script and report the result.
3. `python -I -m open_book_law.us.overruled` must give a byte-identical data/overruled_pairs.jsonl. The `results/data_audit/us_audit.json` and `goodlaw_audit.json` numbers that documents cite must not change.
4. `goodlaw_questions.py`: the input builder must give identical inputs for the first 20 pairs compared with the file already at DATA_ROOT/derived/goodlaw/inputs.jsonl. **A background job is using that folder right now: read it, but never write to or delete anything in it, and do not run the generator.**
5. Existing run files in results/runs/ must stay readable by us_verdicts, and `us_verdicts` must give the same R1a and R2a numbers. Never edit a run file.
6. `dense.py`: the on-disk format of stores under DATA_ROOT/derived/embeddings/ must stay exactly the same, and resuming must still work, since a multi-hour encoding job is using them. The queue's next job imports the code when it starts, so keep the tree importable at every commit and commit in small steps.

## Small additions, all from the plan
- `us_retrieval.py --states N`: restrict `housing` to N randomly chosen states with seed 20261103, for target R2c in Amendment 2, and report the same states for `bm25` and `e5-small`.
- Remove the `mbe` path from fine-tuning, per Amendment 4.
- `us/authority.py`: `status()` must also accept a case id and a docket, because docket-only decisions like Obergefell currently return `unknown` by citation.
- Declare dependencies in pyproject.toml, and write requirements-lock.txt from `~/venvs/open-book-law/bin/pip freeze`, keeping only packages the code needs and their dependencies.
- `make reproduce`: run the tests, then recompute every summary from the committed run files and fail if the result differs from the committed `results/summary/*.json`. It must work with no downloaded data and no model.

## Rules
Commit only explicit paths. Never `git add -A`. Never push. The background jobs stay untouched: do not kill anything, and do not write under DATA_ROOT/derived/embeddings or DATA_ROOT/derived/goodlaw. The GPU is busy, so run nothing heavy.

## When you are done
End your final message with a short factual report: lines per file before and after, the total, what you removed, the result of each acceptance check, tests removed, and every doubt. If a target would force dense or tricky code, miss the target and say so.
