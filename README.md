# Learn Loop

An autonomous agentic system that generates standalone beginner lessons on any topic, evaluates them against a 13-criterion binary PASS/FAIL rubric, and self-corrects on failure through closed-loop retry revisions (hard-capped at 2 retries).

> **Mandatory Disclaimers**:
> - *Self-judged by model; not externally verified.*
> - *Never claim zero hallucinations.*

---

## Key Features
- **Closed-Loop Self-Correction**: When an evaluation fails any blocking criterion, the system formulates targeted revision instructions and re-generates the lesson (max 2 retries).
- **Zero-Token Deterministic Short-Circuiting**: 7 zero-token deterministic checks run before the LLM judge. If any fail, the LLM judge call is skipped, saving ~1,500 - 2,500 tokens per attempt.
- **Strict Budget Ceiling**: Maximum 2 LLM calls per attempt (1 generate/revise, 1 judge).
- **Process Separation**: FastAPI backend and NiceGUI frontend operate as two separate processes communicating strictly over HTTP.
- **Topic Agnostic**: No educational topic is hardcoded anywhere in the codebase.
- **Self-Evolving Learning**:
  - **Level A (Automatic)**: Aggregates top-3 historical failing criteria into static pitfall hints (capped at 150 tokens).
  - **Level B (Approval-Gated)**: CLI-managed proposal amendments with golden regression prevention and `ADMIN_API_KEY` verification.

---

## Quickstart & Setup Guide

### 🚀 Quickest Setup: Docker (Recommended - 3 Steps)

Get the entire system (FastAPI backend + NiceGUI UI + SQLite database) up and running in 3 simple commands:

#### Step 1: Clone the Repository & Navigate to Folder
```bash
git clone <YOUR_REPOSITORY_URL>
cd "Content Systems"
```

#### Step 2: Configure Environment (`.env`)
Copy the template and add your Groq API key:
```bash
# On Linux/macOS:
cp .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```
Open `.env` in any text editor and paste your Groq API key:
```ini
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
```

#### Step 3: Run with Docker Compose
```bash
docker compose up -d --build
```
That's it! 
* **Web UI**: Open **[http://localhost:8080](http://localhost:8080)** in your browser.
* **API Documentation**: Open **[http://localhost:8000/docs](http://localhost:8000/docs)**.

To stop the services anytime:
```bash
docker compose stop
```

---

### 💻 Alternative: Local Python Virtual Environment Setup

If you prefer running without Docker:

#### Step 1: Create and Activate Virtual Environment
```bash
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On Linux/macOS:
source .venv/bin/activate
```

#### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 3: Configure Environment (`.env`)
```bash
cp .env.example .env  # On Windows: Copy-Item .env.example .env
```
Provide your `GROQ_API_KEY` in `.env`.

#### Step 4: Run Services
Start the backend and frontend in separate terminals:

**Terminal 1 (FastAPI Backend - Port 8000):**
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 (NiceGUI Frontend - Port 8080):**
```bash
python ui/app.py
```
Open **`http://localhost:8080`** in your browser.

---

## Running Demonstrations & CLI Utilities

### Rejection & Self-Correction Demonstration
Demonstrate the autonomous rejection gate with intentional defects:
```bash
python scripts/demo_rejection.py --seed-flaw jargon
python scripts/demo_rejection.py --seed-flaw code
python scripts/demo_rejection.py --seed-flaw citation
```

### Managing Level B Self-Evolving Proposals
```bash
# List all proposals
python scripts/manage_proposals.py list

# Evaluate a proposal against the golden regression suite
python scripts/manage_proposals.py evaluate --id <PROPOSAL_ID>

# Approve and activate a proposal (requires ADMIN_API_KEY)
python scripts/manage_proposals.py approve --id <PROPOSAL_ID> --admin-key <KEY>

# Rollback an active proposal
python scripts/manage_proposals.py rollback --id <PROPOSAL_ID> --admin-key <KEY>
```

---

## Testing & Quality Gates

Run the automated test suite:
```bash
# Run all unit and integration tests
pytest tests/ -v

# Run the no-hardcoded-topic gate test
pytest tests/test_no_hardcoded_topic.py -v

# Run documentation compliance tests
pytest tests/test_docs.py -v

# Run live model calibration against the golden set (requires GROQ_API_KEY)
pytest -m live tests/test_live_calibration.py -v
```

---

## Documentation Index
- [Architecture](docs/architecture.md)
- [Codebase Map](docs/codebase_map.md)
- [Workflow Guide](docs/workflow.md)
- [Evaluation Rubric](docs/evaluation_rubric.md)
- [Guardrails & Hallucination Mitigation](docs/guardrails_and_hallucination.md)
- [Prompts Engineering](docs/prompts.md)
- [Data Model & Persistence](docs/data_model.md)
- [API & UI Specifications](docs/api_and_ui.md)
- [Configuration Reference](docs/configuration.md)
- [Token Optimization](docs/token_optimization.md)
- [Architectural Decisions (ADR)](docs/decisions.md)
- [Troubleshooting & FAQ](docs/troubleshooting.md)
