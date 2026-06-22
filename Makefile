.PHONY: install install-locked install-all test test-fast lint typecheck security quality run api demo trace clean

install:
	python -m pip install -e .

install-locked:
	python -m pip install -r requirements-runtime.lock
	python -m pip install -e . --no-deps

install-all:
	python -m pip install -e ".[ai,pdf,ui,dev]"

test:
	python -m pytest --cov=app --cov-report=term-missing --cov-report=xml

test-fast:
	python -m pytest -q

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy app

security:
	bandit -q -r app
	pip-audit

quality: lint typecheck test security

api:
	uvicorn app.api:create_app --factory --host 0.0.0.0 --port 8000 --reload

run:
	python -m app.cli chat --driver-id D-LON-001 --message "Maria waited 135 minutes for a 1.5km airport fare. What should we do?"

demo:
	python -m app.cli demo-maria

trace:
	python scripts/generate_eval_trace.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml dist build var/*.sqlite3
