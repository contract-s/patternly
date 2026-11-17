# Patternly

Learn algorithm patterns by explaining first. One lesson a day: read a real-world scenario, describe your solution in plain words, and an AI tutor tells you which key ideas you hit, which you missed, and gives a hint without giving away the answer. Cover the key ideas and it reveals the pattern.

**Try it live: [d1gzfqnjgnrior.cloudfront.net](https://d1gzfqnjgnrior.cloudfront.net)**. Click "Try it as a guest"
to do a lesson without signing up. To keep the demo's cost fixed, the tutor has a daily budget; once it's used up,
attempts are graded by simple word matching until the next day, and the app says so (see
[Demo limits](#demo-limits)).

> Status: all six phases done: grading evals, retrieval, the tool-using tutor with a leak checker, the learning engine and API, the web app, tracing, CI with an eval gate, and an AWS deploy with email reminders. The planned tester trial was dropped (see Limits). 15 patterns, 30 scenarios, and 60 labeled learner answers (20 sealed for final metrics). See [docs/project-plan.md](docs/project-plan.md).

## Results

| Metric | Result | Sample size |
|---|---|---|
| Rubric-item accuracy | 94.1% mean over 3 runs (92.9%, 95.5%, 93.8%) | 112 rubric items per run (20 sealed answers) |
| False-pass rate | 0.0% (0 of 13 in every run) | 13 sealed answers labeled fail |
| Alternative-solution recognition | 100% (3 of 3 in every run) | 3 sealed alternative answers |
| Hint leak rate | 0 of 117 delivered hints flagged; 2 of 117 first drafts rejected and rewritten | 39 hints per run, 3 runs |
| Retrieval hit rate (vector vs. hybrid + rerank) | Hit@3 77.5% vector, 82.5% hybrid, 82.5% hybrid + rerank | 40 development answers |
| p95 latency / cost per attempt | Eval runs: p95 14.7–15.6 s, $0.017–0.020 per attempt. Live site: p95 19.0 s, $0.026 mean ($0.035 max) per attempt | Eval: 46 attempts per run. Live: 7 attempts on 2026-11-17, mostly test traffic |

The first four rows are from the tutor loop (`claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`)
on the 20 sealed answers, run three times on 2026-11-16 after development was finished. False-fail rate was 0.0%
(0 of 7) and no verdict changed on resubmission in any run. Runs:
[1](evals/runs/2026-11-16T170030_sealed-final-run1/summary.md),
[2](evals/runs/2026-11-16T170151_sealed-final-run2/summary.md),
[3](evals/runs/2026-11-16T170310_sealed-final-run3/summary.md). Model cost for the three runs: $2.53 for the tutor
plus $0.04 for the leak judge.

Two caveats. The leak rate is measured by the same checker (pattern name, copied solution, model judge) that
screens hints before delivery, so it shows the screen works, not that a human would find no leaks; on its own the
judge also flagged 18 of 90 hand-written hints, so it errs toward flagging. Retrieval was only measured on the
development answers. The live numbers come from the server's traces (`patternly trace-report --since 2026-11-17`):
7 graded attempts, mostly test submissions, so with a sample that small the p95 is simply the slowest attempt. Live
attempts were slower and cost more than in the eval runs; the cause wasn't measured.

These sealed runs graded with the rule from before 2026-11-17, when minor rubric items were added (see "Minor
rubric items" below). The sealed set hasn't been rerun with the new rule. Development numbers are below.

## Development results

Baseline tutor (one prompt with the scenario, rubric, and answer; structured output), `claude-opus-5-5` at effort
`medium`, on the 40 development answers × 5 runs (200 calls). Run: [`evals/runs/2026-11-08T172423_baseline-v2`](evals/runs/2026-11-08T172423_baseline-v2/summary.md).

| Metric | Baseline (dev) | Sample size per run |
|---|---|---|
| Rubric-item accuracy | 97.3% (range 96.4–97.8%) | 224 rubric items |
| False-pass rate | 0.0% (0 of 27 in every run) | 27 answers labeled fail |
| False-fail rate | 0.0% | 13 answers labeled pass |
| Alternative-solution acceptance | 100% | 7 alternative answers |
| Hints naming the pattern | 0.0% | 27 hints |
| Verdict changes between runs | 0 of 40 answers | |
| Cost / latency | $0.017 per call; p50 4.6 s, p95 8.6 s | |

These are optimistic: the development answers were relabeled once after the first baseline run (see Limits), and
the remaining rubric disagreements cluster on whether a stated cost counts when the described method doesn't
achieve it. The sealed set is the honest check.

### Note retrieval

Does the right pattern note come back for a learner's answer? Measured on the 40 development answers, with the
scenario's pattern as the target, over 90 note sections (6 per pattern). Local models: `BAAI/bge-small-en-v1.5`
embeddings and the `BAAI/bge-reranker-base` reranker, Postgres + pgvector. Run:
[`evals/runs/2026-11-09T114805_retrieval`](evals/runs/2026-11-09T114805_retrieval/summary.md).

| Query: learner's answer only | Hit@1 | Hit@3 | MRR | p50 latency |
|---|---|---|---|---|
| Vector | 52.5% | 77.5% | 0.666 | 68 ms |
| Keyword (Postgres full text) | 52.5% | 72.5% | 0.659 | 3 ms |
| Hybrid (reciprocal rank fusion) | 57.5% | **82.5%** | **0.719** | 22 ms |
| Hybrid + reranker | 57.5% | 82.5% | 0.689 | 6.5 s |

Hybrid search beat either search alone. The reranker didn't improve Hit@3 and added about 6 seconds per query on a
laptop CPU. Putting the scenario prompt in front of the answer didn't help either (75–77.5% Hit@3). With 40 answers,
one answer is 2.5 points, so the gaps between methods are small. Most misses are wrong-pattern answers (43% Hit@3
for hybrid), which describe a different pattern, so retrieving that other pattern's note isn't really an error.

### Tutor with retrieved notes

Same tutor and settings as the baseline, plus the full notes for the top 3 patterns from hybrid search on the
learner's answer. Same 40 development answers × 5 runs. Run:
[`evals/runs/2026-11-09T201033_notes-hybrid-top3`](evals/runs/2026-11-09T201033_notes-hybrid-top3/summary.md).

| Metric | Baseline (dev) | With notes (dev) |
|---|---|---|
| Rubric-item accuracy | 97.3% (range 96.4–97.8%) | 97.6% (range 96.9–98.2%) |
| Wrong rubric-item calls, all 5 runs | 30 of 1,120 | 27 of 1,120 |
| False-pass / false-fail rate | 0.0% / 0.0% | 0.0% / 0.0% |
| Alternative-solution acceptance | 100% | 100% |
| Hints naming the pattern | 0.0% | 0.0% |
| Hints naming any pattern the learner didn't | 0 of 135 | 0 of 135 |
| Verdict changes between runs | 0 of 40 answers | 0 of 40 answers |
| Cost / latency | $0.017 per call; p50 4.6 s, p95 8.6 s | $0.028 per call; p50 4.8 s, p95 9.2 s |

Retrieval didn't measurably change grading on this set. The accuracy ranges overlap, every verdict is the same, and
the notes fixed some rubric calls while breaking others (for example, they now credit a partial answer with
"explores from every cell" when it never skips finished cells). They cost about 65% more per call because of the
longer prompt. The baseline was already near the ceiling on these answers, so there was little room to improve.

### Tool-using tutor with a hint ladder and leak checker

The tutor is now a tool-calling loop (`backend/src/patternly/tutor/agent.py`) with four tools: get the rubric,
read the learner's history, search notes, and record the attempt. Recording validates the grade (one call per
rubric item, verdict and hint consistent) and runs the hint through a leak checker; a rejected hint goes back to
the model with the reason, and after three rejected drafts the scenario's hand-written hint is used. Hints get
stronger with each failed attempt: level 1 is a nudge, level 2 the shape of the approach, level 3 a strong clue.

The leak checker flags a hint that names the pattern (when the learner hadn't), copies 8+ words of the reference
solution, or, according to a judge model (`claude-haiku-5-5`), states more missed rubric ideas than its level
allows (none at level 1, one at level 2, all but one at level 3).

Does it catch leaks? 44 hints written for the test (40 leaky, 4 tricky but fine), plus the 90 hand-written
scenario hints, which should pass. Run:
[`evals/runs/2026-11-10T143405_leaks-haiku-judge`](evals/runs/2026-11-10T143405_leaks-haiku-judge/summary.md).

| Set | Flagged |
|---|---|
| Planted: names the pattern | 10 of 10 |
| Planted: copies the reference solution | 10 of 10 |
| Planted: states too many missed ideas | 20 of 20 |
| Tricky but fine | 1 of 4 |
| Hand-written scenario hints | 18 of 90 (17 by the judge, 1 for copying 8 words) |

It catches every planted leak but is strict: the judge flags 20% of the hand-written hints, mostly level-2
hints that state two ideas. Either the judge over-reads hints or the level rules are tighter than the
hand-written ladders; this hasn't been resolved.

The tutor on the 40 development answers, each failing answer resubmitted until it had a level 1, 2, and 3
hint (94 attempts). Run:
[`evals/runs/2026-11-10T211147_tutor-loop-v1`](evals/runs/2026-11-10T211147_tutor-loop-v1/summary.md).

| Metric | Tool-using tutor (dev) |
|---|---|
| Rubric-item accuracy (first attempt) | 96.9% of 224 items (baseline-v2: 97.3% averaged over 5 runs) |
| False-pass / false-fail rate | 0.0% of 27 / 0.0% of 13 |
| Alternative-solution acceptance | 100% of 7 |
| Verdict changes when the same answer is resubmitted | 0 of 40 answers |
| Hint first drafts the leak checker rejected | 4 of 81 (4.9%): 2 named the pattern, 2 stated too many ideas |
| Delivered hints the leak checker flags | 0 of 81 (all 4 rewrites passed; no fallbacks) |
| Tool calls / model turns per attempt | 3.1 / 2.1 |
| Cost / latency per attempt | $0.020 (81.5% of input from cache); p50 11.1 s, p95 15.9 s |

The 0 delivered leaks is measured by the same checker that gates the hints, so it shows the guardrail works, not
that the hints are leak-free; the first-draft rate is the better measure of how often the model leaks. Grading
is one run, so the accuracy difference from the baseline is within run-to-run noise.

### Minor rubric items

The first version failed any answer that left out a rubric item, even one like "states the O(n) cost". Now 59
of the 169 items are marked minor: cost statements, the framing ("treat the grid as a graph"), "why it works"
explanations, and edge-case details. A correct answer that states every core item passes without them, and
hints only aim at core items. A simple count ("pass at 4 of 6") was tried on paper first and rejected: on the
development labels it would have passed 5 of 27 failing answers (all missing the key idea) and failed 5 of 13
valid alternatives.

Every labeled verdict already agreed with the new rule (every failing answer misses a core item), so no labels
changed. On the 40 development answers (one run,
[`evals/runs/2026-11-17T021709_tutor-loop-minor-items`](evals/runs/2026-11-17T021709_tutor-loop-minor-items/summary.md)):
rubric-item accuracy 96.0% of 224, false-pass 0.0% of 27, false-fail 0.0% of 13, alternatives 100% of 7, 3 of
81 hint drafts rejected, $0.020 and p95 14.6 s per attempt. Since no labeled answer misses only minor items, that
run can't show the softer rule itself. A spot check did: four new answers stating every core item but no minor
ones all passed with the new prompt; the old prompt failed one of them (it left out when to stop).

## Continuous integration

GitHub Actions runs three workflows on every push to `main` and every pull request:

- **backend:** `ruff check`, `ruff format --check`, `patternly validate`, and `pytest` against a Postgres + pgvector
  service container.
- **frontend:** `oxlint`, Vitest, and a production build.
- **eval-gate:** fails if grading quality drops below the measured baselines. It's free (local models, no
  Claude API calls):
  - `patternly leak-check --max-missed 0 --max-flagged 1`: all 20 planted pattern-name and copied-solution
    leaks are still caught, and no more than the 1 hand-written hint flagged today.
  - `patternly retrieval-eval --methods hybrid --forms answer --min-hit3 0.825`: hybrid search keeps Hit@3 at
    82.5% or better on the 40 development answers.

  The run results are uploaded as the `eval-runs` artifact. The tutor's own accuracy needs paid API calls,
  so `patternly tutor-eval` stays a manual run and isn't part of the gate.

## Running the API

The whole app in Docker (Postgres, the API, and the web app behind nginx):

```
cp backend/.env.example backend/.env           # add ANTHROPIC_API_KEY and JWT_SECRET
docker compose --profile app up -d --build     # http://localhost:8080
```

Put `API_FLAGS=--offline` in `backend/.env` to grade by simple word matching instead of the tutor, which makes no
API calls (for trying the app, not for real grading).

To run it on AWS (one EC2 instance behind CloudFront), see [deploy/README.md](deploy/README.md).

For development, run the database alone and the API and web app locally:

```
docker compose up -d                           # Postgres + pgvector on port 5433
cd backend && uv run patternly serve           # http://127.0.0.1:8000/docs (add --offline to skip the tutor)
cd frontend && npm install && npm run dev      # http://localhost:5173, proxies /api to the API
```

| Endpoint | What it does |
|---|---|
| `POST /auth/register`, `POST /auth/login` | Email, password, and IANA time zone; returns a bearer token (JWT, 7 days) |
| `POST /auth/guest` | A new guest account (random address on `guest.invalid`, reminders off) for trying a lesson |
| `GET /me` | The learner, their streak, and their reminder settings |
| `PUT /me/reminders` | Turns reminder emails on or off and sets the local hour they go out |
| `GET /lessons/today` | Today's lesson, picked on the first request of the learner's local day |
| `POST /lessons/today/attempts` | Grades an explanation: ideas hit (missed ones stay hidden), a hint, and the reveal when the lesson ends |
| `GET /reviews` | Patterns due for review and upcoming ones |
| `GET`/`POST /reminders/unsubscribe` | The link in reminder emails: shows a button, then turns reminders off |

How a day works:

- **Planner.** An overdue review comes first (the lowest box among the most overdue), then the next new
  pattern in `patterns.yaml` order, then extra practice. A review uses a scenario the learner hasn't seen if
  there is one.
- **Lesson.** Up to 4 attempts. Hints climb from level 1 to 3. A pass reveals the pattern; after the 4th failed
  attempt it's revealed anyway and counted as missed.
- **Spaced repetition.** Leitner boxes per pattern, reviewed after 5, 7, 14, 30, or 60 days. Solving on the
  first try moves a pattern up a box, needing hints keeps it in place, and a miss sends it back to box 1, so it
  returns in 5 days. Even a miss waits that long: a review the next day would only test short-term memory, and
  new patterns fill the days in between.
- **Streak.** Days in a row with a finished lesson, in the learner's time zone. Every 7 in a row earns a streak
  freeze (at most 2), used up automatically to cover a missed day.
- **Reminder.** If today's lesson isn't finished by the learner's chosen hour (7 pm local unless they change
  it), `patternly remind` sends one email through Amazon SES with a link to the app and the current streak.
  It runs hourly on the server; each reminder is claimed in the database first, so nobody gets two in a day,
  and a learner whose hour passed while the job was down still gets one later that day. Every email has an
  unsubscribe link.

### Demo limits

The live site is public, and every tutor-graded attempt costs money, so spending has a ceiling. All of these are
off unless their environment variable is set; production sets them in
[`deploy/docker-compose.prod.yml`](deploy/docker-compose.prod.yml):

| Variable | Production | What happens past it |
|---|---|---|
| `PATTERNLY_DAILY_BUDGET_USD` | 1.00 | Tutor spend since midnight UTC reached it: every attempt uses the offline grader until the next UTC day |
| `PATTERNLY_TUTOR_ATTEMPTS_PER_LEARNER` | 5 | That learner's later attempts today use the offline grader |
| `PATTERNLY_SIGNUPS_PER_IP_PER_HOUR` | 5 | New accounts (registered or guest) from that address get a 429 |

If the tutor itself fails (an outage, or the API key's own spend limit), the offline grader grades that attempt
too, so the site keeps working. Each attempt records which grader handled it (`graded_by`), and the web app shows
a note on any attempt the offline grader handled. The budget is checked before each attempt, so attempts submitted at the same moment can
overshoot it slightly; a monthly spend limit on the API key is the hard ceiling.

### Tracing

The API is traced with OpenTelemetry. Each request is a span (FastAPI instrumentation). A graded attempt adds a
`tutor.attempt` span under it, with one span per model call (model, input, output and cache tokens, cost) and
one per tool call. Spans go to a JSON Lines file when `PATTERNLY_TRACE_FILE` is set (Docker Compose writes
`/app/traces/spans.jsonl` on a volume), and to any OTLP collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
With neither, tracing is off.

`patternly trace-report` reads the file and prints p50/p95 tutor and request latency, cost per attempt, and
model turns per attempt (`--since 2026-11-14` for one stretch). In Docker:
`docker compose exec api patternly trace-report`.

### Tester metrics

`patternly tester-report --start 2026-11-16 --exclude you@example.com` reads the database and prints numbers for
a week-long trial with real learners, per learner id and overall. No such trial has been run (see Limits).

- **Daily completion:** tester-days with a finished lesson, out of testers x days in the window (7 by default).
  Only days that are over in every time zone count, so a day still in progress isn't counted as missed.
- **Hints to solve:** hints shown before the pass (one per failed attempt), averaged over solved lessons.
  Lessons revealed after the last failed attempt are counted separately.
- **Longest streak:** each tester's longest run of finished days inside the window, then the median.

### Why learners pick their reminder time

I first planned one fixed reminder time for everyone. Working out that schedule against my own days, I
realized the email would often arrive while I was in class or asleep, and by the time I checked my inbox it
would be buried under everything else that came in. A reminder only helps if it shows up when you can act on
it, so I made the hour a setting: each learner picks it in the web app, in their own time zone.

Tests (`uv run pytest`) run the whole flow through the API with a fake tutor against a scratch database:
a full lesson, the streak growing across days, and a missed pattern coming back in the review queue.

## Challenges

**Knowing whether the grader is actually right.** A grader that agrees with my labels is only as good as the
labels, and after the first baseline run I found label mistakes and fixed them. That can quietly bias the labels
toward whatever the model said. So 20 of the 60 answers were sealed before any tutor work and only used once
development was finished. The gap showed up: 94.1% rubric-item accuracy on the sealed answers against 96.9% on the
development answers the prompts were tuned on. The false-pass rate, the number that matters most because a false
pass teaches a wrong idea, stayed at 0% on both.

**Hints that help without giving the answer away.** The tutor writes good hints, but sometimes too good: 4 of its
first 81 drafts named the pattern or stated too much. The prompt forbids that, but a rule in the prompt wasn't enough, so every hint goes through a
leak checker before the learner sees it (pattern name, 8+ words copied from the reference solution, and a judge
model for "states too many missed ideas"), and a rejected hint goes back with the reason. The hard part is
calibration: the checker catches all 40 planted leaks, but the judge also flags 18 of the 90 hand-written hints,
so it's stricter than the hint ladders were written to be. That's still unresolved.

**Strict grading versus fair grading.** The first version failed any answer that left out a rubric item, so a
correct explanation that never said "O(n)" failed. The obvious fix, "pass at 4 of 6 key ideas", looked fine until
I ran it against the labels: it would have passed 5 of 27 failing answers (the ones that cover the easy points but
miss the key insight) and failed 5 of 13 valid alternative solutions. Key ideas aren't equal, so instead each
rubric item can be marked minor (cost, framing, "why it works", edge cases) and only core items are required.
Accuracy held on the development set.

**Retrieval that didn't pay off.** I expected pattern notes in the prompt to make grading more accurate. On the
development set they changed nothing measurable (every verdict the same, accuracy within noise) and cost 65% more
per call. The reranker was similar: no Hit@3 gain over hybrid search, and about 6.5 seconds per query on a laptop
CPU. Both stayed optional instead of on by default. The useful part was measuring before building more on it.

**Spacing reviews so they test memory.** The first scheduler brought a missed pattern back the next day. That only
tested whether yesterday's answer was still fresh. Reviews now wait at least 5 days (then 7, 14,
30, 60), and new patterns fill the days in between.

**Time zones everywhere.** A "day" is the learner's local day, for lessons, streaks, and reminders. Reminders go
out at each learner's chosen hour, are claimed in the database before sending so a retry can't send two, and still
go out if the hourly job was down at the right moment. The trial metrics only count a day once it has ended in
every time zone, so a day still in progress somewhere isn't counted as missed.

**Email that looks right in real inboxes.** Email clients ignore most CSS, and Gmail doesn't show SVG, so the
reminder is built from tables with inline styles and a PNG logo, with a plain-text version alongside. Amazon SES
starts in a sandbox where every recipient must verify their address first, which shapes how testers get added.

**Deploying cheaply with no domain.** One t3.small behind CloudFront, using CloudFront's own HTTPS certificate,
with no SSH (Session Manager only) and secrets generated on the instance or read from SSM. The local embedding
models make the API image about 1 GB, and building it on the instance briefly uses most of its memory.

**Tracing across threads.** The tutor runs in a worker thread so it doesn't block the async API. Spans only nest
under the request if the trace context crosses into that thread, so grading runs through `asyncio.to_thread`,
which carries it over, and a test checks the nesting.

**Letting anyone try it without an open-ended bill.** A public link on a resume means strangers can run up API
costs. Rather than hide the app behind an invite code, the server tracks what the tutor spent today and switches
to the free word-matching grader past a daily budget or a per-learner cap, and caps sign-ups per IP. The app keeps
working either way and says which grader handled each attempt. The client IP has to come from the right
`X-Forwarded-For` entry, since anything before CloudFront's entry can be set by the client.

**Testing without paying for it.** Every model call costs money, so the test suite uses a fake tutor and a scratch
database, `--offline` grades by word matching for UI work, and the CI eval gate only runs checks that need no API
calls. The paid evaluations are run by hand and saved under `evals/runs/` so every reported number links to a
run.

## Limits

- Labels are one person's judgment.
- The labeled learner answers were written to cover six answer types, not collected from real learners, so they may be cleaner or more predictable than real explanations.
- 60 labeled answers is a small set.
- LLM results vary between runs.
- On the live demo, once the daily tutor budget is used up, grading falls back to word matching, which is much
  weaker than the tutor.
- Not tested with real learners. There was no tester trial, so there are no numbers for daily completion, hints
  needed, or streaks, and nothing here shows that the daily habit loop works for anyone. `patternly tester-report`
  is built for that trial if one happens.
- After the first baseline run, the development labels were corrected once: three answers were rewritten because
  they were actually correct or ambiguous, two scenario prompts were made more specific, and eight rubric-item labels
  were changed where the rubric text didn't support them. That run is kept in `evals/runs/` for comparison
  (94.9% rubric-item accuracy, 5.9% false-pass rate on the old labels). Correcting labels after seeing model output
  can bias them toward the model; the sealed answers were not changed this way.
