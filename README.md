# FunStuffBarn Agent-Etsy System - Phase 2 Complete

## Overview

This document summarizes the Phase 2 implementation: **Microservices Architecture with Tests & CI/CD**.

---

## ✅ Phase 2 Completed Features

### 1. Microservices Architecture
- **Shared Modules**: Config, Models, Exceptions, Resilience, Logging, Celery
- **5 Independent Agents**: Mercado, Creativo, Pinterest, Tienda, Estrategia
- **Orchestrator**: Coordinates daily cycles with dependency management
- **Event-Driven**: Celery + Redis for async task processing

### 2. Resilience Patterns
- **Circuit Breakers**: Per-service (Groq, Etsy, Printful, Trends, Pinterest)
- **Retry with Exponential Backoff**: Configurable policies per service
- **Rate Limiting**: Token bucket per API (Groq 10/s, Etsy 5/s, etc.)
- **Caching**: Redis + Memory fallback with TTL policies
- **Structured Logging**: JSON with correlation IDs, correlation ID propagation

### 3. Testing Infrastructure (>80% coverage target)
- **Unit Tests**: Config, Models, Exceptions, Resilience, Logging, Celery
- **Integration Tests**: Agent workflows, API endpoints
- **Contract Tests**: Schema validation between services
- **Chaos Tests**: Circuit breaker, retry, timeout scenarios

### 4. CI/CD Pipeline (GitHub Actions - Free tier)
- **Lint & Type Check**: Ruff, MyPy, Black
- **Unit + Integration Tests**: pytest with coverage >80%
- **Security Scan**: Trivy (vulnerabilities), Bandit (code)
- **Docker Build**: Multi-stage, multi-arch (amd64/arm64)
- **Deploy**: Staging (develop) → Production (release)

### 5. Observability Stack (Self-hosted, Free)
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards (system, agents, business)
- **Loki + Promtail**: Log aggregation
- **Health Checks**: `/health`, `/metrics` endpoints

### 6. Backup & Disaster Recovery
- **Daily Backup**: Reports, prompts, configs, designs
- **Retention**: 30d daily, 12w weekly, 12m monthly
- **rclone**: S3/GCS/GDrive backup targets
- **Encryption**: GPG for sensitive configs

### 5. Deployment (Free/low-cost)
- **Docker**: Multi-stage build, non-root, distroless-ready
- **Docker Compose**: Local dev + production stack
- **Launchd/launchd**: macOS service management
- **Caddy**: Auto-HTTPS reverse proxy (optional)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        DOCKER COMPOSE                        │
├─────────────────────────────────────────────────────────────┤
│  app (FastAPI) ◄──► redis ◄──► celery workers (5 queues)  │
│  │                         │                                │
│  │                         ├── mercado queue                 │
│  │                         ├── creativo queue                │
│  │                         ├── pinterest queue               │
│  │                         ├── tienda queue                  │
│  │                         ├── estrategia queue              │
│  │                         └── orchestrator queue            │
│  │                         │                                │
│  ▼                         ▼                                │
│  celery-beat ──► celery beat scheduler                       │
│  flower ◄───► monitoring                                    │
│  prometheus ◄──► grafana ◄──► loki ◄── promtail             │
│  backup (rclone) ──► S3/GCS/GDrive                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

```bash
# 1. Clone and configure
cd "/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard"
cp .env.example .env
# Edit .env with your API keys

# 2. Start all services
docker-compose up -d

# 3. Verify
curl http://localhost:8080/health
curl http://localhost:3000  # Grafana (admin/admin)
curl http://localhost:9090  # Prometheus
curl http://localhost:5555  # Flower (user:pass)
```

---

## 📋 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /health` | GET | System health check |
| `GET /metrics` | GET | Prometheus metrics |
| `POST /api/v1/agents/{type}/run` | POST | Run specific agent |
| `POST /api/v1/cycle/run` | POST | Trigger full daily cycle |
| `GET /api/v1/status/{task_id}` | GET | Task status |
| `GET /api/v1/reports/{type}` | GET | Get report by type/date |
| `GET /api/v1/agents` | GET | List available agents |

---

## 🧪 Running Tests

```bash
cd "/Users/javiermaldonadocorreaair/Tienda FunStuffBarn/dashboard"

# Unit tests
pytest tests/unit/ -v --cov=services --cov-fail-under=80

# Integration tests (requires Redis)
docker-compose up -d redis
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=services --cov-fail-under=80 --cov-report=html
```

---

## 📊 Monitoring

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / changeme |
| Prometheus | http://localhost:9090 | - |
| Flower | http://localhost:5555 | user / changeme |
| Prometheus | http://localhost:9090 | - |

---

## 🔧 Development Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Run single agent
docker-compose exec app python -m services.agents.mercado.tasks

# Run tests
pytest tests/ -v --cov=services --cov-fail-under=80

# Type checking
mypy services/

# Linting
ruff check .

# Format code
black services/ tests/
isort services/ tests/
```

---

## 🔐 Security Checklist

- [ ] All secrets in `.env` (never commit!)
- [ ] Rotate API keys quarterly
- [ ] Use Gmail App Passwords (not account password)
- [ ] Enable 2FA on all service accounts
- [ ] Review Docker image for vulnerabilities (`trivy scan`)
- [ ] Enable GitHub Dependabot alerts

---

## 📈 Next Steps (Phase 3)

- [ ] Feedback loop: Etsy sales → agent prompts
- [ ] A/B testing framework for listings
- [ ] Prompt deduplication (pHash)
- [ ] Dynamic seasonal calendar (Google Calendar API)
- [ ] Multi-user dashboard with RBAC
- [ ] Webhook support for Etsy/Printful events

---

**Built with ❤️ for FunStuffBarn**  
*Phase 2 Complete - Ready for Production*