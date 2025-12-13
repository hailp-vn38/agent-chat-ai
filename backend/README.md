# Backend API

Một ứng dụng FastAPI hiệu suất cao với hỗ trợ realtime, AI integration, MQTT, Redis, và PostgreSQL.

## 🚀 Giới thiệu

Backend này cung cấp một platform API toàn diện hỗ trợ:

- **FastAPI** - Web framework modern, high-performance
- **Real-time Services** - WebSocket, ThreadPool, MQTT
- **AI Integration** - MCP (Model Context Protocol), LLM support
- **Database** - PostgreSQL + SQLAlchemy + Alembic
- **Caching** - Redis
- **Authentication** - JWT + OAuth2
- **Task Scheduling** - APScheduler
- **Logging** - Loguru

## 📋 Yêu cầu

- Python 3.10
- PostgreSQL 14+
- Redis
- Docker & Docker Compose (optional)

## 🔧 Cài đặt

### 1. Clone repository

```bash
cd backend
```

### 2. Tạo virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# hoặc
venv\Scripts\activate  # Windows
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Thiết lập environment

```bash
cp .env.example .env
# Chỉnh sửa .env với các giá trị của bạn
```

### 5. Khởi tạo database

```bash
# Chạy migration
alembic upgrade head

# Hoặc sử dụng script
python -m alembic upgrade head
```

## 🐳 Docker Setup

### Khởi động tất cả services

```bash
docker compose up -d
```

### Khởi động riêng backend

```bash
docker compose up backend -d
```

### Xem logs

```bash
docker compose logs -f backend
```

## 🏃 Chạy ứng dụng

### Development mode

```bash
python run.py
```

Ứng dụng sẽ chạy tại `http://localhost:8000`

### Production mode

```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## 📁 Cấu trúc dự án

```
backend/
├── src/app/
│   ├── main.py              # Entry point
│   ├── api/                 # API routes
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── crud/                # CRUD operations
│   ├── services/            # Business logic
│   ├── core/                # Core utilities
│   │   ├── auth.py          # Authentication
│   │   ├── config.py        # Settings
│   │   ├── logger.py        # Logging setup
│   │   └── setup.py         # Application setup
│   ├── ai/                  # AI/ML modules
│   ├── middleware/          # Custom middleware
│   └── config/              # Configuration files
├── migrations/              # Alembic migrations
├── tests/                   # Test files
├── scripts/
│   ├── run_tests.sh        # Test runner
│   └── setup_test_env.sh   # Test environment setup
├── requirements.txt         # Dependencies
├── requirements-dev.txt     # Dev dependencies
├── requirements-test.txt    # Test dependencies
├── docker-compose.yml       # Docker composition
├── Dockerfile               # Docker image
└── Makefile                 # Make commands

```

## 🧪 Testing

### Chạy tất cả tests

```bash
make test
```

### Chạy tests với coverage

```bash
make test-cov
```

### Chạy tests song song (nhanh hơn)

```bash
make test-parallel
```

### Watch mode (tự động chạy khi code thay đổi)

```bash
make test-watch
```

### Chỉ unit tests

```bash
make test-unit
```

### Chỉ API tests

```bash
make test-api
```

### Chạy lại tests đã failed

```bash
make test-failed
```

### Thiết lập môi trường test

```bash
make setup-test
```

## 🗄️ Database

### Migrations

#### Tạo migration mới

```bash
cd src
alembic revision --autogenerate -m "Mô tả thay đổi"
```

#### Áp dụng migrations

```bash
cd src
alembic upgrade head
```

#### Rollback migration

```bash
cd src
alembic downgrade -1
```

#### Xem lịch sử migrations

```bash
cd src
alembic history
```

## 📚 API Documentation

### Swagger UI

```
http://localhost:8000/docs
```

### ReDoc

```
http://localhost:8000/redoc
```

## 🔐 Authentication

API sử dụng JWT tokens cho authentication.

### Lấy token

```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"pass"}'
```

### Sử dụng token

```bash
curl -X GET "http://localhost:8000/api/protected" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## ⚙️ Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379

# JWT
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# MQTT
MQTT_BROKER=localhost
MQTT_PORT=1883

# Logging
LOG_LEVEL=INFO
LOG_DIR=./log
```

## 📝 Make Commands

```bash
make help              # Hiển thị tất cả commands
make test              # Chạy tests
make test-cov          # Tests với coverage
make test-parallel     # Tests song song
make test-watch        # Watch mode
make setup-test        # Setup test environment
make docker-test-up    # Khởi động test database
make docker-test-down  # Dừng test database
```

## 🛠️ Development

### Code Quality

Dự án tuân thủ các quy tắc clean code:

- Meaningful names cho variables, functions, classes
- Single responsibility principle
- DRY (Don't Repeat Yourself)
- Proper error handling
- Type hints

### Commit Convention

```bash
git commit -m "type(scope): description"
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 📦 Dependencies

### Core

- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **SQLAlchemy** - ORM
- **Pydantic** - Data validation
- **FastCRUD** - CRUD helper

### Database

- **PostgreSQL** - Database
- **Alembic** - Migrations
- **asyncpg** - Async PostgreSQL driver
- **psycopg2-binary** - PostgreSQL adapter

### Cache & Queue

- **Redis** - Cache & message broker
- **arq** - Task queue

### AI & LLM

- **openai** - OpenAI API
- **google-generativeai** - Google Generative AI
- **torch** - PyTorch
- **mcp** - Model Context Protocol

### Others

- **paho-mqtt** - MQTT client
- **websockets** - WebSocket support
- **APScheduler** - Task scheduling
- **Loguru** - Logging

## 🤝 Contributing

1. Tạo feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "feat: your message"`
3. Push to branch: `git push origin feature/your-feature`
4. Mở Pull Request

## 📄 License

Xem file LICENSE để biết chi tiết.

## 📞 Support

Nếu có vấn đề, vui lòng mở issue hoặc liên hệ team phát triển.
