Status: implemented

# Token Optimization Documentation

## Design Principles
Token efficiency is a first-class requirement. The system minimizes LLM usage through structured limits and short-circuit evaluation.

## Optimization Strategies

### 1. Hard Per-Attempt LLM Call Ceiling (Max 2 Calls)
Each attempt strictly enforces an upper bound of at most two LLM invocations:
1. `generate` (or `revise` on retries)
2. `judge` (one combined structured call extracting claims and evaluating the 6 LLM criteria).

### 2. Zero-Token Deterministic Short-Circuiting
Before invoking the LLM judge, 7 deterministic checks execute locally in Python:
- Schema completeness & word count bounds
- Readability grade (Flesch-Kincaid)
- Jargon & glossary coverage
- Worked example presence & cross-referencing
- Teaching flow structure
- Python syntax integrity via AST parsing
- Citation grounding against supplied manifest

If any deterministic check fails, the pipeline skips the LLM judge call entirely for that attempt and transitions straight to revision. This saves ~1,500 - 2,500 judge tokens per failed attempt.

### 3. Evaluation Cache
Judge results are cached using a cryptographic hash computed from:
`hash(lesson_content + rubric_version + judge_model + evidence_context)`
If a lesson's content does not change, cached evaluation results are reused without spending tokens. Any modification to lesson text invalidates the cache key.

### 4. Level A Pitfall Hint Token Cap
Static Level A pitfall hints aggregated from historical failures are capped at 150 tokens (~100 words), preventing context window inflation.

## How to modify this
To modify token optimization rules or caching logic, update `agent/graph.py`, `evaluation/judge.py`, and `shared/llm_client.py`.
