Status: implemented

# Configuration Documentation

## Overview
All service parameters, credentials, and network bindings are managed via environment variables.

## Environment Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `GROQ_API_KEY` | *(blank)* | Groq provider secret API key. Never invent model IDs. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model ID used for generation and judging. |
| `API_KEY` | `default-insecure-api-key` | Static API key required in `X-API-Key` request header. |
| `ADMIN_API_KEY` | `default-admin-secret-xyz` | Admin key required to approve Level B self-evolving proposals. |
| `DATABASE_URL` | `sqlite:///./lesson_generator.db` | SQLAlchemy database connection string (SQLite or PostgreSQL). |
| `RATE_LIMIT_PER_MINUTE` | `30` | Maximum generation requests permitted per minute per API key. |
| `API_HOST` | `0.0.0.0` | Bind address for FastAPI backend service. |
| `API_PORT` | `8000` | Port for FastAPI backend service. |
| `UI_PORT` | `8080` | Port for NiceGUI frontend service. |
| `API_URL` | `http://127.0.0.1:8000` | Target URL used by NiceGUI HTTP client to contact backend. |
| `CORS_ORIGINS` | `http://localhost:8080,http://127.0.0.1:8080` | Permitted cross-origin resource sharing origins. |
| `USE_PITFALL_HINTS` | `true` | Toggles Level A automatic pitfall hint aggregation. |

## How to modify this
To update or add configuration options, edit `.env.example`, `api/config.py`, and this document.
