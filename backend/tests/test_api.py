import time
import pytest
from fastapi.testclient import TestClient
from app.main import app


def wait_for_run(client, run_id):
    for _ in range(200):
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in {"completed", "failed"}:
            return run
        time.sleep(0.01)
    pytest.fail("Run did not complete")


def submit(client, configuration=None):
    scenario = client.get("/api/scenarios").json()[0]
    algorithm = client.get("/api/algorithms").json()[0]
    payload = {"scenario_id": scenario["id"], "algorithm_id": algorithm["id"]}
    if configuration:
        payload["configuration"] = configuration
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    return wait_for_run(client, response.json()["id"])


def test_health_and_run_workflow():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/api/scenarios").json()) == 6
        scenario = client.post("/api/scenarios", json={"name": "Brake test", "scenario_type": "emergency_braking"})
        assert scenario.status_code == 201
        algorithm = client.post("/api/algorithms", json={"name": "Cautious", "version": "cautious-v2"})
        assert algorithm.status_code == 201
        response = client.post("/api/runs", json={"scenario_id": scenario.json()["id"], "algorithm_id": algorithm.json()["id"]})
        run = wait_for_run(client, response.json()["id"])
        assert run["status"] == "completed"
        assert run["snapshot"]["algorithm_version"] == "cautious-v2"
        assert client.get(f"/api/runs/{run['id']}/metrics").json() == run["metrics"]
        report = client.post(f"/api/runs/{run['id']}/report", json={}).json()
        assert report["generated_by"] == "deterministic-analysis"
        assert client.get(f"/api/runs/{run['id']}").json()["report"] == report
        csv = client.get(f"/api/runs/{run['id']}/export?format=csv")
        assert csv.headers["content-type"].startswith("text/csv")
        assert "timestamp_s" in csv.text.splitlines()[0]
        exported = client.get(f"/api/runs/{run['id']}/export").json()
        assert exported["snapshot"] == run["snapshot"]
        assert client.get("/api/overview").json()["completed_runs"] == 1


def test_compare_and_validation():
    with TestClient(app) as client:
        first, second = submit(client), submit(client)
        comparison = client.get(f"/api/compare?run_ids={first['id']},{second['id']}").json()
        assert comparison["comparable"]
        assert all(v == 0 for v in comparison["deltas_from_first"][0]["metrics"].values())
        third = submit(client, {"random_seed": 22})
        assert not client.get(f"/api/compare?run_ids={first['id']},{third['id']}").json()["comparable"]
        for query in ["1,1", "1,garbage", "1", "-1,2"]:
            assert client.get(f"/api/compare?run_ids={query}").status_code == 422
        assert client.get(f"/api/compare?run_ids={first['id']},99999").status_code == 404
        assert client.get("/api/runs/999999").status_code == 404
        assert client.post("/api/runs/0/1").status_code == 422
        assert client.post("/api/scenarios", json={"name": "bad", "scenario_type": "emergency_braking", "configuration": {"fog_density": 2}}).status_code == 422
        assert client.post("/api/algorithms", json={"name": "bad", "version": "baseline-v1", "configuration": {"unknown": 2}}).status_code == 422
        assert client.get(f"/api/runs/{first['id']}/export?format=pdf").status_code == 422


def test_failure_and_restart_recovery(monkeypatch):
    from app.services.jobs import JobService, MockSimulator
    from app.db import RunRecord, SessionLocal
    def fail(*args):
        raise RuntimeError("Injected simulator outage")
    monkeypatch.setattr(MockSimulator, "run", fail)
    with TestClient(app) as client:
        run = submit(client)
        assert run["status"] == "failed"
        assert run["error_message"]
        assert client.get(f"/api/runs/{run['id']}/metrics").status_code == 409
        with SessionLocal() as db:
            record = db.get(RunRecord, run["id"])
            record.status = "running"
            db.commit()
        app.state.jobs.recover()
        assert "interrupted" in client.get(f"/api/runs/{run['id']}").json()["error_message"]


def test_llm_fallback_and_cors(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with TestClient(app) as client:
        run = submit(client)
        report = client.post(f"/api/runs/{run['id']}/report", json={"use_llm": True}).json()
        assert report["generated_by"] == "deterministic-analysis"
        assert "unavailable" in report["llm_status"]
        response = client.options("/api/runs", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
