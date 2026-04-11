import time
import mysql.connector
from typing import Dict, Any

class ExecutionResult:
    def __init__(self, query: str, status: str, latency_ms: float, rows: list = None, error: str = None):
        self.query = query
        self.status = status
        self.latency_ms = latency_ms
        self.rows = rows
        self.error = error

def execute_query_safely(conn, query: str) -> ExecutionResult:
    """
    Executes a query against the given connection.
    Safely captures 1213 (Deadlock) and 1205 (Timeout), 
    and handles COMMIT/ROLLBACK/BEGIN.
    Returns an ExecutionResult describing outcome and latency.
    """
    t0 = time.perf_counter()
    status = "SUCCESS"
    rows = None
    error = None

    upper_query = query.upper().strip()
    
    try:
        if upper_query in ("COMMIT", "COMMIT;"):
            conn.commit()
            status = "COMMIT"
        elif upper_query in ("ROLLBACK", "ROLLBACK;"):
            conn.rollback()
            status = "ROLLBACK"
        else:
            cursor = conn.cursor()
            cursor.execute(query)
            if upper_query.startswith("SELECT"):
                raw_rows = cursor.fetchall()
                rows = [list(r) for r in raw_rows]
            cursor.close()

    except mysql.connector.errors.DatabaseError as exc:
        err_code = exc.errno
        if err_code == 1213:
            status = "DEADLOCK"
        elif err_code == 1205:
            status = "TIMEOUT"
        else:
            status = "FAILED"
        error = str(exc)
        
        # MySQL automatically rolls back the *statement* or sometimes the *entire transaction* on deadlock.
        # We allow higher layers to explicitly issue rollback if they choose.
    except Exception as exc:
        status = "FAILED"
        error = str(exc)

    latency_ms = round((time.perf_counter() - t0) * 1000, 3)
    return ExecutionResult(query, status, latency_ms, rows, error)
