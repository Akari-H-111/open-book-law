# Literature notes: four papers behind Open Book

This page explains four papers that this project builds on. For each paper it says what the paper claims, how the authors evaluated it, where the claim might not hold, and how it bears on our work.

## How to read this page

- Numbers from a paper carry that paper's own section, table or figure number. They come from text extracted from the PDF, so check any number against the PDF before you quote it.
- Under "Where it might not hold" every point has one of three labels:
  - **(a) The authors say it.** The paper itself states the limit.
  - **(b) We measured it.** A committed file in this repository holds the result, and the file is named.
  - **(c) Reasoning, not tested.** This is our own argument. Where we only compared two numbers inside the paper, we write "checked in the text".
- No confirmatory result of ours exists yet. `docs/RESULTS.md` shows every hypothesis as pending. The only results of ours on this page are data audits and the BM25 reproduction.

---

## 1. Zheng et al. 2025, "A Reasoning-Focused Legal Retrieval Benchmark"

### What it claims

The authors release two benchmarks that pair legal retrieval with question answering.

- **Bar Exam QA** has 1,195 public questions from old bar exams and 1,815 private ones. Its passage pool holds 856,835 passages (Table 1).
- **Housing Statute QA** has 6,853 yes/no questions. Its pool holds 1,837,403 statutes (Table 1).

They make four claims.

1. A query and its gold passage share few words. The mean TF-IDF similarity is 0.07 for Bar Exam QA and 0.09 for Housing Statute QA. It is 0.26 to 0.27 for Natural Questions, HotpotQA, COLIEE and CLERC (Table 2).
2. Standard retrievers do poorly. On the combined Bar Exam QA set, Recall@10 is 5.03 for BM25 and 7.00 for E5-large-v2 (Table 3).
3. Adding a generated "legal reasoning" text to the query helps. On Bar Exam QA, Recall@10 rises by 6.28 ± 0.99 for BM25 and by 8.86 ± 1.16 for E5-large-v2 (Section 6).
4. For Llama-3-8B-Instruct, an oracle gold passage raises accuracy from 37.84% to 57.38%. Retrieved passages give smaller gains (Table 30).

### How it was evaluated

- **Gold labels, old exams.** A law student annotated one passage per question after using legal research tools (Section 3.1, Appendix A).
- **Gold labels, private questions.** The gold passage is the explanation in the answer key (Section 3.1).
- **Gold labels, housing.** The gold statutes are those cited by the LSC Eviction Laws Database. They are matched to Justia statutes from 2021 (Section 3.2).
- **Pools.** The Bar Exam pool holds the gold passages, case law from 2019 to 2021, and Cornell Wex entries (Section 3.1). Each housing question searches only the statutes of its own state, from 10,676 to 155,974 passages (Section 5.2).
- **Retrievers.** BM25 and four E5 models (Section 5.1). The metrics are Recall@k and MRR@10 (Tables 21 to 25).
- **Query expansion.** GPT-3.5 (`gpt-3.5-turbo-0613`) wrote the added text at temperature 1 (Section 5.3, footnote 7). The prompts are in Table 13.
- **Housing recall.** The upper bound counts a hit when one gold statute is found. The lower bound needs all of them (Section 5.2, Tables 24 and 25).
- **Answers.** Llama 3 picks the answer letter with the highest likelihood (Section 5.4). For "top k", the authors keep the passage that gives the most confident answer (Table 30 caption).
- **Intervals.** A percentile bootstrap with 1,000 resamples (Figure 3 caption).

### Where it might not hold

**(a) The authors say it.**

- The old questions are in the MMLU auxiliary training set, so models may have seen them. This is why the Barbri questions are private (Section 3.1).
- The questions are multiple choice, with short invented fact patterns. They may not match real practice (Section 3).
- Justia covers state law incompletely. When 2021 statutes were missing, the authors used the newest set (Section 3.2).
- One multiple-choice question became several yes/no questions. So some gold statutes do not bear on a given question, and the authors report an upper and a lower bound (Section 5.2).
- One model, GPT-3.5, wrote all the query expansions (Section 6).
- Rules are restated many times in case law, so one gold passage may be incomplete. This is the authors' reason for also reporting answer accuracy (Section 2.2).

