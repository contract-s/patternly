# Evaluation

How well the tutor grades, how well its hints avoid giving the answer away, and what retrieval added. Every number
links to a saved run in [`evals/runs/`](../evals/runs/). Paths in links are relative to this folder.

## Final results (sealed test answers)

| Metric | Result | Sample size |
|---|---|---|
| Rubric-item accuracy | 94.1% mean over 3 runs (92.9%, 95.5%, 93.8%) | 112 rubric items per run (20 sealed answers) |
| False-pass rate | 0.0% (0 of 13 in every run) | 13 sealed answers labeled fail |
| Alternative-solution recognition | 100% (3 of 3 in every run) | 3 sealed alternative answers |
| Hint leak rate | 0 of 117 delivered hints flagged; 2 of 117 first drafts rejected and rewritten | 39 hints per run, 3 runs |
| Retrieval hit rate (vector vs. hybrid + rerank) | Hit@3 77.5% vector, 82.5% hybrid, 82.5% hybrid + rerank | 40 development answers |
| p95 latency / cost per attempt | Eval runs: p95 14.7–15.6 s, $0.017–0.020 per attempt. Live site: p50 12.5 s, p95 19.0 s, $0.024 mean ($0.035 max) per attempt | Eval: 46 attempts per run. Live: 14 attempts from 2026-11-17 to 2026-11-19, my own lessons and testing |

The first four rows are from the tutor loop (`claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`)
on the 20 sealed answers, run three times on 2026-11-16 after development was finished. False-fail rate was 0.0%
(0 of 7) and no verdict changed on resubmission in any run. Runs:
[1](../evals/runs/2026-11-16T170030_sealed-final-run1/summary.md),
[2](../evals/runs/2026-11-16T170151_sealed-final-run2/summary.md),
[3](../evals/runs/2026-11-16T170310_sealed-final-run3/summary.md). Model cost for the three runs: $2.53 for the tutor
plus $0.04 for the leak judge.

Two caveats. The leak rate is measured by the same checker (pattern name, copied solution, model judge) that
screens hints before delivery, so it shows the screen works, not that a human would find no leaks; on its own the
judge also flagged 18 of 90 hand-written hints, so it errs toward flagging. Retrieval was only measured on the
development answers. The live numbers come from the server's traces (`patternly trace-report --since 2026-11-17`):
14 tutor-graded attempts (11 from my own daily lessons, 3 test submissions), so with a sample that small the p95 is
simply the slowest attempt. A 15th request, a test sent before the fallback grader existed, failed at the Claude API
with a 400 and returned an error; it isn't in the latency or cost numbers. Live attempts were slower and cost more
than in the eval runs; the cause wasn't measured.

These sealed runs graded with the rule from before 2026-11-17, when minor rubric items were added (see "Minor rubric
items" below). The sealed set hasn't been rerun with the new rule. Development numbers are below.


## Development results

Baseline tutor (one prompt with the scenario, rubric, and answer; structured output), `claude-opus-5-5` at effort
`medium`, on the 40 development answers × 5 runs (200 calls). Run: [`evals/runs/2026-11-08T172423_baseline-v2`](../evals/runs/2026-11-08T172423_baseline-v2/summary.md).

| Metric | Baseline (dev) | Sample size per run |
|---|---|---|
| Rubric-item accuracy | 97.3% (range 96.4–97.8%) | 224 rubric items |
| False-pass rate | 0.0% (0 of 27 in every run) | 27 answers labeled fail |
| False-fail rate | 0.0% | 13 answers labeled pass |
| Alternative-solution acceptance | 100% | 7 alternative answers |
| Hints naming the pattern | 0.0% | 27 hints |
| Verdict changes between runs | 0 of 40 answers | |
| Cost / latency | $0.017 per call; p50 4.6 s, p95 8.6 s | |

These are optimistic: the development answers were relabeled once after the first baseline run (see [Limits](../README.md#limits)), and
the remaining rubric disagreements cluster on whether a stated cost counts when the described method doesn't
achieve it. The sealed set is the honest check.

### Note retrieval

Does the right pattern note come back for a learner's answer? Measured on the 40 development answers, with the
scenario's pattern as the target, over 90 note sections (6 per pattern). Local models: `BAAI/bge-small-en-v1.5`
embeddings and the `BAAI/bge-reranker-base` reranker, Postgres + pgvector. Run:
[`evals/runs/2026-11-09T114805_retrieval`](../evals/runs/2026-11-09T114805_retrieval/summary.md).

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
[`evals/runs/2026-11-09T201033_notes-hybrid-top3`](../evals/runs/2026-11-09T201033_notes-hybrid-top3/summary.md).

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
[`evals/runs/2026-11-10T143405_leaks-haiku-judge`](../evals/runs/2026-11-10T143405_leaks-haiku-judge/summary.md).

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
[`evals/runs/2026-11-10T211147_tutor-loop-v1`](../evals/runs/2026-11-10T211147_tutor-loop-v1/summary.md).

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
[`evals/runs/2026-11-17T021709_tutor-loop-minor-items`](../evals/runs/2026-11-17T021709_tutor-loop-minor-items/summary.md)):
rubric-item accuracy 96.0% of 224, false-pass 0.0% of 27, false-fail 0.0% of 13, alternatives 100% of 7, 3 of
81 hint drafts rejected, $0.020 and p95 14.6 s per attempt. Since no labeled answer misses only minor items, that
run can't show the softer rule itself. A spot check did: four new answers stating every core item but no minor
ones all passed with the new prompt; the old prompt failed one of them (it left out when to stop).


## The eval gate in CI

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

