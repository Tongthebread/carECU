from contextlib import asynccontextmanager
from datetime import datetime, timezone
import csv
import io
import json
import logging
import os
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import Field, field_validator
from sqlalchemy import select, text, func
from sqlalchemy.orm import Session

from .db import AlgorithmRecord, RunRecord, ScenarioRecord, SessionLocal, init_db
from .schemas import AlgorithmConfig, AlgorithmProfile, ScenarioConfig, ScenarioType, StrictModel
from .services.jobs import JobService
from .services.reports import generate_report as build_report


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                  "event": record.getMessage(), "logger": record.name}
        for field in ("run_id", "sink"):
            if hasattr(record, field):
                result[field] = getattr(record, field)
        if record.exc_info:
            result["exception"] = self.formatException(record.exc_info)
        return json.dumps(result)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("driveeval")
logger.handlers = [handler]
logger.setLevel(logging.INFO)
logger.propagate = False


@asynccontextmanager
async def lifespan(app):
    init_db()
    with SessionLocal() as db:
        existing = set(db.scalars(select(ScenarioRecord.scenario_type)))
        for scenario_type in ScenarioType:
            if scenario_type.value not in existing:
                config = ScenarioConfig(fog_density=0.6 if scenario_type == ScenarioType.LOW_VISIBILITY_OBSTACLE else 0)
                db.add(ScenarioRecord(name=scenario_type.value.replace("_", " ").title(),
                       scenario_type=scenario_type.value, description="Synthetic demonstration scenario", configuration=config.model_dump()))
        existing_algorithms = set(db.scalars(select(AlgorithmRecord.version)))
        for profile in AlgorithmProfile:
            if profile.value not in existing_algorithms:
                db.add(AlgorithmRecord(name=profile.value, version=profile.value,
                                       configuration=AlgorithmConfig().model_dump(), artifact_id="mock-model-0.2"))
        db.commit()
    app.state.jobs = JobService()
    app.state.jobs.recover()
    yield
    app.state.jobs.close()


app = FastAPI(title="DriveEval AI", version="0.2.0", lifespan=lifespan,
              description="Synthetic ADAS simulation, reproducible benchmarking and evaluation. Not vehicle validation.")
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("DRIVEEVAL_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class ScenarioCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    scenario_type: ScenarioType
    description: str = Field("", max_length=500)
    configuration: ScenarioConfig = Field(default_factory=ScenarioConfig)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()


class AlgorithmCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")
    version: AlgorithmProfile
    description: str = Field("", max_length=500)
    configuration: AlgorithmConfig = Field(default_factory=AlgorithmConfig)
    artifact_id: str = Field("", max_length=120)


class RunCreate(StrictModel):
    scenario_id: int = Field(gt=0)
    algorithm_id: int = Field(gt=0)
    configuration: ScenarioConfig | None = None


class ReportRequest(StrictModel):
    use_llm: bool = False


def get_db():
    with SessionLocal() as db:
        yield db


def record_or_404(db, model, record_id):
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(404, detail=f"{model.__tablename__.rstrip('s').title()} not found")
    return record


def completed_run(db, run_id):
    run = record_or_404(db, RunRecord, run_id)
    if run.status != "completed":
        raise HTTPException(409, detail=f"Run is {run.status}; completed results required")
    return run


def serialize(record, exclude=()):
    return {column.name: getattr(record, column.name) for column in record.__table__.columns if column.name not in exclude}


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, detail="Database unavailable")
    return {"status": "ok", "service": "driveeval-api", "simulator": "mock", "data_source": "synthetic"}


@app.get("/api/overview", tags=["Runs"])
def overview(db: Session = Depends(get_db)):
    records = db.execute(select(RunRecord.status, RunRecord.metrics)).all()
    completed = [metrics for state, metrics in records if state == "completed"]
    passed = sum(bool(m.get("passed")) for m in completed)
    return {"total_runs": len(records), "completed_runs": len(completed), "passed_runs": passed,
            "pass_rate": passed / len(completed) * 100 if completed else None,
            "failed_evaluations": len(completed) - passed,
            "active_jobs": sum(state in {"queued", "running"} for state, _ in records)}


@app.post("/api/scenarios", status_code=201, tags=["Scenarios"])
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)):
    record = ScenarioRecord(**payload.model_dump(mode="json"))
    db.add(record)
    db.commit()
    return serialize(record)


@app.get("/api/scenarios", tags=["Scenarios"])
def list_scenarios(db: Session = Depends(get_db)):
    return [serialize(item) for item in db.scalars(select(ScenarioRecord).order_by(ScenarioRecord.id.desc()))]


@app.post("/api/algorithms", status_code=201, tags=["Algorithms"])
def create_algorithm(payload: AlgorithmCreate, db: Session = Depends(get_db)):
    record = AlgorithmRecord(**payload.model_dump(mode="json"))
    db.add(record)
    db.commit()
    return serialize(record)


@app.get("/api/algorithms", tags=["Algorithms"])
def list_algorithms(db: Session = Depends(get_db)):
    return [serialize(item) for item in db.scalars(select(AlgorithmRecord).order_by(AlgorithmRecord.id))]


