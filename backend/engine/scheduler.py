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
    Enables genuine InnoDB Lock Contention and Deadlock errors organically!
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
        worker = DebugWorkerThread(txn_id, isolation_level, scheduler=None)
        worker.start()
        workers[txn_id] = worker
        
    # Synchronization wait to let connections open
    time.sleep(0.2)

    step_results = []
    
    # ── Orchestration Loop ──────────────────────────────────────────────────
    for step_info in all_steps:
        txn_id = step_info["txn_id"]
        step_no = step_info["step"]
        query = step_info["query"]
        
        worker = workers[txn_id]
        
        if worker.fatal_error:
            step_results.append({
                "step": step_no, "txn_id": txn_id, "query": query, 
                "status": "ABORTED (PREV ERROR)", "latency_ms": 0.0, "error": worker.last_result.get("error")
            })
            continue
            
        # Is the worker still blocked on a PREVIOUS query?
        if worker.current_query is not None:
            # We cannot dispatch a new step to a thread already locked.
            # We flag this as an orchestration violation or organic block.
            step_results.append({
                "step": step_no, "txn_id": txn_id, "query": query, 
                "status": "BLOCKED", "latency_ms": 0.0, "error": "Thread still locked on previous query."
            })
            continue

        worker.dispatch_step(step_no, query)
        
        # Wait for the thread to complete the step. 
        # Crucial Timeout! If Thread hits an InnoDB row lock, it blocks natively.
        # We cap the wait at 100ms. If it exceeds 100ms, we assume it's WAITING.
        completed = worker.completed_event.wait(timeout=0.1)
        
        if not completed:
            # Organic MySQL lock wait detected! We move to the next orchestrated step.
            step_results.append({
                "step": step_no, 
                "txn_id": txn_id, 
                "query": query, 
                "status": "WAITING (LOCK)", 
                "latency_ms": 100.0,
                "error": "Thread naturally blocked waiting for InnoDB lock."
            })
        else:
            # Step completed successfully or fatally
            res = worker.last_result
            step_results.append(dict(res))
            _log_step(run_id, step_no, txn_id, query, res)

    # After iterating schedule, forcefully sweep remaining blocked locks.
    time.sleep(0.1)
    for txn_id, worker in workers.items():
        if worker.current_query is not None and worker.completed_event.is_set():
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
            "anomalies_found": len(anomalies)
        }
    }


def _log_step(run_id: str, step: int, txn_id: str, query: str, result: Dict[str, Any]):
    try:
        from db.connection import get_connection
        conn = get_connection("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO execution_log
               (run_id, session_id, txn_id, query_text, status, latency_ms, error_msg)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (run_id, f"debug-step-{step}", txn_id, query, result["status"], result["latency_ms"], result.get("error"))
        )
        cur.close()
        conn.close()
    except Exception:
        pass
