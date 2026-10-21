Status: implemented

# Evaluation Rubric Documentation

## Overview
Content is evaluated against a versioned 13-criterion binary PASS/FAIL rubric (`evaluation/rubric.yaml`). Averaged or numeric scores are strictly prohibited; any failed blocking criterion blocks publication and triggers revision or terminal rejection.

## 13 Criteria Breakdown

### Deterministic Checks (7 Criteria, Zero Tokens)
1. `output_integrity` (Critical, Blocking): Validates Pydantic schema integrity, ensures required sections are non-empty, and verifies word count falls within bounds for requested length profile.
2. `beginner_readability` (Major, Blocking): Computes Flesch-Kincaid Grade Level using `textstat`. Fails if grade exceeds learner level ceiling (16.5 for beginner).
3. `jargon_control` (Major, Blocking): Verifies all terms in `glossary` have definitions and that all terms flagged in `specialized_terms` appear in the glossary or are defined inline.
4. `example_present` (Critical, Blocking): Ensures `worked_example` has non-empty scenario and walkthrough and is explicitly referenced in instructional steps or summary.
5. `teaching_flow_structure` (Major, Blocking): Verifies instructional steps progress sequentially with non-empty headings and body paragraphs.
6. `code_integrity` (Critical, Blocking): Extracts all embedded Python code blocks from markdown fences and parses them using `ast.parse`. Fails on any `SyntaxError`. Non-Python blocks are marked not checked.
7. `citation_integrity` (Critical, Blocking): Verifies that all bibliographic citations reference supplied `source_id`s. Fabricated source IDs trigger immediate rejection.

### LLM Judge Checks (6 Criteria, Structured Model Call)
8. `factual_accuracy` (Critical, Blocking): Verifies core definitions, mechanisms, and claims are factually sound and consistent with reference materials.
9. `internal_consistency` (Critical, Blocking): Ensures that definitions, explanations, and walkthrough examples do not contradict each other across sections.
10. `example_correctness` (Major, Blocking): Validates that the worked example scenario accurately demonstrates the target concept.
11. `topic_coverage` (Major, Blocking): Assesses whether the lesson substantively addresses all stated learning objectives.
12. `coherence_of_flow` (Minor, Non-blocking): Evaluates whether conceptual transitions between prerequisites, definitions, and steps are logically smooth.
13. `standalone_completeness` (Minor, Non-blocking): Assesses whether the lesson provides sufficient context for a learner without external lookups.

## Truth Table
- Any Critical Failure -> REJECT
- Any Major Failure -> REJECT
- Contradicted Claim in Supplied Sources -> REJECT
- Minor Failure -> PASS (with advisory warning in rejection log)
- Partially Supported / Unverifiable Claims (Model Knowledge Only) -> PASS

## How to modify this
To modify rubric criteria, update `evaluation/rubric.yaml` and adjust the corresponding validators in `evaluation/validators.py` and `evaluation/judge.py`.
