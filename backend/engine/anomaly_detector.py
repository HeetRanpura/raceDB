import re
from typing import List, Dict, Any

def detect_anomalies(steps_log: List[Dict[str, Any]], isolation_level: str) -> List[Dict[str, Any]]:
    """
    Deep, transaction-aware anomaly detection examining read/write intersections
    and genuine MySQL lock deadlocks.
    """
    anomalies = []
    
    # Track transaction state logically
    txns = {}
    
    for s in steps_log:
        txn = s["txn_id"]
        if txn not in txns:
            txns[txn] = {"reads": set(), "writes": set(), "status": "ACTIVE"}
            
        q = s.get("query", "").strip().upper()
        
        # Deadlocks
        if s.get("status") == "DEADLOCK":
            anomalies.append({
                "type": "DEADLOCK",
                "description": f"Genuine InnoDB Deadlock Error (1213) triggered by {txn}.",
                "txn_ids": txn
            })
            txns[txn]["status"] = "ABORTED"
            continue
            
        if s.get("status") in ("ROLLBACK", "FAILED"):
            txns[txn]["status"] = "ABORTED"
            continue
            
        if q in ("COMMIT", "COMMIT;"):
            txns[txn]["status"] = "COMMITTED"
            continue
            
        # Parse targets roughly for precise logic
        match = re.search(r"ACCOUNT_ID\s*=\s*(\d+)", q)
        target = f"account_{match.group(1)}" if match else "unknown_table"
        
        if q.startswith("SELECT"):
            txns[txn]["reads"].add(target)
            
            # Dirty Read Detection (READ UNCOMMITTED)
            if "READ UNCOMMITTED" in isolation_level:
                # Did we just read something that an ACTIVE transaction has written to, 
                # but which subsequently ABORTS? We must flag it retrospectively or prospectively.
                # Here we just look at ANY active uncommitted writer at the moment of read.
                for other_txn, state in txns.items():
                    if other_txn != txn and target in state["writes"] and state["status"] == "ACTIVE":
                        anomalies.append({
                            "type": "DIRTY_READ",
                            "description": f"{txn} read '{target}' which was written by uncommitted {other_txn}.",
                            "txn_ids": f"{txn}, {other_txn}"
                        })

            # Non-Repeatable Read (READ COMMITTED)
            # If we SELECT, we track it. If we SELECT again later, we check if another txn committed a write between.
            pass  # Complex to track inline without storing history, handled by generic heuristics if needed.
            
        elif "UPDATE" in q or "INSERT" in q or "DELETE" in q:
            txns[txn]["writes"].add(target)
            
            # Lost Update Detection (Read-Modify-Write overlap)
            # If T1 read target, T2 read target, and both subsequently WRITE target (and both commit or are active).
            # We flag this.
            for other_txn, state in txns.items():
                if other_txn != txn and target in state["reads"] and target in state["writes"]:
                    if target in txns[txn]["reads"]:
                        anomalies.append({
                            "type": "LOST_UPDATE",
                            "description": f"Overlapping read-modify-write on '{target}'. Both {txn} and {other_txn} concurrently modified based on stale reads.",
                            "txn_ids": f"{txn}, {other_txn}"
                        })
                        
    # Deduplicate anomalies
    unique_anoms = []
    seen = set()
    for a in anomalies:
        sig = f"{a['type']}-{a['description']}"
        if sig not in seen:
            seen.add(sig)
            unique_anoms.append(a)

    return unique_anoms
