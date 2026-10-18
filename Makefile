.PHONY: setup dev setup-ingestion-api ingestion-api

PYTHON ?= python3.14

# One-time installation of the API and UI dependencies.
setup:
	$(PYTHON) -m venv repos/banse/.venv
	repos/banse/.venv/bin/python -m pip install -e repos/banse
	cd repos/ui && npm install

# Run the API and the UI in one terminal; Ctrl-C stops both.
dev:
	python3 scripts/dev.py

# Optional private ingestion control API; it is never started by `make dev`.
setup-ingestion-api:
	$(PYTHON) -m venv repos/ingestion/.venv
	repos/ingestion/.venv/bin/python -m pip install -e 'repos/ingestion[test]'

ingestion-api:
	cd repos/ingestion && .venv/bin/league-ingest-api --work-root data --database data/league.duckdb
