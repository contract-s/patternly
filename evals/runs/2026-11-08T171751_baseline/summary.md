# Eval: baseline

- Split: **dev**, 40 answers × 5 runs = 200 calls (0 errors)
- Model: `claude-opus-5-5`, effort `medium`
- Date: 2026-11-08T17:17:51

| Metric | Result | Per-run sample size |
|---|---|---|
| Rubric-item accuracy | 94.9% (range 94.2%–95.5%) | 224 rubric items |
| False-pass rate | 5.9% (range 3.7%–7.4%) | 27 answers labeled fail |
| False-fail rate | 15.4% (range 15.4%–15.4%) | 13 answers labeled pass |
| Alternative-solution acceptance | 71.4% (range 71.4%–71.4%) | 7 alternative answers |
| Hints naming the pattern | 3.7% (range 3.6%–3.7%) | hints given per run (varies) |

- Answers whose verdict changed between runs: 1 of 40
- Cost: $3.37 total, $0.0169 per call; latency p50 4.9s, p95 9.5s

Tutor pass rate by answer type:

- alternative: 71%
- correct: 100%
- missing_key_idea: 9%
- partial: 17%
- vague: 0%
- wrong_pattern: 0%
