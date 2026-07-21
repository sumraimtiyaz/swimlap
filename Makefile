# SwimLap developer shortcuts. Run `make help` for the list.
.DEFAULT_GOAL := help
.PHONY: help install test run-api dashboard mobile compose-up compose-down lint

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (editable) + dashboard deps
	cd backend && pip install -e .
	cd admin-dashboard && npm install

test: ## Run the backend test suite (stdlib unittest, 52 tests)
	cd backend && python -m unittest discover -s tests -p 'test_*.py'

run-api: ## Run the API locally with reload (in-memory by default)
	cd backend && SWIMLAP_PERSISTENCE=memory uvicorn app.main:app --reload

dashboard: ## Run the coordinator console dev server
	cd admin-dashboard && npm run dev

mobile: ## Generate platform folders + run the Flutter app
	cd mobile && flutter create . && flutter pub get && flutter run

compose-up: ## Full stack (Postgres + API) via docker compose
	cd infra && docker compose up --build

compose-down: ## Tear down the docker compose stack
	cd infra && docker compose down

lint: ## Ruff check the backend
	cd backend && ruff check app tests
