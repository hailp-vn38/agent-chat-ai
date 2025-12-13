# Home Chat Bot

Một ứng dụng chat được hỗ trợ bởi AI với khả năng tích hợp các mô-đun MCP, streaming audio, MQTT, và nhiều tính năng advanced khác.

## 🌟 Đặc điểm chính

- **AI-Powered Chat** - Tích hợp các LLM (OpenAI, Google Generative AI, v.v.)
- **Real-time Communication** - WebSocket, MQTT, streaming responses
- **Audio Processing** - Xử lý âm thanh, text-to-speech, speech-to-text
- **MCP Integration** - Model Context Protocol support
- **Multi-language** - Hỗ trợ đa ngôn ngữ (i18n)
- **User Management** - Authentication, authorization, profiles
- **Database** - PostgreSQL + SQLAlchemy ORM
- **Caching** - Redis cache layer
- **Task Scheduling** - APScheduler for background jobs
- **Responsive UI** - React + Tailwind CSS frontend

## 📋 Yêu cầu

- **Docker & Docker Compose** - Để chạy toàn bộ stack
- **Python 3.11+** - Cho backend (nếu run locally)
- **Node.js 18+** - Cho frontend (nếu run locally)
- **PostgreSQL 14+** - Database
- **Redis** - Caching & message broker

## 🚀 Quick Start

### Với Docker Compose (Recommended)

#### 1. Clone repository

```bash
git clone <repository-url>
cd open_source
```

#### 2. Tạo environment file

```bash
cp .env.example .env
# Chỉnh sửa .env với cấu hình của bạn
```

#### 3. Khởi động tất cả services

```bash
# Development mode
make dev

# Hoặc chạy trực tiếp
docker compose up -d
```

#### 4. Truy cập ứng dụng

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc

### Local Setup

#### Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt

# Setup database
cd src
alembic upgrade head

# Chạy ứng dụng
cd ..
python run.py
```

#### Frontend

```bash
cd frontend

# Cài đặt dependencies
npm install

# Chạy development server
npm run dev
```

## 📁 Cấu trúc Project

```
.
├── backend/                    # FastAPI backend
│   ├── src/
│   │   ├── app/               # Main application
│   │   │   ├── main.py        # Entry point
│   │   │   ├── api/           # API routes
│   │   │   ├── models/        # SQLAlchemy models
│   │   │   ├── schemas/       # Pydantic schemas
│   │   │   ├── services/      # Business logic
│   │   │   ├── crud/          # Database operations
│   │   │   ├── core/          # Core utilities
│   │   │   ├── ai/            # AI/ML modules
│   │   │   └── middleware/    # Custom middleware
│   │   ├── migrations/        # Alembic migrations
│   │   └── alembic.ini
│   ├── tests/                 # Test files
│   ├── scripts/               # Helper scripts
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── requirements-test.txt
│   ├── Dockerfile
│   ├── Makefile
│   └── README.md
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── hooks/             # Custom hooks
│   │   ├── services/          # API services
│   │   ├── store/             # Jotai state
│   │   ├── types/             # TypeScript types
│   │   ├── layouts/           # Layout templates
│   │   ├── locales/           # i18n translations
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/                # Static assets
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── Dockerfile
│   └── README.md
│
├── data/                       # Data volumes
│   ├── backend/               # Backend data
│   ├── postgres/              # PostgreSQL data
│   ├── redis/                 # Redis data
│   ├── mcp/                   # MCP config
│   └── openmemory/            # Memory storage
│
├── scripts/                    # Project scripts
│   └── init-volumes.sh        # Initialize volumes
│
├── docker-compose.yml          # Main compose file
├── docker-compose.dev.yml      # Dev overrides
├── docker-compose.prod.yml     # Production overrides
├── docker-compose.test.yml     # Test overrides
├── default.conf                # Nginx config
├── Makefile                    # Make commands
└── README.md                   # This file
```

## 🛠️ Make Commands

### Thông tin chung

```bash
make help              # Hiển thị tất cả commands
```

### Docker Commands

```bash
make dev               # Khởi động dev environment
make prod              # Khởi động production environment
make down              # Dừng tất cả containers
make ps                # Liệt kê running containers
make logs              # Xem logs tất cả services
make logs-backend      # Xem logs backend
make logs-frontend     # Xem logs frontend
make build             # Build tất cả images
make rebuild           # Rebuild without cache
make prune             # Xóa unused resources
```

### Service Commands

```bash
make shell             # Truy cập shell backend
make backend           # Khởi động backend service
make frontend          # Khởi động frontend service
make db-shell          # PostgreSQL shell
make redis-shell       # Redis shell
```

### Database Commands

```bash
make migrate           # Run migrations
make db-backup         # Backup database
make db-restore        # Restore database
make health            # Check services health
```

### Development

```bash
make test              # Run tests
make coverage          # Run tests with coverage
make lint              # Lint code
make stop              # Dừng services
make clean             # Xóa containers
```

## 📚 Backend Documentation

Xem [backend/README.md](backend/README.md) để biết chi tiết:

- Setup & installation
- Database migrations
- API endpoints
- Testing guide
- Authentication
- Configuration

## 🎨 Frontend Documentation

Xem [frontend/README.md](frontend/README.md) để biết chi tiết:

- Development setup
- Component structure
- State management
- API integration
- i18n configuration
- Styling guide

## 🧪 Testing

### Backend Tests

```bash
# Khởi động test database
make docker-test-up

