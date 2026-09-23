PYTHON ?= python3
ENV_ARG := $(if $(wildcard .env),--env-file ../.env,)
VENV := $(CURDIR)/.venv/bin
.PHONY: setup backend-run backend-test frontend-install frontend-build frontend-test frontend-run demo up down migrate
setup:
	$(PYTHON) -m venv .venv
	$(VENV)/python -m pip install -r backend/requirements.lock -e 'backend[test]'
	cd frontend && npm ci
backend-test:
	cd backend && $(VENV)/python -m pytest -q
backend-run:
	cd backend && $(VENV)/uvicorn app.main:app --reload $(ENV_ARG)
frontend-install:
	cd frontend && npm ci
frontend-run:
	cd frontend && npm run dev
frontend-build:
	cd frontend && npm run build
frontend-test:
	cd frontend && npm test
migrate:
	cd backend && $(VENV)/python -m alembic upgrade head
demo:
	$(VENV)/python sample_data/run_campaign.py
up:
	docker compose up --build -d
down:
	docker compose down
