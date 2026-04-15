import time
import threading
from typing import Dict, List, Any

from db.connection import get_connection, close_resources
from db.executor import execute_query_safely


class DebugWorkerThread(threading.Thread):
    """
    Runs a single transaction over a dedicated MySQL connection.
    Controlled step-by-step by the Scheduler via threading.Event.
    """

    def __init__(self, txn_id: str, isolation_level: str):
        super().__init__(name=f"Worker-{txn_id}", daemon=True)
        self.txn_id = txn_id
        self.isolation_level = isolation_level

        self.conn = None

        # Fix #2: All mutable state guarded by a single lock.
        # The scheduler dispatches work via `_pending_query` and reads results
        # via `last_result` — both under `_state_lock`.
        self._state_lock = threading.Lock()
        self._pending_query: str | None = None
        self._pending_step_num: int | None = None

        self.trigger_event = threading.Event()
        self.completed_event = threading.Event()
        self.completed_event.set()  # starts "idle" (completed)

        # State tracking
        self.is_running = True
        self.last_result: dict | None = None
        self.fatal_error = False

    def run(self):
        try:
            self.conn = get_connection(self.isolation_level)
        except Exception as e:
            self.last_result = {
                "status": "FAILED",
                "error": f"Conn failed: {e}",
                "latency_ms": 0,
            }
            self.fatal_error = True
            self.completed_event.set()
            return

        while self.is_running:
            self.trigger_event.wait()
            self.trigger_event.clear()

            if not self.is_running:
                break

            # Grab pending work under lock
            with self._state_lock:
                query = self._pending_query
                step_num = self._pending_step_num
                self._pending_query = None
                self._pending_step_num = None

            if query is None:
                continue

            # This will properly block against MySQL locks!
            exec_result = execute_query_safely(self.conn, query)

            self.last_result = {
                "step": step_num,
                "txn_id": self.txn_id,
                "query": query,
                "status": exec_result.status,
                "latency_ms": exec_result.latency_ms,
                "result_rows": exec_result.rows,
                "error": exec_result.error,
            }

            # Fix #3: On fatal error, immediately rollback so MySQL doesn't
            # keep an orphaned transaction in Database_trx.
            if exec_result.status in ("FAILED", "DEADLOCK", "TIMEOUT"):
                self.fatal_error = True
                try:
                    execute_query_safely(self.conn, "ROLLBACK")
                except Exception:
                    pass

            self.completed_event.set()

        close_resources(self.conn)

    def dispatch_step(self, step_num: int, query: str):
        """Called by the scheduler to hand off the next query to this thread."""
        with self._state_lock:
            self._pending_step_num = step_num
            self._pending_query = query
        self.completed_event.clear()
        self.trigger_event.set()

    def is_idle(self) -> bool:
        """Thread-safe check: has the worker finished its last dispatched step?"""
        return self.completed_event.is_set()

    def shutdown(self):
        self.is_running = False
        self.trigger_event.set()
