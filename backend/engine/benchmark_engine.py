"""
RaceDB — Benchmark Engine
Generates + executes concurrent transaction workloads against MySQL (InnoDB).
Uses ThreadPoolExecutor for real concurrency.
"""
from __future__ import annotations
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import mysql.connector

from database import get_connection
from engine.anomaly_detector import detect_anomalies

# ── Workload patterns ─────────────────────────────────────────────────────

READ_HEAVY = [
    "SELECT balance FROM accounts WHERE account_id = {acc1}",
    "SELECT balance FROM accounts WHERE account_id = {acc2}",
    "SELECT * FROM accounts ORDER BY balance DESC LIMIT 5",
    "UPDATE accounts SET balance = balance - {amount} WHERE account_id = {acc1}",
]

WRITE_HEAVY = [
    "SELECT balance FROM accounts WHERE account_id = {acc1}",
    "UPDATE accounts SET balance = balance - {amount} WHERE account_id = {acc1}",
    "UPDATE accounts SET balance = balance + {amount} WHERE account_id = {acc2}",
    "UPDATE accounts SET version = version + 1 WHERE account_id = {acc1}",
]

MIXED = [
    "SELECT balance FROM accounts WHERE account_id = {acc1}",
    "UPDATE accounts SET balance = balance - {amount} WHERE account_id = {acc1}",
    "SELECT balance FROM accounts WHERE account_id = {acc2}",
    "UPDATE accounts SET balance = balance + {amount} WHERE account_id = {acc2}",
]

PATTERNS = {"read-heavy": READ_HEAVY, "write-heavy": WRITE_HEAVY, "mixed": MIXED}


def _random_params() -> Dict[str, Any]:
    acc_ids = random.sample(range(1, 11), 2)  # pick 2 distinct account IDs from our 10
    return {
        "acc1": acc_ids[0],
        "acc2": acc_ids[1],
        "amount": round(random.uniform(10, 500), 2),
    }


def _execute_transaction(
    txn_index: int,
    queries: List[str],
    isolation_level: str,
    run_uuid: str,
) -> Dict[str, Any]:
    """Execute one auto-generated transaction. Returns metrics dict."""
    txn_id = f"T{txn_index}"
    steps: List[Dict[str, Any]] = []
    status = "SUCCESS"
    t_start = time.perf_counter()

    try:
        conn = get_connection(isolation_level)
        cursor = conn.cursor()
        conn.start_transaction()

        step_no = 0
        for query_tpl in queries:
            step_no += 1
            params = _random_params()
            query = query_tpl.format(**params)
            t0 = time.perf_counter()
            step_status = "SUCCESS"
            err = None

            try:
                cursor.execute(query)
                if query.strip().upper().startswith("SELECT"):
                    cursor.fetchall()
            except mysql.connector.errors.DatabaseError as exc:
                err = str(exc)
                if exc.errno == 1213:
                    step_status = "DEADLOCK"
                    status = "DEADLOCK"
                elif exc.errno == 1205:
                    step_status = "TIMEOUT"
                    status = "FAILED"
                else:
                    step_status = "FAILED"
                    status = "FAILED"
                break  # abort remaining steps on error

            latency = round((time.perf_counter() - t0) * 1000, 3)
            steps.append({
                "step": step_no,
                "txn_id": txn_id,
                "query": query,
                "status": step_status,
                "latency_ms": latency,
                "error": err,
            })

        if status == "SUCCESS":
            conn.commit()
        else:
            conn.rollback()

        cursor.close()
        conn.close()

    except Exception as exc:
        status = "FAILED"
        steps.append({
            "step": 0,
            "txn_id": txn_id,
            "query": "CONNECT",
            "status": "FAILED",
            "latency_ms": 0,
            "error": str(exc),
        })

    total_latency = round((time.perf_counter() - t_start) * 1000, 3)

    # Persist steps to execution_log
    _log_steps(run_uuid, steps)

    return {
        "txn_id": txn_id,
        "status": status,
        "latency_ms": total_latency,
        "steps": steps,
    }


