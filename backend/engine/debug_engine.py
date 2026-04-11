"""
RaceDB — Debug Engine
Executes a deterministic, user-defined transaction schedule step-by-step.
Each transaction gets its own MySQL connection/session.
"""
from __future__ import annotations
import time
import uuid
from typing import Any, Dict, List

import mysql.connector

from database import get_connection
from engine.anomaly_detector import detect_anomalies


def run_debug(
    transactions: Dict[str, List[Dict[str, Any]]],
    isolation_level: str,
) -> Dict[str, Any]:
    """
    Execute an interleaved transaction schedule and return per-step results.

    `transactions` is already the validated dict from DebugRequest, where each
    value is a list of {"step": int, "query": str} dicts.
    """
    run_id = str(uuid.uuid4())[:8]

    # Flatten and sort all steps globally
    all_steps: List[Dict[str, Any]] = []
    for txn_id, steps in transactions.items():
        for s in steps:
            all_steps.append({"txn_id": txn_id, "step": s["step"], "query": s["query"]})
    all_steps.sort(key=lambda x: x["step"])

    # Open one connection per transaction (keep alive across steps)
    connections: Dict[str, Any] = {}
    cursors: Dict[str, Any] = {}
    for txn_id in transactions:
        try:
            conn = get_connection(isolation_level)
            connections[txn_id] = conn
            cursors[txn_id] = conn.cursor()
        except Exception as exc:
            # Clean up already-opened connections
            for c in connections.values():
                try:
                    c.close()
                except Exception:
                    pass
            raise RuntimeError(f"Cannot open connection for {txn_id}: {exc}") from exc

    step_results: List[Dict[str, Any]] = []

    for step_info in all_steps:
        txn_id = step_info["txn_id"]
        step_no = step_info["step"]
        query = step_info["query"].strip()
        conn = connections[txn_id]
        cursor = cursors[txn_id]

        result: Dict[str, Any] = {
            "step": step_no,
            "txn_id": txn_id,
            "query": query,
            "status": "SUCCESS",
            "latency_ms": 0.0,
            "result_rows": None,
            "error": None,
        }

        t0 = time.perf_counter()
        try:
            upper = query.upper().strip()

            if upper in ("COMMIT", "COMMIT;"):
                conn.commit()
                result["status"] = "SUCCESS"

            elif upper in ("ROLLBACK", "ROLLBACK;"):
                conn.rollback()
                result["status"] = "ROLLBACK"

            elif upper.startswith("START TRANSACTION") or upper.startswith("BEGIN"):
                cursor.execute(query)
                result["status"] = "SUCCESS"

            else:
                cursor.execute(query)
                if upper.startswith("SELECT"):
                    rows = cursor.fetchall()
                    result["result_rows"] = [list(r) for r in rows]
                result["status"] = "SUCCESS"

        except mysql.connector.errors.DatabaseError as exc:
            err_code = exc.errno
            if err_code == 1213:  # deadlock
                result["status"] = "DEADLOCK"
            elif err_code == 1205:  # lock wait timeout
                result["status"] = "TIMEOUT"
            else:
                result["status"] = "FAILED"
            result["error"] = str(exc)
            # Rollback this session on error
            try:
                conn.rollback()
            except Exception:
                pass

        finally:
            result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)

        step_results.append(result)

        # Persist to execution_log
        _log_step(run_id, step_no, txn_id, query, result)

    # Close all connections
    for txn_id in list(connections.keys()):
        try:
            cursors[txn_id].close()
            connections[txn_id].close()
        except Exception:
            pass

    anomalies = detect_anomalies(step_results, isolation_level)

    successful = sum(1 for s in step_results if s["status"] == "SUCCESS")
    failed = len(step_results) - successful

    return {
        "run_id": run_id,
        "isolation_level": isolation_level,
        "steps": step_results,
        "anomalies": anomalies,
        "summary": {
            "total_steps": len(step_results),
            "successful": successful,
            "failed": failed,
            "anomalies_found": len(anomalies),
        },
    }


def _log_step(
    run_id: str,
    step: int,
    txn_id: str,
    query: str,
    result: Dict[str, Any],
) -> None:
    """Write a single step result to execution_log (best-effort)."""
    try:
        from database import get_connection as _gc
        conn = _gc("READ COMMITTED")
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO execution_log
               (run_id, session_id, txn_id, query_text, status, latency_ms, error_msg)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                run_id,
                f"debug-step-{step}",
                txn_id,
                query,
                result["status"],
                result["latency_ms"],
                result.get("error"),
            ),
        )
        cur.close()
        conn.close()
    except Exception:
        pass  # logging must never crash the engine
