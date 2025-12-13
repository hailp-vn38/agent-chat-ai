#!/bin/bash
# Script để chạy tests với Docker Compose

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Khởi động test environment...${NC}"

# Khởi động test database
echo -e "${YELLOW}📦 Starting test database...${NC}"
docker compose -f docker-compose.test.yml up -d

# Đợi database sẵn sàng
echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
sleep 5

# Kiểm tra database health
until docker compose -f docker-compose.test.yml exec -T test-db pg_isready -U test_user -d test_db; do
  echo -e "${YELLOW}⏳ Waiting for test database...${NC}"
  sleep 2
done

echo -e "${GREEN}✅ Test database is ready!${NC}"

# Export test database URL
export TEST_DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db"
export TEST_REDIS_URL="redis://localhost:6380/0"

# Chạy tests
echo -e "${BLUE}🧪 Running tests...${NC}"

if [ "$1" == "coverage" ]; then
  echo -e "${BLUE}📊 Running tests with coverage...${NC}"
  uv run pytest --cov=src --cov-report=html --cov-report=term-missing
elif [ "$1" == "watch" ]; then
  echo -e "${BLUE}👀 Running tests in watch mode...${NC}"
  uv run pytest -f
elif [ "$1" == "parallel" ]; then
  echo -e "${BLUE}⚡ Running tests in parallel...${NC}"
  uv run pytest -n auto
else
  uv run pytest "$@"
fi

TEST_EXIT_CODE=$?

# Cleanup (optional - uncomment nếu muốn tự động dọn dẹp)
# echo -e "${YELLOW}🧹 Cleaning up...${NC}"
# docker compose -f docker-compose.test.yml down

if [ $TEST_EXIT_CODE -eq 0 ]; then
  echo -e "${GREEN}✅ All tests passed!${NC}"
else
  echo -e "${RED}❌ Tests failed!${NC}"
fi

exit $TEST_EXIT_CODE
