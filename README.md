# RaceDB 
**Real-Time Data Consistency Debugger — Transaction Concurrency Testing & Benchmarking System**

MySQL · FastAPI

---

## Quick Start

### 1. MySQL Setup

```bash
mysql -u root -p < database/01_schema.sql
mysql -u root -p < database/02_seed.sql
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API Docs: http://localhost:8000/api/docs

### 3. Frontend

Open http://localhost:8000 in your browser (served by FastAPI).

Or open `frontend/index.html` directly in a browser (you'll need CORS).

---

## Environment

Copy `.env.example` → `.env` and update credentials:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=racedb
DB_UNIX_SOCKET=/tmp/mysql.sock
```

---

## Architecture

```
Frontend (4-tab SPA: Debug / Benchmark / Logs / History)
    ↓ REST
FastAPI Backend
    ↓
Debug Engine (deterministic scheduler, per-txn MySQL sessions)
Benchmark Engine (ThreadPoolExecutor, concurrent database workload)
Anomaly Detector (post-run log analysis)
    ↓
MySQL 8 Database (racedb schema)
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/run-debug` | Run a deterministic debug scenario |
| POST | `/run-benchmark` | Run a concurrent benchmark |
| GET | `/logs` | Paginated execution log |
| GET | `/benchmark-results` | All historical runs |
| GET | `/benchmark-results/{run_id}` | Run detail + anomalies |
| GET | `/lock-status` | Live Database trx + lock waits |
| GET | `/accounts` | Current account state |
| POST | `/accounts/reset` | Reset account balances |

---
