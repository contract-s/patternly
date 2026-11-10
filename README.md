# Patternly

Learn algorithm patterns by explaining first. One lesson a day: read a real-world scenario, describe your solution in plain words, and an AI tutor tells you which key ideas you hit, which you missed, and gives a hint without giving away the answer. Cover the key ideas and it reveals the pattern.

> Status: Weekend 2 (baseline tutor) done; Weekend 3 (pattern notes and retrieval) done. 15 patterns, 30 scenarios, and 60 labeled learner answers for 10 of them (20 sealed for final metrics), plus a baseline grader measured on the 40 development answers. See [docs/project-plan.md](docs/project-plan.md).

## Results

| Metric | Result | Sample size |
|---|---|---|
| Rubric-item accuracy | TBD | |
| False-pass rate | TBD | |
| Alternative-solution recognition | TBD | |
| Hint leak rate | TBD | |
| Retrieval hit rate (vector vs. hybrid + rerank) | TBD | |
| Hints to solve | TBD | |
| Daily completion | TBD | |
| Longest streak (median) | TBD | |
| p95 latency / cost per attempt | TBD | |

Final numbers above come from the sealed test answers once the tutor is finished. Development numbers are below.

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

## Limits

- Labels are one person's judgment.
- The labeled learner answers were written to cover six answer types, not collected from real learners, so they may be cleaner or more predictable than real explanations.
- 60 labeled answers is a small set.
- LLM results vary between runs.
- After the first baseline run, the development labels were corrected once: three answers were rewritten because
  they were actually correct or ambiguous, two scenario prompts were made more specific, and eight rubric-item labels
  were changed where the rubric text didn't support them. That run is kept in `evals/runs/` for comparison
  (94.9% rubric-item accuracy, 5.9% false-pass rate on the old labels). Correcting labels after seeing model output
  can bias them toward the model; the sealed answers were not changed this way.
