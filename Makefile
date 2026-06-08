# Codifeed - Makefile for API and Frontend development

.PHONY: help install dev build test format lint typecheck clean openapi-gen db-migrate db-upgrade db-downgrade

# Colors for output
BLUE := \033[34m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Default target
help: ## Show this help message
	@echo "$(BLUE)Codifeed Development Commands$(RESET)"
	@echo "$(YELLOW)Usage: make <target>$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'

# =============================================================================
# Installation
# =============================================================================

install: install-api install-web ## Install all dependencies

install-api: ## Install API dependencies
	@echo "$(BLUE)Installing API dependencies...$(RESET)"
	cd api && poetry install

install-web: ## Install Frontend dependencies
	@echo "$(BLUE)Installing Frontend dependencies...$(RESET)"
	cd web && pnpm install

# =============================================================================
# Development
# =============================================================================

dev: ## Start both API and Frontend in development mode
	@echo "$(BLUE)Starting development servers...$(RESET)"
	@echo "$(YELLOW)API will be available at: http://localhost:8000$(RESET)"
	@echo "$(YELLOW)Frontend will be available at: http://localhost:3000$(RESET)"
	@echo "$(YELLOW)Press Ctrl+C to stop both servers$(RESET)"
	@trap 'kill %1; kill %2; kill %3' INT; \
	cd database && docker compose up & \
	sleep 2 && cd api && poetry run python dev.py & \
	sleep 4 && cd web && pnpm run dev & \
	wait

dev-api: ## Start API development server
	@echo "$(BLUE)Starting API development server...$(RESET)"
	cd api && poetry run python dev.py

dev-web: ## Start Frontend development server
	@echo "$(BLUE)Starting Frontend development server...$(RESET)"
	cd web && pnpm run dev

dev-db: ## Start database development server
	@echo "$(BLUE)Starting database development server...$(RESET)"
	cd database && docker compose up

# =============================================================================
# Build
# =============================================================================

build: build-api build-web ## Build both API and Frontend

build-api: ## Build API
	@echo "$(BLUE)API doesn't need to be built.$(RESET)"

build-web: ## Build Frontend
	@echo "$(BLUE)Building Frontend...$(RESET)"
	cd web && pnpm run build



# =============================================================================
# Code Quality
# =============================================================================

# Fixing

format-fix: format-fix-api format-fix-web ## Format all code

format-fix-api: ## Fix API code formatting
	@echo "$(BLUE)Formatting API code...$(RESET)"
	cd api && poetry run ruff format .

format-fix-web: ## Fix Frontend code formatting
	@echo "$(BLUE)Formatting Frontend code...$(RESET)"
	cd web && pnpm run format:fix

lint-fix: lint-fix-api lint-fix-web ## Lint all code

lint-fix-api: ## Fix API code linting
	@echo "$(BLUE)Linting API code...$(RESET)"
	cd api && poetry run ruff check --fix .

lint-fix-web: ## Fix Frontend code linting
	@echo "$(BLUE)Linting Frontend code...$(RESET)"
	cd web && pnpm run lint:fix

# Checking

format-check: format-check-api format-check-web ## Check all code formatting

format-check-api: ## Check API code formatting
	@echo "$(BLUE)Checking API code formatting...$(RESET)"
	cd api && poetry run ruff format --check .

format-check-web: ## Check Frontend code formatting
	@echo "$(BLUE)Checking Frontend code formatting...$(RESET)"
	cd web && pnpm run format:check

lint-check: lint-check-api lint-check-web ## Check all code linting

lint-check-api: ## Check API code linting
	@echo "$(BLUE)Checking API code linting...$(RESET)"
	cd api && poetry run ruff check .

lint-check-web: ## Check Frontend code linting
	@echo "$(BLUE)Checking Frontend code linting...$(RESET)"
	cd web && pnpm run lint:check

typecheck: typecheck-api typecheck-web ## Type check all code

typecheck-api: ## Type check API code
	@echo "$(BLUE)Type checking API code...$(RESET)"
	cd api && poetry run pyright

typecheck-web: ## Type check Frontend code
	@echo "$(BLUE)Type checking Frontend code...$(RESET)"
	cd web && pnpm run typecheck

check: check-api check-web ## Run format, lint, and typecheck for all

check-api: format-check-api lint-check-api typecheck-api ## Run format, lint, and typecheck for API
	@echo "$(GREEN)API code quality checks completed$(RESET)"

check-web: format-check-web lint-check-web typecheck-web ## Run format, lint, and typecheck for Frontend
	@echo "$(BLUE)Running Frontend code quality checks...$(RESET)"
	cd web && pnpm run check

# =============================================================================
# Testing
# =============================================================================

test: test-api test-web ## Run all tests

test-api: ## Run API tests
	@echo "$(BLUE)Running API tests...$(RESET)"
	cd api && poetry run pytest --cov --cov-report=term-missing

test-web: ## Run Frontend tests
	@echo "$(BLUE)Running Frontend tests...$(RESET)"
	@echo "$(YELLOW)Frontend tests are not implemented yet$(RESET)"

# =============================================================================
# Database
# =============================================================================

db-migrate: ## Create a new database migration
	@echo "$(BLUE)Creating database migration...$(RESET)"
	@read -p "Enter migration message: " message; \
	cd api && poetry run alembic revision --autogenerate -m "$$message"

db-upgrade: ## Apply pending migrations
	@echo "$(BLUE)Applying database migrations...$(RESET)"
	cd api && poetry run alembic upgrade head

db-downgrade: ## Downgrade database by one migration
	@echo "$(BLUE)Downgrading database...$(RESET)"
	cd api && poetry run alembic downgrade -1

db-fake-data: ## Ensure fake data in database
	@echo "$(BLUE)Ensuring fake data in database...$(RESET)"
	cd api && poetry run python scripts/seed_fake_data.py

db-default-admin: ## Ensure default admin user in database
	@echo "$(BLUE)Ensuring default admin user in database...$(RESET)"
	cd api && poetry run python scripts/seed_default_admin.py


# =============================================================================
# OpenAPI
# =============================================================================

openapi-json: ## Generate OpenAPI JSON spec
	@echo "$(BLUE)Generating OpenAPI JSON spec...$(RESET)"
	cd api && poetry run python scripts/generate_openapi_json.py

openapi-ts: ## Generate TypeScript types from OpenAPI spec
	@echo "$(BLUE)Generating TypeScript types from OpenAPI spec...$(RESET)"
	@echo "$(YELLOW)Make sure the API server is running on localhost:8000$(RESET)"
	cd web && pnpm run openapi-ts

openapi-ts-watch: ## Watch for API changes and regenerate types
	@echo "$(BLUE)Watching for API changes and regenerating types...$(RESET)"
	@echo "$(YELLOW)Make sure the API server is running on localhost:8000$(RESET)"
	cd web && pnpm run openapi-ts:watch

# =============================================================================
# Maintenance
# =============================================================================

clean: clean-api clean-web ## Clean build artifacts and caches

clean-api: ## Clean API artifacts
	@echo "$(BLUE)Cleaning API artifacts...$(RESET)"
	cd api && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	cd api && find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	cd api && find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	cd api && find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	cd api && find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	cd api && find . -name ".coverage" -delete 2>/dev/null || true
	cd api && find . -name "*.pyc" -delete 2>/dev/null || true

clean-web: ## Clean Frontend artifacts
	@echo "$(BLUE)Cleaning Frontend artifacts...$(RESET)"
	cd web && rm -rf dist/ .turbo/ node_modules/.cache/ 2>/dev/null || true
	cd web && pnpm store prune 2>/dev/null || true


# =============================================================================
# Shortcuts for convenience
# =============================================================================

api: dev-api ## Shortcut for dev-api
web: dev-web ## Shortcut for dev-web
