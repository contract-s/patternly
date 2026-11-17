# Tutor loop eval: tutor-loop-minor-items

Model `claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`, note search off. 40 dev answers, up to 3 attempts each (resubmitting the same answer). 94 attempts, 0 errors.

## Grading (first attempt)

| Metric | Result | Sample |
|---|---|---|
| Rubric-item accuracy | 96.0% | 224 items |
| False-pass rate | 0.0% | 27 labeled fail |
| False-fail rate | 0.0% | 13 labeled pass |
| Alternative acceptance | 100.0% | 7 alternatives |
| Verdict changes on resubmission | 0 | 40 answers |

## Hints

- Hints given: 81 (by level: level 1: 27, level 2: 27, level 3: 27)
- First drafts the checker rejected: 3 of 81 (pattern-name 1, revealed-steps 2)
- Delivered hints by source: rewrite 3, tutor 78
- Delivered hints the checker flags: 0 of 81

## Loop

- Tool calls: get_rubric 94, read_history 94, record_attempt 97
- Per attempt: 3.0 tool calls, 2.0 model turns
- Cost: $1.85 total, $0.0197 per attempt (judge $0.0253); input from cache 81.6%
- Latency per attempt: p50 10.8 s, p95 14.6 s
