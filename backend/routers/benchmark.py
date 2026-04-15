"""
RaceDB — /run-benchmark router
"""
from fastapi import APIRouter, HTTPException
from models import BenchmarkRequest, BenchmarkResponse, AnomalyItem
from engine.benchmark_runner import run_benchmark

router = APIRouter()


@router.post("/run-benchmark", response_model=BenchmarkResponse, tags=["Benchmark"])
async def benchmark_endpoint(req: BenchmarkRequest):
    """Launch a concurrent workload benchmark against MySQL."""
    try:
        raw = run_benchmark(
            num_transactions=req.num_transactions,
            concurrency_level=req.concurrency_level,
            pattern=req.pattern,
            isolation_level=req.isolation_level,
        )
        return BenchmarkResponse(
            **{k: v for k, v in raw.items() if k != "anomalies"},
            anomalies=[AnomalyItem(**a) for a in raw["anomalies"]],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
