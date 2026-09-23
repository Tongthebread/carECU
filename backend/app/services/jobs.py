import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from sqlalchemy import select
from ..db import RunRecord, SessionLocal
from ..schemas import AlgorithmConfig, AlgorithmProfile, ScenarioConfig, ScenarioType
from ..simulators import MockSimulator

logger = logging.getLogger("driveeval.jobs")


class JobService:
    """Single-process worker; persisted interrupted jobs fail explicitly on restart."""
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="simulation")

    def recover(self):
        with SessionLocal() as db:
            for run in db.scalars(select(RunRecord).where(RunRecord.status.in_(["queued", "running"]))):
                run.status = "failed"
                run.error_message = "Worker interrupted. Submit a new run using the saved configuration."
                run.ended_at = datetime.now(timezone.utc)
            db.commit()

    def submit(self, run_id):
        self.executor.submit(self.execute, run_id)

    def execute(self, run_id):
        try:
            with SessionLocal() as db:
                run = db.get(RunRecord, run_id)
                run.status = "running"
                run.started_at = datetime.now(timezone.utc)
                db.commit()
                snapshot = run.snapshot
            result = MockSimulator().run(ScenarioType(snapshot["scenario_type"]),
                ScenarioConfig(**snapshot["configuration"]), AlgorithmProfile(snapshot["algorithm_version"]),
                AlgorithmConfig(**snapshot["algorithm_configuration"]))
            with SessionLocal() as db:
                run = db.get(RunRecord, run_id)
                run.telemetry = [sample.model_dump() for sample in result.telemetry]
                run.metrics = result.metrics.model_dump()
                run.status = "completed"
                run.ended_at = datetime.now(timezone.utc)
                db.commit()
            logger.info("simulation_completed", extra={"run_id": run_id})
            from .integrations import publish_result
            publish_result(run_id, result)
        except Exception:
            logger.exception("simulation_failed", extra={"run_id": run_id})
            with SessionLocal() as db:
                run = db.get(RunRecord, run_id)
                # Optional integrations may never turn a completed simulation into a failure.
                if run and run.status != "completed":
                    run.status = "failed"
                    run.error_message = "Simulation failed; inspect service logs and saved configuration."
                    run.ended_at = datetime.now(timezone.utc)
                    db.commit()

    def close(self):
        self.executor.shutdown(wait=True)
