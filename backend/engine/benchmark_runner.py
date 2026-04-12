"""
RaceDB — Benchmark Runner (v2)

Fix #7:  p95 latency uses safe percentile calculation.
Fix #8:  Benchmark results are persisted to benchmark_results + anomaly_log.
"""
import uuid
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

from db.connection import get_connection, close_resources
from db.executor import execute_query_safely
from engine.anomaly_detector import detect_anomalies

# ── Workload patterns ────────────────────────────────────────────────────
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
    acc_ids = random.sample(range(1, 11), 2)
    return {"acc1": acc_ids[0], "acc2": acc_ids[1], "amount": round(random.uniform(10, 500), 2)}


def _execute_workload_txn(
    txn_index: int, queries: List[str], isolation_level: str
) -> Dict[str, Any]:
    txn_id = f"BenchT{txn_index}"
    steps: List[Dict[str, Any]] = []

    conn = None
    try:
        conn = get_connection(isolation_level)
    except Exception as exc:
        return {"txn_id": txn_id, "status": "FAILED", "latency_ms": 0, "steps": [], "error": str(exc)}

    t_start = time.perf_counter()
    status = "SUCCESS"

    execute_query_safely(conn, "START TRANSACTION")

    step_no = 0
    for query_tpl in queries:
        step_no += 1
        query = query_tpl.format(**_random_params())

        exec_res = execute_query_safely(conn, query)
        steps.append({
            "step": step_no,
            "txn_id": txn_id,
            "query": query,
            "status": exec_res.status,
            "latency_ms": exec_res.latency_ms,
            "error": exec_res.error,
        })

        if exec_res.status in ("FAILED", "DEADLOCK", "TIMEOUT"):
            status = exec_res.status
            break

    if status == "SUCCESS":
        c_res = execute_query_safely(conn, "COMMIT")
        if c_res.status in ("FAILED", "DEADLOCK", "TIMEOUT"):
            status = c_res.status
    else:
        execute_query_safely(conn, "ROLLBACK")

    close_resources(conn)
    total_latency = round((time.perf_counter() - t_start) * 1000, 3)

    return {"txn_id": txn_id, "status": status, "latency_ms": total_latency, "steps": steps}


def _safe_percentile(sorted_latencies: List[float], pct: float) -> float:
    """
    Fix #7: Calculate percentile safely regardless of sample size.
    Uses linear interpolation matching numpy.percentile behavior.
    """
    n = len(sorted_latencies)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_latencies[0]
    # Linear interpolation
    idx = (pct / 100.0) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return round(sorted_latencies[lo] + frac * (sorted_latencies[hi] - sorted_latencies[lo]), 2)


def _save_benchmark_result(
    total, successful, aborted, deadlocks,
    anomalies_count, avg_latency, p50_latency, p95_latency,
    throughput, isolation_level, pattern, concurrency_level,
    anomaly_list,
) -> int:
    """Fix #8: Persist benchmark_results row and anomaly_log rows; return run_id."""
    try:
        conn = get_connection("READ COMMITTED")
        conn.autocommit = False
        cur = conn.cursor()

        cur.execute(
            """INSERT INTO benchmark_results
               (total_transactions, successful, aborted, deadlocks, anomalies_detected,
                avg_latency_ms, throughput_tps, isolation_level, pattern, concurrency_level)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (total, successful, aborted, deadlocks, anomalies_count,
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


def run_benchmark(
    num_transactions: int,
    concurrency_level: int,
    pattern: str,
    isolation_level: str,
) -> Dict[str, Any]:
    query_template = PATTERNS.get(pattern, MIXED)

    results: List[Dict[str, Any]] = []
    all_steps: List[Dict[str, Any]] = []

    t_wall_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency_level) as pool:
        futures = {
            pool.submit(_execute_workload_txn, i, query_template, isolation_level): i
            for i in range(1, num_transactions + 1)
        }
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            all_steps.extend(res.get("steps", []))

    wall_time = time.perf_counter() - t_wall_start

    # ── Metrics ──────────────────────────────────────────────────────────
    successful = sum(1 for r in results if r["status"] == "SUCCESS")
    aborted = sum(1 for r in results if r["status"] not in ("SUCCESS", "DEADLOCK"))
    deadlocks = sum(1 for r in results if r["status"] == "DEADLOCK")

    latencies = sorted([r["latency_ms"] for r in results if r["latency_ms"] > 0])
    avg_latency = round(statistics.mean(latencies), 2) if latencies else 0.0
    p50_latency = _safe_percentile(latencies, 50)
    p95_latency = _safe_percentile(latencies, 95)
    throughput = round(num_transactions / wall_time, 2) if wall_time > 0 else 0.0

    # ── Anomalies ────────────────────────────────────────────────────────
    anomalies = detect_anomalies(all_steps, isolation_level)

    # Fix #8: Persist to DB; returns auto-incremented run_id
    run_id = _save_benchmark_result(
        num_transactions, successful, aborted, deadlocks,
        len(anomalies), avg_latency, p50_latency, p95_latency,
        throughput, isolation_level, pattern, concurrency_level,
        anomalies,
    )

    return {
        "run_id": run_id,
        "total_transactions": num_transactions,
        "successful": successful,
        "aborted": aborted,
        "deadlocks": deadlocks,
        "anomalies_detected": len(anomalies),
        "avg_latency_ms": avg_latency,
        "p50_latency_ms": p50_latency,
        "p95_latency_ms": p95_latency,
        "throughput_tps": throughput,
        "isolation_level": isolation_level,
        "pattern": pattern,
        "concurrency_level": concurrency_level,
        "anomalies": anomalies,
    }
