Status: implemented

# Troubleshooting Documentation

## Common Operational Issues & Remediation

### 1. Runs Stranded in `RUNNING` Status After Server Crash
- **Symptom**: Runs appear stuck in `RUNNING` status indefinitely.
- **Cause**: Server process terminated or restarted while background tasks were active.
- **Remediation**: The system automatically executes `recover_stale_running_runs()` during FastAPI application startup (`api/main.py`), transitioning stranded runs to `ERROR` status with the message `"Server restarted or terminated while run was in progress."`.

### 2. Provider Rate Limits (HTTP 429)
- **Symptom**: Model calls fail with HTTP 429 Too Many Requests.
- **Remediation**: `GroqLLMClient` implements exponential backoff across 3 retries (1s, 2s, 4s). If the provider remains saturated after 3 retries, the run transitions to `ERROR` status. Infrastructure outages never count as lesson retries.

### 3. Rate Limit Exceeded on Client (HTTP 429)
- **Symptom**: API returns 429 when calling `POST /api/v1/lessons/generate`.
- **Remediation**: The API enforces `RATE_LIMIT_PER_MINUTE` (default 30). Wait 60 seconds before submitting new tasks or adjust `RATE_LIMIT_PER_MINUTE` in `.env`.

### 4. Code Blocks Failing Syntax Checks (`code_integrity`)
- **Symptom**: Lessons containing Python code fail with `code_integrity: SyntaxError`.
- **Remediation**: The revision prompt automatically isolates the syntax error and instructs the model to correct missing parentheses, colons, or indentation. Non-Python snippets should be tagged with their appropriate language tag (e.g. ````sql```, ````bash```) so `ast.parse` skips them.

### 5. UI Cannot Connect to Backend
- **Symptom**: NiceGUI displays `API Error: ConnectError`.
- **Remediation**: Verify the FastAPI service is running on port 8000 (`uvicorn api.main:app --port 8000`) and that `API_URL` is set to `http://127.0.0.1:8000` in the UI environment.

## How to modify this
To add troubleshooting entries, append the symptom, cause, and remediation steps to this document.