def enqueue(payload, request, db):
    scenario = record_or_404(db, ScenarioRecord, payload.scenario_id)
    algorithm = record_or_404(db, AlgorithmRecord, payload.algorithm_id)
    config = payload.configuration or ScenarioConfig(**scenario.configuration)
    active_count = db.scalar(select(func.count()).select_from(RunRecord).where(RunRecord.status.in_(["queued", "running"])))
    if active_count >= 100:
        raise HTTPException(429, detail="Simulation queue is full")
    snapshot = {"scenario_name": scenario.name, "scenario_type": scenario.scenario_type,
                "configuration": config.model_dump(), "algorithm_name": algorithm.name,
                "algorithm_version": algorithm.version, "algorithm_configuration": algorithm.configuration,
                "artifact_id": algorithm.artifact_id, "simulator": "mock", "simulator_version": "0.2"}
    run = RunRecord(scenario_id=scenario.id, algorithm_id=algorithm.id, status="queued",
                    random_seed=config.random_seed, environment=config.model_dump(), snapshot=snapshot)
    db.add(run)
    db.commit()
    response = serialize(run, exclude=("telemetry", "report"))
    request.app.state.jobs.submit(run.id)
    return response


@app.post("/api/runs", status_code=202, tags=["Runs"])
def start_run(payload: RunCreate, request: Request, db: Session = Depends(get_db)):
    return enqueue(payload, request, db)


@app.post("/api/runs/{scenario_id:int}/{algorithm_id:int}", status_code=202, tags=["Runs"], deprecated=True)
def start_run_legacy(scenario_id: int, algorithm_id: int, request: Request, db: Session = Depends(get_db)):
    if scenario_id < 1 or algorithm_id < 1:
        raise HTTPException(422, detail="Scenario and algorithm IDs must be positive")
    return enqueue(RunCreate(scenario_id=scenario_id, algorithm_id=algorithm_id), request, db)


@app.get("/api/runs", tags=["Runs"])
def list_runs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    return [serialize(run, exclude=("telemetry", "report")) for run in db.scalars(
        select(RunRecord).order_by(RunRecord.id.desc()).limit(limit).offset(offset))]


@app.get("/api/runs/{run_id}", tags=["Runs"])
def get_run(run_id: int, db: Session = Depends(get_db)):
    return serialize(record_or_404(db, RunRecord, run_id))


@app.get("/api/runs/{run_id}/status", tags=["Runs"])
def get_status(run_id: int, db: Session = Depends(get_db)):
    run = record_or_404(db, RunRecord, run_id)
    return {"id": run.id, "status": run.status, "error_message": run.error_message,
            "started_at": run.started_at, "ended_at": run.ended_at}


@app.get("/api/runs/{run_id}/telemetry", tags=["Results"])
def get_telemetry(run_id: int, db: Session = Depends(get_db)):
    return completed_run(db, run_id).telemetry


@app.get("/api/runs/{run_id}/metrics", tags=["Results"])
def get_metrics(run_id: int, db: Session = Depends(get_db)):
    return completed_run(db, run_id).metrics


@app.get("/api/compare", tags=["Results"])
def compare_runs(run_ids: str, db: Session = Depends(get_db)):
    try:
        ids = [int(value.strip()) for value in run_ids.split(",")]
    except ValueError:
        raise HTTPException(422, detail="run_ids must be comma-separated integers")
    if not 2 <= len(ids) <= 10 or len(set(ids)) != len(ids) or any(i < 1 for i in ids):
        raise HTTPException(422, detail="Provide 2–10 distinct positive run IDs")
    runs = [completed_run(db, run_id) for run_id in ids]
    signatures = [(r.snapshot.get("scenario_type"), r.environment) for r in runs]
    comparable = all(signature == signatures[0] for signature in signatures) and all(r.snapshot for r in runs)
    keys = [key for key, value in runs[0].metrics.items() if type(value) in (float, int)]
    return {"runs": [serialize(run, exclude=("telemetry", "report")) for run in runs],
            "comparable": comparable,
            "warning": None if comparable else "Scenario, seed or environment differ, or legacy snapshots are missing; this is not a controlled algorithm comparison.",
            "deltas_from_first": [{"run_id": run.id, "metrics": {key: round(run.metrics[key] - runs[0].metrics[key], 5)
                for key in keys if type(run.metrics.get(key)) in (float, int)}} for run in runs[1:]]}


@app.get("/api/runs/{run_id}/report", tags=["Reports"])
def get_report(run_id: int, db: Session = Depends(get_db)):
    run = completed_run(db, run_id)
    return run.report or build_report(run)


@app.post("/api/runs/{run_id}/report", tags=["Reports"])
def generate_report(run_id: int, payload: ReportRequest, db: Session = Depends(get_db)):
    run = completed_run(db, run_id)
    run.report = build_report(run, payload.use_llm)
    db.commit()
    return run.report


@app.get("/api/runs/{run_id}/export", tags=["Results"])
def export_run(run_id: int, format: Literal["json", "csv"] = "json", db: Session = Depends(get_db)):
    run = completed_run(db, run_id)
    if format == "json":
        content = json.dumps(serialize(run), default=lambda value: value.isoformat())
        media_type = "application/json"
    else:
        output = io.StringIO(newline="")
        fields = list(run.telemetry[0]) if run.telemetry else []
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(run.telemetry)
        content, media_type = output.getvalue(), "text/csv"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="driveeval-run-{run_id}.{format}"'})
