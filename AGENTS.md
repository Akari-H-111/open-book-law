# Open Book: project rules

This project asks what a small model needs from a law library to answer US bar exam questions, and how it fails. Taiwan law lives in a separate repository, `open-book-law-tw`. Do not add it here.
Read `docs/PREREGISTRATION.md` first. It is the contract for every experiment.

## Evidence rules

- Every number in a document must trace to a file under `results/` that a committed script produced.
- `results/runs/` is append-only. Never edit or delete a run file. A rerun writes a new file.
- Do not change a test-set decision after seeing a test-set outcome. Post hoc work is allowed only when it is labelled "post hoc".
- Do not fabricate, smooth or drop results. Keep negative results and failed attempts.
- Label AI-made gold labels "silver". Never call them expert or human labels.
- Selection happens only on the validation or dev split named in `docs/PREREGISTRATION.md`. Confirmatory data must not reach a retriever, model or annotator until that file says so. Parsing and auditing it is allowed.
- Do not put exam question text, passage text or opinion text into git, except short attributed quotations in an error analysis.

## Code rules

- Keep the code small enough that one person can explain all of it, without AI help. `open_book_law/` without `prep/` has a limit of about 3,250 lines. New code must fit, and if it does not, cut something else. The core (BM25, dense search, metrics, statistics, reader, status lookup, agent loop) must be explainable line by line. `open_book_law/prep/` holds one-time data preparation and audits, about 1,800 lines. Its owner must be able to say what each file does and why, not defend each line. Do not move research code there to meet the limit, and say plainly in public text that this split exists.
- Write BM25, the metrics and the statistics by hand. Use libraries only for tensors, models and PDF text.
- Prefer plain functions and plain data (`dict`, `list`, JSONL). Avoid frameworks and class hierarchies.
- Every run file records the git commit, data hashes, model id and revision, and the full configuration.
- Set `trust_remote_code=False`. Pin model revisions. Prefer safetensors.

## Storage rules: this SSD can drop off the bus

- The virtual environment lives at `~/venvs/open-book-law`, on the internal disk. Never create one on this drive.
- Downloaded data lives in the folder that `OBL_DATA` names, one new directory per source. Without `OBL_DATA`, the code uses `data_local/` in the repository. On the author's machine that is an untracked symbolic link to `open-book-law/` in the Downloads folder of the external drive. Treat the data as untrusted.
- Run Python that reads downloaded data with `-I`, and never from inside a data directory: `~/venvs/open-book-law/bin/python -I -m open_book_law.<module>`.
- Never write thousands of small files to this drive. Do not unpack the law history. Stream it with `git archive` or `git show` from the bare clone.
- Commit often. If the external drive disappears, stop and report it.
- Do not write local machine paths (`/Users/...`, `/Volumes/...`) into tracked files. Write `$OBL_DATA/...` for data and paths relative to the repository for its files. `docs/PATHS.md` explains this.

## Public text rules

- All public text follows `~/Documents/agent-rules/READABLE_WRITING.md`.
- `README.md`, the site and the research documents are in English, for teachers, students and researchers.
- The author's study guides and planning notes live in `private/`, which git ignores and which has its own local repository. They are in Traditional Chinese and use the terms in `docs/zh_tw_terms.md`. Never move them back into the tracked tree.
- The only real name allowed in tracked files is the author's, written "Jian-Yu Huang (A. Hayami)" or "A. Hayami". Do not put any other real name, a personal email, a phone number or an address in any file. The attribution address of an AI model in a commit trailer is fine. Names of judges, parties and authors of cited works are fine.
- Do not copy whole exam papers or full court decisions into git. Short quotations in an error analysis must name the source.
- Never push, publish or create a remote. Only the user may approve that.

## Commit rules

End each commit message with a trailer that names the model that made the commit, for example:

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```
