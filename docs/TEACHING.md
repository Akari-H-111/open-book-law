# Teaching with Open Book

Five lesson ideas for students from about 15 to 22. Four of them need no programming. You need a browser and, if you like, a printer.

- **Website:** <https://akari-h-111.github.io/open-book-law/>
- **A 67-second trailer** to open a lesson: <https://www.youtube.com/watch?v=Z9x9vX72wcE>
- **Worksheet to print** (for lessons 1, 2, 3 and 5)**:** <https://akari-h-111.github.io/open-book-law/worksheet.html>
- **Answer key:** <https://akari-h-111.github.io/open-book-law/answer-key.html>
- **No internet in class?** Download the site bundle from the [Releases page](https://github.com/Akari-H-111/open-book-law/releases), unzip it and open `index.html`.

## Before you teach

- **This is not legal advice.** The project studies AI models. It does not teach the law of any state.
- **The questions about overruled decisions are AI-written.** No person has checked them yet. Treat them as study material about AI, not as statements of the law.
- **Overruling is a legal event.** It does not say which side was morally right. The examples were chosen to keep the lesson about method.
- **AI models did most of the work, and no person has checked the results yet.** This is itself a good topic for discussion. Lesson 5 uses it.
- **You may copy and adapt everything here.** The website and its text are under the MIT License.

## The project in four sentences

A research project gave small AI models old multiple-choice questions from the US bar exam, the exam that people take to become lawyers. Sometimes the model could also read a passage from a law library. Before the main runs, the project wrote down 11 claims and how big an effect each one needed. The website shows which claims held and which did not.

## Lesson 1: Predict, then check

Any subject · about 20 minutes · no programming · worksheet part A

**Goal.** Students learn that a careful study states its expectations before it sees the results, and that results can surprise.

1. Explain the question in one sentence: does a small AI model answer old bar exam questions better when it can read from a law library?
2. Open "The 11 tests" on the website and turn on classroom mode. Choose the group "Reading (H1 to H3)", and later "Old law (H7 to H10)". The search engine tests (H4 to H6) are hard to guess without a technical background. Read each claim aloud. Students vote, and you click the guess of the majority.
3. Press "Reveal the verdicts". The page counts how many guesses were right.
4. Discuss the surprises. Why could the library fail to help (H1), while the right passage helps a lot (H3)?

**Questions to ask.** What does "not supported" mean? Is it the same as "false"? Why did the project fix its tests before the main runs?

## Lesson 2: When the law changes

Civics or government · about 30 minutes · no programming · worksheet part C

**Goal.** Students learn what a precedent is, what it means to overrule one, and why a tool that only searches text cannot tell old law from new.

1. Explain precedent and overruling. One example that students know from online shopping is *South Dakota v. Wayfair* (2018), about sales tax on sales from other states.
2. Open "The old-law trap". Compare the bars "Nothing to read" and "Only the old decision".
3. Open "Try a question". Read one question together and let students choose. Then show the answers.
4. Discuss: a search tool matches words and meanings. What could go wrong if a person, or an AI model, relied on an old decision?

**Questions to ask.** How does a lawyer check that a case is still good law? Why did taking the overruled decisions out of the search not clearly help (H8)?

The government's "Table of Supreme Court Decisions Overruled by Subsequent Decisions" is part of the Constitution Annotated, which is free online.

## Lesson 3: Fair tests and honest statistics

Statistics · about 45 minutes · no programming · worksheet parts B and D

**Goal.** Students read an uncertainty range, and they see why a study needs rules that are fixed in advance.

1. On "The 11 tests", look at H1 and H3. For each, find the measured difference, the range and the size that the plan required.
2. Ask why the project compared the same questions under two conditions, and not two different groups of questions.
3. Ask what it means when the range includes zero.
4. Explain the correction for 11 tests: when you run 11 tests, one may look good by luck. The correction makes each test harder to pass, to allow for this.

**Questions to ask.** H8 moved in the hoped-for direction. Why is it still "not supported"? What would you need to find out more?

## Lesson 4: How a search engine works

Computer science · 45 to 90 minutes · for students with some programming

**Goal.** Students read a complete search engine and check its arithmetic by hand.

1. Open [`open_book_law/retrieval/bm25.py`](../open_book_law/retrieval/bm25.py). It is a search engine in about 130 lines of plain Python. The formula is at the top of the file.
2. Give students three short documents and one query. They compute the score of each document by hand.
3. Students run the code on the same documents and compare.
4. Discuss what word matching cannot see: meaning, and time.

Students who want more can follow [`docs/ENGINEERING.md`](ENGINEERING.md) and rebuild every result of the project.

## Lesson 5: Who checked what?

AI literacy or research ethics · about 30 minutes · no programming · worksheet part D

**Goal.** Students learn to ask which parts of a piece of work a person checked.

1. Read [`docs/AI_ASSISTANCE.md`](AI_ASSISTANCE.md) together. It lists each step, what AI models did and what the author did.
2. Students mark each step: done by AI, done by a person, or checked by a person.
3. Discuss: the record says that no person has checked the results yet. What can a reader still trust, and why? What should a reader check?

**Questions to ask.** Why does the project call labels made by AI "silver"? Why does it let anyone rebuild every number?

## Questions and corrections

If you find a mistake or have a question from class, open an issue in the repository. [`CONTRIBUTING.md`](../CONTRIBUTING.md) explains how.
