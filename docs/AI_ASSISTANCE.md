# How AI was used

This page says which steps AI models did, which steps the author did, and what no person has checked yet.

It has two kinds of source. The AI part comes from the repository: commit messages, `docs/EXECUTION_LEDGER.md`, the worker briefs in `docs/worker_briefs/` and the local logs of the worker runs. The author's part comes from the author's own answers, given on 2026-11-12, and from the author's planning notes, which are not published.

## Summary

- **AI models did most of the work.** One main Claude Opus 5.5 session planned the project, wrote the preregistration, gave tasks to other AI models, reviewed their work and wrote most of the documents. This page calls that session the *lead session*. Every commit names a Claude model as co-author.
- **The author did not write or edit any code or document directly.** All of the author's input was carried out by Claude after a discussion with the author.
- **The verdicts come from scripts, not from judgment.** Scripts in `open_book_law/experiments/` compute every number and verdict from the stored run files. The rules for each verdict were committed before the runs that they judge.
- **No person has checked the code or the results yet.** The author has not recomputed a verdict or read the run logs. The good-law questions and the error analysis also wait for the author's review.

## Models and their roles

| Role | Model | Where this is recorded |
|---|---|---|
| Lead session: planning, preregistration, tasks for other models, review of all work, most documents | Claude Opus 5.5 | Commit messages; Amendment 5 of `docs/PREREGISTRATION.md`, which says that only the lead session's review accepts work |
| Writing the code: data loading, search, reading, good-law data, simplification, the research agent | Claude Opus 5.5 | Briefs `w2` to `w6` in `docs/worker_briefs/`; local logs |
| Code fixes and literature notes | Claude Sonnet 5.5 | Briefs `w7`, `w8` and `w10`; local logs |
| Independent review of code and documents | OpenAI Codex models `gpt-6.1-terra`, `gpt-5.6-terra` and `gpt-6.1-sol` | `docs/EXECUTION_LEDGER.md` (2026-11-04); Amendments 5 and 8 |
| Writing the good-law questions | Claude Opus 5.5 | Section 8.2 of the preregistration; `docs/GOOD_LAW.md` |
| Checking the good-law questions | Claude Sonnet 5.5 | Same |
| Relevance judgments in the label audit | Claude Opus 5.5, then Claude Sonnet 5.5 on its own | Section 9 of the preregistration |
| First pass of the error analysis | Claude Opus 5.5 | `docs/review/error_sample.md` |
| README, this page, the release files and a first draft of the site | Claude Opus 5.5, with reviews by Claude Sonnet 5.5, `gpt-6.1-sol` and `gpt-6.1-terra` | Commits of 2026-11-12 |
| The final website, the repository layout, the engineering guide and the teaching guide | Claude Fable 5.2, with reviews by Claude Sonnet 5.5 and `gpt-6.1-sol` | Commits of 2026-11-12; brief `f1` in `docs/worker_briefs/` |

Some models are the *subject* of the study, not helpers. Llama 3 and Qwen3 answered the questions in the tests. Phi-4 mini answered only the validation questions, when the project chose between open models. They are not listed above.

## Step by step

| Step | What AI models did | What the author did |
|---|---|---|
| Choosing the topic | The lead session compared candidate topics and chose Open Book. The author had allowed it to decide | The author asked for a focus on US law instead of Taiwan law. On 2026-11-03, the author decided to move Taiwan law to a separate repository |
| Study of US law | Three or more AI models searched state and federal websites, study materials and public compilations, from the point of view of a JD student or a bar candidate | The author had the AI models do this research. The author used their own knowledge of Anglo-American law, from courses at Soochow University, to decide which compilations had to be read |
| Preregistration and amendments | The lead session wrote the plan, the hypotheses, the thresholds and all nine amendments | The author read and approved the plan and its amendments before the confirmatory runs. The author read them through Chinese paraphrases that Claude wrote. The author did not propose or change any hypothesis (H1 to H10) or any threshold |
| Data and code | AI models wrote all the code. The lead session reviewed it. Codex models reviewed the core, and the lead session confirmed each reported defect before a model fixed it | None directly. The author cannot yet explain BM25, the metrics, the statistics, the reader or the agent loop line by line |
| Running the experiments | AI sessions prepared the queues of runs and recorded problems in the ledger | The author started the long runs on their laptop. The author restarted the laptop after it stopped responding on 2026-11-04 |
| Selection and verdicts | Scripts computed them from the run files. No model judged a verdict | The author has not yet checked any result |
| Good-law questions | Claude Opus 5.5 worked through 291 official pairs of decisions and wrote the questions. After its own screening, automatic checks and a check by Claude Sonnet 5.5, 227 questions remained. The lead session read the 5 pilot questions and 3 more at random | Not yet. A random sample of 30 waits for the author's review in `docs/review/goodlaw_sample.md` |
| Label audit | Two Claude models judged passages, each on its own | None. These labels stay "silver" |
| Error analysis | Claude Opus 5.5 labelled 100 wrong answers | Not yet. The author's columns in `docs/review/error_sample.md` are empty |
| Removing local file paths before publication | An AI session wrote and ran the script. `docs/PATHS.md` records it | The author agreed |
| The trailer video | Claude Fable 5.2 built it from public-domain scans and photographs and a piece of music under CC BY 4.0. Claude Sonnet 5.5 and Gemini 3.8 Flash searched for the material | The author asked for it, listened to the music, asked for one change, and uploaded it |
| Publication | AI sessions wrote the README, the website, the guides and the release files | The author decided which files to publish, the name in `LICENSE` and the GitHub account |

## A note on "I" in the preregistration

In `docs/PREREGISTRATION.md`, "I" means the lead session, not the author. For example, the lead session checked the plan against the text of a job posting (Amendment 1) and read the five pilot questions (Amendment 3).

## The author's background

In the author's words: "trained in law in Taiwan with a Bachelor of Laws (LL.B.), and took Anglo-American law courses at Soochow University; no US law degree, and not a licensed US attorney."

## Not yet checked by a person

| Item | Where | What would count as checked |
|---|---|---|
| 227 good-law questions | `docs/review/goodlaw_sample.md` holds a random sample of 30 | The author fills in the four checks for all 30 questions |
| Error analysis of 100 wrong answers | `docs/review/error_sample.md` | The author fills in the "Author label" column |
| Relevance labels of the label audit | `results/runs/us_label_audit/` | Nobody plans to check these by hand. They stay "silver" |
| The verdicts and the run files | `docs/RESULTS.md`, `results/runs/` | A person reruns the summary scripts, as the README explains, and reads the run files |

## Why this matters

The project tests how AI models handle law, and AI models also built the project. A reader should know which parts a person checked. So the project labels AI-made answers "silver", keeps negative results, and lets anyone rebuild every number from the stored run files.
