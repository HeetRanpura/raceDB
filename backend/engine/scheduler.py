import uuid
import time
from typing import Dict, List, Any

from engine.transaction_engine import DebugWorkerThread
from engine.anomaly_detector import detect_anomalies


def run_debug_deterministic(
    transactions: Dict[str, List[Dict[str, Any]]],
    isolation_level: str,
) -> Dict[str, Any]:
    """
    Executes an interleaved transaction schedule deterministically across Threads.
    Enables genuine Database Lock Contention and Deadlock errors organically!
    """
    run_id = str(uuid.uuid4())[:8]

    # Flatten and globally sort all steps
    all_steps: List[Dict[str, Any]] = []
    for txn_id, steps in transactions.items():
        for s in steps:
            all_steps.append({"txn_id": txn_id, "step": s["step"], "query": s["query"]})
    all_steps.sort(key=lambda x: x["step"])

    # Boot Thread workers
    workers: Dict[str, DebugWorkerThread] = {}
    for txn_id in transactions.keys():
        worker = DebugWorkerThread(txn_id, isolation_level)
        worker.start()
        workers[txn_id] = worker

    # Synchronization wait to let connections open
    time.sleep(0.2)

    step_results: List[Dict[str, Any]] = []

    # ── Orchestration Loop ──────────────────────────────────────────────────
    for step_info in all_steps:
        txn_id = step_info["txn_id"]
        step_no = step_info["step"]
        query = step_info["query"]

        worker = workers[txn_id]

        if worker.fatal_error:
            step_results.append({
                "step": step_no, "txn_id": txn_id, "query": query,
                "status": "ABORTED", "latency_ms": 0.0,
                "error": worker.last_result.get("error") if worker.last_result else "Previous step failed",
            })
            continue

        # Fix #2: Use is_idle() (backed by completed_event) instead of current_query
        if not worker.is_idle():
            step_results.append({
                "step": step_no, "txn_id": txn_id, "query": query,
                "status": "BLOCKED", "latency_ms": 0.0,
                "error": "Thread still blocked on previous query.",
            })
            continue

        worker.dispatch_step(step_no, query)

        # Wait for the thread to complete the step.
        # If it hits an Database row lock, it blocks natively in MySQL.
        # We cap the wait at 100ms; if exceeded, we assume it's WAITING.
        completed = worker.completed_event.wait(timeout=0.1)

        if not completed:
            step_results.append({
                "step": step_no,
                "txn_id": txn_id,
                "query": query,
                "status": "WAITING (LOCK)",
                "latency_ms": 100.0,
                "error": "Thread naturally blocked waiting for Database lock.",
            })
        else:
            res = worker.last_result
            step_results.append(dict(res))
            _log_step(run_id, step_no, txn_id, query, res)

    # After iterating schedule, sweep remaining blocked ops that finished late.
    time.sleep(0.2)
    for txn_id, worker in workers.items():
        if not worker.is_idle():
            # Give it a final 200ms to complete
            worker.completed_event.wait(timeout=0.2)
        if worker.completed_event.is_set() and worker.last_result:
            # Check if this result was already captured above
            already_logged = any(
                s["txn_id"] == txn_id and s["step"] == worker.last_result.get("step")
                and s["status"] not in ("WAITING (LOCK)", "BLOCKED")
                for s in step_results
            )
            if not already_logged:
                res = worker.last_result
                step_results.append(dict(res))
                _log_step(run_id, res["step"], txn_id, res["query"], res)

    # Cleanup Threads
    for worker in workers.values():
        worker.shutdown()
        worker.join(timeout=0.5)

    # ── Post Analysis ────────────────────────────────────────────────────────
    anomalies = detect_anomalies(step_results, isolation_level)
    successful = sum(1 for s in step_results if s["status"] in ("SUCCESS", "COMMIT", "ROLLBACK"))

    return {
        "run_id": run_id,
        "isolation_level": isolation_level,
        "steps": step_results,
        "anomalies": anomalies,
        "summary": {
            "total_steps": len(step_results),
            "successful": successful,
            "failed": len(step_results) - successful,
            "anomalies_found": len(anomalies),
        },
    }


def _log_step(run_id: str, step: int, txn_id: str, query: str, result: Dict[str, Any]):
    """Write a single step result to execution_log (best-effort)."""
    try:
        from db.connection import get_connection
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        # Map non-ENUM statuses to SUCCESS for DB storage
        db_status = result["status"]
        if db_status not in ("SUCCESS", "FAILED", "DEADLOCK", "ROLLBACK", "TIMEOUT", "COMMIT",
                             "WAITING", "BLOCKED", "ABORTED"):
            db_status = "SUCCESS"
        cur.execute(
            """INSERT INTO execution_log
               (run_id, session_id, txn_id, query_text, status, latency_ms, error_msg)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (run_id, f"debug-step-{step}", txn_id, query,
             db_status, result["latency_ms"], result.get("error")),
        )
        cur.close()
        conn.close()
    except Exception:
        pass
