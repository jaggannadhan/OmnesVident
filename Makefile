.PHONY: help setup setup-py setup-frontend \
        api ingest frontend run-be run-fe \
        test test-ingestion test-intelligence test-api \
        deploy-be deploy-fe refine-all create-super-user \
        all stop

CLOUD_RUN_URL  ?= https://omnesvident-api-naqkmfs2qa-uc.a.run.app
INGEST_SECRET  ?= $(shell grep INGEST_SECRET .env | cut -d= -f2)

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
	@echo "  Deploy"
	@echo "    make deploy-be      Build + deploy backend to Cloud Run"
	@echo "    make deploy-fe      Deploy frontend to Vercel"
	@echo "    make refine-all     Backfill is_breaking/heat_score on all Firestore docs"
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
# Deploy
# ─────────────────────────────────────────────

deploy-be:
	@echo "→ Building and deploying backend to Cloud Run…"
	gcloud run deploy omnesvident-api \
		--source . \
		--region us-central1 \
		--allow-unauthenticated
	@echo "✓ Backend deployed."

deploy-fe:
	@echo "→ Deploying frontend to Vercel…"
	cd frontend_portal && npx vercel --prod
	@echo "✓ Frontend deployed."

refine-all:
	@echo "→ Triggering full geo + breaking-news re-refinement on $(CLOUD_RUN_URL)…"
	@curl -s -X POST "$(CLOUD_RUN_URL)/tasks/refine-all" \
		-H "X-Ingest-Token: $(INGEST_SECRET)" \
		-H "Content-Type: application/json" | python3 -m json.tool
	@echo "✓ Refinement queued (runs in background on Cloud Run)."

# Provision (or update) a privileged api_users record.
#   make create-super-user NAME="Jagan" EMAIL="jegsirox@gmail.com" PASSWORD="…" LEVELS="super_user,admin"
# Add ROTATE=1 to force a brand-new API key for an existing email.
# PASSWORD is hashed with bcrypt before storage; required for /v1/auth/login.
# LEVELS defaults to "super_user,admin" when omitted.
create-super-user:
	@if [ -z "$(NAME)" ] || [ -z "$(EMAIL)" ]; then \
		echo "Usage: make create-super-user NAME=\"Full Name\" EMAIL=\"you@example.com\" [PASSWORD=\"…\"] [LEVELS=\"super_user,admin\"] [ROTATE=1]"; \
		exit 1; \
	fi
	@FIRESTORE_PROJECT=omnesvident $(PYTHON) -m intelligence_layer.scripts.create_super_user \
		--name "$(NAME)" --email "$(EMAIL)" \
		$(if $(LEVELS),--levels "$(LEVELS)",) \
		$(if $(PASSWORD),--password "$(PASSWORD)",) \
		$(if $(ROTATE),--rotate,)

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
