# Open Book v1.0.0

**Does a small AI model answer US bar exam questions better when it can look things up in a law library?**

This first release holds the study as it stands: the plan written before the main runs, every run file, the results of all 11 preregistered tests, and a website with one path for teachers and students and one for engineers. It is a research project, not legal advice, and its scores are not bar exam scores.

## What we found

Six of the 11 tests came out supported, and five did not. The numbers come from `docs/RESULTS.md`, in percentage points.

- **Looking things up did not help overall (H1, not supported).** With the best real library, the model scored −0.19 points compared with no library.
- **The right passage helps a lot (H3, supported).** With the passage that a law student had marked, the model scored +12.04 points above the best real library. The tests do not show how often search missed useful text.
- **Old law is a trap (H7 and H9, supported).** With only the overruled decision to read, the model chose the outdated rule 53.33 points more often than with nothing to read. In 38.67% of questions, search ranked a passage from the old decision above every passage from the new one.
- **Two simple fixes did not help clearly (H8 and H10, not supported).** Removing overruled decisions from search lowered outdated answers by 1.33 points. An agent that could check the law lowered them by 2.67 points. Neither difference can be told apart from chance.

The README has all 11 tests, the limits and a glossary. `docs/TEACHING.md` has lesson ideas, and `docs/ENGINEERING.md` explains how to reproduce, verify and fork the project.

## Downloads

| File | What it holds |
|---|---|
| `open-book-site-v1.0.0.zip` | The website: ten static pages with the results, lesson ideas, a printable worksheet and a page for engineers. Unzip it and open `index.html`. It works without internet access |
| `open-book-full-v1.0.0.zip` | Everything in the repository at this version: code, run files, summaries and documents |
| `SHA256SUMS` | The SHA-256 checksum of each zip file |

The page is also online at <https://akari-h-111.github.io/open-book-law/>. A 67-second trailer is at <https://www.youtube.com/watch?v=Z9x9vX72wcE>.

## How to verify

1. **The download is unchanged.** In the folder that holds the files, run `shasum -a 256 -c SHA256SUMS`. Each line must end in `OK`.
2. **The results follow from the run files.** Clone the repository at tag `v1.0.0`. Then, with Python 3.11 or newer:

   ```bash
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

   The last line prints `Same results: yes` only if every script ran and no tracked file changed. For the unzipped full bundle, which is not a git repository, `docs/ENGINEERING.md` gives the same steps with a manifest check at the end.
3. **The release files match the tagged code.** In a clone at tag `v1.0.0`, run `python3 -I tools/make_release.py v1.0.0 && cat dist/SHA256SUMS`. The script writes `dist/SHA256SUMS`, which must equal the one attached here. The script reads every file from git's stored objects for that commit, and the zip files store them with fixed metadata. So the files come out byte for byte the same on every computer. We tested a checkout with Windows line endings on macOS, and the checksums matched. We have not tested on Windows itself.
4. **The checks also run on GitHub.** The `verify` workflow runs the tests and rebuilds the results table and the site data on every push.

## A change to stored run files

The project's rule says that run files are never edited. Before publication, one exception was made, and the author agreed to it. The run files stored file paths from the author's laptop, with the author's user name and the name of a private drive. A script replaced these paths with `$OBL_DATA/...` or with paths inside the repository. No number changed, and the summary scripts give the same results before and after.

In three run files, the changed path was part of the run's settings. Their run ids are a hash of those settings, so the ids no longer equal the hash of the stored settings: `c32ecf8920ae7b1d` (test H4a), `fb646bf5a440f2bf` (test H4b) and `37fbf29d54ace455` (a smoke run). `docs/PATHS.md` gives the full record.

This public repository starts from a single commit. The earlier history stays private, and the author can share it with reviewers on request.

## When the plan was fixed

This public repository starts from a single commit. The earlier history is private, and the author can share it with reviewers on request. These are the private commits that added each part of the plan, and the first confirmatory runs, so that the times can be checked against that history. Times are Taiwan time (UTC+8).

| Event | Private commit | Time |
|---|---|---|
| First preregistration | `5d65376` | 2026-11-03 15:36 |
| US law becomes the main track (version 3) | `ad9cab7` | 2026-11-03 16:05 |
| Amendment 1: authority graph, citation extraction, research agent | `296d23d` | 2026-11-03 16:18 |
| Amendment 2: what this machine can run | `f3682a9` | 2026-11-03 17:07 |
| Amendment 3: the good-law data | `dcd8498` | 2026-11-03 18:10 |
| Amendment 4: gaps in selection and in fine-tuning | `e1116fe` | 2026-11-03 18:13 |
| Amendment 5: H9 test, workers and the code limit | `42abfb4` | 2026-11-04 02:47 |
| First confirmatory runs (run `bc9866b8f509d13c` for search, `37b2a24e08bf9b8c` for reading) | code at `4f75e0e` | 2026-11-04 06:22 and 07:32 |
| Amendment 6: the H6 grid | `98efa2e` | 2026-11-07 07:53 |
| Amendment 7: a batching defect in the H6 grid | `a3f866d` | 2026-11-07 15:28 |
| Amendment 8: the corrected grid and the test evaluation | `73ee102` | 2026-11-07 22:40 |
| The H6 test evaluation (run `bd578ac4833d144c`) | code at `73ee102` | 2026-11-08 01:00 |
| Amendment 9: after the H6 test | `21e548b` | 2026-11-08 01:01 |

Every run file also records the commit of the code that produced it. Those commit ids point into the private history too.

## What has not been checked by a person

- The 227 good-law questions were written and checked by AI models. A random sample of 30 waits for the author's review.
- The reasons given for 100 wrong answers are an AI first pass.
- The relevance labels of the label audit are AI judgments, called "silver".

- No person has recomputed the verdicts yet. The author has not yet checked the results.

`docs/AI_ASSISTANCE.md` lists which steps AI models did and which steps the author did.

## Not included

The exam questions, the law library and the model weights are not part of this release. They come from their original sources under their own terms. The repository stores only IDs, scores and short quotations with their sources.

## License

Copyright 2026 Jian-Yu Huang (A. Hayami). The code and documents are under the MIT License.
