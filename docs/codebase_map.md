Status: implemented

# Codebase Map

This document catalogues every file comprising the Learn Loop repository.

## Files List
- `ui/app.py`: NiceGUI web application containing Create, Run, History, and Metrics pages.
- `ui/api_client.py`: HTTPX client abstraction used by the frontend to communicate with the FastAPI backend.
- `api/main.py`: FastAPI application entrypoint with lifespan startup tasks, CORS, and correlation ID tracing.
- `api/routes.py`: REST endpoint handlers for generation, status polling, cancellation, feedback, metrics, and probes.
- `api/schemas.py`: Pydantic v2 request, response, and error schemas.
- `api/config.py`: Environment configuration loading and application settings.
- `agent/state.py`: TypedDict state definition for the LangGraph agent state machine.
- `agent/graph.py`: StateGraph definition linking nodes and conditional routing edges.
- `agent/nodes.py`: Node execution functions implementing generation, deterministic evaluation, judging, and persistence.
- `generation/schema.py`: Pydantic v2 lesson structure models and section types.
- `generation/service.py`: Service wrapper formatting prompts and calling LLMs for generation and revision.
- `generation/prompts/generate.md`: Topic-agnostic prompt template for initial lesson generation.
- `generation/prompts/revise.md`: Topic-agnostic prompt template for targeted revision using rejection feedback.
- `evaluation/rubric.yaml`: Versioned 13-criterion evaluation rubric definition.
- `evaluation/validators.py`: 7 zero-token deterministic validators executing before LLM judging.
- `evaluation/judge.py`: Service invoking structured LLM judge to evaluate pedagogical criteria and extract claims.
- `evaluation/prompts/judge.md`: Temperature 0 structured prompt template for the LLM judge.
- `guardrails/release_gate.py`: Pure function release gate computing pass/fail based on rubric truth table.
- `guardrails/input.py`: Guardrail validating request inputs and screening reference text for prompt injection.
- `guardrails/output.py`: Output sanitization stripping scripts, iframes, and dangerous URLs from markdown.
- `hallucination/claims.py`: Excerpt retrieval, untrusted block delimiters, quote verification, and SymPy math checking.
- `memory/store.py`: SQLAlchemy ORM models, session context managers, pitfall aggregations, and stale run recovery.
- `shared/llm_client.py`: LLM client interface, Groq implementation with exponential backoff, and token tracker.
- `shared/enums.py`: Canonical project enumerations.
- `scripts/demo_rejection.py`: CLI demonstrating rejection logging and revision queueing.
- `scripts/manage_proposals.py`: CLI for Level B self-evolving proposals (list, evaluate, approve, rollback).
- `tests/test_graph.py`: 13 core LangGraph integration and edge-case gate tests.
- `tests/test_validators.py`: Unit tests for all 7 deterministic validators.
- `tests/test_release_gate.py`: Truth table unit tests for the pure release decision gate.
- `tests/test_hallucination.py`: Unit tests for top-k retrieval, injection screening, quote match, and SymPy.
- `tests/test_memory.py`: Persistence roundtrip, Level A pitfall hints, and Level B proposals tests.
- `tests/test_api.py`: FastAPI integration tests covering endpoints, rate limits, cancel, and auth.
- `tests/test_ui_state.py`: Tests for ApiClient polling transitions and network error resilience.
- `tests/test_no_hardcoded_topic.py`: Source code scanner ensuring demo topic strings are not hardcoded.
- `tests/test_docs.py`: Docstring validation and documentation compliance gate test.
- `tests/test_live_calibration.py`: Golden benchmark calibration running against live judge.
- `tests/fixtures/golden/lesson_1_good.json`: Golden benchmark passing fixture 1.
- `tests/fixtures/golden/lesson_2_good.json`: Golden benchmark passing fixture 2.
- `tests/fixtures/golden/lesson_3_good.json`: Golden benchmark passing fixture 3.
- `tests/fixtures/golden/lesson_4_flawed_jargon.json`: Golden benchmark fixture with seeded jargon flaw.
- `tests/fixtures/golden/lesson_5_flawed_code.json`: Golden benchmark fixture with seeded broken code flaw.
- `tests/fixtures/golden/lesson_6_flawed_citations.json`: Golden benchmark fixture with seeded fabricated citation flaw.
- `docs/architecture.md`: Architecture overview and system topology.
- `docs/codebase_map.md`: Complete catalogue of all project files.
- `docs/workflow.md`: Step-by-step lifecycle and state machine transition guide.
- `docs/evaluation_rubric.md`: Detailed explanation of the 13 evaluation criteria and methods.
- `docs/guardrails_and_hallucination.md`: Guardrails, injection screening, and claim verification architecture.
- `docs/prompts.md`: Prompt engineering rationale and template specifications.
- `docs/data_model.md`: Database schemas, relations, and entity lifecycles.
- `docs/api_and_ui.md`: REST API specifications and NiceGUI interface design.
- `docs/configuration.md`: Environment variables and operational settings.
- `docs/token_optimization.md`: Token budgets, caching, and deterministic short-circuit savings.
- `docs/decisions.md`: Architectural decision records and locked engineering choices.
- `docs/troubleshooting.md`: Common operational issues, recovery procedures, and FAQ.
- `README.md`: Project summary, quickstart guide, and execution commands.
- `.env.example`: Template configuration file with blank model IDs and default settings.
- `requirements.txt`: Locked Python dependency package manifest.
- `pyproject.toml`: Configuration for pytest, ruff, and mypy.
- `Dockerfile`: Multi-stage container definition.
- `docker-compose.yml`: Multi-service compose orchestrating API, UI, and storage.
- `Makefile`: Convenience development tasks (test, lint, format, run).
- `.gitignore`: Git file ignore specifications.
- `.dockerignore`: Docker build ignore specifications.
- `.github/workflows/ci.yml`: GitHub Actions automated CI testing workflow.

## How to modify this
When new files or directories are added or renamed, update this file and verify compliance using `tests/test_docs.py`.
