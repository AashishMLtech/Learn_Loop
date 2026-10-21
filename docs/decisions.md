Status: implemented

# Architectural Decisions (ADR)

## Locked Technical Decisions

### ADR-1: Process Split (Two Distinct Processes)
- **Decision**: The UI (NiceGUI) and API (FastAPI) run as two independent processes. The UI communicates strictly over HTTP via an HTTPX client.
- **Rationale**: Isolates the frontend from the background execution loop, preventing blocking GUI threads and enabling independent scaling and restarts.

### ADR-2: Deterministic Short-Circuiting
- **Decision**: Deterministic checks execute before LLM judging. A failed deterministic check skips the judge call for that attempt.
- **Rationale**: Prevents wasting tokens on model evaluation when structural, readability, or syntax flaws can be caught instantly at zero cost.

### ADR-3: Pure Function Release Gate
- **Decision**: `guardrails/release_gate.py` is implemented as a pure function importing solely from `shared.enums`.
- **Rationale**: Decouples business release policies from database models, LLM clients, and network transport, allowing exhaustive unit testing of the truth table.

### ADR-4: Static Pitfall Templates for Level A
- **Decision**: Historical failure hints are constructed strictly from static templates keyed by criterion ID, never free-form LLM text.
- **Rationale**: Eliminates prompt-injection vectors, guarantees token ceilings (<= 150 tokens), and ensures predictable instructional guidance.

### ADR-5: Hard Capped Retries (Max 2 Retries)
- **Decision**: Retries are hard-capped at 2 (total 3 attempts).
- **Rationale**: Guarantees termination of the state machine, preventing infinite revision loops and unbounded token expenditure.

## How to modify this
To record new architectural decisions, append an ADR entry following this structure and maintain `Status: implemented` on line 1.
