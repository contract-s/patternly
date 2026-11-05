# Patternly: Project Plan

_Source: "Patternly Project Plan.pdf" (Nov 5, 2026). Transcribed to Markdown so it lives with the code._

## Goal

Patternly teaches algorithm patterns by making you **explain first**. Each day you open the app and do one lesson, about 10 minutes long. The lesson gives you a real-world scenario, such as "Find the longest stretch of minutes in a delivery app's log with at most three failed payments." You describe your solution in plain words, with no code. An AI tutor compares your explanation to a hidden checklist of key ideas, tells you which ones you hit and which you missed, and gives a hint without giving away the answer. Once you've covered the key ideas, it reveals the pattern's name (here, sliding window) with a short explanation.

**The Duolingo part:** one lesson per day, picked for you, and a streak counts the days in a row you finish it. A reminder email goes out if you haven't done today's lesson.

**Where the posting skills go:**

- **RAG:** the tutor retrieves your own pattern notes and your past mistakes with hybrid search, instead of relying on the model's memory.
- **Agent with tools:** the tutor can get the rubric, search notes, read your history, and record the attempt.
- **Evals and guardrails:** a set of labeled learner answers measures how often the tutor wrongly passes someone, and a leak checker keeps hints from giving away the answer.
- **Backend, frontend, and delivery:** FastAPI, Postgres, React with TypeScript, scheduled jobs for reminders, Docker, CI, and AWS.

**Why this idea:** you'd use it to study, it's easy to demo, and the hard part is measurable: how accurate the AI's critique is. One honest risk: apps that teach LeetCode patterns already exist. What sets this apart is explain-first teaching and a measured evaluation of the tutor. **Write the scenarios yourself and don't copy problem text from other sites.**

## Daily lesson loop

1. **Pick.** A daily planner chooses today's scenario: a new pattern while you move through the curriculum, or a review scenario when a pattern is overdue or you missed it recently.
2. **Do.** You write your explanation, read the tutor's critique, and revise. Cap it at a few hint rounds (~10 minutes).
3. **Reveal.** When you've covered the rubric, show the pattern's name, a short explanation, and its time cost.
4. **Schedule.** The spaced-repetition scheduler sets when this pattern returns.
5. **Streak.** Finishing a lesson counts for today. Count days in the learner's own time zone, and decide whether a missed day resets the streak or uses a streak freeze.
6. **Remind.** A scheduled job (cron or Celery beat) emails a reminder via a service such as Amazon SES if today's lesson isn't done.

**Content planning:** the 10 scenarios from weekend 1 cover the first 10 days. Growing to 10 patterns × 3 scenarios gives 30 days before anything repeats, so write new scenarios as you go.

## Architecture and stack

A learner's answer goes to a FastAPI service. A tutor agent retrieves the rubric and your notes, grades the answer, and returns a hint that a checker has cleared. Until you earn the reveal, each hint sends you back to rewrite your answer; the tutor reads the rubric and your past mistakes from the store.

| Component | Tool | Covers in postings |
|---|---|---|
| Content | ~10 patterns × 3 scenarios, written by you. Each scenario has a hidden rubric of key ideas, a reference solution, the pattern name, and its time cost | Data modeling, domain content |
| Storage | Postgres with pgvector: patterns, scenarios, rubrics, attempts, learning history | SQL, embeddings |
| Retrieval | Hybrid keyword + vector search, reranked, over your pattern notes and past mistakes | RAG, hybrid search, reranking |
| Tutor agent | Tool-calling loop with four tools: get rubric, search notes, read history, record attempt. LangGraph optional | Tool use, orchestration, LangGraph |
| Guardrails | Leak checker that blocks the pattern name and solution steps until earned; structured output validated with Pydantic | Guardrails, structured output |
| Evals | 60+ hand-labeled learner answers; rubric-level accuracy, false-pass rate, leak rate; CI gate | Evals, LLM-as-judge |
| Learning engine | Spaced-repetition scheduler (Leitner box or SM-2-style), plus progress per pattern | Backend logic, algorithms |
| Daily planner | Picks one scenario per day: a new pattern, or a review chosen by the scheduler | Backend logic, scheduling |
| Streaks and reminders | Streak counted in learner's time zone; scheduled job (cron / Celery beat) emails a reminder via e.g. Amazon SES | Scheduled jobs, task queues, cloud services |
| API | FastAPI with JWT login, async endpoints, pytest tests | REST APIs, authentication, testing |
| Web app | React + TypeScript: today's lesson card, answer box, critique panel, pattern reveal, streak, review queue | React, TypeScript |
| Tracing | OpenTelemetry traces with latency, tokens, and cost per attempt | Observability, cost tracking |
| Delivery | Docker Compose, GitHub Actions eval gate, one AWS instance | Docker, CI/CD, AWS |

## Build plan

Six weekends, each ending with something that runs. **Do not start a weekend until the previous one's check passes.**

### Weekend 1: content and test answers
- Write 10 scenarios across 5 patterns. For each, write the hidden rubric of key ideas and a reference solution.
- Write 6 learner answers per scenario ranging from fully correct to wrong: correct, partly correct, missing a key idea, wrong pattern, vague, and correct-but-different valid approach.
- Label which rubric items each answer hits or misses. Set aside 20 answers as a **sealed test set**.
- **Done when** all 60 answers have labels.

