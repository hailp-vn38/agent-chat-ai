.PHONY: help test test-cov test-parallel test-watch setup-test clean-test docker-test-up docker-test-down

help:  ## Hiển thị help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Test Commands
test:  ## Chạy tất cả tests
	@./scripts/run_tests.sh

test-cov:  ## Chạy tests với coverage report
	@./scripts/run_tests.sh coverage

test-parallel:  ## Chạy tests song song (nhanh hơn)
	@./scripts/run_tests.sh parallel

test-watch:  ## Chạy tests ở watch mode
	@./scripts/run_tests.sh watch

test-unit:  ## Chỉ chạy unit tests
	@./scripts/run_tests.sh -m unit

test-api:  ## Chỉ chạy API tests
	@./scripts/run_tests.sh -m api

test-failed:  ## Chạy lại tests đã failed
	@./scripts/run_tests.sh --lf

# Setup Commands
setup-test:  ## Setup môi trường test lần đầu
	@chmod +x scripts/setup_test_env.sh
	@chmod +x scripts/run_tests.sh
	@./scripts/setup_test_env.sh

install-test-deps:  ## Cài đặt test dependencies
	@uv pip install -r requirements-test.txt

# Docker Commands
docker-test-up:  ## Khởi động test database
	@docker compose -f docker-compose.test.yml up -d
	@echo "Waiting for database..."
	@sleep 5
	@docker compose -f docker-compose.test.yml exec test-db pg_isready -U test_user -d test_db || true

docker-test-down:  ## Dừng test database
	@docker compose -f docker-compose.test.yml down

docker-test-restart:  ## Restart test database
	@docker compose -f docker-compose.test.yml restart

docker-test-logs:  ## Xem logs của test database
	@docker compose -f docker-compose.test.yml logs -f

# Cleanup Commands
clean-test:  ## Dọn dẹp test environment
	@docker compose -f docker-compose.test.yml down -v
	@rm -rf .pytest_cache
	@rm -rf htmlcov
	@rm -rf .coverage
	@rm -rf coverage.xml
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Test environment cleaned!"

clean-coverage:  ## Xóa coverage reports
	@rm -rf htmlcov coverage.xml .coverage
	@echo "Coverage reports cleaned!"

# Coverage Commands
coverage-report:  ## Mở HTML coverage report
	@open htmlcov/index.html || xdg-open htmlcov/index.html

coverage-xml:  ## Generate XML coverage report
	@./scripts/run_tests.sh --cov=src --cov-report=xml

# Database Commands
test-db-shell:  ## Kết nối vào test database shell
	@docker compose -f docker-compose.test.yml exec test-db psql -U test_user -d test_db

test-db-reset:  ## Reset test database
	@docker compose -f docker-compose.test.yml down -v
	@docker compose -f docker-compose.test.yml up -d
	@sleep 5
	@echo "Test database reset complete!"

# Development Commands
lint:  ## Chạy linter
	@uv run ruff check src tests

format:  ## Format code
	@uv run ruff format src tests

type-check:  ## Type checking với mypy
	@uv run mypy src

quality:  ## Chạy tất cả quality checks
	@make lint
	@make type-check
	@make test-cov

# All-in-one Commands
ci:  ## Chạy CI pipeline (lint + type-check + test)
	@echo "Running CI pipeline..."
	@make lint
	@make type-check
	@make test-cov
	@echo "CI pipeline completed!"

dev-test:  ## Development test workflow
	@make docker-test-up
	@make test
	@echo "Development tests completed!"
