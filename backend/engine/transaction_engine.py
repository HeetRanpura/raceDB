import time
import threading
import uuid
from typing import Dict, List, Any

from db.connection import get_connection, close_resources
from db.executor import execute_query_safely

class DebugWorkerThread(threading.Thread):
    """
    Runs a single transaction over a dedicated MySQL connection.
    Controlled step-by-step by the Scheduler via threading.Event.
    """
    def __init__(self, txn_id: str, isolation_level: str, scheduler):
        super().__init__(name=f"Worker-{txn_id}")
        self.txn_id = txn_id
        self.isolation_level = isolation_level
        self.scheduler = scheduler
        
        self.conn = None
        self.current_query = None
        self.current_step_num = None
        
        self.trigger_event = threading.Event()
        self.completed_event = threading.Event()
        
        # State tracking
        self.is_running = True
        self.last_result = None
        self.fatal_error = False

    def run(self):
        try:
            self.conn = get_connection(self.isolation_level)
        except Exception as e:
            self.last_result = {"status": "FAILED", "error": f"Conn failed: {e}", "latency_ms": 0}
            self.fatal_error = True
            return

        while self.is_running:
            # Wait for scheduler to trigger us with a query
            self.trigger_event.wait()
            self.trigger_event.clear()
            
            if not self.is_running:
                break
                
            if self.current_query:
                # This will properly block against MySQL InnoDB locks!
                # If another thread holds the lock, this line hangs until timeout or deadlock.
                exec_result = execute_query_safely(self.conn, self.current_query)
                
                self.last_result = {
                    "step": self.current_step_num,
                    "txn_id": self.txn_id,
                    "query": self.current_query,
                    "status": exec_result.status,
                    "latency_ms": exec_result.latency_ms,
                    "result_rows": exec_result.rows,
                    "error": exec_result.error
                }
                
                if exec_result.status in ("FAILED", "DEADLOCK", "TIMEOUT"):
                    # Abort tracking for this thread if fatally failed
                    self.fatal_error = True

                self.current_query = None
                self.completed_event.set()

        close_resources(self.conn)

    def dispatch_step(self, step_num: int, query: str):
        """Called by the scheduler to hand off the next query to this thread."""
        self.current_step_num = step_num
        self.current_query = query
        self.completed_event.clear()
        self.trigger_event.set()

    def shutdown(self):
        self.is_running = False
        self.trigger_event.set() # wake up if sleeping
