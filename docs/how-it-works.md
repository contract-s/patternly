# How it works

The technical details behind the app: running it, the API, how a lesson day works, the demo's cost limits,
tracing, CI, and the engineering problems along the way.

## Running it

The whole app in Docker (Postgres, the API, and the web app behind nginx):

```
cp backend/.env.example backend/.env           # add ANTHROPIC_API_KEY and JWT_SECRET
docker compose --profile app up -d --build     # http://localhost:8080
```

Put `API_FLAGS=--offline` in `backend/.env` to grade by simple word matching instead of the tutor, which makes no
API calls (for trying the app, not for real grading).

To run it on AWS (one EC2 instance behind CloudFront), see [deploy/README.md](../deploy/README.md).

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


Tests (`uv run pytest`) run the whole flow through the API with a fake tutor against a scratch database:
a full lesson, the streak growing across days, and a missed pattern coming back in the review queue.

## Demo limits

The live site is public, and every tutor-graded attempt costs money, so spending has a ceiling. All of these are
off unless their environment variable is set; production sets them in
[`deploy/docker-compose.prod.yml`](../deploy/docker-compose.prod.yml):

| Variable | Production | What happens past it |
|---|---|---|
| `PATTERNLY_DAILY_BUDGET_USD` | 1.00 | Tutor spend since midnight UTC reached it: every attempt uses the offline grader until the next UTC day |
| `PATTERNLY_TUTOR_ATTEMPTS_PER_LEARNER` | 5 | That learner's later attempts today use the offline grader |
| `PATTERNLY_SIGNUPS_PER_IP_PER_HOUR` | 5 | New accounts (registered or guest) from that address get a 429 |

If the tutor itself fails (an outage, or the API key's own spend limit), the offline grader grades that attempt
too, so the site keeps working. Each attempt records which grader handled it (`graded_by`), and the web app shows
a note on any attempt the offline grader handled. The budget is checked before each attempt, so attempts submitted at the same moment can
overshoot it slightly; a monthly spend limit on the API key is the hard ceiling.

## Tracing

The API is traced with OpenTelemetry. Each request is a span (FastAPI instrumentation). A graded attempt adds a
`tutor.attempt` span under it, with one span per model call (model, input, output and cache tokens, cost) and
one per tool call. Spans go to a JSON Lines file when `PATTERNLY_TRACE_FILE` is set (Docker Compose writes
`/app/traces/spans.jsonl` on a volume), and to any OTLP collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.
With neither, tracing is off.

`patternly trace-report` reads the file and prints p50/p95 tutor and request latency, cost per attempt, and
model turns per attempt (`--since 2026-11-14` for one stretch). In Docker:
`docker compose exec api patternly trace-report`.

## Tester metrics

`patternly tester-report --start 2026-11-16 --exclude you@example.com` reads the database and prints numbers for
a week-long trial with real learners, per learner id and overall. No such trial has been run (see [Limits](../README.md#limits)).

- **Daily completion:** tester-days with a finished lesson, out of testers x days in the window (7 by default).
  Only days that are over in every time zone count, so a day still in progress isn't counted as missed.
- **Hints to solve:** hints shown before the pass (one per failed attempt), averaged over solved lessons.
  Lessons revealed after the last failed attempt are counted separately.
- **Longest streak:** each tester's longest run of finished days inside the window, then the median.


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


## Engineering notes

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