**(b) We measured it.**

- *Gold passages are a separate source.* All 1,195 public gold passages have the pool source `mbe`. Only one gold text, for question `mbe_748`, also appears as a case-law passage. The pool holds 847,228 case-law, 6,714 `wex` and 2,893 `mbe` passages (`results/data_audit/us_audit.json`, keys `gold_passages` and `pool_by_source`). So a library made of real law, without the `mbe` passages, holds no labelled gold passage. Amendment 2 of `docs/PREREGISTRATION.md` draws this conclusion.
- *Old questions.* The source years run from 1972 to 1998 (`us_audit.json`, key `by_source_year`).
- *Near duplicates.* Within a split, 191 pairs of questions have a character 5-gram Jaccard of at least 0.8, and 187 of these pairs share the same prompt. Across splits there are 2 such pairs. Also, 41 gold passages serve 87 questions (`us_audit.json`, keys `duplicates_by_query` and `gold_passages`).
- *Housing question groups.* The 6,853 questions form 226 question groups (`us_audit.json`, key `housing_qa`). Section 7 of the preregistration says that groups repeat across states.
- *BM25 reproduces on the public questions.* On Historical MBE our BM25 gives Recall@10, @100 and @1000 of 0.67, 2.43 and 7.95, against 0.75, 2.26 and 8.79 in Table 22 (`docs/REPRODUCTION.md`, target R1a). All three are within the preregistered limits.
- *BM25 on housing only partly reproduces.* Our Recall@10 is 37.22 against 40.81 in Table 24 (`docs/REPRODUCTION.md`, target R2a). A rerun with stemming and stopword removal came within 0.2 points at all three depths (run `65cb3b18226d7b1c`, `results/runs/us_diagnostics/`). This suggests that the paper's BM25 used stemming. The paper does not say so, and we did not run Lucene.
- *Our first dense run differs.* The execution ledger records that our first `e5-small` run on `mbe` misses Table 22 by more than the preregistered limit at R@1000, and that the cause is not yet known (`docs/EXECUTION_LEDGER.md`, entry of 2026-11-04).
- *Unstated settings.* The paper does not state the query format for `mbe`, the BM25 parameters or the E5 truncation length. Our choices are in `docs/REPRODUCTION.md`.

**(c) Reasoning, not tested.**

Checked in the text:

1. The headline Bar Exam numbers mix two kinds of gold label. BM25 Recall@10 is 0.75 on Historical MBE (Table 22), 7.66 on Barbri (Table 23) and 5.03 combined (Table 21). Barbri is 1,815 of the 3,010 questions (Table 1). Nobody outside the authors can reproduce 5.03, because Barbri is private.
2. Section 6 says that expansion helps "across all models evaluated". That phrase is too broad. Figure 3 shows a change of −1.22 for E5-mistral on Bar Exam QA (Table 21: 15.25 to 14.03), and the sentence right after it reports no gain for E5-mistral-7b-instruct. We read this as an imprecise summary sentence and not as a hidden contradiction.
3. Section 4 gives the mean similarity of the two benchmarks as 0.07 and 0.08. Table 2 gives 0.07 and 0.09.
4. Section 3.1 says that annotation took about 6 months. Appendix A says roughly 9 months.
5. The E5-mistral baseline reaches Recall@10 of 11.15 on Natural Questions (Table 26) and 17.25 on HotpotQA (Table 27). E5-large-v2 reaches 68.68 and 56.18. We found no explanation. A different setup for that model is possible.
6. Table 30 does not say which Bar Exam questions it covers. Our preregistration treats its figures as including private questions (target R4 in `docs/REPRODUCTION.md`).
7. The authors checked "subsets" of the gold passages (Section 3.1). We found no agreement rate or error rate for the labels.

Untested:

