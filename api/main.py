"""FastAPI Application Main Module.

Purpose:
    Instantiates and configures the FastAPI service with CORS middleware, correlation
    ID tracing, structured JSON logging, startup database initialization, and stale
    run recovery.

Inputs/Outputs:
    Inputs: Incoming HTTP requests, environment settings.
    Outputs: Configured FastAPI application instance (app).

What it must NOT do:
    - Must NOT log authorization secrets or full prompt texts.
    - Must NOT execute UI components or UI server loops.
"""
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import settings
from api.routes import health_endpoint, ready_endpoint
from api.routes import router as api_v1_router
from memory.store import init_db, recover_stale_running_runs


# Configure structured logging
class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured observability without sensitive data."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        return json.dumps(log_obj)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Avoid duplicate handlers if reloaded
if not root_logger.handlers:
    root_logger.addHandler(handler)
else:
    root_logger.handlers[0] = handler

logger = logging.getLogger("lesson_generator.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager executing startup initialization and shutdown teardown.

    Initializes database schema and marks any stale runs in RUNNING state as ERROR.
    """
    logger.info("Initializing database schema...")
    init_db()
    stale_count = recover_stale_running_runs()
    if stale_count > 0:
        logger.warning("Recovered %d orphaned runs stuck in RUNNING status to ERROR.", stale_count)
    logger.info("Application startup sequence completed successfully.")
    yield
    logger.info("Application shutdown sequence completed.")


app = FastAPI(
    title="Learn Loop API",
    description="Autonomous educational content generation and closed-loop evaluation platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    """Attaches a unique correlation ID to requests and responses."""
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Run-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler returning typed ErrorResponse."""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.error("Unhandled exception processing request: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred.",
            "error_type": exc.__class__.__name__,
            "correlation_id": correlation_id,
        },
    )


# Mount root health probes
app.add_api_route("/health", health_endpoint, methods=["GET"], tags=["probes"])
app.add_api_route("/ready", ready_endpoint, methods=["GET"], tags=["probes"])

# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")
