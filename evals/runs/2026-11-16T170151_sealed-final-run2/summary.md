# Tutor loop eval: sealed-final-run2

Model `claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`, note search off. 20 sealed answers, up to 3 attempts each (resubmitting the same answer). 46 attempts, 0 errors.

## Grading (first attempt)

| Metric | Result | Sample |
|---|---|---|
| Rubric-item accuracy | 95.5% | 112 items |
| False-pass rate | 0.0% | 13 labeled fail |
| False-fail rate | 0.0% | 7 labeled pass |
| Alternative acceptance | 100.0% | 3 alternatives |
| Verdict changes on resubmission | 0 | 20 answers |

## Hints

- Hints given: 39 (by level: level 1: 13, level 2: 13, level 3: 13)
- First drafts the checker rejected: 2 of 39 (revealed-steps 2)
- Delivered hints by source: rewrite 2, tutor 37
- Delivered hints the checker flags: 0 of 39

## Loop

- Tool calls: get_rubric 46, read_history 46, record_attempt 48
- Per attempt: 3.0 tool calls, 2.0 model turns
- Cost: $0.81 total, $0.0176 per attempt (judge $0.0128); input from cache 91.6%
- Latency per attempt: p50 11.2 s, p95 15.6 s