8. Recall may understate retrieval quality. Each question has one gold passage in a pool of 856,835, and the authors say that rules recur in many passages (Section 2.2). So a Recall@10 below 1% on Historical MBE does not show that useful passages are missing. Our label audit (preregistration, section 9) will test this. It has not run.
9. The exam answers rest on law from 1972 to 1998, while the pool's case law is from 2019 to 2021 (Section 3.1). Where the law changed, a good retrieval could contradict the answer key. The error analysis has a label `law-changed` for this. We do not know how often it applies.
10. GPT-3.5 may have seen these questions in training. The authors raise this risk for models in general (Section 3.1). We found no discussion of it for the query expansions.
11. The bootstrap unit is not stated (Figure 3 caption). If it resamples questions and not question groups, the housing intervals could be too narrow.
12. Section 6 argues that a 10% retrieval gain can give at most a 2% answer gain "in theory". The argument scales the 20-point gold-passage ceiling, so it is not an empirical estimate of cause. The authors say that it fits the trends in Appendix I.

**What the paper got right.**

- It reports the Historical MBE subset on its own (Table 22). This is the only reason that a reproduction on public data is possible.
- It gives both an upper and a lower bound for housing (Tables 24 and 25).
- It publishes the expansion prompts (Tables 13 and 14).
- It pairs retrieval with answer accuracy. It also shows that gold passages help a larger model, from 52.22 to 68.80 for Llama-3-70B-Instruct (Table 31).
- It tests the low-overlap claim against four other datasets (Tables 17 to 20).
- It discloses the training-data risk.

### How it bears on this project

- Section 5 of the preregistration takes its reproduction targets from Tables 22, 24, 30 and 33. Target R4 is comparison only, because of the private questions.
- Our `rollout` retriever uses the prompt of Table 13. A local model writes the text and not GPT-3.5, so we cannot compare our gain with the paper's gain directly (preregistration, section 3.1).
- E5-mistral-7b is out of scope for our machine (preregistration, section 3.1).
- Finding (b) on gold passages is why H1 and H2 compare libraries by reader accuracy and not by gold recall.

---

## 2. Magesh et al. 2024, "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools"

### What it claims

The authors test the vendors' claims that retrieval makes legal AI tools "hallucination-free". They find that the claims are overstated. Figure 4 reports the share of responses that were accurate, incomplete and hallucinated:

| Tool | Accurate | Incomplete | Hallucinated |
|---|---:|---:|---:|
| Lexis+ AI | 65% | 18% | 17% |
| Westlaw AI-Assisted Research | 42% | 25% | 33% |
| Ask Practical Law AI | 20% | 63% | 17% |
| GPT-4 | 49% | 8% | 43% |

They also classify the causes of hallucination in the three products (Table 6). The shares among hallucinated responses are:

| Cause | Lexis+ AI | Westlaw | Practical Law |
|---|---:|---:|---:|
| Naive retrieval | 0.47 | 0.20 | 0.34 |
| Inapplicable authority | 0.38 | 0.23 | 0.34 |
| Reasoning error | 0.28 | 0.61 | 0.49 |
| Sycophancy | 0.06 | 0.00 | 0.03 |

"Inapplicable authority" includes a source for the wrong jurisdiction and a source that was overruled (Section 6.3).

### How it was evaluated

- **Queries.** There are 202, in four groups: 80 general research, 70 jurisdiction or time specific, 22 false premise and 30 factual recall (Table 2). Twenty come from LegalBench and 20 from a bar-prep book. The authors wrote or adapted the other 162 (Section 5.2).
- **Preregistration.** The queries were registered on 22 March 2024 (Section 5.3). One query had been run before registration, and some were reworded afterwards (footnote 16, Appendix B.1).
- **Running the tools.** The authors pasted each query into a new chat in each product (Appendix B). Lexis+ AI, Practical Law and GPT-4 ran from 22 March to 22 April 2024. Westlaw ran from 23 to 27 May 2024 (Section 5.3).
- **GPT-4.** It ran through the API (`gpt-4-turbo-2024-04-09`) with a system prompt that asks for case citations and little hedging, and with no retrieval (Section 5.3).
- **Definitions.** A response is hallucinated when it is incorrect, or when it cites a source that does not support its claim (Sections 4.1 to 4.4). "Incorrect" means that the response makes any false statement, whether or not it matters (Appendix C.2).
- **Labelling.** One of three labelers coded each response. A fourth labeler coded 48 of them again, stratified by tool and task. Cohen's kappa was 0.77 and raw agreement 85.4% (Section 5.4).

