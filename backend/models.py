"""
RaceDB — Pydantic request/response models
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ───────────────────────────────── Debug ─────────────────────────────────

class TransactionStep(BaseModel):
    step: int = Field(..., description="Global execution order index (1-N)")
    query: str = Field(..., description="SQL statement to execute")


class DebugRequest(BaseModel):
    isolation_level: str = Field("REPEATABLE READ", description="MySQL isolation level")
    transactions: Dict[str, List[TransactionStep]] = Field(
        ...,
        description="Map of transaction name → ordered steps",
        example={
            "T1": [
                {"step": 1, "query": "SELECT balance FROM accounts WHERE account_id=1"},
                {"step": 3, "query": "UPDATE accounts SET balance=balance-100 WHERE account_id=1"},
                {"step": 5, "query": "COMMIT"},
            ],
            "T2": [
                {"step": 2, "query": "SELECT balance FROM accounts WHERE account_id=1"},
                {"step": 4, "query": "UPDATE accounts SET balance=balance+100 WHERE account_id=2"},
                {"step": 6, "query": "COMMIT"},
            ],
        },
    )


class StepResult(BaseModel):
    step: int
    txn_id: str
    query: str
    status: str
    latency_ms: float
    result_rows: Optional[List[Any]] = None
    error: Optional[str] = None


class DebugResponse(BaseModel):
    run_id: str
    isolation_level: str
    steps: List[StepResult]
    anomalies: List[AnomalyItem] = []
    summary: Dict[str, Any] = {}


# ──────────────────────────────── Benchmark ──────────────────────────────

class BenchmarkRequest(BaseModel):
    num_transactions: int = Field(50, ge=1, le=1000)
    concurrency_level: int = Field(10, ge=1, le=100)
    pattern: str = Field("mixed", pattern="^(read-heavy|write-heavy|mixed)$")
    isolation_level: str = Field("READ COMMITTED")


class AnomalyItem(BaseModel):
    type: str
    description: str
    txn_ids: Optional[str] = None


class BenchmarkResponse(BaseModel):
    run_id: int
    total_transactions: int
    successful: int
    aborted: int
    deadlocks: int
    anomalies_detected: int
    avg_latency_ms: float
    throughput_tps: float
    isolation_level: str
    pattern: str
    concurrency_level: int
    anomalies: List[AnomalyItem] = []


# ─────────────────────────────── Logs / History ──────────────────────────

class LogEntry(BaseModel):
    log_id: int
    run_id: Optional[str]
    txn_id: Optional[str]
    query_text: Optional[str]
    status: str
    latency_ms: Optional[float]
    error_msg: Optional[str]
    executed_at: str


class BenchmarkSummary(BaseModel):
    run_id: int
    total_transactions: int
    successful: int
    aborted: int
    deadlocks: int
    anomalies_detected: int
    avg_latency_ms: float
    throughput_tps: float
    isolation_level: str
    pattern: str
    concurrency_level: int
    timestamp: str
