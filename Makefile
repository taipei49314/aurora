# AURORA — developer entry points (spec §32).
# Core engine + tests need no third-party runtime deps; the API needs fastapi.

PY ?= python
PYTHONPATH := backend

.PHONY: help install test lint demo benchmark audit backtest api generate frontend

help:
	@echo "make install    - install python deps (fastapi, pytest, hypothesis)"
	@echo "make test        - run the full test suite"
	@echo "make demo        - generate corpus, run discovery, print classified hypotheses"
	@echo "make generate    - (re)generate the Northstar corpus + ground truth"
	@echo "make backtest    - run a historical discovery backtest"
	@echo "make benchmark   - time each pipeline stage on the full corpus"
	@echo "make audit       - print the spec self-audit"
	@echo "make api         - run the FastAPI backend on :8000"
	@echo "make frontend    - run the Vite dev server on :5173 (needs npm install)"

install:
	$(PY) -m pip install -r backend/requirements.txt

test:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m pytest

lint:
	$(PY) -m compileall -q backend/aurora

demo:
	PYTHONPATH=$(PYTHONPATH) $(PY) backend/aurora/cli.py

generate:
	$(PY) datasets/northstar/generate.py

backtest:
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/run_backtest.py

benchmark:
	PYTHONPATH=$(PYTHONPATH) $(PY) benchmarks/bench.py

audit:
	@cat docs/self-audit.md

api:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m uvicorn api:app --app-dir backend --port 8000

frontend:
	cd frontend && npm install && npm run dev