### Where it might not hold

**(a) The authors say it.**

- Three products only (Section 7). Lexis released a newer version after the tests (Section 5.1, footnote 13).
- The results are a snapshot, and the products changed during the study (Section 7).
- The sample of 202 queries is small, and it is not "an unbiased estimate" of real use (Section 7).
- Groundedness is a matter of degree. A citation to an overruled case is coded as misgrounded, although it may still help a researcher (Section 7).
- Westlaw gives the longest answers, with 350 words on average against 219 and 175 for the others. Longer answers contain more claims that can be false (Section 6.1).
- The lists of retrieved documents were not copied consistently (Appendix B). The authors cannot see which text reached the model (Section 6.3).

**(b) We measured it.** See "Partial check on the public half" below.

**(c) Reasoning, not tested.**

- The second labeler coded 48 of about 800 responses. The paper does not say whether labelers knew which tool wrote a response. The chat windows look different, so blind coding seems unlikely.
- The Westlaw queries ran at least a month after the other queries (Section 5.3). Differences between tools may partly be differences in time.
- GPT-4 is told to cite case law and not to hedge (Section 5.3). Its answers contain more checkable claims than a cautious answer would. The comparison "tools hallucinate less than GPT-4" mixes retrieval with prompting.
- Appendix C.2 counts any false statement, material or not. The rate therefore depends on answer length, as the authors note for Westlaw.

### Partial check on the public half

We checked the paper's Figure 4 against the public file. This check is exploratory. It is not a preregistered test.

**What we ran.** The file is `dataset.csv` from `reglab/legal_rag_hallucinations`. It has 400 rows, 100 queries and 4 tools. The script is `tools/magesh_check.py`. It uses only the standard library, and we ran it with `~/venvs/open-book-law/bin/python -I tools/magesh_check.py`. It writes `results/data_audit/magesh_check.json`, which also records the SHA-256 hash of the data file. It does four things:

1. It counts the public queries in each category and compares the counts with Appendix A of the paper.
2. It counts the responses of each tool by the `Label` column. It adds a 95% Wilson interval for each share.
3. It rebuilds the label from the `Correctness` and `Groundedness` columns with the rules of Sections 4.1 to 4.4, and it counts rows where the two disagree.
4. It reweights the shares so that each category has the paper's number of queries.

In step 3 the script treats "Partially Correct" as correct, and it treats "Irrelevant / Unhelpful" as a refusal. The paper's rules do not cover these two values, so this is our choice.

**Result.** All numbers below come from `results/data_audit/magesh_check.json`. Each cell shows the public count, which is also its percentage because each tool has 100 responses. The 95% interval follows in brackets, and the paper's figure follows after the semicolon.

| Tool | Accurate | Incomplete | Hallucinated |
|---|---|---|---|
| Lexis+ AI | 63 [53, 72]; paper 65 | 18 [12, 27]; paper 18 | 19 [13, 28]; paper 17 |
| Westlaw | 42 [33, 52]; paper 42 | 20 [13, 29]; paper 25 | 38 [29, 48]; paper 33 |
| Practical Law | 21 [14, 30]; paper 20 | 63 [53, 72]; paper 63 | 16 [10, 24]; paper 17 |
| GPT-4 | 50 [40, 60]; paper 49 | 11 [6, 19]; paper 8 | 39 [30, 49]; paper 43 |

**What it shows.**

1. Every paper figure lies inside our interval. This is weak support, because the public half is part of the paper's 202 queries. The two samples overlap, so close agreement is expected.
2. The gap between GPT-4 and Westlaw is 1 point on the public half (39 against 38). In the paper it is 10 points (43 against 33). If the paper's rounded figures are right, the unreleased half has about 47 to 48% for GPT-4 and about 28% for Westlaw. This is arithmetic on rounded numbers. With 100 responses per tool, chance could also explain the difference. We cannot tell which.
3. The public file is a stratified half, but not an even half. It has exactly half of each category in Appendix A, except Circuit Splits (9 of 10 queries) and Local Rules (5 of 20).
4. Reweighting to the paper's category counts moves no share by more than 2.1 points (key `reweighted_to_paper_categories`). So the category mix does not explain the differences above.
5. In 4 of 400 rows, the `Label` is "Hallucination" although `Correctness` is "Partially Correct" and `Groundedness` is "Ungrounded". The rules of Section 4.4, as we applied them, would give "Incomplete" (key `label_rule_mismatches`). Appendix C.3 says that a response that is both ungrounded and misgrounded counts as misgrounded, and footnote 18 mentions a second validation of every hallucination. Either could explain the four rows. We did not test this.

