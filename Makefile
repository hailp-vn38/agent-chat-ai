# ============================================================================
# Home Chat Bot - Makefile
# ============================================================================
# Docker Compose Management Commands
# Usage: make [target]
# ============================================================================

.PHONY: help dev prod down logs build rebuild ps shell stop clean prune \
        backup restore migrate db-shell redis-shell frontend backend \
        health lint test coverage db-backup db-restore

# Default target
.DEFAULT_GOAL := help

# Variables
DOCKER_COMPOSE := docker compose
DC_DEV := -f docker-compose.yml -f docker-compose.dev.yml
DC_PROD := -f docker-compose.yml -f docker-compose.prod.yml
SHELL := /bin/bash

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
YELLOW := \033[1;33m
NC := \033[0m # No Color

# ============================================================================
# HELP
# ============================================================================

help: ## Show this help message
	@printf "\n"
	@printf "$(BLUE)╔════════════════════════════════════════════════════════════════╗$(NC)\n"
	@printf "$(BLUE)║     Home Chat Bot - Docker Compose Management                  ║$(NC)\n"
	@printf "$(BLUE)╚════════════════════════════════════════════════════════════════╝$(NC)\n"
	@printf "\n"
	@printf "$(YELLOW)Development:$(NC)\n"
	@printf "  $(GREEN)make dev$(NC)                  Start development environment\n"
	@printf "  $(GREEN)make dev-tools$(NC)            Enable pgAdmin, Redis Commander, Mailhog\n"
	@printf "  $(GREEN)make dev-workers$(NC)          Enable background workers\n"
	@printf "  $(GREEN)make dev-db$(NC)               Start only database and redis\n"
	@printf "\n"
	@printf "$(YELLOW)Production:$(NC)\n"
	@printf "  $(GREEN)make prod$(NC)                 Start production environment\n"
	@printf "  $(GREEN)make prod-workers$(NC)         Enable background workers (prod)\n"
	@printf "  $(GREEN)make prod-backup$(NC)          Enable automatic database backups\n"
	@printf "\n"
	@printf "$(YELLOW)Management:$(NC)\n"
	@printf "  $(GREEN)make build$(NC)                Build all images\n"
	@printf "  $(GREEN)make rebuild$(NC)              Rebuild images (no cache)\n"
	@printf "  $(GREEN)make up$(NC)                   Alias for dev\n"
	@printf "  $(GREEN)make down$(NC)                 Stop and remove containers\n"
	@printf "  $(GREEN)make stop$(NC)                 Stop containers (keep data)\n"
	@printf "  $(GREEN)make ps$(NC)                   Show running containers\n"
	@printf "  $(GREEN)make logs$(NC)                 View logs (all services)\n"
	@printf "  $(GREEN)make logs-backend$(NC)         View backend logs\n"
	@printf "  $(GREEN)make logs-frontend$(NC)        View frontend logs\n"
	@printf "  $(GREEN)make logs-db$(NC)              View database logs\n"
	@printf "  $(GREEN)make logs-redis$(NC)           View redis logs\n"
	@printf "\n"
	@printf "$(YELLOW)Database:$(NC)\n"
	@printf "  $(GREEN)make migrate$(NC)              Run database migrations\n"
	@printf "  $(GREEN)make migrate-create$(NC)       Create new migration (use MSG='description')\n"
	@printf "  $(GREEN)make db-shell$(NC)             Access PostgreSQL shell\n"
	@printf "  $(GREEN)make db-backup$(NC)            Backup database\n"
	@printf "  $(GREEN)make db-restore$(NC)           Restore database (use FILE='backup.sql')\n"
	@printf "\n"
	@printf "$(YELLOW)Redis:$(NC)\n"
	@printf "  $(GREEN)make redis-shell$(NC)          Access Redis CLI\n"
	@printf "  $(GREEN)make redis-info$(NC)           Show Redis info\n"
	@printf "\n"
	@printf "$(YELLOW)Services:$(NC)\n"
	@printf "  $(GREEN)make shell-backend$(NC)        SSH into backend container\n"
	@printf "  $(GREEN)make shell-frontend$(NC)       SSH into frontend container\n"
	@printf "  $(GREEN)make backend$(NC)              View backend container logs\n"
	@printf "  $(GREEN)make frontend$(NC)             View frontend container logs\n"
	@printf "\n"
	@printf "$(YELLOW)Health & Monitoring:$(NC)\n"
	@printf "  $(GREEN)make health$(NC)               Check service health\n"
	@printf "  $(GREEN)make stats$(NC)                Show container resource usage\n"
	@printf "\n"
	@printf "$(YELLOW)Setup:$(NC)\n"
	@printf "  $(GREEN)make init-volumes$(NC)         Initialize data directories for volumes\n"
	@printf "\n"
	@printf "$(YELLOW)Testing:$(NC)\n"
	@printf "  $(GREEN)make test$(NC)                 Run tests\n"
	@printf "  $(GREEN)make coverage$(NC)             Generate coverage report\n"
	@printf "\n"
	@printf "$(YELLOW)Cleanup:$(NC)\n"
	@printf "  $(GREEN)make clean$(NC)                Remove containers (keep data)\n"
	@printf "  $(GREEN)make prune$(NC)                Remove containers, volumes, networks\n"
	@printf "  $(GREEN)make prune-all$(NC)            Aggressive cleanup (DANGER!)\n"
	@printf "\n"
	@printf "$(YELLOW)Configuration:$(NC)\n"
	@printf "  $(GREEN)make env$(NC)                  Show environment variables\n"
	@printf "  $(GREEN)make validate$(NC)             Validate compose files\n"
	@printf "\n"

# ============================================================================
# DEVELOPMENT
# ============================================================================

dev: ## Start development environment (docker-compose.yml + docker-compose.dev.yml)
	@printf "$(GREEN)Starting development environment...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) up -d
	@printf "$(GREEN)✓ Development environment started$(NC)\n"
	@printf "\n"
	@printf "$(BLUE)Services available at:$(NC)\n"
	@printf "  Frontend: http://localhost:3000\n"
	@printf "  Backend:  http://localhost:8000\n"
	@printf "  API Docs: http://localhost:8000/docs\n"
	@printf "  DB:       localhost:5432\n"
	@printf "  Redis:    localhost:6379\n"

up: dev ## Alias for 'make dev'

dev-tools: ## Enable development tools (pgAdmin, Redis Commander, Mailhog)
	@printf "$(GREEN)Enabling development tools...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) --profile dev-tools up -d
	@printf "$(GREEN)✓ Development tools enabled$(NC)\n"
	@printf "\n"
	@printf "$(BLUE)Development tools available at:$(NC)\n"
	@printf "  pgAdmin:           http://localhost:5050\n"
	@printf "  Redis Commander:   http://localhost:8081\n"
	@printf "  Mailhog (SMTP):    localhost:1025\n"
	@printf "  Mailhog (Web UI):  http://localhost:8025\n"

dev-workers: ## Enable background workers (development)
	@printf "$(GREEN)Enabling workers...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) --profile workers up -d
	@printf "$(GREEN)✓ Workers enabled$(NC)\n"

dev-db: ## Start only database and redis (development)
	@printf "$(GREEN)Starting database and redis...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) up -d db redis
	@printf "$(GREEN)✓ Database and redis started$(NC)\n"
	@printf "\n"
	@printf "$(BLUE)Services available at:$(NC)\n"
	@printf "  DB:    localhost:5432\n"
	@printf "  Redis: localhost:6379\n"

# ============================================================================
# PRODUCTION
# ============================================================================

prod: ## Start production environment (docker-compose.yml + docker-compose.prod.yml)
	@printf "$(GREEN)Starting production environment...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_PROD) up -d
	@printf "$(GREEN)✓ Production environment started$(NC)\n"
	@printf "\n"
	@printf "$(BLUE)Services available at:$(NC)\n"
	@printf "  NGINX: http://localhost (expose port 80/443)\n"

prod-workers: ## Enable background workers (production)
	@printf "$(GREEN)Enabling workers...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_PROD) --profile workers up -d
	@printf "$(GREEN)✓ Workers enabled$(NC)\n"

prod-backup: ## Enable automatic database backups (production)
	@printf "$(GREEN)Enabling database backups...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_PROD) --profile backup up -d
	@printf "$(GREEN)✓ Database backups enabled$(NC)\n"

# ============================================================================
# MANAGEMENT
# ============================================================================

build: ## Build all Docker images
	@printf "$(GREEN)Building Docker images...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) build
	@printf "$(GREEN)✓ Build complete$(NC)\n"

rebuild: ## Rebuild all Docker images (no cache)
	@printf "$(GREEN)Rebuilding Docker images (no cache)...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) build --no-cache
	@printf "$(GREEN)✓ Rebuild complete$(NC)\n"

down: ## Stop and remove containers
	@printf "$(YELLOW)Stopping containers...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) down
	@printf "$(GREEN)✓ Containers stopped$(NC)\n"

stop: ## Stop containers (keep data)
	@printf "$(YELLOW)Stopping containers...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) stop
	@printf "$(GREEN)✓ Containers stopped$(NC)\n"

ps: ## Show running containers and status
	@printf "$(BLUE)Running containers:$(NC)\n"
	@$(DOCKER_COMPOSE) $(DC_DEV) ps

logs: ## View logs from all services (follow mode)
	@$(DOCKER_COMPOSE) $(DC_DEV) logs -f

logs-backend: ## View backend logs
	@$(DOCKER_COMPOSE) $(DC_DEV) logs -f backend

logs-frontend: ## View frontend logs
	@$(DOCKER_COMPOSE) $(DC_DEV) logs -f frontend

logs-db: ## View database logs
	@$(DOCKER_COMPOSE) $(DC_DEV) logs -f db

logs-redis: ## View redis logs
	@$(DOCKER_COMPOSE) $(DC_DEV) logs -f redis

stats: ## Show container resource usage
	@$(DOCKER_COMPOSE) $(DC_DEV) stats

# ============================================================================
# DATABASE
# ============================================================================

migrate: ## Run database migrations
	@printf "$(GREEN)Running migrations...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec -T backend alembic upgrade head
	@printf "$(GREEN)✓ Migrations complete$(NC)\n"

migrate-create: ## Create new migration
	@if [ -z "$(MSG)" ]; then \
		printf "$(RED)Error: MSG is required (use: make migrate-create MSG='description')$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(GREEN)Creating migration: $(MSG)$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec -T backend alembic revision --autogenerate -m "$(MSG)"
	@printf "$(GREEN)✓ Migration created$(NC)\n"

db-shell: ## Access PostgreSQL shell
	@printf "$(BLUE)Connecting to PostgreSQL...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec db psql -U $${POSTGRES_USER:-homebot} -d $${POSTGRES_DB:-homebot}

db-backup: ## Backup database
	@printf "$(GREEN)Backing up database...$(NC)\n"
	@mkdir -p ./data/postgres/backups
	@$(DOCKER_COMPOSE) $(DC_DEV) exec -T db pg_dump -U $${POSTGRES_USER:-homebot} $${POSTGRES_DB:-homebot} | \
		gzip > ./data/postgres/backups/backup-$$(date +%Y%m%d-%H%M%S).sql.gz
	@printf "$(GREEN)✓ Database backup complete$(NC)\n"

db-restore: ## Restore database from backup
	@if [ -z "$(FILE)" ]; then \
		printf "$(RED)Error: FILE is required (use: make db-restore FILE='backup.sql.gz')$(NC)\n"; \
		exit 1; \
	fi
	@printf "$(YELLOW)Restoring database from $(FILE)...$(NC)\n"
	@if [[ "$(FILE)" == *.gz ]]; then \
		gunzip -c ./data/postgres/backups/$(FILE) | $(DOCKER_COMPOSE) $(DC_DEV) exec -T db psql -U $${POSTGRES_USER:-homebot} $${POSTGRES_DB:-homebot}; \
	else \
		$(DOCKER_COMPOSE) $(DC_DEV) exec -T db psql -U $${POSTGRES_USER:-homebot} $${POSTGRES_DB:-homebot} < ./data/postgres/backups/$(FILE); \
	fi
	@printf "$(GREEN)✓ Database restore complete$(NC)\n"

# ============================================================================
# REDIS
# ============================================================================

redis-shell: ## Access Redis CLI
	@printf "$(BLUE)Connecting to Redis...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec redis redis-cli

redis-info: ## Show Redis info
	@printf "$(BLUE)Redis information:$(NC)\n"
	@$(DOCKER_COMPOSE) $(DC_DEV) exec redis redis-cli info

redis-flush: ## Flush Redis (DANGER!)
	@printf "$(RED)WARNING: This will delete ALL Redis data!$(NC)\n"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) $(DC_DEV) exec redis redis-cli FLUSHALL; \
		printf "$(GREEN)✓ Redis flushed$(NC)\n"; \
	else \
		printf "$(YELLOW)Cancelled$(NC)\n"; \
	fi

# ============================================================================
# SHELL ACCESS
# ============================================================================

shell-backend: ## SSH into backend container
	@printf "$(BLUE)Entering backend container...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec backend bash

shell-frontend: ## SSH into frontend container
	@printf "$(BLUE)Entering frontend container...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec frontend bash

backend: ## Alias for 'make logs-backend'
	@$(MAKE) logs-backend

frontend: ## Alias for 'make logs-frontend'
	@$(MAKE) logs-frontend

# ============================================================================
# HEALTH & MONITORING
# ============================================================================

health: ## Check health of all services
	@printf "$(BLUE)Checking service health...$(NC)\n"
	@$(DOCKER_COMPOSE) $(DC_DEV) ps --format "table {{.Service}}\t{{.Status}}\t{{.Health}}"
	@printf "\n"
	@printf "$(BLUE)Detailed health checks:$(NC)\n"
	@printf "Frontend: $$($(DOCKER_COMPOSE) $(DC_DEV) exec -T frontend wget --quiet --tries=1 --spider http://localhost:3000 2>&1 && printf '✓' || printf '✗')\n"
	@printf "Backend:  $$($(DOCKER_COMPOSE) $(DC_DEV) exec -T backend curl -f http://localhost:8000/health 2>/dev/null && printf '✓' || printf '✗')\n"
	@printf "Database: $$($(DOCKER_COMPOSE) $(DC_DEV) exec -T db pg_isready -U $${POSTGRES_USER:-homebot} 2>&1 | grep -q accepting && printf '✓' || printf '✗')\n"
	@printf "Redis:    $$($(DOCKER_COMPOSE) $(DC_DEV) exec -T redis redis-cli ping 2>&1 | grep -q PONG && printf '✓' || printf '✗')\n"

# ============================================================================
# TESTING
# ============================================================================

test: ## Run backend tests
	@printf "$(GREEN)Running tests...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec -T backend pytest -v

coverage: ## Generate test coverage report
	@printf "$(GREEN)Generating coverage report...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) exec -T backend pytest --cov=src --cov-report=html
	@printf "$(GREEN)✓ Coverage report generated (htmlcov/index.html)$(NC)\n"

# ============================================================================
# CLEANUP
# ============================================================================

clean: ## Remove containers (keep data and volumes)
	@printf "$(YELLOW)Removing containers...$(NC)\n"
	$(DOCKER_COMPOSE) $(DC_DEV) down
	@printf "$(GREEN)✓ Containers removed$(NC)\n"

prune: ## Remove containers, volumes, networks (DANGER!)
	@printf "$(RED)WARNING: This will delete containers and volumes!$(NC)\n"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) $(DC_DEV) down -v; \
		printf "$(GREEN)✓ Cleanup complete$(NC)\n"; \
	else \
		printf "$(YELLOW)Cancelled$(NC)\n"; \
	fi

