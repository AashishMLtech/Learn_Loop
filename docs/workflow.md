Status: implemented

# Workflow Documentation

## Execution Lifecycle
This document outlines the step-by-step lifecycle of a lesson generation request through the agentic state machine.

### Step 1: Input Validation and Guardrails
1. The user submits a topic, learner level, objectives, target length, retry cap (0-2), and optional reference files via UI or API.
2. `guardrails/input.py` enforces constraints: topic <= 300 chars, objectives <= 10 items, reference uploads <= 200 KB in `.txt` or `.md`.
3. Reference texts are screened for prompt injection patterns. Any adversarial directives are redacted.
4. An initial run record is created in the database with status `RUNNING`.

### Step 2: Generation
1. Top 3 historical failing criteria are aggregated from recent runs, formatting a static Level A pitfall hint (capped at 150 tokens).
2. The generator node calls the LLM with `generation/prompts/generate.md`.
3. The returned markdown JSON block is validated against the Pydantic `Lesson` schema.
4. Version 1 is stored in the database.

### Step 3: Zero-Token Deterministic Checks
1. Before spending tokens on an LLM judge, 7 deterministic validators run:
   - `output_integrity`: Required sections populated, word count within bounds.
   - `beginner_readability`: Flesch-Kincaid grade level <= learner level ceiling.
   - `jargon_control`: Glossary definitions present and specialized terms covered.
   - `example_present`: Worked example present and connected to teaching steps.
   - `teaching_flow_structure`: Logical ordering of sequential steps.
   - `code_integrity`: Embedded Python snippets parse with AST without `SyntaxError`.
   - `citation_integrity`: Citations strictly reference supplied source IDs.
2. If any blocking deterministic criterion fails, the pipeline skips the LLM judge entirely and jumps directly to Step 5 (Revision).

### Step 4: Structured LLM Judge
1. If all deterministic checks pass, the combined LLM judge call executes with `evaluation/prompts/judge.md` at temperature 0.
2. The judge assesses 6 criteria (`factual_accuracy`, `internal_consistency`, `example_correctness`, `topic_coverage`, `coherence_of_flow`, `standalone_completeness`) and extracts material claims.
3. Claims are verified against reference texts (literal quote matching and SymPy math equation parsing).

### Step 5: Release Decision Gate
1. `guardrails/release_gate.py` computes the verdict using the binary pass/fail truth table.
2. If all blocking criteria pass:
   - Status transitions to `PASS`.
   - The lesson is marked finalized and ready for release.
3. If any blocking criterion fails:
   - A rejection log entry is recorded with failed criteria, failure reasons, and suggested fixes.
   - If retries remain (attempt <= max_retries <= 2):
     - Targeted revision feedback is formulated.
     - The pipeline loops back to `revise_node` and generates Version N+1.
   - If retry cap is reached:
     - Status transitions to `REJECTED`.
     - The terminal rejection log is saved and the loop halts.

## How to modify this
To modify the workflow, update this document and adjust the node routing in `agent/graph.py` and `agent/nodes.py`.