The intervals treat each response as independent. The four tools answered the same queries, so a paired test would be tighter. We did not run one.

### How it bears on this project

- The Casey example in Figure 2 is the failure that our good-law test targets. Lexis+ AI described Casey as the governing standard, although Dobbs overruled it. Our audit of the `mbe` pool finds 72 passages that cite Casey (`docs/GOOD_LAW.md`, from `results/data_audit/goodlaw_audit.json`). A citation shows exposure and not reliance.
- Table 6 puts "inapplicable authority" at 0.23 to 0.38 of hallucinated responses. This is the group that the `citator` and `note` conditions of section 8.3 in the preregistration try to reduce.
- The authors coded by hand and checked agreement. Our label audit uses AI judges, so we call its labels silver and report agreement between the two judges (preregistration, section 9).
- The public file is a literature check only (preregistration, section 2).

---

## 3. Dahl et al. 2024, "Large Legal Fictions: Profiling Legal Hallucinations in Large Language Models"

### What it claims

The authors ask whether language models know American case law. They claim that:

1. Models give wrong answers to direct questions about federal cases between 58% (GPT-4) and 88% (Llama 2) of the time. The figure pools the nine tasks that have a reference answer (Section 1, Figure 1).
2. The error rate rises as a case sits lower in the court hierarchy, is less prominent, or is very old or very new (Figures 3, 5 and 6).
3. Models accept false premises. For a question that wrongly assumes a Supreme Court case was overruled, the error rates are 0.531 for GPT-4, 0.821 for GPT-3.5 and 1.000 for PaLM 2. Llama 2 scores 0.027 (Table 6).
4. Models are overconfident. The pooled expected calibration error is 0.057 for PaLM 2, 0.099 for GPT-3.5, 0.190 for GPT-4 and 0.421 for Llama 2 (Section 5.3).
5. Models do poorly on the year a case was overruled. With three-shot prompts, the error rate is 0.725 for GPT-4 on 279 cases (Table 4).

### How it was evaluated

- **Sample.** The authors drew 5,000 cases from each of three levels: the Supreme Court, the courts of appeals and the district courts. They sampled by year, by circuit and year, or by state and year (Section 4.1).
- **Fourteen tasks.** They range from "is this a real case?" to "what is the central holding?" (Table 2).
- **Reference-based tasks.** Nine tasks have an answer in case metadata. The authors reason that models did not train on metadata kept apart from the opinion text. A wrong answer counts as a hallucination. A refusal does not (Section 4.2).
- **Reference-free tasks.** For five tasks there is no answer key. The model answers twice at temperature 1, and GPT-4 judges whether the two answers contradict each other. The rate is therefore a lower bound (Section 4.3).
- **Checking the judge.** On 100 queries, two humans and GPT-4 agreed with kappa of 0.87, 0.77 and 0.79 (Appendix C, Table 2).
- **Models.** GPT-4 (`gpt-4-1106-preview`), GPT-3.5, PaLM 2 and Llama-2-13b-chat, each with zero-shot and three-shot prompts, in more than 800,000 queries (Section 4.4).
- **Retrieval.** None was used. The models answered closed book.

### Where it might not hold

**(a) The authors say it.**

- Rates for the reference-free tasks are lower bounds (Section 4.3). The Supreme Court "subsequent history" rate is probably too low, because GPT-4 repeats one wrong answer that never contradicts itself (Section 5.1.1).
- The Existence task is inflated by a habit of answering "yes". Appendix E.1 shows that GPT-3.5 and PaLM 2 also accept fake cases.
- The reporter in a citation reveals the court, so the Supreme Court Court task is easy (Section 3.1).
- Llama 2 scores well on false premises because it often denies that the case exists (Section 5.2).
- Retrieval may fix or hide some of these errors. The authors add that a retriever must tell outdated and out-of-jurisdiction sources from binding law (Sections 4.3 and 6).