def run_benchmark(
    num_transactions: int,
    concurrency_level: int,
    pattern: str,
    isolation_level: str,
) -> Dict[str, Any]:
    """Execute the full benchmark workload and return aggregate metrics + anomalies."""
    run_uuid = str(uuid.uuid4())[:8]
    query_template = PATTERNS.get(pattern, MIXED)

    results: List[Dict[str, Any]] = []
    all_steps: List[Dict[str, Any]] = []

    t_wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency_level) as pool:
        futures = {
            pool.submit(
                _execute_transaction, i, query_template, isolation_level, run_uuid
            ): i
            for i in range(1, num_transactions + 1)
        }
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except Exception as exc:
                res = {
                    "txn_id": f"T{futures[fut]}",
                    "status": "FAILED",
                    "latency_ms": 0,
                    "steps": [],
                }
            results.append(res)
            all_steps.extend(res.get("steps", []))

    wall_time = time.perf_counter() - t_wall_start

    # ── Aggregate metrics ────────────────────────────────────────────────
    successful = sum(1 for r in results if r["status"] == "SUCCESS")
    aborted = sum(1 for r in results if r["status"] not in ("SUCCESS",))
    deadlocks = sum(1 for r in results if r["status"] == "DEADLOCK")
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    throughput = round(num_transactions / wall_time, 2) if wall_time > 0 else 0.0

    # ── Anomaly detection ─────────────────────────────────────────────────
    anomalies = detect_anomalies(all_steps, isolation_level)

    # ── Persist aggregate row ─────────────────────────────────────────────
    run_id = _save_benchmark_result(
        num_transactions, successful, aborted, deadlocks,
        len(anomalies), avg_latency, throughput,
        isolation_level, pattern, concurrency_level, anomalies
    )

    return {
        "run_id": run_id,
        "total_transactions": num_transactions,
        "successful": successful,
        "aborted": aborted,
        "deadlocks": deadlocks,
        "anomalies_detected": len(anomalies),
        "avg_latency_ms": avg_latency,
        "throughput_tps": throughput,
        "isolation_level": isolation_level,
        "pattern": pattern,
        "concurrency_level": concurrency_level,
        "anomalies": anomalies,
    }


def _log_steps(run_uuid: str, steps: List[Dict[str, Any]]) -> None:
    """Bulk-insert step records into execution_log (best-effort)."""
    if not steps:
        return
    try:
        from database import get_connection as _gc
        conn = _gc("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        cur.executemany(
            """INSERT INTO execution_log
               (run_id, session_id, txn_id, query_text, status, latency_ms, error_msg)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (
                    run_uuid,
                    f"bench-{s['txn_id']}",
                    s["txn_id"],
                    s.get("query"),
                    s.get("status", "SUCCESS"),
                    s.get("latency_ms"),
                    s.get("error"),
                )
                for s in steps
            ],
        )
        cur.close()
        conn.close()
    except Exception:
        pass


def _save_benchmark_result(
    total, successful, aborted, deadlocks,
    anomalies, avg_latency, throughput,
    isolation_level, pattern, concurrency_level,
    anomaly_list,
) -> int:
    """Persist benchmark_results row and anomaly_log rows; return run_id."""
    try:
        from database import get_connection as _gc
        conn = _gc("READ COMMITTED")
        conn.autocommit = False
        cur = conn.cursor()

        cur.execute(
            """INSERT INTO benchmark_results
               (total_transactions, successful, aborted, deadlocks, anomalies_detected,
                avg_latency_ms, throughput_tps, isolation_level, pattern, concurrency_level)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (total, successful, aborted, deadlocks, anomalies,
             avg_latency, throughput, isolation_level, pattern, concurrency_level),
        )
        run_id = cur.lastrowid

        for a in anomaly_list:
            cur.execute(
                """INSERT INTO anomaly_log (run_id, type, description, txn_ids)
                   VALUES (%s, %s, %s, %s)""",
                (run_id, a["type"], a["description"], a.get("txn_ids")),
            )

        conn.commit()
        cur.close()
        conn.close()
        return run_id
    except Exception:
        return -1