### Weekend 2: baseline tutor
- Simplest version: one prompt containing the scenario, the rubric, and the learner's answer, returning structured JSON with hits, misses, and a hint.
- **Done when** you have baseline rubric-item accuracy and false-pass rate on the non-sealed answers.

### Weekend 3: retrieval and pattern notes
- Write short notes on each pattern, store them in pgvector with full-text search, and add a reranker.
- Ground the tutor in the retrieved notes and measure the change against the baseline.
- **Done when** you can state whether retrieval improved grading or hints.

### Weekend 4: agent, guardrails, hint ladder
- Write the tutor loop yourself with the four tools. Add three hint levels, from a nudge to a stronger clue.
- Add the leak checker and Pydantic validation, and plant leaky hints to test the checker.
- **Done when** planted leaks are caught and the leak rate is measured.

### Weekend 5: learning engine and service
- Store attempts and history in Postgres; add the spaced-repetition scheduler, daily planner, and streak tracking.
- FastAPI endpoints with JWT login and pytest tests.
- **Done when** a full lesson works through the API, finishing it extends your streak, and a missed pattern comes back in the review queue.

### Weekend 6: web app, CI gate, deployment, testers
- React + TypeScript app, Docker Compose, tracing, and a GitHub Actions workflow that fails if accuracy drops.
- Deploy to one AWS instance; have 3–5 classmates use it daily for a week with reminder emails on. Record hints needed and daily lesson completion.
- Write the README with a results table and a plain list of limits.
- **Done when** every metric below has a measured number.

## Metrics to measure

Record these in the README as you measure. Only use numbers you actually measured.

| Metric | How to measure it | Result |
|---|---|---|
| Rubric-item accuracy | Share of rubric items where the tutor's hit/miss call matches your label, on the sealed test answers | TBD |
| False-pass rate | Answers the tutor calls correct that you labeled incorrect. **Most important number** — a false pass teaches a wrong idea | TBD |
| Alternative-solution recognition | Valid but different approaches (e.g. hash map instead of sliding window) that the tutor accepts | TBD |
| Hint leak rate | Hints containing the pattern name or solution steps before the learner earned them | TBD |
| Retrieval hit rate | How often the correct pattern note is in the top 3, vector-only vs. hybrid + reranker | TBD |
| Hints to solve | Average hints needed per scenario by the 3–5 testers | TBD |
| Daily completion | Share of tester-days with a finished lesson over the 7-day trial | TBD |
| Longest streak | Median longest streak among testers during the trial | TBD |
| Latency and cost | p95 response time and model cost per attempt, from traces | TBD |

LLM outputs vary between runs, so run the test answers several times and report the spread. With a small answer set, state the sample size next to each number.

## Resume bullets

Fill each bracket with a measured number. If you can't fill one, cut that claim instead of rounding up.

**Patternly** | Python, FastAPI, PostgreSQL, pgvector, React, TypeScript, Docker, AWS

- Built an AI tutor that grades free-text explanations of algorithm scenarios against hidden rubrics, using a tool-using agent and hybrid retrieval over [N] pattern notes; matched my labels on [X]% of [Y] rubric items with a [Z]% false-pass rate.
- Implemented guardrails (a leak checker and Pydantic-validated output) that kept [A]% of hints free of the answer.
- Built a daily-lesson engine with a spaced-repetition scheduler, streak tracking in the learner's time zone, and scheduled email reminders; [T] testers finished a lesson on [D]% of days over a 7-day trial.
- Developed a FastAPI and React/TypeScript app with JWT login and a GitHub Actions eval gate, deployed on AWS; testers needed [H] hints per scenario on average, at p95 latency of [L] s and [M] cents per attempt.

Add these to Skills only after using them in the project: FastAPI, PostgreSQL, pgvector, Pydantic, React, TypeScript, Docker, GitHub Actions, AWS, OpenTelemetry, pytest.

## Interview prep, limits, and scope cuts

Be able to explain without notes:

- Why the tutor grades against a hidden rubric of key ideas instead of asking the model "is this right?"
- Why a false pass is worse than a false fail, and what a false fail costs (e.g. rejecting a valid alternative approach).
- How retrieval grounds the tutor, and what changed in the numbers when it was added.
- How the leak checker works, and what it can miss (e.g. a hint that gives away the answer without naming the pattern).
- How spaced repetition decides when a pattern returns.

**Limits to state in the README:** labels are one person's judgment, 60 answers is a small set, and results vary between runs.

**If time runs short, cut in this order:**
1. Drop the AWS deployment; keep Docker Compose.
2. Drop OpenTelemetry; log latency and cost to Postgres instead.
3. Drop email reminders; show the streak in-app only.
4. Replace the spaced-repetition scheduler with a simple list of missed patterns.
5. **Keep** the labeled answers, the baseline-vs-retrieval comparison, the false-pass rate, and the leak checker. Without them the project has no numbers.

## Optional extensions (pick one)

- **Code mode.** After earning the reveal, the learner submits code. It runs in a sandboxed Docker container (no network, time and memory limits) against your test cases; the tutor explains failures.
- **AI concepts track.** Scenarios whose answer is an AI pattern, e.g. "A support bot quotes the wrong refund policy," where the reveal is retrieval failure vs. generation failure. Teaches RAG, chunking, and evals inside the app.

Resume line for either: added [code mode / an AI concepts track] with [N] scenarios; [X]% of [Y] test cases passed in the sandbox, or [X]% tutor accuracy on the new track.