**(b) We measured it.**

- Dahl et al. score the overruling year by exact match (Section 3.2). Their list comes from a Library of Congress source (Appendix Table 1). In our parse of the Constitution Annotated table, the year in the table differs from the decision date in the Caselaw Access Project for 34 entries. Most are old decisions that the Project dates by court term (`docs/GOOD_LAW.md`, from `results/data_audit/goodlaw_audit.json`, key `table_year_differs_from_case_date`). We do not know whether their list has the same problem.

**(c) Reasoning, not tested.**

Checked in the text:

1. The 58% to 88% figures pool tasks that are not alike. On Disposition, a two-way choice, the three-shot error rate is 0.452 to 0.502 for all four models at the Supreme Court level, which is the rate of a coin flip (Table 4). On the Supreme Court Court task it is 0.000 (Table 3). We did not find how the paper weights tasks in the pool.
2. Section 5.1 says that zero-shot and few-shot prompting differ little. Some cells differ a lot. For GPT-4 on district-court citations the rate falls from 0.610 to 0.270 (Table 3). For Llama 2 on Supreme Court existence it rises from 0.303 to 1.000 (Table 3). For GPT-4 on Supreme Court quotations it rises from 0.312 to 0.854 (Table 4).
3. Zero-shot quotation errors for GPT-4 and GPT-3.5 are 0.001 and 0.000 at the appeals and district levels. Three-shot errors are 0.637 to 1.000 (Table 4). The scoring accepts "any fuzzy string of characters" from the majority opinion (Section 3.2).

Untested:

4. Item 3 may mean that a short generic quotation can pass the check. We have not tried this.
5. GPT-4 is both a model under test and the judge of contradictions (Section 4.3), so the rates may depend on how GPT-4 itself judges. The authors reduce this risk with two human coders on 100 queries, who agreed with GPT-4 at kappa of 0.87 and 0.77 (Appendix C).
6. The five reference-free tasks use 100 cases per court level (Table 5). The standard errors are 0.02 to 0.05.
7. The models date from 2023 and ran without retrieval. The paper cannot tell us how current models, or models with a library, would score.
8. The "agree or disagree" labels for doctrinal agreement come from Shepard's treatment codes that the authors coarsened (Section 3.3). The paper gives no estimate of label noise.

**What the paper got right.**

- It builds its answer key from metadata that is unlikely to sit in training text (Section 4.2).
- It samples by strata and reports standard errors (Tables 3 to 7).
- It tests fake cases to expose the "yes" habit (Appendix E.1).
- It states which rates are lower bounds.
- It counts refusals as non-hallucinations and says so (Section 4.2).

### How it bears on this project

- Our good-law test is the open-book counterpart of Table 4. Dahl et al. ask a closed-book model for the overruling year. We hand a model the old opinion, the new opinion or retrieved passages, and we ask which rule is current.
- The false overruling premise (Table 6) and our `old-only` condition both test whether a model accepts what its input says about overruling. In Table 6 the input is a wrong claim. In `old-only` it is an overruled passage.
- Their list holds 279 overruled decisions up to 2022 (Table 4, footnote a). Ours holds 283 distinct overruled decisions from a table that is current to June 2026 (`docs/GOOD_LAW.md`). The paper names its source as the Congress.gov "Table of Supreme Court Decisions Overruled by Subsequent Decisions", which is the Constitution Annotated table. It does not describe how it parsed the rows. The gap between 279 and 283 may come from later decisions and from how rows are parsed. We have not checked.
- Section 6 says that a retriever "must have some mechanism" to tell overruled sources from binding law. Our authority graph and the `citator` condition are one such mechanism.

---

## 4. Weller et al. 2025, "On the Theoretical Limitations of Embedding-Based Retrieval"

### What it claims

The authors argue that a single vector per text cannot return every possible set of top results, whatever the training data.

