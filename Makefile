# AURORA — developer entry points (spec §32).
# Core engine + tests need no third-party runtime deps; the API needs fastapi.

PY ?= python
PYTHONPATH := backend

.PHONY: help install test lint demo benchmark audit backtest api generate frontend validate-example adapt-uspto adapt-merge-demo retro-case patentsview-sample multisource-case check-all

help:
	@echo "make install    - install python deps (fastapi, pytest, hypothesis)"
	@echo "make test        - run the full test suite"
	@echo "make demo        - generate corpus, run discovery, print classified hypotheses"
	@echo "make generate    - (re)generate the Northstar corpus + ground truth"
	@echo "make backtest    - run a historical discovery backtest"
	@echo "make benchmark   - time each pipeline stage on the full corpus"
	@echo "make audit       - print the spec self-audit"
	@echo "make validate-example - import examples/real_mini_package.json (+ optional pipeline)"
	@echo "make adapt-uspto - USPTO fixture -> package + import_package validation"
	@echo "make adapt-merge-demo - uspto+jobs+news merge into cases/iron-air-mini + scorecard"
	@echo "make retro-case  - iron-air-retro cutoff ledger (Loop 3)"
	@echo "make patentsview-sample - PatentsView-compatible dump case (Loop 4A)"
	@echo "make multisource-case - patents+jobs+news with LEI external_ids"
	@echo "make check-all   - pytest + cases + resolve smoke (pre-push gate)"
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

validate-example:
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/validate_package.py examples/real_mini_package.json --run

adapt-uspto:
	$(PY) -m adapters uspto adapters/fixtures/uspto_sample.json -o examples/generated_uspto_package.json --strip --validate --strict

adapt-merge-demo:
	$(PY) -m adapters uspto adapters/fixtures/uspto_sample.json -o cases/iron-air-mini/from_uspto.json --strip
	$(PY) -m adapters jobs adapters/fixtures/jobs_sample.json -o cases/iron-air-mini/from_jobs.json --strip
	$(PY) -m adapters news adapters/fixtures/news_sample.json -o cases/iron-air-mini/from_news.json --strip
	$(PY) -m adapters merge cases/iron-air-mini/from_uspto.json cases/iron-air-mini/from_jobs.json cases/iron-air-mini/from_news.json -o cases/iron-air-mini/package.json --strip --validate --strict
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/check_case_scorecard.py cases/iron-air-mini

retro-case:
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/run_retro_case.py cases/iron-air-retro

patentsview-sample:
	$(PY) -m adapters patentsview cases/patentsview-sample/dump.json -o cases/patentsview-sample/package.json --strip --validate --strict
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/check_case_scorecard.py cases/patentsview-sample

multisource-case:
	$(PY) scripts/build_multisource_case.py
	PYTHONPATH=$(PYTHONPATH) $(PY) scripts/check_case_scorecard.py cases/multisource-iron-air

check-all:
	$(PY) scripts/check_all.py

api:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m uvicorn api:app --app-dir backend --port 8000

frontend:
	cd frontend && npm install && npm run dev
