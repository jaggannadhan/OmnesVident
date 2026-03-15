.PHONY: help setup setup-py setup-frontend \
        api ingest frontend run-be run-fe \
        test test-ingestion test-intelligence test-api \
        all stop

PYTHON  := .venv/bin/python
PIP     := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
NPM     := npm

API_HOST := 127.0.0.1
API_PORT := 8000
UI_PORT  := 5173

# ─────────────────────────────────────────────
# Default target
# ─────────────────────────────────────────────
help:
	@echo ""
	@echo "  OmnesVident — Global News Discovery Portal"
	@echo "  ─────────────────────────────────────────"
	@echo "  Setup"
	@echo "    make setup          Install all Python + frontend deps"
	@echo "    make setup-py       Install Python deps only"
	@echo "    make setup-frontend Install npm deps only"
	@echo ""
	@echo "  Run"
	@echo "    make run-be         Start API + ingestion engine together"
	@echo "    make run-fe         Start Vite dev server  (port $(UI_PORT))"
	@echo ""
	@echo "  Test"
	@echo "    make test               Run all test suites"
	@echo "    make test-ingestion     Module 1 tests only"
	@echo "    make test-intelligence  Module 2 tests only"
	@echo "    make test-api           Module 3 tests only"
	@echo ""
	@echo "  Env vars (optional)"
	@echo "    NEWSDATA_API_KEY    API key for newsdata.io (falls back to mock data)"
	@echo "    DATABASE_URL        SQLAlchemy URL (default: sqlite:///./omnesvident.db)"
	@echo ""

# ─────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────
setup: setup-py setup-frontend
	@echo "✓ All dependencies installed."

setup-py:
	$(PIP) install -r requirements.txt

setup-frontend:
	cd frontend_portal && $(NPM) install

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

# Start the API in the background, wait for it to be ready, run ingestion,
# then keep the API alive until Ctrl+C.
run-be:
	@echo "→ Starting API on :$(API_PORT)…"
	@$(UVICORN) api_storage.routes:app \
		--host $(API_HOST) \
		--port $(API_PORT) \
		--reload & \
	sleep 3 && \
	echo "→ Running ingestion engine…" && \
	$(PYTHON) -m ingestion_engine.main; \
	wait

run-fe:
	@echo "→ Starting frontend on :$(UI_PORT)…"
	cd frontend_portal && $(NPM) run dev

api:
	$(UVICORN) api_storage.routes:app \
		--host $(API_HOST) \
		--port $(API_PORT) \
		--reload

ingest:
	$(PYTHON) -m ingestion_engine.main

frontend:
	cd frontend_portal && $(NPM) run dev

# ─────────────────────────────────────────────
# Test
# ─────────────────────────────────────────────
test:
	$(PYTHON) -m pytest ingestion_engine/tests/ intelligence_layer/tests/ api_storage/tests/ -v

test-ingestion:
	$(PYTHON) -m pytest ingestion_engine/tests/ -v

test-intelligence:
	$(PYTHON) -m pytest intelligence_layer/tests/ -v

test-api:
	$(PYTHON) -m pytest api_storage/tests/ -v