1. **A bound.** Suppose that every set of k documents among n must be returnable as the top k, with a gap of 2γ between the scores of the k documents and the scores of all others. Then the embedding dimension d must satisfy d ≥ log C(n, k) / log(1 + 1/γ) (Theorem 1, Section 3). With γ = 0.1 and n = 10⁶, the bound is 12 for k = 2, 52 for k = 10 and 425 for k = 100 (Table 1).
2. **A best-case test.** With vectors that are optimised directly on the test relevance matrix, there is a largest corpus size n for each d. A cubic fit through these points predicts 500 thousand documents at d = 512, 4 million at d = 1,024 and 250 million at d = 4,096 (Section 4, Figure 2).
3. **A benchmark called LIMIT.** It has 50,000 documents and 1,000 queries of the form "who likes X?". Each query has two relevant documents. The tested single-vector dense models score below 20% Recall@100. The multi-vector model gte-ModernColBERT reaches 54.8, and BM25 reaches 93.6 (Section 5.2, Figure 3 and Table 5). On a version with 46 documents, they fail even at Recall@20 (Figure 4). BM25 is close to perfect.

### How it was evaluated

- **Free embeddings.** The authors optimise random vectors with Adam and the InfoNCE loss, using full batches, and stop when the loss stops improving (Section 4). They increase n until the task is no longer solved at 100%. The fit uses k = 2 (Section 4, Table 6).
- **LIMIT.** They test GritLM, Qwen3 Embedding, Promptriever, Gemini Embedding, Snowflake Arctic, E5-Mistral, BM25 and gte-ModernColBERT. They cut embeddings down to smaller sizes for some models (Section 5.2).
- **Domain shift.** They fine-tune one model on a training split with different attributes, and on the test split itself (Figure 5, Table 3).
- **Synonyms.** They rewrite the small version with synonyms to remove word overlap (Figure 6).
- **A reranker.** Gemini-2.5-Pro solves all 1,000 queries of the small version in one pass (Section 5.3).

### Where it might not hold

**(a) The authors say it.**

- The bound is "an extreme lower bound". Real models must also learn by gradient descent and handle natural language (Section 3).
- The theory covers single-vector models only. It gives no result for multi-vector models, or for a user who accepts some mistakes (Limitations).
- The authors cannot say in advance which combinations a model will fail on. Some tasks may be solved perfectly (Limitations).
- Free embeddings can fit the 46-document version of LIMIT in 12 dimensions, yet no tested dense or multi-vector model solves it perfectly, while BM25 reaches 100.0 at Recall@20. The authors read this as a sign of "other architectural weaknesses" (Section 5.2). So the dimension bound does not explain the failures on that version.
- A sign-rank argument in Appendix D.3 gives at most 2k dimensions for any relevance pattern. It needs infinite precision, so it is not usable in practice.
- A sigmoid loss solves the free-embedding task in fewer dimensions. The authors say that this leaves open questions about learnability (Appendix C).
- Models that were not trained for truncation do worse at small sizes, so part of the trend with dimension in Figure 3 can come from truncation (Section 5.2).
- On the synonym version, BM25 drops by more than 89% and falls below most neural models (Section 5.2, Figure 6). A token-level TF-IDF model scores 100% because it "reverse engineers" the construction (Section 5.2, footnote 8). So the lexical advantage on LIMIT comes partly from how the data was built.
- The authors "could not prove" that their relevance matrix is the hardest one (Section 5.2).

**(b) We measured it.** Nothing yet. Our dense runs are unfinished. `docs/REPRODUCTION.md` shows the E5 targets as pending.

**(c) Reasoning, not tested.**

