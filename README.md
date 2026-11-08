# Patternly

Learn algorithm patterns by explaining first. One lesson a day: read a real-world scenario, describe your solution in plain words, and an AI tutor tells you which key ideas you hit, which you missed, and gives a hint without giving away the answer. Cover the key ideas and it reveals the pattern.

> Status: Weekend 2 (baseline tutor) done. 15 patterns, 30 scenarios, and 60 labeled learner answers for 10 of them (20 sealed for final metrics), plus a baseline grader measured on the 40 development answers. See [docs/project-plan.md](docs/project-plan.md).

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