prune-all: ## Aggressive cleanup: remove images, containers, volumes (VERY DANGEROUS!)
	@printf "$(RED)WARNING: This will delete ALL Docker resources!$(NC)\n"
	@read -p "Are you really sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker system prune -a --volumes; \
		printf "$(GREEN)✓ Aggressive cleanup complete$(NC)\n"; \
	else \
		printf "$(YELLOW)Cancelled$(NC)\n"; \
	fi

# ============================================================================
# CONFIGURATION
# ============================================================================

init-volumes: ## Initialize data directories for volumes
	@printf "$(GREEN)Initializing volumes...$(NC)\n"
	@bash ./scripts/init-volumes.sh

env: ## Show current environment variables from .env
	@printf "$(BLUE)Environment variables from .env:$(NC)\n"
	@if [ -f .env ]; then \
		grep -v '^#' .env | grep -v '^$$'; \
	else \
		printf "$(RED).env file not found$(NC)\n"; \
	fi

validate: ## Validate Docker Compose files
	@printf "$(GREEN)Validating docker-compose.yml...$(NC)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.yml config > /dev/null && printf "$(GREEN)✓ Valid$(NC)\n" || printf "$(RED)✗ Invalid$(NC)\n"
	@printf "$(GREEN)Validating docker-compose.dev.yml...$(NC)\n"
	@$(DOCKER_COMPOSE) $(DC_DEV) config > /dev/null && printf "$(GREEN)✓ Valid$(NC)\n" || printf "$(RED)✗ Invalid$(NC)\n"
	@printf "$(GREEN)Validating docker-compose.prod.yml...$(NC)\n"
	@$(DOCKER_COMPOSE) $(DC_PROD) config > /dev/null && printf "$(GREEN)✓ Valid$(NC)\n" || printf "$(RED)✗ Invalid$(NC)\n"

