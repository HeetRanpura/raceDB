"""
RaceDB — Anomaly Detector
Analyses execution_log rows for a given run to surface consistency anomalies.
"""
from __future__ import annotations
from typing import List, Dict, Any


DEADLOCK_CODE = 1213
LOCK_TIMEOUT_CODE = 1205


def detect_anomalies(
    steps: List[Dict[str, Any]],
    isolation_level: str,
) -> List[Dict[str, Any]]:
    """
    Given a list of step-result dicts (from debug or benchmark runs),
    return a list of detected anomaly objects.

    Each anomaly: { type, description, txn_ids }
    """
    anomalies: List[Dict[str, Any]] = []

    # ── 1. Deadlocks ────────────────────────────────────────────────────
    deadlock_txns = [s["txn_id"] for s in steps if s.get("status") == "DEADLOCK"]
    if deadlock_txns:
        anomalies.append({
            "type": "DEADLOCK",
            "description": (
                f"MySQL detected {len(deadlock_txns)} deadlock(s). "
                f"Affected transactions: {', '.join(set(deadlock_txns))}."
            ),
            "txn_ids": ", ".join(set(deadlock_txns)),
        })

    # ── 2. Lost Updates ─────────────────────────────────────────────────
    # Heuristic: two different transactions both execute UPDATE on the same
    # table/row pattern without an intervening COMMIT from the first.
    update_steps = [s for s in steps if "UPDATE" in s.get("query", "").upper()]
    update_by_table: Dict[str, List[Dict]] = {}
    for s in update_steps:
        q = s.get("query", "").upper()
        # crude table extraction
        parts = q.split("SET")[0].split()
        table = parts[1] if len(parts) > 1 else "unknown"
        update_by_table.setdefault(table, []).append(s)

    for table, ups in update_by_table.items():
        txns = list({u["txn_id"] for u in ups})
        if len(txns) >= 2:
            # Check no COMMIT between first and last update from different txns
            anomalies.append({
                "type": "LOST_UPDATE",
                "description": (
                    f"Potential lost update on table '{table}': "
                    f"{len(txns)} transactions ({', '.join(txns)}) "
                    f"performed concurrent writes."
                ),
                "txn_ids": ", ".join(txns),
            })

    # ── 3. Dirty Read (only possible at READ UNCOMMITTED) ───────────────
    if "READ UNCOMMITTED" in isolation_level.upper():
        read_steps = [s for s in steps if s.get("query", "").upper().startswith("SELECT")]
        write_steps = [s for s in steps if "UPDATE" in s.get("query", "").upper()
                       and s.get("status") in ("ROLLBACK", "FAILED")]
        if read_steps and write_steps:
            anomalies.append({
                "type": "DIRTY_READ",
                "description": (
                    f"Dirty read risk: reads occurred while uncommitted writes "
                    f"from {len(write_steps)} transaction(s) were later rolled back. "
                    f"Isolation level: {isolation_level}."
                ),
                "txn_ids": ", ".join({s["txn_id"] for s in write_steps}),
            })

    # ── 4. Non-repeatable Read (READ COMMITTED) ─────────────────────────
    if isolation_level.upper() in ("READ COMMITTED",):
        # Look for same txn issuing ≥2 SELECTs on same table
        selects_by_txn: Dict[str, list] = {}
        for s in steps:
            if s.get("query", "").upper().startswith("SELECT"):
                selects_by_txn.setdefault(s["txn_id"], []).append(s)
        for txn, sels in selects_by_txn.items():
            if len(sels) >= 2:
                # Did an update from another txn happen between those SELECTs?
                min_step = min(s["step"] for s in sels)
                max_step = max(s["step"] for s in sels)
                interleaved = [
                    u for u in update_steps
                    if u["txn_id"] != txn
                    and min_step < u.get("step", 0) < max_step
                ]
                if interleaved:
                    anomalies.append({
                        "type": "NON_REPEATABLE_READ",
                        "description": (
                            f"Non-repeatable read in {txn}: "
                            f"a concurrent write by {interleaved[0]['txn_id']} "
                            f"occurred between two reads."
                        ),
                        "txn_ids": f"{txn}, {interleaved[0]['txn_id']}",
                    })

    return anomalies
