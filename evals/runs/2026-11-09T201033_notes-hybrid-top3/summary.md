# Eval: notes-hybrid-top3

- Split: **dev**, 40 answers × 5 runs = 200 calls (0 errors)
- Model: `claude-opus-5-5`, effort `medium`, notes: hybrid-top3
- Date: 2026-11-09T20:10:33

| Metric | Result | Per-run sample size |
|---|---|---|
| Rubric-item accuracy | 97.6% (range 96.9%–98.2%) | 224 rubric items |
| False-pass rate | 0.0% (range 0.0%–0.0%) | 27 answers labeled fail |
| False-fail rate | 0.0% (range 0.0%–0.0%) | 13 answers labeled pass |
| Alternative-solution acceptance | 100.0% (range 100.0%–100.0%) | 7 alternative answers |
| Hints naming the pattern | 0.0% (range 0.0%–0.0%) | hints given per run (varies) |

- Answers whose verdict changed between runs: 0 of 40
- Cost: $5.49 total, $0.0275 per call; latency p50 4.8s, p95 9.2s

Tutor pass rate by answer type:

- alternative: 100%
- correct: 100%
- missing_key_idea: 0%
- partial: 0%
- vague: 0%
- wrong_pattern: 0%
