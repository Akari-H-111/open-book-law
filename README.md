# Open Book

**Does a small AI model answer old US bar exam questions better when it can look things up in a law library?**

Open Book is a research project that you can check. It is not legal advice, and its scores are not bar exam scores. AI models did most of the work, and no person has checked the code or the results yet. In this text, "we" means the project: the author together with the AI models that did the work. [How AI was used](#how-ai-was-used) has the details.

**Watch the 67-second trailer:** <https://www.youtube.com/watch?v=Z9x9vX72wcE>

## Choose your path

| If you are… | Start here | You need |
|---|---|---|
| **A teacher or a student** | **[The website](https://akari-h-111.github.io/open-book-law/)**: every result with plain explanations, and a classroom mode in which students guess first. Then [lesson ideas](docs/TEACHING.md), a [worksheet](https://akari-h-111.github.io/open-book-law/worksheet.html) and an [answer key](https://akari-h-111.github.io/open-book-law/answer-key.html) | A browser. No setup and no programming |
| **An engineer or a researcher** | **[The engineering guide](docs/ENGINEERING.md)**: how the code and the data fit together, three levels of reproduction, how to verify a release, and how to fork and extend | git and Python for the first level |
| **Someone who wants the files** | **[Releases](https://github.com/Akari-H-111/open-book-law/releases)**: the website and the full results as zip files, with checksums. [Downloads](#downloads) explains them | Nothing |

New to the words? The [glossary](#glossary) below explains the main ones, and the website explains [all of them](https://akari-h-111.github.io/open-book-law/words.html).

## In one minute

- We gave small AI models that run on a laptop some old multiple-choice questions from the US bar exam. Some questions also came with passages from a law library.
- We wrote down 11 tests and their rules for success before the main runs. Six came out **supported** and five came out **not supported**.
- **The library we could actually give the model did not help overall.** But when the model got the passage that a law student had marked as the right one, it scored 12 points higher than with the best library we could build. So finding the right text matters a great deal.
- **Old law is a trap.** Courts sometimes overrule their own earlier decisions. When we showed the model only the overruled decision, it chose the outdated rule far more often. Search tools also often ranked the old decision above the new one. The two simple fixes that we tried did not reduce the problem by a clear amount.
- **An example.** In 1972, the Supreme Court overruled a 1941 decision about how railroad workers may bring claims for wrongful discharge. When the model read only the 1941 decision, it chose the old rule. When it read only the 1972 decision, it chose the current rule.

## For teachers

The project can support lessons in statistics, civics and government, computer science, and AI literacy, for students from about 15 to 22. Four of the five lessons need no programming.

| Lesson | Subject | Time |
|---|---|---|
| 1. Predict, then check | Any | About 20 minutes |
| 2. When the law changes | Civics or government | About 30 minutes |
| 3. Fair tests and honest statistics | Statistics | About 45 minutes |
| 4. How a search engine works | Computer science, with some programming | 45 to 90 minutes |
| 5. Who checked what? | AI literacy or research ethics | About 30 minutes |

[`docs/TEACHING.md`](docs/TEACHING.md) has the steps and the discussion questions for each lesson. The website has the same lessons, a [printable worksheet](https://akari-h-111.github.io/open-book-law/worksheet.html) and an [answer key](https://akari-h-111.github.io/open-book-law/answer-key.html).

Please keep three points in mind in class. This is not legal advice. The questions about overruled decisions are AI-written and not yet checked by a person. And you may copy and adapt everything here for teaching, under the MIT License.

## For engineers

Every number in this project comes from a stored run file through a committed script. You can rebuild all of them in a few minutes. This needs git, Python 3.11 or newer and NumPy, and no exam data, no AI model and no graphics card.

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

The last line prints `Same results: yes` only if every script ran and no tracked file changed. Then you rebuilt the summaries of the tests, the tables in both results documents and the data of the website, byte for byte. The scripts do not rerun the experiments: they start from the stored run files. The same check runs on every push ([`.github/workflows/verify.yml`](.github/workflows/verify.yml)).

[`docs/ENGINEERING.md`](docs/ENGINEERING.md) explains the rest: the module map, the format of a run file, how to rebuild and verify the release files, how to rerun the experiments, and how to fork and extend the project.

## The question

To practise law in the United States, a person usually has to pass a **bar exam**. One part of it is the **MBE**, a long multiple-choice test on core subjects such as contracts, torts and constitutional law. The new NextGen version of the exam gives test takers some legal resources during parts of the test. So it matters what a test taker can look up, and how well they use it.

We asked the same question about AI. Imagine a small model that starts from zero. If we hand it a law library, does it do better? If it fails, why does it fail? Is the reason that search found the wrong text, or that the model misread the right text, or that the law has changed?

## What we did

1. **Questions.** We used three sets of questions:
   - 1,195 historical MBE questions from 1972 to 1998, from the public dataset `reglab/barexam_qa`. A law student marked one "gold" passage for each question as the passage that answers it.
   - 6,853 yes-or-no questions about state housing law, from `reglab/housing_qa`.
   - A **good-law test** that we built. The US government publishes a table of Supreme Court decisions that the Court later overruled. For each pair of decisions, an AI model wrote one question. Its right answer changed when the old decision was overruled. A second AI model checked each question. This left 227 questions. Two of them later left the test, because the newer decision was itself overruled, so the tests use 225.
2. **Libraries.** The model could read passages from a legal encyclopedia (Wex, from the Legal Information Institute at Cornell), from court opinions, or from both. For the good-law test, the library held Supreme Court opinions.
3. **Search.** We used two kinds of search. BM25 counts matching words, much like a classic search engine. E5 is a small AI model that compares meanings. AI models wrote BM25, the scores and the statistics without search or statistics libraries. They kept the code short, so that one person could explain every line. The author cannot do this yet.
4. **Readers.** The models that answered the questions were Llama 3 and Qwen3. Each has 8 billion parameters, the numbers that a model learns in training. Both were shrunk to run on a laptop. All runs for the 11 tests ran on one MacBook Air with no fan and 16 GB of memory. Writing the good-law questions and the AI labels used Claude models in the cloud.
5. **Rules first.** Before the main runs, the plan was written down in [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md). An AI model wrote it, and the author approved it. It fixed which tests count, what counts as a success, and which data we may look at. Later changes are dated "amendments" in the same file, and each one was committed before the run that it affects. This public repository starts from a single commit, so you cannot check these times here. The release notes list the private commits and their times, and the author can share that history on request.
6. **Which questions count.** The tests on MBE questions use 1,071 of the 1,195 questions: the training and test parts of the dataset. The other 124 questions are the validation part. The plan reserved them for choosing settings, such as which library and which model to use, before the tests ran.
7. **Reproduction.** We also tried to reproduce the published results of Zheng et al. (2025), "A Reasoning-Focused Legal Retrieval Benchmark". The results are in [`docs/REPRODUCTION.md`](docs/REPRODUCTION.md). Most targets came out "reproduced" or "partly reproduced". One target diverged: on housing questions without a library, our model scored higher than the paper's model did. Two targets need the largest search model, which was too slow for this laptop, so they did not run.

## What we found

All numbers below come from [`docs/RESULTS.md`](docs/RESULTS.md), which a script writes from the stored run files. Differences are in **percentage points**. "Interval" is a 95% range of plausible values. For most tests, it comes from resampling the questions many times (a bootstrap). For H9, which is a share, it comes from a standard formula for shares (the Wilson interval). The number of questions comes from `results/summary/us_hypotheses.json`, which the same script writes.

A test is **supported** only if three things hold. The difference must be at least the size that the plan required. The interval must not include zero. And the test must pass after a correction for running 11 tests (the Holm correction). When you run 11 tests, one may look good by luck, and the correction allows for this.

Tests H4 to H6 are about search engines. Readers who care mainly about law can skip them.

| Test | The claim, in plain words | Questions | Difference | Interval | Verdict |
|---|---|---:|---:|---|---|
| H1 | Giving the model the best real library beats giving it no library | 1,071 | −0.19 | −2.80 to +2.33 | not supported |
| H2 | An encyclopedia helps more than court opinions | 1,071 | +0.65 | −1.87 to +3.17 | not supported |
| H3 | The gold passage beats the best real library | 1,071 | +12.04 | +9.06 to +15.03 | supported |
| H4a | Adding the model's own reasoning to the search words helps a word-matching search engine (BM25) rank the gold passage among its first 100 results | 1,071 | +5.51 | +4.11 to +7.00 | supported |
| H4b | The same, for a search model that compares meanings (E5) | 1,071 | +3.92 | +2.71 to +5.23 | supported |
| H5 | Searching only the right state's laws beats searching every state's laws | 2,000 | +5.60 | +3.50 to +7.70 | supported |
| H6 | Extra training on some states' laws helps the meaning-based search model on states that it has not seen | 1,854 | −0.59 | −2.91 to +1.67 | not supported |
| H7 | Showing only the overruled decision makes the model pick the outdated rule more often than showing nothing | 225 | +53.33 | +46.67 to +60.00 | supported |
| H8 | Removing overruled decisions from search results lowers how often the model picks the outdated rule | 225 | +1.33 | −1.78 to +4.44 | not supported |
| H9 | Search often ranks the overruled decision above the decision that overruled it | 225 | 38.67% of questions | 32.54% to 45.17% | supported |
| H10 | An AI agent that can check whether a case is still good law picks the outdated rule less often than plain search | 225 | +2.67 | −4.00 to +8.89 | not supported |

How to read some rows:

- **H1 and H3.** With the encyclopedia, the model scored 0.19 points *lower* than with no library. With the gold passage, it scored 12.04 points higher than with the encyclopedia. The gap between these two rows is the main lesson: the right text helps, and our search may often have missed it. These tests do not measure how often it missed.
- **H7.** When the model saw only the overruled decision, the share of outdated answers rose by 53.33 points.
- **H8 and H10.** A positive number means that the fix lowered the share of outdated answers. Both fixes moved in that direction, but the intervals include zero, so we cannot tell them apart from chance.
- **H9.** This row is a share, not a difference. In 38.67% of questions, a passage from the old decision ranked above every passage from the new one. The plan required the lower end of the interval to be above 30%, and it is.

**"Not supported" does not mean "proven false".** It means that this experiment did not show the effect clearly enough. A larger model, a better library or more questions might give a different answer.

## What this project cannot show

- **These are not bar exam scores.** The questions are old exam questions released from 1972 to 1998, and the real exam is scored differently. A score here says nothing about whether a model, or a person, could practise law.
- **The law has changed since 1972.** Some official answers may rest on rules that are no longer good law.
- **Small models only.** We tested two 8-billion-parameter models in compressed form, with one prompt, on one laptop. Larger models may behave very differently.
- **One gold passage per question.** Many other passages may also state the right rule. So the search scores may understate how good the search really is.
- **The good-law questions are AI-written and not yet checked by a person.** The table of overruled decisions is official, but an AI model wrote the questions and their four options. A random sample of 30 is in [`docs/review/goodlaw_sample.md`](docs/review/goodlaw_sample.md), waiting for the author's review.
- **The error analysis is an AI first pass.** An AI model labelled why 100 wrong answers went wrong. The author has not reviewed those labels yet ([`docs/review/error_sample.md`](docs/review/error_sample.md)).
- **AI judgments are "silver" labels.** Wherever an AI model judged relevance or correctness, we call the result "silver" and never call it an expert label.
- **The author is not a licensed US attorney.** Nothing here is legal advice.

## Downloads

Each release on the GitHub Releases page has these files:

| File | What it holds |
|---|---|
| `open-book-site-<version>.zip` | The website. Unzip it and open `index.html`. It works without internet access |
| `open-book-full-<version>.zip` | Everything in the repository at this version: the code, the run files, the summaries and the documents. These hold every number in this project. The summary scripts also run inside it, without git. [`docs/ENGINEERING.md`](docs/ENGINEERING.md) has the steps |
| `SHA256SUMS` | A checksum for each file |

**To check a download,** compare its checksum with the one in `SHA256SUMS`. On macOS or Linux, run `shasum -a 256 -c SHA256SUMS` in the folder that holds the files. On Windows, run `certutil -hashfile <file> SHA256` and compare the result by eye. Each zip file also holds a `MANIFEST.sha256` with a checksum for every file inside it.

**To check that the files match the code,** anyone can rebuild them from the tagged commit with `python3 -I tools/make_release.py <version> && cat dist/SHA256SUMS`. The script writes the same bytes on every computer, so the checksums must match.

## Glossary

- **Bar exam.** The licensing exam that a person must usually pass before practising law in a US state.
- **MBE (Multistate Bar Examination).** The multiple-choice part of the bar exam that most states use. It covers subjects such as contracts, torts, criminal law and constitutional law.
- **Retrieval.** Finding the passages in a large collection that are most likely to help with a question. A search engine does retrieval.
- **RAG (retrieval-augmented generation).** A method in which a system first retrieves some passages and then gives them to an AI model together with the question. This project tests whether RAG helps on bar exam questions.
- **Preregistration.** A plan that researchers publish before they see their results. It fixes the tests and what counts as success, so that nobody can pick the favourable tests afterwards.
- **Overruled precedent.** A precedent is an earlier court decision that later courts follow. A court overrules a precedent when it decides that the earlier decision was wrong. After that, the old rule is no longer "good law". For example, in *South Dakota v. Wayfair* (2018), the Supreme Court overruled two earlier decisions about sales tax on sales from other states.
- **Good law.** A rule or decision that courts still follow. Lawyers must check this before they rely on a case.
- **Citator.** A tool that tells a lawyer whether a decision has been overruled or questioned. Our "citator" is a simple version built from the government's table.
- **Agent.** An AI model that can take steps on its own, such as searching, reading a passage and checking a case, before it answers.
- **Percentage point.** The difference between two percentages. Going from 40% to 45% is a rise of 5 percentage points.
- **95% interval.** A range of plausible values for the true difference, given how much the result could vary by chance. If it includes zero, we cannot rule out "no difference".

## How AI was used

AI models did most of the work in this repository. Claude models wrote the plan, the code and the documents, and the author started the long runs on their laptop. The author read and approved the plan, through Chinese paraphrases that Claude wrote, before the main runs. The author also decided which public law compilations the AI research had to read. The author did not write or edit any code or document directly, and has not yet checked the results. Every commit names a Claude model as co-author. OpenAI Codex models reviewed some of the code and documents. Inside the experiments, Claude models wrote and checked the good-law questions, judged passages in the label audit and made the first pass of the error analysis.

[`docs/AI_ASSISTANCE.md`](docs/AI_ASSISTANCE.md) lists each step: what an AI model did, what the author decided or checked, and what is still waiting for a human check.

## Repository layout

| Path | What it holds | For whom |
|---|---|---|
| [`site/`](site/) | The website: ten static pages, one style sheet, one script and one data file | Everyone |
| [`docs/TEACHING.md`](docs/TEACHING.md) | Lesson ideas with steps and discussion questions | Teachers |
| [`docs/ENGINEERING.md`](docs/ENGINEERING.md) | How to study, reproduce, verify and fork the project | Engineers |
| [`docs/RESULTS.md`](docs/RESULTS.md), [`docs/REPRODUCTION.md`](docs/REPRODUCTION.md) | The 11 tests, and the comparison with published results. Scripts write both tables | Everyone |
| [`docs/PREREGISTRATION.md`](docs/PREREGISTRATION.md) | The plan, with dated amendments | Researchers |
| [`docs/AI_ASSISTANCE.md`](docs/AI_ASSISTANCE.md), [`docs/STATUS.md`](docs/STATUS.md) | Who did what, what is done, and what no person has checked yet | Everyone |
| [`docs/README.md`](docs/README.md) | A guide to all the other documents and records | Everyone |
| `open_book_law/` | The code. One-time data preparation is in `prep/`, which is held to a lower standard of line-by-line explanation | Engineers |
| `results/` | One file per run, and the summaries that scripts compute from them | Engineers |
| `tests/`, `tools/`, `.github/` | Automated tests, the scripts that build the site and the release, and the checks that run on every push | Engineers |
| [`AGENTS.md`](AGENTS.md) | The rules that AI agents followed while they worked in this repository | Engineers |

The datasets are not in this repository. They come from their original sources under their own terms. The repository stores only question IDs, passage IDs, scores and short quotations with their sources.

## License and citation

Copyright 2026 Jian-Yu Huang (A. Hayami). The code, the documents and the website are released under the MIT License. See [`LICENSE`](LICENSE). To cite the project, see [`CITATION.cff`](CITATION.cff). To report a mistake or ask a question, see [`CONTRIBUTING.md`](CONTRIBUTING.md).
