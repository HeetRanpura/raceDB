"""
RaceDB — /run-debug router
"""
from fastapi import APIRouter, HTTPException
from models import DebugRequest, DebugResponse, StepResult, AnomalyItem
from engine.scheduler import run_debug_deterministic

router = APIRouter()


@router.post("/run-debug", response_model=DebugResponse, tags=["Debug"])
async def debug_endpoint(req: DebugRequest):
    """Execute a deterministic, manually-defined transaction schedule."""
    try:
        raw = run_debug_deterministic(
            transactions={k: [s.model_dump() for s in v] for k, v in req.transactions.items()},
            isolation_level=req.isolation_level,
        )
        return DebugResponse(
            **{k: v for k, v in raw.items() if k not in ("steps", "anomalies")},
            steps=[StepResult(**s) for s in raw["steps"]],
            anomalies=[AnomalyItem(**a) for a in raw["anomalies"]],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
