# Retrieval eval: retrieval

- 40 development answers; target is the scenario's pattern
- Embeddings `BAAI/bge-small-en-v1.5`, reranker `BAAI/bge-reranker-base`
- Date: 2026-11-09T11:48:05

| Query | Method | Hit@1 | Hit@3 | MRR | p50 latency |
|---|---|---|---|---|---|
| answer | vector | 52.5% | 77.5% | 0.666 | 68 ms |
| answer | keyword | 52.5% | 72.5% | 0.659 | 3 ms |
| answer | hybrid | 57.5% | 82.5% | 0.719 | 22 ms |
| answer | hybrid-rerank | 57.5% | 82.5% | 0.689 | 6473 ms |
| scenario+answer | vector | 60.0% | 75.0% | 0.689 | 75 ms |
| scenario+answer | keyword | 47.5% | 72.5% | 0.627 | 3 ms |
| scenario+answer | hybrid | 57.5% | 77.5% | 0.695 | 36 ms |
| scenario+answer | hybrid-rerank | 55.0% | 75.0% | 0.666 | 7769 ms |

Hit@3 by answer type:

| Query | Method | alternative | correct | missing_key_idea | partial | vague | wrong_pattern |
|---|---|---|---|---|---|---|---|
| answer | vector | 71% | 100% | 86% | 83% | 86% | 43% |
| answer | keyword | 71% | 100% | 100% | 67% | 71% | 29% |
| answer | hybrid | 71% | 100% | 100% | 100% | 86% | 43% |
| answer | hybrid-rerank | 71% | 100% | 86% | 100% | 86% | 57% |
| scenario+answer | vector | 71% | 100% | 86% | 67% | 57% | 71% |
| scenario+answer | keyword | 57% | 100% | 86% | 67% | 71% | 57% |
| scenario+answer | hybrid | 71% | 100% | 100% | 83% | 57% | 57% |
| scenario+answer | hybrid-rerank | 29% | 100% | 86% | 100% | 71% | 71% |
