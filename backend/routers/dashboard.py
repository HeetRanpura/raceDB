"""
RaceDB — /api/dashboard router
Serves live aggregate metrics for the Dashboard view.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.connection import get_connection, close_resources

router = APIRouter(prefix="/api/dashboard-metrics", tags=["Dashboard"])

class AccountTypeBreakdown(BaseModel):
    account_type: str
    count: int

class DashboardMetricsResponse(BaseModel):
    total_liquidity: float
    total_loan_book: float
    active_customers: int
    active_cards: int
    account_breakdown: list[AccountTypeBreakdown]

@router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics():
    """Fetch high-level metrics across the banking domain."""
    conn = None
    cursor = None
    try:
        conn = get_connection(isolation_level="READ COMMITTED")
        cursor = conn.cursor(dictionary=True)

        metrics = {
            "total_liquidity": 0.0,
            "total_loan_book": 0.0,
            "active_customers": 0,
            "active_cards": 0,
            "account_breakdown": []
        }

        # 1. Total Liquidity (Sum of balances)
        cursor.execute("SELECT SUM(balance) as sm FROM accounts")
        row = cursor.fetchone()
        metrics["total_liquidity"] = float(row["sm"] or 0)

        # 2. Total Loan Book (Sum of active loan principals)
        cursor.execute("SELECT SUM(principal) as sm FROM loans WHERE status = 'ACTIVE'")
        row = cursor.fetchone()
        metrics["total_loan_book"] = float(row["sm"] or 0)

        # 3. Active Customers (Count of users)
        cursor.execute("SELECT COUNT(*) as ct FROM users")
        row = cursor.fetchone()
        metrics["active_customers"] = int(row["ct"] or 0)

        # 4. Active Cards
        cursor.execute("SELECT COUNT(*) as ct FROM cards WHERE is_active = TRUE")
        row = cursor.fetchone()
        metrics["active_cards"] = int(row["ct"] or 0)

        # 5. Account Breakdown
        cursor.execute("SELECT account_type, COUNT(*) as ct FROM accounts GROUP BY account_type")
        for r in cursor.fetchall():
            metrics["account_breakdown"].append({
                "account_type": r["account_type"],
                "count": int(r["ct"])
            })

        return DashboardMetricsResponse(**metrics)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        close_resources(conn, cursor)
