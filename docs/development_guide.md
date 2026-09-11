# Development Guide

This guide covers local environment setup, architecture workflows, and common developer tasks for **AI Job Agent India**.

---

## 1. Prerequisites

Ensure you have the following installed on your host system:
- **Docker & Docker Compose**
- **Python 3.11+**
- **Node.js 18+ (Node 20+ recommended)**
- **Git**

---

## 2. Setting Up the Environment

### Step 1: Clone Repository & Create `.env`
```bash
git clone https://github.com/vivans720/AI-Job-Search.git
cd AI-Job-Search
cp .env.example .env
```

Review `.env`. By default, it connects to PostgreSQL on `localhost:5432` and uses local ONNX embeddings (`BAAI/bge-small-en-v1.5`), meaning no paid cloud embedding APIs are required.

### Step 2: Boot PostgreSQL with pgvector
```bash
make db-up
```
Verify the container is healthy:
```bash
docker compose ps
```

### Step 3: Set Up Backend Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cd ..
```

### Step 4: Set Up Frontend
```bash
cd frontend
npm install
cd ..
```

---

## 3. Running Services

### Backend (FastAPI)
```bash
make backend
```
Access points:
- API Base: `http://localhost:8000`
- OpenAPI Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### Frontend (Next.js 15)
```bash
make frontend
```
Dashboard URL: `http://localhost:3000`

---

## 4. Ingestion & Matching Workflows

1. **Seed Candidate Resume Profile**:
   ```bash
   make seed
   ```
2. **Ingest Fresh Jobs**:
   ```bash
   make sync
   ```
3. **Execute Job Matching Evaluation**:
   ```bash
   make agent
   ```

---

## 5. Testing & Code Quality

Run tests:
```bash
make test
```

Run linter:
```bash
make lint
```

Clean build artifacts:
```bash
make clean
```