# ============================================================================
# UTILITY
# ============================================================================

init: ## Initialize project (create .env from .env.example if needed)
	@if [ ! -f .env ]; then \
		printf "$(GREEN)Creating .env from .env.example...$(NC)\n"; \
		cp .env.example .env; \
		printf "$(YELLOW)Please edit .env with your configuration$(NC)\n"; \
	else \
		printf "$(BLUE).env already exists$(NC)\n"; \
	fi

install: init build ## Initialize and build project

version: ## Show Docker and Docker Compose versions
	@printf "$(BLUE)Docker versions:$(NC)\n"
	@docker --version
	@docker compose version

# ============================================================================
# DEFAULT WORKFLOW
# ============================================================================

start: ## Quick start (dev environment)
	@$(MAKE) init-volumes
	@$(MAKE) init
	@$(MAKE) build
	@$(MAKE) dev
	@$(MAKE) migrate
	@printf "$(GREEN)✓ Application is ready!$(NC)\n"

# ============================================================================
# Notes
# ============================================================================
# Development Workflow:
#   1. make init           - Initialize .env
#   2. make build          - Build images
#   3. make dev            - Start development
#   4. make migrate        - Run migrations
#   5. make logs           - View logs
#
# Production Workflow:
#   1. make prod           - Start production
#   2. make prod-workers   - Enable workers
#   3. make prod-backup    - Enable backups
#   4. make health         - Check health
#   5. make logs           - View logs
#
# ============================================================================
