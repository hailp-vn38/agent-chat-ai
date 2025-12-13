#!/bin/bash
# Script để setup môi trường test lần đầu

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🔧 Setting up test environment...${NC}"

# Cài đặt test dependencies
echo -e "${YELLOW}📦 Installing test dependencies...${NC}"
uv pip install -r requirements-test.txt

# Tạo test database container
echo -e "${YELLOW}🐳 Creating test database container...${NC}"
docker compose -f docker-compose.test.yml up -d

# Đợi database khởi động
echo -e "${YELLOW}⏳ Waiting for database...${NC}"
sleep 5

# Chạy migrations cho test database
echo -e "${YELLOW}🔄 Running migrations...${NC}"
export TEST_DATABASE_URL="postgresql+asyncpg://test_user:test_pass@localhost:5433/test_db"
cd src
uv run alembic upgrade head
cd ..

echo -e "${GREEN}✅ Test environment setup complete!${NC}"
echo -e "${BLUE}ℹ️  Run tests with: ${YELLOW}./scripts/run_tests.sh${NC}"
echo -e "${BLUE}ℹ️  Run with coverage: ${YELLOW}./scripts/run_tests.sh coverage${NC}"
echo -e "${BLUE}ℹ️  Run in parallel: ${YELLOW}./scripts/run_tests.sh parallel${NC}"
