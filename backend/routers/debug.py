"""
RaceDB — /run-debug router
"""
from fastapi import APIRouter, HTTPException
from models import DebugRequest, DebugResponse, StepResult
from engine.debug_engine import run_debug

router = APIRouter()


@router.post("/run-debug", response_model=DebugResponse, tags=["Debug"])
async def debug_endpoint(req: DebugRequest):
    """Execute a deterministic, manually-defined transaction schedule."""
    try:
        raw = run_debug(
            transactions={
                k: [s.model_dump() for s in v]
                for k, v in req.transactions.items()
            },
            isolation_level=req.isolation_level,
        )
        return DebugResponse(
            run_id=raw["run_id"],
            isolation_level=raw["isolation_level"],
            steps=[StepResult(**s) for s in raw["steps"]],
            anomalies=raw["anomalies"],
            summary=raw["summary"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
