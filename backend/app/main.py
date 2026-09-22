from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import AlgorithmRecord, RunRecord, ScenarioRecord, SessionLocal, init_db
from .schemas import AlgorithmProfile, ScenarioConfig, ScenarioType
from .simulators import MockSimulator

app = FastAPI(title="DriveEval AI", version="0.1.0", description="ADAS simulation and model evaluation platform")
simulator = MockSimulator()


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scenario_type: ScenarioType
    description: str = ""
    configuration: ScenarioConfig = ScenarioConfig()


class AlgorithmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: AlgorithmProfile
    description: str = ""
    configuration: dict = {}
    artifact_id: str = ""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "driveeval-api", "simulator": "mock"}


@app.post("/api/scenarios", status_code=status.HTTP_201_CREATED)
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)) -> dict:
    record = ScenarioRecord(name=payload.name, scenario_type=payload.scenario_type.value, description=payload.description, configuration=payload.configuration.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "name": record.name, "scenario_type": record.scenario_type, "configuration": record.configuration}


@app.get("/api/scenarios")
def list_scenarios(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": item.id, "name": item.name, "scenario_type": item.scenario_type, "description": item.description, "configuration": item.configuration} for item in db.query(ScenarioRecord).order_by(ScenarioRecord.id.desc()).all()]


@app.post("/api/algorithms", status_code=status.HTTP_201_CREATED)
def create_algorithm(payload: AlgorithmCreate, db: Session = Depends(get_db)) -> dict:
    record = AlgorithmRecord(name=payload.name, version=payload.version.value, description=payload.description, configuration=payload.configuration, artifact_id=payload.artifact_id)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "name": record.name, "version": record.version}


@app.get("/api/algorithms")
def list_algorithms(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": item.id, "name": item.name, "version": item.version, "description": item.description} for item in db.query(AlgorithmRecord).all()]


@app.post("/api/runs/{scenario_id}/{algorithm_id}", status_code=status.HTTP_201_CREATED)
def start_run(scenario_id: int, algorithm_id: int, db: Session = Depends(get_db)) -> dict:
    scenario = db.get(ScenarioRecord, scenario_id)
    algorithm = db.get(AlgorithmRecord, algorithm_id)
    if scenario is None or algorithm is None:
        raise HTTPException(status_code=404, detail="Scenario or algorithm not found")
    result = simulator.run(ScenarioType(scenario.scenario_type), ScenarioConfig(**scenario.configuration), AlgorithmProfile(algorithm.version))
    record = RunRecord(scenario_id=scenario.id, algorithm_id=algorithm.id, status="completed", started_at=datetime.now(timezone.utc), ended_at=datetime.now(timezone.utc), random_seed=result.random_seed, environment=scenario.configuration, telemetry=[item.model_dump() for item in result.telemetry], metrics=result.metrics.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "status": record.status, "metrics": record.metrics}


@app.get("/api/runs")
def list_runs(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": item.id, "scenario_id": item.scenario_id, "algorithm_id": item.algorithm_id, "status": item.status, "metrics": item.metrics} for item in db.query(RunRecord).order_by(RunRecord.id.desc()).all()]


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    record = db.get(RunRecord, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"id": record.id, "scenario_id": record.scenario_id, "algorithm_id": record.algorithm_id, "status": record.status, "environment": record.environment, "metrics": record.metrics, "telemetry": record.telemetry}


@app.get("/api/runs/{run_id}/telemetry")
def get_telemetry(run_id: int, db: Session = Depends(get_db)) -> list[dict]:
    record = db.get(RunRecord, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return record.telemetry