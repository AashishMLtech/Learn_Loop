.PHONY: install test lint typecheck run-api run-ui demo check-all clean

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

test-live:
	pytest -m live tests/test_live_calibration.py -v

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy shared generation evaluation guardrails hallucination memory agent api

run-api:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	python ui/app.py

demo:
	python scripts/demo_rejection.py --seed-flaw jargon

check-all: lint typecheck test
	python scripts/demo_rejection.py --seed-flaw jargon

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
