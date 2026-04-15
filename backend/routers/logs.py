"""
RaceDB — /logs, /benchmark-results, /lock-status routers
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from models import LogEntry, BenchmarkSummary
from db.connection import get_connection
import mysql.connector

router = APIRouter()


def _row_to_dict(cursor, row) -> dict:
    cols = [d[0] for d in cursor.description]
    return {c: (str(v) if not isinstance(v, (int, float, type(None))) else v)
            for c, v in zip(cols, row)}


# ── Execution Log ────────────────────────────────────────────────────────

@router.get("/logs", tags=["Logs"])
async def get_logs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Retrieve paginated execution log entries."""
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM execution_log WHERE status=%s ORDER BY executed_at DESC LIMIT %s OFFSET %s",
                (status.upper(), limit, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM execution_log ORDER BY executed_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
        rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"logs": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Benchmark Results ────────────────────────────────────────────────────

@router.get("/benchmark-results", tags=["Benchmark"])
async def get_benchmark_results(limit: int = Query(50, ge=1, le=200)):
    """Return all historical benchmark runs (most recent first)."""
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM benchmark_results ORDER BY timestamp DESC LIMIT %s", (limit,)
        )
        rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"results": rows, "count": len(rows)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/benchmark-results/{run_id}", tags=["Benchmark"])
async def get_benchmark_detail(run_id: int):
    """Return a single benchmark run plus its anomaly log."""
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("SELECT * FROM benchmark_results WHERE run_id=%s", (run_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        result = _row_to_dict(cur, row)

        cur.execute("SELECT * FROM anomaly_log WHERE run_id=%s ORDER BY detected_at", (run_id,))
        anomalies = [_row_to_dict(cur, r) for r in cur.fetchall()]

        cur.close()
        conn.close()
        return {"result": result, "anomalies": anomalies}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Accounts ─────────────────────────────────────────────────────────────

@router.get("/accounts", tags=["Accounts"])
async def get_accounts():
    """Fetch current state of all accounts."""
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT * FROM accounts ORDER BY account_id")
        rows = [_row_to_dict(cur, r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return {"accounts": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/accounts/reset", tags=["Accounts"])
async def reset_accounts():
    """Reset all account balances to their original seeded values."""
    seed = [5000, 3200, 8750, 1200, 15000, 4500, 2800, 9300, 6100, 3750]
    try:
        conn = get_connection("READ COMMITTED")
        cur = conn.cursor()
        for i, bal in enumerate(seed, 1):
            cur.execute(
                "UPDATE accounts SET balance=%s, version=0 WHERE account_id=%s",
                (bal, i),
            )
        conn.commit()
        cur.close()
        conn.close()
        return {"message": "Accounts reset to seed values"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
