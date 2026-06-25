.PHONY: install install-locked install-all test test-fast lint format typecheck security quality run api demo trace manual-export manual-evaluate reviewer-demo reviewer-demo-compact reviewer-demo-json clean

PYTHON ?= python
DRIVER_ID ?= D-LON-001
MESSAGE ?= Maria waited 135 minutes for a 1.5km airport fare. What should we do?
MANUAL_DIR ?= manual_runs/maria

install:
	$(PYTHON) -m pip install -e .

install-locked:
	$(PYTHON) -m pip install -r requirements-runtime.lock
	$(PYTHON) -m pip install -e . --no-deps

install-all:
	$(PYTHON) -m pip install -e ".[ai,pdf,ui,dev]"

test:
	$(PYTHON) -m pytest \
		--cov=app \
		--cov-branch \
		--cov-report=term-missing \
		--cov-report=xml \
		--cov-fail-under=85

test-fast:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy app

security:
	$(PYTHON) -m bandit -q -r app
	$(PYTHON) -m pip_audit

quality: lint typecheck test security

api:
	$(PYTHON) -m uvicorn app.api:create_app \
		--factory \
		--host 0.0.0.0 \
		--port 8000 \
		--reload

run:
	$(PYTHON) -m app.cli chat \
		--driver-id "$(DRIVER_ID)" \
		--message "$(MESSAGE)"

demo:
	$(PYTHON) -m app.cli demo-maria

trace:
	$(PYTHON) -m scripts.generate_eval_trace

reviewer-demo:
	$(PYTHON) -m scripts.reviewer_demo

reviewer-demo-compact:
	$(PYTHON) -m scripts.reviewer_demo --compact

reviewer-demo-json:
	$(PYTHON) -m scripts.reviewer_demo --json

manual-export:
	$(PYTHON) -m app.cli manual-export \
		--driver-id "$(DRIVER_ID)" \
		--message "$(MESSAGE)" \
		--output-dir "$(MANUAL_DIR)"

manual-evaluate:
	$(PYTHON) -m app.cli manual-evaluate \
		--bundle-file "$(MANUAL_DIR)/request.json" \
		--response-file "$(MANUAL_DIR)/response.json"

clean:
	rm -rf \
		.pytest_cache \
		.mypy_cache \
		.ruff_cache \
		htmlcov \
		.coverage \
		.coverage.* \
		coverage.xml \
		dist \
		build \
		var/*.sqlite3 \
		var/*.sqlite3-* \
		*.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
