"""Optional result sinks. Dependencies and service outages do not block local evaluation."""
import json
import logging
import os
from typing import Protocol

logger = logging.getLogger("driveeval.integrations")


class ResultSink(Protocol):
    def publish(self, run_id: int, result) -> None: ...


class MLflowSink:
    def publish(self, run_id, result):
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
        os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")
        import mlflow
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "DriveEval AI"))
        with mlflow.start_run(run_name=f"driveeval-{run_id}"):
            mlflow.log_params({"seed": result.random_seed, "algorithm": result.algorithm_version.value,
                               "scenario": result.scenario_type.value, "source": "synthetic-mock"})
            mlflow.log_metrics({key: float(value) for key, value in result.metrics.model_dump().items()
                                if isinstance(value, (int, float, bool))})


class S3Sink:
    def publish(self, run_id, result):
        import boto3
        from botocore.config import Config
        client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL"),
                              config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}))
        client.put_object(Bucket=os.environ["S3_BUCKET"], Key=f"runs/{run_id}.json",
                          Body=json.dumps(result.model_dump(mode="json")).encode(), ContentType="application/json")


def publish_result(run_id, result):
    for enabled, sink in [(os.getenv("MLFLOW_TRACKING_URI"), MLflowSink()), (os.getenv("S3_BUCKET"), S3Sink())]:
        if enabled:
            try:
                sink.publish(run_id, result)
            except Exception:
                logger.warning("optional_integration_unavailable", extra={"run_id": run_id, "sink": type(sink).__name__})
