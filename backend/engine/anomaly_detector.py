"""
RaceDB — Anomaly Detector (v2)

Fix #5: Replays execution log in step order, tracking per-transaction state
        incrementally so dirty-read detection uses the *moment-of-read* state.
Fix #6: Implements Non-Repeatable Read and Phantom Read detection.
"""
import re
from typing import List, Dict, Any, Set, Tuple


def _extract_target(query_upper: str) -> str:
    """Extract a rough row-level target identifier from the query."""
    match = re.search(r"ACCOUNT_ID\s*=\s*(\d+)", query_upper)
    return f"account_{match.group(1)}" if match else "unknown_target"


def _extract_predicate(query_upper: str) -> str:
    """Extract WHERE clause predicate for phantom-read tracking."""
    match = re.search(r"WHERE\s+(.+?)(?:ORDER|LIMIT|GROUP|HAVING|FOR|;|$)", query_upper)
    return match.group(1).strip() if match else ""


def detect_anomalies(
    steps_log: List[Dict[str, Any]],
    isolation_level: str,
) -> List[Dict[str, Any]]:
    """
    Replay execution log in step order. Track per-transaction state incrementally
    to detect anomalies at the *moment they occur*, not post-hoc.
    """
    anomalies: List[Dict[str, Any]] = []

    # Per-transaction accumulated state (built incrementally during replay)
    txn_reads: Dict[str, Set[str]] = {}        # txn -> set of targets read
    txn_writes: Dict[str, Set[str]] = {}       # txn -> set of targets written
    txn_status: Dict[str, str] = {}            # txn -> ACTIVE | COMMITTED | ABORTED
    txn_read_results: Dict[str, List[Tuple[str, Any]]] = {}  # txn -> [(target, result_rows), ...]
    txn_select_predicates: Dict[str, List[Tuple[str, int, Any]]] = {}  # txn -> [(predicate, step, rows), ...]

    # Sort by step to ensure correct replay order
    sorted_steps = sorted(steps_log, key=lambda s: s.get("step", 0))

    for s in sorted_steps:
        txn = s["txn_id"]
        q = s.get("query", "").strip().upper()
        status = s.get("status", "")
        result_rows = s.get("result_rows")

        # Initialize tracking for new transactions
        if txn not in txn_status:
            txn_reads[txn] = set()
            txn_writes[txn] = set()
            txn_status[txn] = "ACTIVE"
            txn_read_results[txn] = []
            txn_select_predicates[txn] = []

        # ── Deadlock ────────────────────────────────────────────────────
        if status == "DEADLOCK":
            anomalies.append({
                "type": "DEADLOCK",
                "description": f"Genuine Database Deadlock Error (1213) triggered by {txn}.",
                "txn_ids": txn,
            })
            txn_status[txn] = "ABORTED"
            continue

        if status in ("FAILED", "TIMEOUT"):
            txn_status[txn] = "ABORTED"
            continue

        # ── COMMIT / ROLLBACK ───────────────────────────────────────────
        if q in ("COMMIT", "COMMIT;") or status == "COMMIT":
            txn_status[txn] = "COMMITTED"
            continue

        if q in ("ROLLBACK", "ROLLBACK;") or status == "ROLLBACK":
            txn_status[txn] = "ABORTED"
            continue

        if status in ("ABORTED", "BLOCKED", "WAITING (LOCK)"):
            continue

        target = _extract_target(q)

        # ── SELECT ──────────────────────────────────────────────────────
        if q.startswith("SELECT"):
            txn_reads[txn].add(target)
            txn_read_results[txn].append((target, result_rows))

            # Track predicate for phantom read detection
            predicate = _extract_predicate(q)
            if predicate:
                txn_select_predicates[txn].append((predicate, s.get("step", 0), result_rows))

            # ── Dirty Read Detection (Fix #5) ───────────────────────────
            # Check at the *moment of this read* if any other ACTIVE txn
            # has written to this target. "ACTIVE" means uncommitted right now.
            if "READ UNCOMMITTED" in isolation_level.upper():
                for other_txn, other_status in txn_status.items():
                    if other_txn != txn and other_status == "ACTIVE" and target in txn_writes.get(other_txn, set()):
                        anomalies.append({
                            "type": "DIRTY_READ",
                            "description": (
                                f"{txn} read '{target}' which was written by "
                                f"uncommitted {other_txn} (still ACTIVE at step {s.get('step')})."
                            ),
                            "txn_ids": f"{txn}, {other_txn}",
                        })

            # ── Non-Repeatable Read Detection (Fix #6) ──────────────────
            # If this txn has previously read the same target, and another txn
            # committed a write to that target between those two reads.
            if isolation_level.upper() in ("READ COMMITTED", "READ UNCOMMITTED"):
                prev_reads = [(t, rows) for (t, rows) in txn_read_results[txn][:-1] if t == target]
                if prev_reads:
                    prev_target, prev_rows = prev_reads[-1]
                    if result_rows is not None and prev_rows is not None and result_rows != prev_rows:
                        # Check if another txn committed a write between these reads
                        writing_txns = [
                            ot for ot, ow in txn_writes.items()
                            if ot != txn and target in ow and txn_status[ot] == "COMMITTED"
                        ]
                        if writing_txns:
                            anomalies.append({
                                "type": "NON_REPEATABLE_READ",
                                "description": (
                                    f"Non-repeatable read in {txn} on '{target}': "
                                    f"different results observed across two reads. "
                                    f"Committed writer(s): {', '.join(writing_txns)}."
                                ),
                                "txn_ids": f"{txn}, {', '.join(writing_txns)}",
                            })

        # ── UPDATE / INSERT / DELETE ────────────────────────────────────
        elif "UPDATE" in q or "INSERT" in q or "DELETE" in q:
            txn_writes[txn].add(target)

            # ── Lost Update Detection (Fix #5 — two-pass logic) ─────────
            # Condition: both this txn AND another txn have independently
            # performed read-then-write on the *same* target.
            for other_txn in txn_writes:
                if other_txn == txn:
                    continue
                if target in txn_writes[other_txn] and target in txn_reads.get(other_txn, set()) and target in txn_reads.get(txn, set()):
                    anomalies.append({
                        "type": "LOST_UPDATE",
                        "description": (
                            f"Overlapping read-modify-write on '{target}'. "
                            f"Both {txn} and {other_txn} read then wrote concurrently."
                        ),
                        "txn_ids": f"{txn}, {other_txn}",
                    })

            # ── Phantom Read Detection (Fix #6) ────────────────────────
            # If another ACTIVE txn has run a range SELECT, and this txn
            # inserts/deletes a row that could affect those results, flag it.
            # Only relevant under READ COMMITTED or READ UNCOMMITTED.
            if "INSERT" in q or "DELETE" in q:
                for other_txn, preds in txn_select_predicates.items():
                    if other_txn == txn or txn_status[other_txn] != "ACTIVE":
                        continue
                    for pred, _, _ in preds:
                        if target != "unknown_target":
                            anomalies.append({
                                "type": "PHANTOM_READ",
                                "description": (
                                    f"Potential phantom read: {txn} performed "
                                    f"{'INSERT' if 'INSERT' in q else 'DELETE'} affecting "
                                    f"'{target}' while {other_txn} has an active range query."
                                ),
                                "txn_ids": f"{txn}, {other_txn}",
                            })

    # ── Deduplicate ─────────────────────────────────────────────────────
    unique_anoms: List[Dict[str, Any]] = []
    seen: set = set()
    for a in anomalies:
        sig = f"{a['type']}-{a['txn_ids']}"
        if sig not in seen:
            seen.add(sig)
            unique_anoms.append(a)

    return unique_anoms
