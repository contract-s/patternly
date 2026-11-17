# Tutor loop eval: sealed-final-run3

Model `claude-opus-5-5`, effort `medium`, leak judge `claude-haiku-5-5`, note search off. 20 sealed answers, up to 3 attempts each (resubmitting the same answer). 46 attempts, 0 errors.

## Grading (first attempt)

| Metric | Result | Sample |
|---|---|---|
| Rubric-item accuracy | 93.8% | 112 items |
| False-pass rate | 0.0% | 13 labeled fail |
| False-fail rate | 0.0% | 7 labeled pass |
| Alternative acceptance | 100.0% | 3 alternatives |
| Verdict changes on resubmission | 0 | 20 answers |

## Hints

- Hints given: 39 (by level: level 1: 13, level 2: 13, level 3: 13)
- First drafts the checker rejected: 0 of 39 
- Delivered hints by source: tutor 39
- Delivered hints the checker flags: 0 of 39

## Loop

- Tool calls: get_rubric 46, read_history 46, record_attempt 46
- Per attempt: 3.0 tool calls, 2.0 model turns
- Cost: $0.78 total, $0.0170 per attempt (judge $0.0119); input from cache 92.1%
- Latency per attempt: p50 11.3 s, p95 14.8 s
