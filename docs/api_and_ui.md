Status: implemented

# API and UI Documentation

## Process Architecture
The system consists of two separate processes:
1. **FastAPI Backend Service (`api/main.py`)**: Runs on port 8000 by default.
2. **NiceGUI Frontend UI (`ui/app.py`)**: Runs on port 8080 by default.

The UI contains zero generation, evaluation, or database logic; all interaction is handled over HTTP via `ui/api_client.py`.

## API Endpoints

### Authentication & Headers
All `/api/v1/*` routes require header `X-API-Key: <API_KEY>`.

### Public Health Probes
- `GET /health`: Liveness probe returning `{"status": "ok"}`.
- `GET /ready`: Readiness probe checking database connectivity and provider configuration.

### Generation & Run Operations
- `POST /api/v1/lessons/generate`: Submits a lesson request. Returns `run_id` immediately; work runs asynchronously in the background. Enforces sliding window rate limit.
- `GET /api/v1/runs`: Lists past runs ordered by newest first.
- `GET /api/v1/runs/{id}`: Detailed status, full lesson content, evaluations, rejection log, and token usage.
- `GET /api/v1/runs/{id}/history`: Returns complete version snapshots and per-version evaluation results.
- `POST /api/v1/runs/{id}/cancel`: Sets cancellation flag; running loop terminates immediately.
- `POST /api/v1/runs/{id}/feedback`: Records user rating (1-5 stars), issue tags, and comments.

### Metrics & Configuration
- `GET /api/v1/metrics`: Global pass rates, retry distribution, token averages, and pitfall effectiveness.
- `GET /api/v1/config/rubric`: Returns active rubric specification.

## Frontend UI (NiceGUI)
- **Create Page (`/`)**: Input topic, level, objectives, length, retry slider (capped at 2), file upload, token budget estimate.
- **Run Page (`/runs/{id}`)**: Real-time status badge, polling every 1.5s, 5 interactive tabs (Lesson, Rubric filterable by severity, Claims, Rejection Log, User Feedback), JSON download, and mandatory quality disclaimers.
- **History Page (`/history`)**: Sortable table of runs with links to inspect individual runs.
- **Metrics Page (`/metrics`)**: KPI summary cards and distribution breakdown.

## How to modify this
To modify the API or UI, update `api/routes.py`, `api/schemas.py`, `ui/app.py`, and `ui/api_client.py`.
