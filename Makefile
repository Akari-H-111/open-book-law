PY := $(HOME)/venvs/open-book-law/bin/python
RUFF := $(HOME)/venvs/open-book-law/bin/ruff

.PHONY: test lint reproduce

test:
	$(PY) -m pytest -q

lint:
	$(RUFF) check .

# Recompute every summary from the run files and fail if a result differs from the committed one.
# This needs no downloaded data and no model.
reproduce: test
	$(PY) -I -m open_book_law.experiments.us_answers
	$(PY) -I -m open_book_law.experiments.us_verdicts
	$(PY) -I -m open_book_law.experiments.us_select
	$(PY) -I -m open_book_law.experiments.us_hypotheses
	git diff HEAD --exit-code -- results/summary docs/REPRODUCTION.md docs/RESULTS.md

.PHONY: us-audit us-retrieval us-repro

us-audit:
	$(PY) -I -m open_book_law.prep.audit

# One configuration at a time: make us-retrieval DATASET=mbe RETRIEVER=bm25
us-retrieval:
	$(PY) -I -m open_book_law.experiments.us_retrieval --dataset $(DATASET) --retriever $(RETRIEVER)

us-repro:
	$(PY) -I -m open_book_law.experiments.us_answers
	$(PY) -I -m open_book_law.experiments.us_verdicts

.PHONY: us-reader us-rollout us-finetune us-select us-hypotheses

# Arguments pass through ARGS: make us-reader ARGS="--dataset mbe --reader llama8 --condition closed"
us-reader:
	$(PY) -I -m open_book_law.experiments.us_reader $(ARGS)

us-rollout:
	$(PY) -I -m open_book_law.experiments.us_rollout $(ARGS)

us-finetune:
	$(PY) -I -m open_book_law.experiments.us_finetune $(ARGS)

us-select:
	$(PY) -I -m open_book_law.experiments.us_select

us-hypotheses:
	$(PY) -I -m open_book_law.experiments.us_hypotheses

.PHONY: goodlaw-data goodlaw-questions

# Parses the table, downloads CAP, links both, and audits.
goodlaw-data:
	$(PY) -I -m open_book_law.prep.overruled
	$(PY) -I -m open_book_law.prep.caselaw download
	$(PY) -I -m open_book_law.prep.caselaw build
	$(PY) -I -m open_book_law.prep.caselaw link
	$(PY) -I -m open_book_law.prep.citations

# Calls the Claude CLI: make goodlaw-questions ARGS="--limit 5"
goodlaw-questions:
	$(PY) -I -m open_book_law.prep.goodlaw_questions $(ARGS)