1. The bound asks for every k-subset to be returnable. Recall@k asks only that one gold passage lies within the top k. That is a much weaker requirement.
2. For one gold passage (k = 1) in our pool of 856,835 passages, the formula with γ = 0.1 gives log(856,835) / log(11), which is about 5.7. So at least 6 dimensions are needed. For k = 10 at n = 10⁶ the paper's own Table 1 gives 52. The paper says that most embeddings used for web-scale search have fewer than 1,000 dimensions, and that the largest used in research have about 4,096 (Section 3.0.1). So the bound alone does not predict trouble at our sizes.
3. The fit in Figure 2 uses dimensions up to 45 (Table 6, last row: n = 626). The prediction for d = 4,096 is about 90 times beyond that range. The figures for d = 512 to 4,096 are therefore model-based projections and not measured capacities. The authors call them an extrapolation of a best case (Section 4).
4. LIMIT is synthetic. Every document is a short list of random likes, and a query asks for one item. Its dense pattern of relevant documents limits how far the results carry over to legal search. The authors also find no obvious link between a model's score on LIMIT and its score on BEIR (Appendix D.4, Figure 7). We read this as a limit on scope, and not as a missing control.
5. Our agent may issue several searches per question (preregistration, Amendment 1, part D). This may avoid the single-vector limit, because the agent does not need one vector to return an exact set. This is a hope, not a result.

**What the paper got right.**

- The proof is short and can be read in a few minutes. We followed it. We did not check it independently.
- The authors label the bound as extreme and say what it does not cover.
- They run controls: train against test (Figure 5), synonyms (Figure 6) and a reranker (Section 5.3).
- They report the weakness of BM25 next to its strength.

### How it bears on this project

- The preregistered `hybrid` retriever fuses `bm25` and the best dense model with reciprocal rank fusion (section 3.1). Weller et al. name hybrid sparse and dense retrieval as future work (Section 5.3), and they do not test it.
- Section 5.2 shows that exact word matching can beat embeddings when the words match, and that it fails when they do not. Our BM25 result on housing shows how much the tokenizer matters: stemming and stopword removal alone closed a gap of about 3 points to the paper (`docs/REPRODUCTION.md`).
- Our plan has no reranker (preregistration, section 3.1). The paper's reranker result is a reason to treat that as a limit of our design.
- Hypothesis H6 fine-tunes `e5-small` on held-out states. Table 3 of the paper shows that fine-tuning on a training split with different attributes barely helped. That result is for a different task, so it tells us only to expect modest gains.

---

## 5. Open-source work that this project uses

All facts in this section come from the repository documents named in each item.

**Caselaw Access Project.** It supplies opinion text and citation metadata for the U.S. Reports volumes. The opinions are public domain. We keep the text in the data folder and never in git (`docs/GOOD_LAW.md`, sources table).

- *Size.* We read 330,011 cases, of which 329,995 come from the Project and 16 from Cornell. We split them into 1,007,513 passages. 11,263 cases have no opinion text (`docs/GOOD_LAW.md`).
- *Authority graph.* The graph holds 330,012 cases and 564,602 citation links taken from the Project's metadata (`docs/GOOD_LAW.md`).
- *Citation metadata is not the truth.* We scored our citation extractor against the Project's `cites_to` field on 500 random opinions. Precision was 0.986 and recall 1.000. We changed the reference after a first run that gave 0.971 and 0.988, so the second score comes from a choice made after seeing the first. In a read of 20 disagreements, the text printed the citation and the Project had missed it in 17 cases. An AI model made those verdicts (`docs/GOOD_LAW.md`).
- *Gaps.* For one pair, the Project holds two full opinions with the same name on the same day. For another, it has an entry with no opinion text. It dates many old cases by court term, which causes some of the 34 year differences noted above. It stops before the newest decisions (`docs/GOOD_LAW.md`).

**Constitution Annotated, "Table of Supreme Court Decisions Overruled by Subsequent Decisions".** It is a U.S. government work and may be committed (`docs/PREREGISTRATION.md`, section 2).

- *Size.* We parsed 237 rows into 293 pairs and 283 distinct overruled decisions. The preregistration's first count of 271 came from counting rows and semicolons, and Amendment 3 corrects it (`docs/GOOD_LAW.md`).
- *Why it matters.* The table, and not an AI model, decides what counts as overruled (`docs/GOOD_LAW.md`).
- *Limits.* It lists only decisions that the Supreme Court itself overruled. It marks 36 pairs as overruled "in part" without saying which part. For 100 overruled decisions it gives no citation (`docs/GOOD_LAW.md`).

**Public datasets.** We use `reglab/barexam_qa`, `reglab/housing_qa` and `reglab/legal_rag_hallucinations`. We keep no question text, passage text or opinion text in git (`docs/PREREGISTRATION.md`, section 2).
