# Tutor loop eval: tutor-loop-v1

Model `claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`, note search off. 40 dev answers, up to 3 attempts each (resubmitting the same answer). 94 attempts, 0 errors.

## Grading (first attempt)

| Metric | Result | Sample |
|---|---|---|
| Rubric-item accuracy | 96.9% | 224 items |
| False-pass rate | 0.0% | 27 labeled fail |
| False-fail rate | 0.0% | 13 labeled pass |
| Alternative acceptance | 100.0% | 7 alternatives |
| Verdict changes on resubmission | 0 | 40 answers |

## Hints

- Hints given: 81 (by level: level 1: 27, level 2: 27, level 3: 27)
- First drafts the checker rejected: 4 of 81 (pattern-name 2, revealed-steps 2)
- Delivered hints by source: rewrite 4, tutor 77
- Delivered hints the checker flags: 0 of 81

## Loop

- Tool calls: get_rubric 94, read_history 94, record_attempt 99
- Per attempt: 3.1 tool calls, 2.1 model turns
- Cost: $1.86 total, $0.0198 per attempt (judge $0.0270); input from cache 81.5%
- Latency per attempt: p50 11.1 s, p95 15.9 s