# Chạy tests
cd backend
make test

# Tests with coverage
make test-cov

# Cleanup
make docker-test-down
```

### Frontend Tests

```bash
cd frontend
npm run test
```

## 🔐 Environment Configuration

### Required Variables

#### Backend

```env
# Database
DATABASE_URL=postgresql://user:password@postgres:5432/dbname

# Redis
REDIS_URL=redis://redis:6379

# JWT & Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# LLM Services
OPENAI_API_KEY=your-key
GOOGLE_API_KEY=your-key

# MQTT
MQTT_BROKER=mqtt
MQTT_PORT=1883

# Logging
LOG_LEVEL=INFO
```

#### Frontend

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

## 🔄 Data Persistence

Tất cả data được lưu trong `data/` folder:

- **PostgreSQL**: `data/postgres/`
- **Redis**: `data/redis/`
- **Backend logs**: `data/backend/log/`
- **MCP config**: `data/mcp/`

## 📊 Architecture

### Layers

```
┌─────────────────────────────┐
│       Frontend (React)       │
│   - UI Components            │
│   - State Management (Jotai) │
│   - React Query              │
└──────────────┬──────────────┘
               │
        ┌──────▼──────┐
        │  API Layer  │
        │  (Axios)    │
        └──────┬──────┘
               │
┌──────────────▼─────────────────┐
│    Backend (FastAPI)           │
│ - API Routes                   │
│ - Authentication               │
│ - Business Logic               │
│ - AI Integration               │
└──────────────┬──────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼──┐  ┌────▼───┐  ┌──▼─────┐
│  DB  │  │ Redis  │  │  MQTT  │
└──────┘  └────────┘  └────────┘
```

### Technology Stack

**Frontend:**

- React 19
- TypeScript
- Vite
- Tailwind CSS
- Radix UI
- React Router v7
- React Query
- Jotai
- i18next

**Backend:**

- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Redis
- Alembic (migrations)
- Pydantic
- FastCRUD
- APScheduler
- MQTT

**DevOps:**

- Docker
- Docker Compose
- PostgreSQL
- Redis

## 🚢 Deployment

### Production Deployment

```bash
make prod
```

File `docker-compose.prod.yml` chứa cấu hình production-optimized.

### Environment Setup

1. Cấu hình `.env` cho production
2. Cấu hình SSL/TLS certificates
3. Cấu hình database backup
4. Setup monitoring & logging

## 🔗 API Documentation

API documentation tự động tạo bởi FastAPI:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 📝 Git Workflow

```bash
# Feature branch
git checkout -b feature/your-feature

# Commit with conventional commits
git commit -m "feat(backend): add new endpoint"
git commit -m "fix(frontend): fix button styling"
git commit -m "docs(readme): update setup guide"

# Push & create PR
git push origin feature/your-feature
```

Commit types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## 🤝 Contributing

1. **Fork repository**
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Make changes** theo clean code guidelines
4. **Commit changes**: `git commit -m "feat: description"`
5. **Push to branch**: `git push origin feature/amazing-feature`
6. **Open Pull Request**

### Guidelines

- Tuân thủ code style (ESLint, Black, Flake8)
- Viết tests cho features mới
- Update documentation
- Follow commit convention

## 📖 Documentation

- [Backend README](backend/README.md) - Backend setup & API docs
- [Frontend README](frontend/README.md) - Frontend setup & component docs

## 🐛 Troubleshooting

### Database Connection Error

```bash
# Check PostgreSQL
make db-shell

# Or restart database
docker compose restart postgres
```

### Port Already in Use

```bash
# Change ports in docker-compose.yml
# Or kill process
sudo lsof -i :3000  # for port 3000
```

### Permission Denied

```bash
# Fix script permissions
chmod +x scripts/*.sh
```

## 📞 Support

Nếu gặp vấn đề:

1. Kiểm tra logs: `make logs`
2. Xem troubleshooting section
3. Mở issue trên GitHub
4. Liên hệ team phát triển

## 📄 License

Xem file LICENSE để biết chi tiết.

## 🎯 Roadmap

- [ ] End-to-end encryption
- [ ] Voice call support
- [ ] Advanced analytics
- [ ] Mobile app
- [ ] Plugin system
- [ ] Custom AI models support

## 🙌 Acknowledgments

- FastAPI - Modern API framework
- React - UI library
- PostgreSQL - Database
- All open source contributors

---

**Happy Coding! 🚀**
